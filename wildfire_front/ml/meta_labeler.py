"""Safety Meta-Labeler for Wildfire Front Prediction.

This module implements a secondary safety filter (Meta-Labeler) that evaluates
the reliability of the primary spatiotemporal model predictions. If the primary
model is likely to make an error (due to high prediction entropy, steep slope,
or adverse wind conditions), the Meta-Labeler votes to veto the prediction.

Serialization security
----------------------
``save`` / ``load`` prefer **joblib** (sklearn standard) and write a small
JSON metadata sidecar. Raw ``pickle`` is still accepted for legacy ``.pkl``
files, but only when the path resolves under an **allowlisted root**
(default: the repository ``models/`` directory). Loading untrusted pickles is
remote-code-execution risk; treat model files as untrusted input.
"""

from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier

logger = logging.getLogger(__name__)

# Schema version for on-disk meta-labeler artifacts.
_ARTIFACT_VERSION = 1

# Default directory name (relative to repo root) allowed for legacy pickle loads.
_DEFAULT_ALLOWLIST_DIRNAME = "models"


def _repo_root() -> Path:
    """Return the repository root (parent of the ``wildfire_front`` package)."""
    return Path(__file__).resolve().parents[2]


def default_allowlisted_roots() -> list[Path]:
    """Roots under which legacy pickle loads are permitted."""
    return [_repo_root() / _DEFAULT_ALLOWLIST_DIRNAME]


def _path_under_roots(path: Path, roots: list[Path]) -> bool:
    """True if *path* resolves under any of *roots*."""
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def _try_import_joblib() -> Any | None:
    try:
        import joblib

        return joblib
    except ImportError:
        return None


