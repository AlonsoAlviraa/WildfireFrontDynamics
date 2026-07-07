# Módulo de Machine Learning para Wildfire Front Dynamics

try:
    from .dataset import WildfireDataset, NpzWildfireDataset
    from .train import fine_tune_model
except ModuleNotFoundError as exc:
    if exc.name != "torch":
        raise
    WildfireDataset = None  # type: ignore[assignment]
    NpzWildfireDataset = None  # type: ignore[assignment]
    fine_tune_model = None  # type: ignore[assignment]

__all__ = ["WildfireDataset", "NpzWildfireDataset", "fine_tune_model"]
