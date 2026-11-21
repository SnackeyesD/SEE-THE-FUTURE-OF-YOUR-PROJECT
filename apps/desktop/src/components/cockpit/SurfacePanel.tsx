import type { Scenario, SurfaceAxis, SurfaceMetric } from "@see/protocol";
import { Button, Field, InlineAlert, ProgressBar, SelectField } from "@see/ui";
import { useMemo, useState } from "react";

import { ASSUMPTION_BY_KEY } from "../../lib/assumptions";
import { formatNumber } from "../../lib/format";
import { SURFACE_METRICS } from "../../lib/metrics";
import type { SurfaceState } from "../../hooks/useAnalysis";
import { Heatmap } from "./Heatmap";

export interface SurfaceFormValues {
  axisX: SurfaceAxis;
  axisY: SurfaceAxis;
  metric: SurfaceMetric;
  grid: [number, number];
  runs: number;
}

export interface SurfacePanelProps {
  scenario: Scenario;
  currency: string;
  state: SurfaceState;
  seed: number;
  disabled?: boolean;
  onRun: (values: SurfaceFormValues) => void;
  onCancel: () => void;
  onApplyPoint: (points: Record<string, number>) => void;
}

const GRID_OPTIONS = [9, 12, 15, 20];

interface AxisForm {
  key: string;
  min: string;
  max: string;
}

function numericBounds(
  key: string,
  scenario: Scenario,
): { minimum: number; maximum: number } {
  const hypothesis = scenario.assumptions?.[key];
  const spec = ASSUMPTION_BY_KEY.get(key);
  const value = hypothesis?.value ?? 0;
  const minimum = spec?.min ?? hypothesis?.min ?? 0;
  const maximum = spec?.max ?? hypothesis?.max ?? Math.max(value * 2, 1);
  return { minimum, maximum: Math.max(maximum, minimum + 1e-9) };
}

function axisForm(key: string, scenario: Scenario): AxisForm {
  const bounds = numericBounds(key, scenario);
  return {
    key,
    min: String(formatNumber(bounds.minimum, 4)),
    max: String(formatNumber(bounds.maximum, 4)),
  };
}

/**
 * Formulaire de surface 2D : deux axes, une métrique, une grille. Le coût est
 * affiché avant le lancement (grille × runs) et le résultat n'est jamais
 * recalculé ici : la heatmap reçoit les lignes du moteur.
 */
