"""Ensemble uncertainty diagnostics + optional logistic calibrator (Head A).

Diagnostics are pure functions of member probability stacks — no weights needed for tests.
Head A features (design freeze): mean_entropy, member_disagreement, mean_margin.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

HEAD_A_FEATURE_NAMES: tuple[str, ...] = (
    "mean_entropy",
    "member_disagreement",
    "mean_margin",
)

CALIBRATION_SCHEMA = "ml_uncertainty_calibration_v1"
DEFAULT_ABSTAIN_THRESHOLD = 0.35


@dataclass(frozen=True)
class SpreadPrediction:
    """Canonical uncertainty-aware prediction payload (design: predict_with_uncertainty)."""

    prob: np.ndarray
    growth_prob: np.ndarray
    binary: np.ndarray
    confidence: float
    confidence_map: np.ndarray | None
    abstain: bool
    diagnostics: dict[str, float]
    product_id: str
    protocol: str | None = None
    calibrator_id: str | None = None

    def to_ml_live_metrics(self) -> dict[str, Any]:
        return {
            "schema": "ml_live_metrics_v1",
            "product_id": self.product_id,
            "confidence": float(self.confidence),
            "abstain": bool(self.abstain),
            "mean_entropy": float(self.diagnostics.get("mean_entropy", 0.0)),
            "member_disagreement": float(self.diagnostics.get("member_disagreement", 0.0)),
            "mean_margin": float(self.diagnostics.get("mean_margin", 0.0)),
            "calibrator_id": self.calibrator_id,
            "n_members": int(self.diagnostics.get("n_members", 0)),
        }


def _binary_entropy(p: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    p = np.clip(p, eps, 1.0 - eps)
    return -(p * np.log(p) + (1.0 - p) * np.log(1.0 - p))


def ensemble_diagnostics(
    member_probs: Sequence[np.ndarray],
    *,
    mix_weights: Sequence[float] | None = None,
) -> dict[str, float]:
    """Compute mean_entropy, member_disagreement, mean_margin from member maps.

    Parameters
    ----------
    member_probs:
        List of H×W arrays in (0,1) — per-member **absolute fire** probabilities
        (design: Head A on abs domain; growth-only maps are systematically wrong for
        already-burned pixels under target_mode=delta).
    """
    if not member_probs:
        return {
            "mean_entropy": 0.0,
            "member_disagreement": 0.0,
            "mean_margin": 0.0,
            "n_members": 0.0,
        }
    stack = np.stack([np.asarray(m, dtype=np.float64) for m in member_probs], axis=0)
    n = stack.shape[0]
    if mix_weights is not None and len(mix_weights) == n:
        w = np.asarray(mix_weights, dtype=np.float64)
        w = w / w.sum()
        mean_p = (stack * w.reshape(-1, 1, 1)).sum(axis=0)
    else:
        mean_p = stack.mean(axis=0)

    ent = float(_binary_entropy(mean_p).mean())
    # disagreement: mean pairwise absolute difference (upper triangle)
    if n >= 2:
        diffs = []
        for i in range(n):
            for j in range(i + 1, n):
                diffs.append(np.abs(stack[i] - stack[j]).mean())
        disagree = float(np.mean(diffs))
    else:
        disagree = 0.0
    margin = float(np.abs(mean_p - 0.5).mean())
    return {
        "mean_entropy": ent,
        "member_disagreement": disagree,
        "mean_margin": margin,
        "n_members": float(n),
        # Optional audit field only — not part of Head A feature vector.
        "mean_prob": float(mean_p.mean()),
    }


def features_from_diagnostics(diag: dict[str, float]) -> np.ndarray:
    """3-D Head A feature vector (design freeze; no mean_growth)."""
    return np.asarray(
        [
            float(diag.get("mean_entropy", 0.0)),
            float(diag.get("member_disagreement", 0.0)),
            float(diag.get("mean_margin", 0.0)),
        ],
        dtype=np.float64,
    )


def logistic_sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


@dataclass
class LogisticCalibrator:
    """Head A: P(IoU >= tau | x) from diagnostics features. method=logistic only."""

    weights: np.ndarray  # shape (n_features + 1,) bias last
    feature_names: tuple[str, ...] = HEAD_A_FEATURE_NAMES
    method: str = "logistic"
    calibrator_id: str = "uncertainty_calibration_v1"
    tau_iou: float = 0.5
    fit_split: str = "val"
    abstain_threshold: float = DEFAULT_ABSTAIN_THRESHOLD
    # Research-only: allow ad-hoc linear heuristic when weights wrong/empty.
    allow_identity_heuristic: bool = False

    def __post_init__(self) -> None:
        if self.method != "logistic":
            raise ValueError(f"only method='logistic' supported in v1, got {self.method!r}")
        self.weights = np.asarray(self.weights, dtype=np.float64).ravel()

    @property
    def is_identity(self) -> bool:
        return self.weights.size == 0

    def predict_proba(self, diag: dict[str, float]) -> float:
        x = features_from_diagnostics(diag)
        expected = x.size + 1
        if self.weights.size == 0:
            # Identity: neutral conf; product path should force abstain when using identity.
            if self.allow_identity_heuristic:
                return float(
                    np.clip(
                        0.5
                        + 0.4 * float(diag.get("mean_margin", 0.0))
                        - 0.2 * float(diag.get("mean_entropy", 0.0))
                        - 0.3 * float(diag.get("member_disagreement", 0.0)),
                        0.0,
                        1.0,
                    )
                )
            return 0.5
        if self.weights.size != expected:
            if self.allow_identity_heuristic:
                return float(
                    np.clip(
                        0.5
                        + 0.4 * float(diag.get("mean_margin", 0.0))
                        - 0.2 * float(diag.get("mean_entropy", 0.0))
                        - 0.3 * float(diag.get("member_disagreement", 0.0)),
                        0.0,
                        1.0,
                    )
                )
            raise ValueError(
                f"calibrator weight length {self.weights.size} != n_features+1={expected}; "
                "refusing silent heuristic (set allow_identity_heuristic=True for research only)"
            )
        z = float(np.dot(self.weights[:-1], x) + self.weights[-1])
        return float(logistic_sigmoid(z))

    def to_dict(self) -> dict[str, Any]:
        coef = self.weights[:-1].tolist() if self.weights.size else []
        intercept = float(self.weights[-1]) if self.weights.size else 0.0
        return {
            "schema": CALIBRATION_SCHEMA,
            "method": "logistic",
            "calibrator_id": self.calibrator_id,
            "weights": self.weights.tolist(),
            "feature_names": list(self.feature_names),
            "features": list(self.feature_names),
            "tau_iou": self.tau_iou,
            "fit_split": self.fit_split,
            "head": "patch_reliability",
            "label": {
                "type": "patch_iou_ge_tau",
                "tau": self.tau_iou,
                "mask_threshold": 0.5,
            },
            "params": {
                "coef": coef,
                "intercept": intercept,
            },
            "abstain_threshold": float(self.abstain_threshold),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogisticCalibrator":
        method = str(data.get("method") or "logistic")
        if method != "logistic":
            raise ValueError(f"only logistic calibrator supported, got {method!r}")
        names = data.get("feature_names") or data.get("features")
        if names is not None:
            feature_names = tuple(str(n) for n in names)
        else:
            feature_names = HEAD_A_FEATURE_NAMES
        weights_raw = data.get("weights")
        if weights_raw is None or (isinstance(weights_raw, (list, tuple)) and len(weights_raw) == 0):
            params = data.get("params") if isinstance(data.get("params"), dict) else {}
            coef = params.get("coef") if params else None
            intercept = params.get("intercept") if params else None
            if coef is not None:
                weights_raw = list(coef) + [float(intercept if intercept is not None else 0.0)]
            else:
                weights_raw = []
        tau = data.get("tau_iou")
        if tau is None and isinstance(data.get("label"), dict):
            tau = data["label"].get("tau")
        return cls(
            weights=np.asarray(weights_raw or [], dtype=np.float64),
            feature_names=feature_names,
            calibrator_id=str(data.get("calibrator_id") or "uncertainty_calibration_v1"),
            tau_iou=float(tau if tau is not None else 0.5),
            fit_split=str(data.get("fit_split") or "val"),
            abstain_threshold=float(
                data.get("abstain_threshold")
                if data.get("abstain_threshold") is not None
                else DEFAULT_ABSTAIN_THRESHOLD
            ),
            allow_identity_heuristic=bool(data.get("allow_identity_heuristic", False)),
        )

    @classmethod
    def identity(cls, *, allow_identity_heuristic: bool = False) -> "LogisticCalibrator":
        """Unfitted placeholder — conf=0.5; force abstain on product path."""
        return cls(
            weights=np.asarray([], dtype=np.float64),
            allow_identity_heuristic=allow_identity_heuristic,
        )


def load_calibrator(path: str | Path) -> LogisticCalibrator:
    """Load Head A logistic calibrator from JSON (fixture or VAL-fit artifact).

    Accepts both flat ``weights`` (coef + bias) and design ``params.coef/intercept``.
    Rejects non-logistic methods.
    """
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"calibrator JSON must be an object: {p}")
    method = str(data.get("method") or "logistic")
    if method != "logistic":
        raise ValueError(f"only method='logistic' supported in v1, got {method!r}")
    return LogisticCalibrator.from_dict(data)


def save_calibrator(
    calibrator: LogisticCalibrator,
    path: str | Path,
    *,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write calibrator JSON artifact (operator / fixture path)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = calibrator.to_dict()
    if extra:
        doc.update(extra)
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return p


def build_ml_prediction_document(
    pred: SpreadPrediction,
    *,
    mask_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Outbox / predict_spread JSON — live metrics only; no ROS fields."""
    live = pred.to_ml_live_metrics()
    doc: dict[str, Any] = {
        "schema": "ml_prediction_v1",
        "product_id": pred.product_id,
        "abstain": bool(pred.abstain),
        "confidence": float(pred.confidence),
        "diagnostics": {
            "mean_entropy": float(pred.diagnostics.get("mean_entropy", 0.0)),
            "member_disagreement": float(pred.diagnostics.get("member_disagreement", 0.0)),
            "mean_margin": float(pred.diagnostics.get("mean_margin", 0.0)),
            "n_members": int(pred.diagnostics.get("n_members", 0)),
        },
        "ml_live_metrics": live,
        "calibrator_id": pred.calibrator_id,
        "protocol": pred.protocol,
    }
    if mask_summary is not None:
        doc["mask_summary"] = mask_summary
    return doc