class WildfireMetaLabeler:
    """
    Safety filter evaluating primary model reliability.

    Inputs:
    - Base prediction probability
    - Shannon entropy of base prediction (uncertainty)
    - Slope and Aspect (geospatial factors)
    - Temperature, humidity, and wind speed (meteorological factors)
    """

    def __init__(
        self, n_estimators: int = 100, max_depth: int = 10, random_state: int = 42
    ) -> None:
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state,
            class_weight="balanced",
        )
        self.is_trained = False
        self._single_class_label: int | None = None

    def compute_entropy(self, prob: np.ndarray) -> np.ndarray:
        """Compute Shannon entropy for probability values."""
        prob = np.clip(prob, 1e-7, 1.0 - 1e-7)
        return -(prob * np.log2(prob) + (1.0 - prob) * np.log2(1.0 - prob))

    def build_features(
        self,
        prob: np.ndarray,
        slope: np.ndarray,
        aspect: np.ndarray,
        wind_speed: float | np.ndarray,
        humidity: float | np.ndarray,
        temp: float | np.ndarray,
    ) -> np.ndarray:
        """
        Construct feature matrix from grid arrays.

        Returns array of shape (N, 7) with columns:
        [prob, entropy, slope, aspect, wind_speed, humidity, temp].
        """
        prob_flat = prob.flatten()
        entropy_flat = self.compute_entropy(prob_flat)
        slope_flat = slope.flatten()
        aspect_flat = aspect.flatten()

        N = len(prob_flat)
        ws_flat = (
            np.full(N, wind_speed) if np.isscalar(wind_speed) else np.asarray(wind_speed).flatten()
        )
        hum_flat = np.full(N, humidity) if np.isscalar(humidity) else np.asarray(humidity).flatten()
        temp_flat = np.full(N, temp) if np.isscalar(temp) else np.asarray(temp).flatten()

        # Stack features into (N, 7) shape
        features = np.column_stack(
            [
                prob_flat,
                entropy_flat,
                slope_flat,
                aspect_flat,
                ws_flat,
                hum_flat,
                temp_flat,
            ]
        )
        return features

    # ------------------------------------------------------------------ #
    # Sprint 2: Enhanced features with spatial context
    # ------------------------------------------------------------------ #
    def build_enhanced_features(
        self,
        prob: np.ndarray,
        slope: np.ndarray,
        aspect: np.ndarray,
        wind_speed: float | np.ndarray,
        humidity: float | np.ndarray,
        temp: float | np.ndarray,
        burning_neighbors: np.ndarray | None = None,
    ) -> np.ndarray:
        """Construct enriched feature matrix with spatial context.

        Extends :meth:`build_features` with five additional columns:

        8. ``prob_mean`` — mean probability across the 8 neighbours of the
           burning cell (captures overall model confidence for this cell).
        9. ``prob_std`` — standard deviation of neighbour probabilities
           (high variance = front edge / transition zone).
        10. ``prob_max`` — maximum neighbour probability (strongest spread
            signal).
        11. ``burning_density`` — fraction of the 8 neighbours that are
            currently burning (0.0–1.0). Cells surrounded by fire propagate
            differently than isolated cells.
        12. ``prob_gradient`` — ``max - min`` of neighbour probabilities,
            a cheap proxy for the Sobel gradient magnitude.

        Parameters
        ----------
        burning_neighbors
            Optional boolean array (same length as *prob*) indicating which
            neighbours are currently on fire.  If ``None``, this column is
            set to zero.

        Returns
        -------
        np.ndarray
            Feature matrix of shape ``(N, 12)``.
        """
        base = self.build_features(prob, slope, aspect, wind_speed, humidity, temp)
        prob_flat = prob.flatten()
        N = len(prob_flat)

        prob_mean = float(np.mean(prob_flat))
        prob_std = float(np.std(prob_flat))
        prob_max = float(np.max(prob_flat))
        prob_gradient = float(np.max(prob_flat) - np.min(prob_flat))

        if burning_neighbors is not None:
            bn = np.asarray(burning_neighbors, dtype=np.float64).flatten()
            burning_density_val = float(np.mean(bn)) if len(bn) > 0 else 0.0
        else:
            burning_density_val = 0.0

        # All five spatial features are scalars replicated across rows
        extra = np.column_stack(
            [
                np.full(N, prob_mean),
                np.full(N, prob_std),
                np.full(N, prob_max),
                np.full(N, burning_density_val),
                np.full(N, prob_gradient),
            ]
        )
        return np.hstack([base, extra])

    def train(self, X: np.ndarray, y: np.ndarray) -> None:
        """Train the Meta-Labeler classifier.

        Guards against the single-class degenerate case: if all labels are
        identical (e.g. the primary model is perfectly correct — or perfectly
        wrong — on the validation set), ``RandomForestClassifier.fit`` succeeds
        but ``predict_proba`` later returns a single-column array, causing an
        ``IndexError`` at ``[:, 1]``. We record the degenerate label and return
        it verbatim from ``predict_probability`` / ``predict_trustworthiness``.
        """
        unique_labels = np.unique(y)
        self._single_class_label = None
        if len(unique_labels) < 2:
            # Degenerate: cannot learn a discriminative boundary. Memorize the
            # constant label so downstream code still gets a usable signal.
            self._single_class_label = int(unique_labels[0])
            self.is_trained = True
            return
        self.model.fit(X, y)
        self.is_trained = True

    def predict_trustworthiness(self, X: np.ndarray) -> np.ndarray:
        """Predict binary trustworthiness (1: Trust / 0: Veto)."""
        if not self.is_trained:
            raise ValueError("Meta-Labeler must be trained before predicting.")
        if self._single_class_label is not None:
            return np.full(len(X), self._single_class_label, dtype=np.int64)
        return self.model.predict(X)

    def predict_probability(self, X: np.ndarray) -> np.ndarray:
        """Predict confidence score/probability of base prediction correctness."""
        if not self.is_trained:
            raise ValueError("Meta-Labeler must be trained before predicting.")
        if self._single_class_label is not None:
            return np.full(len(X), float(self._single_class_label), dtype=np.float64)
        return self.model.predict_proba(X)[:, 1]

    def _metadata_dict(self) -> dict[str, Any]:
        """JSON-serializable metadata (no sklearn objects)."""
        return {
            "artifact_version": _ARTIFACT_VERSION,
            "format": "wildfire_meta_labeler",
            "is_trained": self.is_trained,
            "single_class_label": self._single_class_label,
            "n_estimators": int(self.model.n_estimators),
            "max_depth": self.model.max_depth,
            "random_state": self.model.random_state,
        }

    def _write_metadata_sidecar(self, model_path: Path) -> Path:
        """Write ``{name}.meta.json`` next to the model artifact."""
        meta_path = model_path.parent / f"{model_path.name}.meta.json"
        meta_path.write_text(json.dumps(self._metadata_dict(), indent=2) + "\n", encoding="utf-8")
        return meta_path

    def save(self, path: Path | str) -> Path:
        """Save Meta-Labeler via joblib (preferred) or restricted pickle.

        Preferred path: joblib dump of a versioned payload dict plus a JSON
        metadata sidecar. joblib is the sklearn-standard serializer and is
        used when available (it ships with scikit-learn).

        If joblib is unavailable, falls back to pickle **with a warning**.
        Prefer saving under ``models/`` so legacy loads remain allowlisted.

        Returns
        -------
        Path
            Path written for the model artifact.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload: dict[str, Any] = {
            **self._metadata_dict(),
            "model": self.model,
        }

        joblib = _try_import_joblib()
        if joblib is not None:
            # Normalize extension toward .joblib when caller passed .pkl
            out = path
            if out.suffix.lower() == ".pkl":
                out = out.with_suffix(".joblib")
            elif out.suffix == "":
                out = out.with_suffix(".joblib")
            joblib.dump(payload, out)
            self._write_metadata_sidecar(out)
            return out

        warnings.warn(
            "joblib is not available; falling back to pickle for Meta-Labeler "
            "serialization. Install scikit-learn/joblib and prefer paths under "
            "models/. Pickle can execute arbitrary code on load — only load "
            "artifacts you trust.",
            stacklevel=2,
        )
        import pickle

        with open(path, "wb") as f:
            pickle.dump(payload, f)
        self._write_metadata_sidecar(path)
        return path

    @classmethod
    def load(
        cls,
        path: Path | str,
        *,
        allowlisted_roots: list[Path] | None = None,
        allow_pickle: bool = True,
    ) -> WildfireMetaLabeler:
        """Load Meta-Labeler from a joblib (preferred) or allowlisted pickle file.

        Parameters
        ----------
        path
            Path to a ``.joblib`` / ``.pkl`` artifact produced by :meth:`save`,
            or a legacy full-object pickle of ``WildfireMetaLabeler``.
        allowlisted_roots
            Directories under which **pickle** loads are permitted. Defaults to
            the repository ``models/`` directory. joblib loads are not restricted
            by path (still only load trusted files).
        allow_pickle
            If False, refuse pickle fallback entirely (joblib-only).

        Raises
        ------
        FileNotFoundError
            If *path* does not exist (and no sibling ``.joblib`` is found).
        PermissionError
            If a pickle load is requested outside allowlisted roots.
        ValueError
            If the artifact cannot be interpreted as a Meta-Labeler.
        """
        path = Path(path)
        roots = allowlisted_roots if allowlisted_roots is not None else default_allowlisted_roots()

        # Prefer sibling .joblib when caller still points at a legacy .pkl name.
        candidates = [path]
        if path.suffix.lower() == ".pkl":
            candidates.insert(0, path.with_suffix(".joblib"))
        elif path.suffix == "":
            candidates.insert(0, path.with_suffix(".joblib"))

        resolved: Path | None = None
        for candidate in candidates:
            if candidate.is_file():
                resolved = candidate
                break
        if resolved is None:
            raise FileNotFoundError(f"Meta-Labeler artifact not found: {path}")

        payload = cls._load_payload(resolved, roots=roots, allow_pickle=allow_pickle)
        return cls._from_payload(payload)

    @classmethod
    def _load_payload(
        cls,
        path: Path,
        *,
        roots: list[Path],
        allow_pickle: bool,
    ) -> Any:
        suffix = path.suffix.lower()
        joblib = _try_import_joblib()

        # joblib path (preferred)
        if suffix == ".joblib" or (joblib is not None and suffix != ".pkl"):
            if joblib is not None:
                try:
                    return joblib.load(path)
                except Exception:
                    # Fall through to pickle only for true .pkl or when joblib fails
                    if suffix == ".joblib":
                        raise

        if suffix == ".joblib" and joblib is None:
            raise ImportError(
                "joblib is required to load .joblib Meta-Labeler artifacts "
                "(install scikit-learn)."
            )

        # Legacy / pickle path — restricted
        if not allow_pickle:
            raise PermissionError(
                f"Pickle load disabled (allow_pickle=False) for path: {path}"
            )
        if not _path_under_roots(path, roots):
            roots_str = ", ".join(str(r) for r in roots)
            raise PermissionError(
                f"Refusing to unpickle Meta-Labeler from outside allowlisted roots. "
                f"path={path.resolve()} roots=[{roots_str}]. "
                f"Re-save with joblib (WildfireMetaLabeler.save) or place the "
                f"file under models/. Pickle can execute arbitrary code."
            )
        warnings.warn(
            f"Loading Meta-Labeler via pickle from {path}. Pickle is unsafe for "
            f"untrusted files (arbitrary code execution). Prefer joblib artifacts "
            f"produced by WildfireMetaLabeler.save under models/.",
            stacklevel=3,
        )
        import pickle

        with open(path, "rb") as f:
            return pickle.load(f)

    @classmethod
    def _from_payload(cls, payload: Any) -> WildfireMetaLabeler:
        """Rebuild instance from joblib/pickle payload (dict or legacy instance)."""
        # Legacy: full object was pickled
        if isinstance(payload, cls):
            return payload

        if not isinstance(payload, dict):
            raise ValueError(
                f"Unrecognized Meta-Labeler artifact type: {type(payload)!r}"
            )

        n_estimators = int(payload.get("n_estimators", 100))
        max_depth = payload.get("max_depth", 10)
        random_state = payload.get("random_state", 42)
        instance = cls(
            n_estimators=n_estimators,
            max_depth=max_depth if max_depth is not None else 10,
            random_state=random_state if random_state is not None else 42,
        )
        instance.is_trained = bool(payload.get("is_trained", False))
        scl = payload.get("single_class_label", None)
        instance._single_class_label = int(scl) if scl is not None else None

        model = payload.get("model")
        if model is not None and instance._single_class_label is None:
            instance.model = model
            instance.is_trained = True
        return instance
