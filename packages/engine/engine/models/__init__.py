from __future__ import annotations

from ..errors import UnknownModelError
from .base import BatchResult, InputSpec, SimulationModel
from .retail_depot import RetailDepotModel

MODELS: dict[str, SimulationModel] = {
    RetailDepotModel.name: RetailDepotModel(),
}


def get_model(name: str) -> SimulationModel:
    try:
        return MODELS[name]
    except KeyError as exc:
        raise UnknownModelError(name) from exc


__all__ = ["BatchResult", "InputSpec", "MODELS", "RetailDepotModel", "SimulationModel", "get_model"]
