# Módulo de Machine Learning para Wildfire Front Dynamics

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .dataset import NpzWildfireDataset as NpzWildfireDataset
    from .dataset import WildfireDataset as WildfireDataset
    from .train import fine_tune_model as fine_tune_model
else:
    try:
        from .dataset import NpzWildfireDataset, WildfireDataset
        from .train import fine_tune_model
    except ModuleNotFoundError as exc:
        if exc.name != "torch":
            raise
        WildfireDataset: Any = None
        NpzWildfireDataset: Any = None
        fine_tune_model: Any = None

__all__ = ["WildfireDataset", "NpzWildfireDataset", "fine_tune_model"]
