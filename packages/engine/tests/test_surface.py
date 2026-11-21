"""Tests de la phase 11 : surface de résultat 2D."""

from __future__ import annotations

import pytest

from engine import (
    AxisSpec,
    CancelToken,
    EngineError,
    SimulationCancelled,
    SimulationConfig,
    surface,
)


def _deterministic_scenario(scenario_factory):
    """Scénario linéaire : 10 unités/mois sur 12 mois, marge = prix − coût."""

    return scenario_factory(
        horizonMonths=12,
        assumptions={
            "initial_stock": {"value": 10_000},
            "initial_cash": {"value": 0},
            "unit_price": {"value": 10},
            "unit_cost": {"value": 5},
            "demand_mean_monthly": {"value": 10},
            "demand_cv": {"value": 0},
            "loss_rate": {"value": 0},
            "fixed_costs_monthly": {"value": 0},
            "logistics_cost_per_unit": {"value": 0},
            "target_stock_months": {"value": 0},
        },
    )


def test_surface_shape_orientation_and_values(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    result = surface(
        scenario,
        axis_x=AxisSpec(key="unit_price", minimum=10, maximum=20),
        axis_y=AxisSpec(key="unit_cost", minimum=5, maximum=7),
        grid=(2, 2),
        runs=20,
        seed=7,
    )

    assert result.grid == (2, 2)
    assert result.x_values == [10.0, 20.0]
    assert result.y_values == [5.0, 7.0]
    assert result.current == (10.0, 5.0)
    # z[ligne_y][colonne_x] : 120 unités vendues sur l'horizon.
    assert result.z_p50[0][0] == pytest.approx(600.0)
    assert result.z_p50[0][1] == pytest.approx(1_800.0)
    assert result.z_p50[1][0] == pytest.approx(360.0)
    assert result.z_p50[1][1] == pytest.approx(1_560.0)
    assert result.z_p10 is not None
    assert result.z_p90 is not None
    assert result.cost == 2 * 2 * 20
    assert result.runs == 20
    assert result.seed == 7


def test_surface_is_deterministic_for_a_seed(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    kwargs = {
        "axis_x": AxisSpec(key="unit_price", minimum=10, maximum=20),
        "axis_y": AxisSpec(key="unit_cost", minimum=4, maximum=8),
        "grid": (3, 3),
        "runs": 25,
        "seed": 123,
    }
    first = surface(scenario, **kwargs)
    second = surface(scenario, **kwargs)
    assert first.z_p50 == second.z_p50
    assert first.z_p10 == second.z_p10
    assert first.z_p90 == second.z_p90


def test_surface_does_not_mutate_the_scenario(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    before = scenario.model_dump()
    surface(
        scenario,
        axis_x=AxisSpec(key="unit_price", minimum=10, maximum=20),
        axis_y=AxisSpec(key="unit_cost", minimum=5, maximum=7),
        grid=(2, 2),
        runs=5,
    )
    assert scenario.model_dump() == before


def test_surface_progress_covers_every_point(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    values: list[float] = []
    surface(
        scenario,
        axis_x=AxisSpec(key="unit_price", minimum=10, maximum=20),
        axis_y=AxisSpec(key="unit_cost", minimum=5, maximum=7),
        grid=(2, 3),
        runs=5,
        on_progress=values.append,
    )
    assert values[0] == 0.0
    assert values[-1] == pytest.approx(1.0)
    assert len(values) == 2 * 3 + 1
    assert values == sorted(values)


def test_surface_row_callback_matches_the_matrix(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    rows: list[tuple[int, list[float], list[float] | None, list[float] | None]] = []
    result = surface(
        scenario,
        axis_x=AxisSpec(key="unit_price", minimum=10, maximum=20),
        axis_y=AxisSpec(key="unit_cost", minimum=5, maximum=7),
        grid=(3, 2),
        runs=5,
        on_row=lambda index, values, p10, p90: rows.append(
            (index, values, p10, p90)
        ),
    )
    assert [row[0] for row in rows] == [0, 1]
    assert rows[0][1] == result.z_p50[0]
    assert rows[1][1] == result.z_p50[1]
    assert rows[0][2] == result.z_p10[0]
    assert rows[0][3] == result.z_p90[0]


def test_surface_uses_the_config_seed_by_default(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    result = surface(
        scenario,
        config=SimulationConfig(seed=99),
        axis_x=AxisSpec(key="unit_price", minimum=10, maximum=20),
        axis_y=AxisSpec(key="unit_cost", minimum=5, maximum=7),
        grid=(2, 2),
        runs=5,
    )
    assert result.seed == 99


def test_surface_cancellation_before_the_first_point(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    cancel = CancelToken()
    cancel.cancel()
    with pytest.raises(SimulationCancelled) as error:
        surface(
            scenario,
            axis_x=AxisSpec(key="unit_price", minimum=10, maximum=20),
            axis_y=AxisSpec(key="unit_cost", minimum=5, maximum=7),
            grid=(2, 2),
            runs=5,
            cancel=cancel,
        )
    assert error.value.completed_runs == 0
    assert error.value.total_runs == 4


def test_surface_cancellation_midway_keeps_completed_count(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    cancel = CancelToken()

    def on_progress(value: float) -> None:
        if value >= 0.5:
            cancel.cancel()

    with pytest.raises(SimulationCancelled) as error:
        surface(
            scenario,
            axis_x=AxisSpec(key="unit_price", minimum=10, maximum=20),
            axis_y=AxisSpec(key="unit_cost", minimum=5, maximum=7),
            grid=(3, 3),
            runs=5,
            on_progress=on_progress,
            cancel=cancel,
        )
    assert 0 < error.value.completed_runs < 9


def test_surface_non_profit_metric_leaves_percentiles_empty(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    result = surface(
        scenario,
        axis_x=AxisSpec(key="unit_price", minimum=10, maximum=20),
        axis_y=AxisSpec(key="unit_cost", minimum=5, maximum=7),
        grid=(2, 2),
        runs=5,
        metric="loss_probability",
    )
    assert result.metric == "loss_probability"
    assert result.z_p10 is None
    assert result.z_p90 is None
    assert result.z_p50 == [[0.0, 0.0], [0.0, 0.0]]


def test_surface_break_even_sentinel(scenario_factory):
    scenario = scenario_factory(
        horizonMonths=6,
        assumptions={
            "initial_stock": {"value": 10_000},
            "unit_price": {"value": 5},
            "unit_cost": {"value": 10},
            "demand_mean_monthly": {"value": 10},
            "demand_cv": {"value": 0},
            "loss_rate": {"value": 0},
            "fixed_costs_monthly": {"value": 0},
            "target_stock_months": {"value": 0},
        },
    )
    result = surface(
        scenario,
        axis_x=AxisSpec(key="unit_price", minimum=4, maximum=6),
        axis_y=AxisSpec(key="unit_cost", minimum=10, maximum=12),
        grid=(2, 2),
        runs=5,
        metric="break_even_months_p50",
    )
    # Le point mort n'est jamais atteint : sentinelle horizon + 1.
    assert result.z_p50 == [[7.0, 7.0], [7.0, 7.0]]


def test_surface_rejects_invalid_axes_and_grid(scenario_factory):
    scenario = _deterministic_scenario(scenario_factory)
    axis_x = AxisSpec(key="unit_price", minimum=10, maximum=20)
    axis_y = AxisSpec(key="unit_cost", minimum=5, maximum=7)

    with pytest.raises(EngineError):
        surface(scenario, axis_x=axis_x, axis_y=None)
    with pytest.raises(EngineError):
        surface(scenario, axis_x=axis_x, axis_y=axis_x)
    with pytest.raises(EngineError):
        surface(scenario, axis_x=axis_x, axis_y=axis_y, grid=(1, 5))
    with pytest.raises(EngineError):
        surface(scenario, axis_x=axis_x, axis_y=axis_y, grid=(61, 2))
    with pytest.raises(EngineError):
        surface(scenario, axis_x=axis_x, axis_y=axis_y, runs=0)
    with pytest.raises(EngineError):
        surface(
            scenario,
            axis_x=AxisSpec(key="unknown", minimum=1, maximum=2),
            axis_y=axis_y,
            grid=(2, 2),
        )
    with pytest.raises(EngineError):
        # ``loss_rate`` est borné à 1 par le modèle.
        surface(
            scenario,
            axis_x=AxisSpec(key="loss_rate", minimum=0, maximum=2),
            axis_y=axis_y,
            grid=(2, 2),
        )
    with pytest.raises(EngineError):
        # Borne de l'hypothèse elle-même.
        bounded = scenario.model_copy(
            update={
                "assumptions": {
                    **scenario.assumptions,
                    "unit_price": scenario.assumptions["unit_price"].model_copy(
                        update={"max": 15}
                    ),
                }
            }
        )
        surface(
            bounded,
            axis_x=AxisSpec(key="unit_price", minimum=10, maximum=20),
            axis_y=axis_y,
            grid=(2, 2),
        )


def test_axis_spec_requires_ordered_bounds():
    with pytest.raises(ValueError):
        AxisSpec(key="unit_price", minimum=10, maximum=10)
