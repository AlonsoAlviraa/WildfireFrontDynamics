"""Safety Meta-Labeler for Wildfire Front Prediction.

This module implements a secondary safety filter (Meta-Labeler) that evaluates
the reliability of the primary spatiotemporal model predictions. If the primary
model is likely to make an error (due to high prediction entropy, steep slope,
or adverse wind conditions), the Meta-Labeler votes to veto the prediction.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier


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

    def save(self, path: Path | str) -> None:
        """Save Meta-Labeler weights via pickle serialization."""
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: Path | str) -> WildfireMetaLabeler:
        """Load Meta-Labeler from a serialized pickle file."""
        with open(path, "rb") as f:
            return pickle.load(f)