export function SurfacePanel({
  scenario,
  currency,
  state,
  seed,
  disabled = false,
  onRun,
  onCancel,
  onApplyPoint,
}: SurfacePanelProps) {
  const assumptionKeys = useMemo(
    () => Object.keys(scenario.assumptions ?? {}),
    [scenario.assumptions],
  );
  const initialX = assumptionKeys.includes("unit_price")
    ? "unit_price"
    : (assumptionKeys[0] ?? "");
  const initialY = assumptionKeys.includes("unit_cost")
    ? "unit_cost"
    : (assumptionKeys.find((key) => key !== initialX) ?? "");

  const [metric, setMetric] = useState<SurfaceMetric>("profit_p50");
  const [gridSize, setGridSize] = useState(12);
  const [runs, setRuns] = useState("200");
  const [xAxis, setXAxis] = useState<AxisForm>(() => axisForm(initialX, scenario));
  const [yAxis, setYAxis] = useState<AxisForm>(() => axisForm(initialY, scenario));
  const [formError, setFormError] = useState<string | null>(null);

  const running = state.status === "running" || state.status === "cancelling";
  const runsNumber = Number(runs);
  const cost =
    Number.isInteger(runsNumber) && runsNumber > 0 ? gridSize * gridSize * runsNumber : 0;

  const updateAxis = (
    axis: "x" | "y",
    patch: Partial<AxisForm>,
  ) => {
    if (axis === "x") setXAxis((current) => ({ ...current, ...patch }));
    else setYAxis((current) => ({ ...current, ...patch }));
  };

  const submit = () => {
    setFormError(null);
    if (!xAxis.key || !yAxis.key) {
      setFormError("Choisissez deux hypothèses.");
      return;
    }
    if (xAxis.key === yAxis.key) {
      setFormError("Les deux axes doivent porter sur des hypothèses différentes.");
      return;
    }
    const minimumX = Number(xAxis.min.replace(",", "."));
    const maximumX = Number(xAxis.max.replace(",", "."));
    const minimumY = Number(yAxis.min.replace(",", "."));
    const maximumY = Number(yAxis.max.replace(",", "."));
    if (
      !Number.isFinite(minimumX) ||
      !Number.isFinite(maximumX) ||
      !(minimumX < maximumX)
    ) {
      setFormError("L'axe X doit avoir un minimum strictement inférieur au maximum.");
      return;
    }
    if (
      !Number.isFinite(minimumY) ||
      !Number.isFinite(maximumY) ||
      !(minimumY < maximumY)
    ) {
      setFormError("L'axe Y doit avoir un minimum strictement inférieur au maximum.");
      return;
    }
    if (!Number.isInteger(runsNumber) || runsNumber < 1) {
      setFormError("Le nombre de runs doit être un entier positif.");
      return;
    }
    onRun({
      axisX: { key: xAxis.key, minimum: minimumX, maximum: maximumX },
      axisY: { key: yAxis.key, minimum: minimumY, maximum: maximumY },
      metric,
      grid: [gridSize, gridSize],
      runs: runsNumber,
    });
  };

  const xLabel = ASSUMPTION_BY_KEY.get(xAxis.key)?.label ?? xAxis.key;
  const yLabel = ASSUMPTION_BY_KEY.get(yAxis.key)?.label ?? yAxis.key;

  return (
    <section className="surface-panel" aria-label="Surface 2D">
      <div className="surface-panel__grid">
        <SelectField
          label="Axe X (colonnes)"
          value={xAxis.key}
          disabled={running || disabled}
          onChange={(event) => updateAxis("x", axisForm(event.target.value, scenario))}
        >
          {assumptionKeys.map((key) => (
            <option key={key} value={key}>
              {ASSUMPTION_BY_KEY.get(key)?.label ?? key}
            </option>
          ))}
        </SelectField>
        <Field
          label="Minimum X"
          inputMode="decimal"
          value={xAxis.min}
          disabled={running || disabled}
          onChange={(event) => updateAxis("x", { min: event.target.value })}
        />
        <Field
          label="Maximum X"
          inputMode="decimal"
          value={xAxis.max}
          disabled={running || disabled}
          onChange={(event) => updateAxis("x", { max: event.target.value })}
        />

        <SelectField
          label="Axe Y (lignes)"
          value={yAxis.key}
          disabled={running || disabled}
          onChange={(event) => updateAxis("y", axisForm(event.target.value, scenario))}
        >
          {assumptionKeys.map((key) => (
            <option key={key} value={key}>
              {ASSUMPTION_BY_KEY.get(key)?.label ?? key}
            </option>
          ))}
        </SelectField>
        <Field
          label="Minimum Y"
          inputMode="decimal"
          value={yAxis.min}
          disabled={running || disabled}
          onChange={(event) => updateAxis("y", { min: event.target.value })}
        />
        <Field
          label="Maximum Y"
          inputMode="decimal"
          value={yAxis.max}
          disabled={running || disabled}
          onChange={(event) => updateAxis("y", { max: event.target.value })}
        />

        <SelectField
          label="Métrique"
          value={metric}
          disabled={running || disabled}
          onChange={(event) => setMetric(event.target.value as SurfaceMetric)}
        >
          {SURFACE_METRICS.map((entry) => (
            <option key={entry.key} value={entry.key}>
              {entry.label}
            </option>
          ))}
        </SelectField>
        <SelectField
          label="Grille"
          value={String(gridSize)}
          disabled={running || disabled}
          onChange={(event) => setGridSize(Number(event.target.value))}
        >
          {GRID_OPTIONS.map((size) => (
            <option key={size} value={size}>
              {size} × {size}
            </option>
          ))}
        </SelectField>
        <Field
          label="Runs par point"
          inputMode="numeric"
          value={runs}
          disabled={running || disabled}
          onChange={(event) => setRuns(event.target.value)}
          hint="Qualité brouillon, même graine partout."
        />
      </div>

      <p className="surface-panel__cost">
        Coût : {gridSize * gridSize} points ×{" "}
        {Number.isInteger(runsNumber) ? runsNumber : 0} runs ={" "}
        <strong>{formatNumber(cost)} runs</strong> · graine {seed}
      </p>

      {formError ? (
        <InlineAlert tone="danger" title="Surface incomplète">
          {formError}
        </InlineAlert>
      ) : null}

      <div className="surface-panel__actions">
        <Button
          onClick={submit}
          disabled={running || disabled || assumptionKeys.length < 2}
        >
          Calculer la surface
        </Button>
        {running ? (
          <Button variant="ghost" onClick={onCancel}>
            Annuler la surface
          </Button>
        ) : null}
      </div>

      {running ? (
        <ProgressBar
          value={state.fraction}
          label={`Surface — ${state.completedPoints} / ${state.totalPoints} points`}
        />
      ) : null}

      {state.status === "cancelling" ? (
        <p className="ui-muted" role="status">
          Annulation demandée…
        </p>
      ) : null}

      {state.error ? (
        <InlineAlert
          tone={state.status === "cancelled" ? "neutral" : "danger"}
          title={state.status === "cancelled" ? "Surface annulée" : "Surface impossible"}
        >
          {state.error}
        </InlineAlert>
      ) : null}

      {state.rows.length > 0 ? (
        <Heatmap
          xValues={state.result?.xValues ?? null}
          yValues={state.result?.yValues ?? null}
          rows={state.rows}
          metric={metric}
          xLabel={xLabel}
          yLabel={yLabel}
          currency={currency}
          current={state.result?.current ?? null}
          onApply={
            state.result
              ? (x, y) => onApplyPoint({ [xAxis.key]: x, [yAxis.key]: y })
              : undefined
          }
          applyLabel="Appliquer au scénario"
        />
      ) : (
        <p className="ui-muted">
          Lancez une surface pour afficher la carte de chaleur. Chaque cellule sera un
          résultat moteur complet.
        </p>
      )}

      {state.result ? (
        <p className="ui-muted">
          Point courant : {xLabel} = {formatNumber(state.result.current[0] ?? 0, 4)},{" "}
          {yLabel} = {formatNumber(state.result.current[1] ?? 0, 4)}.
        </p>
      ) : null}
    </section>
  );
}