def fit_logistic_calibrator(
    feature_rows: Sequence[np.ndarray],
    labels: Sequence[int | float | bool],
    *,
    split_context: Any = None,
    l2: float = 1e-2,
    n_iter: int = 200,
    lr: float = 0.5,
    tau_iou: float = 0.5,
) -> LogisticCalibrator:
    """Simple L2-regularized logistic regression (no sklearn required).

    Requires VAL ``SplitContext`` with action fit_uncertainty / calibrate.
    Labels should be 1{IoU >= tau}; values are thresholded at 0.5.
    """
    from wildfire_front.ml.protocol_rails import (
        ProtocolRailError,
        SplitContext,
        assert_split_context,
    )

    if split_context is None:
        raise TypeError(
            "split_context is required (SplitContext(split='val', action='fit_uncertainty'))"
        )
    if not isinstance(split_context, SplitContext):
        raise TypeError("split_context must be a SplitContext instance")
    assert_split_context(split_context)
    # Fit only — not report/scorecard/gate on VAL.
    if str(split_context.action) not in ("fit_uncertainty", "calibrate"):
        raise ProtocolRailError(
            f"fit_logistic_calibrator requires action in "
            f"{{'fit_uncertainty','calibrate'}}, got {split_context.action!r}"
        )

    X = np.stack([np.asarray(r, dtype=np.float64).ravel() for r in feature_rows], axis=0)
    y = np.asarray(labels, dtype=np.float64).ravel()
    if X.size == 0 or X.shape[0] != y.shape[0]:
        return LogisticCalibrator.identity()
    y = (y >= 0.5).astype(np.float64)
    n, d = X.shape
    # weights: d features + bias
    w = np.zeros(d + 1, dtype=np.float64)
    for _ in range(n_iter):
        z = X @ w[:-1] + w[-1]
        # stable sigmoid
        p = np.where(z >= 0, 1.0 / (1.0 + np.exp(-z)), np.exp(z) / (1.0 + np.exp(z)))
        err = p - y
        grad_w = (X.T @ err) / n + l2 * w[:-1]
        grad_b = float(err.mean())
        w[:-1] -= lr * grad_w
        w[-1] -= lr * grad_b
    return LogisticCalibrator(weights=w, tau_iou=tau_iou, fit_split=str(split_context.split))
