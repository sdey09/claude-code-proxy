from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass
class ModelCost:
    input_per_1m: float
    output_per_1m: float
    cache_write_per_1m: float
    cache_read_per_1m: float

_DEFAULT_COSTS: dict[str, ModelCost] = {
    # Claude Sonnet 5 / 4.5
    "claude-sonnet-5": ModelCost(3.00, 15.00, 3.75, 0.30),
    "claude-sonnet-4-5": ModelCost(3.00, 15.00, 3.75, 0.30),
    # Claude Opus 4.8 / 4
    "claude-opus-4-8": ModelCost(15.00, 75.00, 18.75, 1.50),
    "claude-opus-4": ModelCost(15.00, 75.00, 18.75, 1.50),
    # Claude Haiku 4.5
    "claude-haiku-4-5": ModelCost(0.80, 4.00, 1.00, 0.08),
    # Fable 5
    "claude-fable-5": ModelCost(3.00, 15.00, 3.75, 0.30),
}

# Fallback for unknown models: use Sonnet pricing
_FALLBACK = ModelCost(3.00, 15.00, 3.75, 0.30)


def _load_table() -> dict[str, ModelCost]:
    override_json = os.environ.get("COST_TABLE_JSON")
    if not override_json:
        return _DEFAULT_COSTS
    try:
        raw: dict[str, dict[str, float]] = json.loads(override_json)
        return {k: ModelCost(**v) for k, v in raw.items()}
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("COST_TABLE_JSON parse error: %s — using defaults", e)
        return _DEFAULT_COSTS


_TABLE = _load_table()


def _resolve(model: str) -> ModelCost:
    if model in _TABLE:
        return _TABLE[model]
    for key, cost in _TABLE.items():
        if key in model:
            return cost
    import logging
    logging.getLogger(__name__).debug(
        "Unknown model %r — falling back to Sonnet pricing (cost estimate may not match billing)", model
    )
    return _FALLBACK


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    c = _resolve(model)
    return (
        input_tokens * c.input_per_1m / 1_000_000
        + output_tokens * c.output_per_1m / 1_000_000
        + cache_write_tokens * c.cache_write_per_1m / 1_000_000
        + cache_read_tokens * c.cache_read_per_1m / 1_000_000
    )
