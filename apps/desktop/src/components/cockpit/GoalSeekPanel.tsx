import type {
  GoalComparator,
  GoalLever,
  GoalObjective,
  GoalSeekResult,
  Scenario,
  SimulationQuality,
  SurfaceMetric,
} from "@see/protocol";
import {
  Button,
  Field,
  InlineAlert,
  ProgressBar,
  SelectField,
} from "@see/ui";
import { useEffect, useMemo, useState } from "react";

import { ASSUMPTION_BY_KEY } from "../../lib/assumptions";
import { formatNumber } from "../../lib/format";
import {
  formatMetricValue,
  SURFACE_METRICS,
  surfaceMetricSpec,
} from "../../lib/metrics";
import type { GoalSeekState } from "../../hooks/useAnalysis";

export interface GoalSeekFormValues {
  objective: GoalObjective;
  levers: GoalLever[];
  maxEvaluations: number;
  runs: number;
  confirmQuality: SimulationQuality | null;
}

export interface ApplyState {
  status: "idle" | "running" | "done" | "error";
  message: string | null;
}

const EMPTY_LOCKS: ReadonlySet<string> = new Set();

export interface GoalSeekPanelProps {
  scenario: Scenario;
  currency: string;
  state: GoalSeekState;
  seed: number;
  defaultMetric?: SurfaceMetric;
  disabled?: boolean;
  /** Paramètres verrouillés dans le panneau d'hypothèses, exclus de la recherche. */
  locked?: ReadonlySet<string>;
  applyState?: ApplyState;
  onRun: (values: GoalSeekFormValues) => void;
  onCancel: () => void;
  onApply: (result: GoalSeekResult, branchLabel: string) => void;
}

function comparatorFor(metric: SurfaceMetric): GoalComparator {
  return surfaceMetricSpec(metric).lowerIsBetter ? "<=" : ">=";
}

function firstUnlocked(keys: string[], locked: ReadonlySet<string>): string {
  return ["unit_price", "unit_cost", "demand_mean_monthly", ...keys].find(
    (key) => keys.includes(key) && !locked.has(key),
  ) ?? "";
}

function defaultBounds(
  key: string,
  scenario: Scenario,
): { min: string; max: string } {
  const hypothesis = scenario.assumptions?.[key];
  const spec = ASSUMPTION_BY_KEY.get(key);
  const value = hypothesis?.value ?? 0;
  const lower = spec?.min ?? hypothesis?.min ?? 0;
  const upper = spec?.max ?? hypothesis?.max ?? Math.max(value * 2, 1);
  return {
    min: String(lower),
    max: String(upper),
  };
}

function formatGap(metric: SurfaceMetric, gap: number, currency: string): string {
  const sign = gap > 0 ? "+" : "";
  const spec = surfaceMetricSpec(metric);
  if (spec.format === "probability") {
    return `${sign}${formatNumber(gap * 100, 1)} pts`;
  }
  if (spec.format === "months") {
    return `${sign}${formatNumber(gap, 1)} mois`;
  }
  const formatted = formatMetricValue(metric, Math.abs(gap), currency);
  return gap < 0 ? `−${formatted.replace(/^-/, "")}` : `${sign}${formatted}`;
}

/**
 * Formulaire et résultat d'une recherche d'objectif.
 *
 * Le panel ne calcule aucune valeur : il construit la requête à partir des
 * hypothèses du scénario, puis affiche le résultat moteur tel quel. Le bouton
 * d'application est désactivé pendant l'écriture de la branche ; un objectif
 * non atteint ne reçoit jamais le libellé « objectif atteint ».
 */
export function GoalSeekPanel({
  scenario,
  currency,
  state,
  seed,
  defaultMetric = "profit_p50",
  disabled = false,
  locked = EMPTY_LOCKS,
  applyState = { status: "idle", message: null },
  onRun,
  onCancel,
  onApply,
}: GoalSeekPanelProps) {
  const assumptionKeys = useMemo(
    () => Object.keys(scenario.assumptions ?? {}),
    [scenario.assumptions],
  );
  const initialLever = firstUnlocked(assumptionKeys, locked);

  const [metric, setMetric] = useState<SurfaceMetric>(defaultMetric);
  const [comparator, setComparator] = useState<GoalComparator>(
    comparatorFor(defaultMetric),
  );
  const [target, setTarget] = useState("");
  const [tolerance, setTolerance] = useState("");
  const [selected, setSelected] = useState<string[]>(
    initialLever ? [initialLever] : [],
  );
  const [bounds, setBounds] = useState<Record<string, { min: string; max: string }>>(
    () =>
      initialLever
        ? { [initialLever]: defaultBounds(initialLever, scenario) }
        : {},
  );
  const [maxEvaluations, setMaxEvaluations] = useState("80");
  const [runs, setRuns] = useState("500");
  const [confirm, setConfirm] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    setSelected((current) => {
      const next = current.filter((key) => !locked.has(key));
      if (next.length > 0) return next;
      const fallback = firstUnlocked(assumptionKeys, locked);
      return fallback ? [fallback] : [];
    });
  }, [assumptionKeys, locked]);

  const activeSelected = selected.filter((key) => !locked.has(key));
  const activeSelectedKey = activeSelected.join("|");
  useEffect(() => {
    setBounds((current) => {
      let changed = false;
      const next = { ...current };
      for (const key of activeSelectedKey.split("|").filter(Boolean)) {
        if (!next[key]) {
          next[key] = defaultBounds(key, scenario);
          changed = true;
        }
      }
      return changed ? next : current;
    });
  }, [activeSelectedKey, scenario]);

  const running = state.status === "running" || state.status === "cancelling";
  const spec = surfaceMetricSpec(metric);
  const result = state.result;
  // Le résultat porte sa propre métrique : changer le formulaire après coup
  // ne doit pas réétiqueter les chiffres déjà produits par le moteur.
  const resultMetric = result?.metric ?? metric;
  const resultSpec = surfaceMetricSpec(resultMetric);

  const toggleLever = (key: string, checked: boolean) => {
    if (locked.has(key)) return;
    setSelected((current) => {
      if (checked) {
        if (current.includes(key) || current.length >= 3) return current;
        return [...current, key];
      }
      return current.filter((candidate) => candidate !== key);
    });
    setBounds((current) => {
      if (!checked) return current;
      return current[key] ? current : { ...current, [key]: defaultBounds(key, scenario) };
    });
  };

  const updateBound = (key: string, field: "min" | "max", value: string) => {
    setBounds((current) => ({
      ...current,
      [key]: {
        min: current[key]?.min ?? "",
        max: current[key]?.max ?? "",
        [field]: value,
      },
    }));
  };

  const submit = () => {
    setFormError(null);
    const parsedTarget = Number(target.replace(",", "."));
    if (!Number.isFinite(parsedTarget)) {
      setFormError("La cible doit être un nombre.");
      return;
    }
    if (activeSelected.length === 0) {
      setFormError("Choisissez au moins un levier non verrouillé.");
      return;
    }
    const levers: GoalLever[] = [];
    for (const key of activeSelected) {
      const current = bounds[key];
      const minimum = Number((current?.min ?? "").replace(",", "."));
      const maximum = Number((current?.max ?? "").replace(",", "."));
      if (!Number.isFinite(minimum) || !Number.isFinite(maximum)) {
        setFormError(`Bornes invalides pour ${ASSUMPTION_BY_KEY.get(key)?.label ?? key}.`);
        return;
      }
      if (minimum >= maximum) {
        setFormError(
          `Le minimum doit être inférieur au maximum pour ${
            ASSUMPTION_BY_KEY.get(key)?.label ?? key
          }.`,
        );
        return;
      }
      levers.push({ key, minimum, maximum });
    }
    const budget = Number(maxEvaluations);
    if (!Number.isInteger(budget) || budget < 1 || budget > 500) {
      setFormError("Le budget d'évaluations doit être un entier entre 1 et 500.");
      return;
    }
    const draftRuns = Number(runs);
    if (!Number.isInteger(draftRuns) || draftRuns < 1) {
      setFormError("Le nombre de runs doit être un entier positif.");
      return;
    }
    const parsedTolerance = tolerance.trim()
      ? Number(tolerance.replace(",", "."))
      : undefined;
    if (
      parsedTolerance !== undefined &&
      (!Number.isFinite(parsedTolerance) || parsedTolerance < 0)
    ) {
      setFormError("La tolérance doit être un nombre positif ou vide.");
      return;
    }

    onRun({
      objective: {
        metric,
        comparator,
        target: parsedTarget,
        ...(parsedTolerance !== undefined ? { tolerance: parsedTolerance } : {}),
      },
      levers,
      maxEvaluations: budget,
      runs: draftRuns,
      confirmQuality: confirm ? "final" : null,
    });
  };

  const apply = () => {
    if (!result) return;
    const label = `Objectif ${resultSpec.label} ${
      result.feasible ? "atteint" : "compromis"
    } · ${formatMetricValue(resultMetric, result.achieved, currency)}`;
    onApply(result, label);
  };

  return (
    <section className="goal-seek" aria-label="Recherche d'objectif">
      <div className="goal-seek__grid">
        <SelectField
          label="Métrique"
          value={metric}
          disabled={running || disabled}
          onChange={(event) => {
            const next = event.target.value as SurfaceMetric;
            setMetric(next);
            setComparator(comparatorFor(next));
          }}
        >
          {SURFACE_METRICS.map((entry) => (
            <option key={entry.key} value={entry.key}>
              {entry.label}
            </option>
          ))}
        </SelectField>

        <SelectField
          label="Sens"
          value={comparator}
          disabled={running || disabled}
          onChange={(event) => setComparator(event.target.value as GoalComparator)}
        >
          <option value=">=">Au moins (≥)</option>
          <option value="<=">Au plus (≤)</option>
        </SelectField>

        <Field
          label={`Cible (${spec.unit})`}
          inputMode="decimal"
          value={target}
          disabled={running || disabled}
          onChange={(event) => setTarget(event.target.value)}
          hint="Valeur demandée, lue dans le moteur."
        />

        <Field
          label={`Tolérance (${spec.unit})`}
          inputMode="decimal"
          value={tolerance}
          disabled={running || disabled}
          onChange={(event) => setTolerance(event.target.value)}
          hint="Optionnelle ; 0 par défaut."
        />
      </div>

      <fieldset className="goal-seek__levers" disabled={running || disabled}>
        <legend>Leviers (1 à 3)</legend>
        <div className="goal-seek__levers-list">
          {assumptionKeys.map((key) => {
            const hypothesis = scenario.assumptions?.[key];
            const leverSpec = ASSUMPTION_BY_KEY.get(key);
            const isLocked = locked.has(key);
            const checked = selected.includes(key) && !isLocked;
            return (
              <div key={key} className="goal-seek__lever">
                <label className="goal-seek__lever-toggle">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(event) => toggleLever(key, event.target.checked)}
                    disabled={isLocked || (!checked && activeSelected.length >= 3)}
                  />
                  <span>{leverSpec?.label ?? key}</span>
                  {isLocked ? <span className="ui-muted">verrouillé</span> : null}
                  {hypothesis ? (
                    <span className="ui-muted">
                      actuel {formatNumber(hypothesis.value, 4)}
                      {leverSpec?.unit ? ` ${leverSpec.unit}` : ""}
                    </span>
                  ) : null}
                </label>
                {checked ? (
                  <div className="goal-seek__bounds">
                    <Field
                      label="Minimum"
                      inputMode="decimal"
                      value={bounds[key]?.min ?? ""}
                      onChange={(event) => updateBound(key, "min", event.target.value)}
                    />
                    <Field
                      label="Maximum"
                      inputMode="decimal"
                      value={bounds[key]?.max ?? ""}
                      onChange={(event) => updateBound(key, "max", event.target.value)}
                    />
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </fieldset>

      <div className="goal-seek__grid">
        <Field
          label="Budget d'évaluations"
          inputMode="numeric"
          value={maxEvaluations}
          disabled={running || disabled}
          onChange={(event) => setMaxEvaluations(event.target.value)}
          hint="Chaque évaluation est une simulation complète."
        />
        <Field
          label="Runs par évaluation"
          inputMode="numeric"
          value={runs}
          disabled={running || disabled}
          onChange={(event) => setRuns(event.target.value)}
          hint="Qualité brouillon pendant la recherche."
        />
        <label className="goal-seek__confirm">
          <input
            type="checkbox"
            checked={confirm}
            disabled={running || disabled}
            onChange={(event) => setConfirm(event.target.checked)}
          />
          <span>Confirmer le meilleur point en qualité finale</span>
        </label>
      </div>

      <p className="goal-seek__cost">
        Coût maximal :{" "}
        {formatNumber(
          (Number.isInteger(Number(maxEvaluations)) ? Number(maxEvaluations) : 0) *
            (Number.isInteger(Number(runs)) ? Number(runs) : 0),
        )}{" "}
        runs (budget × runs) · graine {seed}.
      </p>

      {formError ? (
        <InlineAlert tone="danger" title="Formulaire incomplet">
          {formError}
        </InlineAlert>
      ) : null}

      <div className="goal-seek__actions">
        <Button onClick={submit} disabled={running || disabled || assumptionKeys.length === 0}>
          Chercher l'objectif
        </Button>
        {running ? (
          <Button variant="ghost" onClick={onCancel}>
            Annuler l'analyse
          </Button>
        ) : null}
      </div>

      {running ? (
        <ProgressBar
          value={state.fraction}
          label={`Recherche — ${state.completed} / ${state.total} évaluations`}
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
          title={state.status === "cancelled" ? "Recherche annulée" : "Recherche impossible"}
        >
          {state.error}
        </InlineAlert>
      ) : null}

      {result ? (
        <div className="goal-seek__result" role="status">
          <InlineAlert
            tone={result.feasible ? "ok" : result.budgetExhausted ? "warn" : "danger"}
            title={
              result.feasible
                ? "Objectif atteint"
                : result.budgetExhausted
                  ? "Budget épuisé — meilleur compromis"
                  : "Cible non atteinte"
            }
          >
            {result.message}
          </InlineAlert>
          <dl className="goal-seek__figures">
            <div>
              <dt>Valeur atteinte</dt>
              <dd>{formatMetricValue(resultMetric, result.achieved, currency)}</dd>
            </div>
            <div>
              <dt>Cible</dt>
              <dd>{formatMetricValue(resultMetric, result.target, currency)}</dd>
            </div>
            <div>
              <dt>Écart signé</dt>
              <dd>{formatGap(resultMetric, result.gap, currency)}</dd>
            </div>
            <div>
              <dt>Évaluations</dt>
              <dd>
                {result.evaluations}
                {result.budgetExhausted ? " (budget épuisé)" : ""}
              </dd>
            </div>
          </dl>
          <div className="goal-seek__best">
            <strong>Meilleur point</strong>
            <ul>
              {Object.entries(result.best).map(([key, value]) => (
                <li key={key}>
                  <span>{ASSUMPTION_BY_KEY.get(key)?.label ?? key}</span>
                  <code>{formatNumber(value, 4)}</code>
                </li>
              ))}
            </ul>
          </div>
          <details className="goal-seek__trace">
            <summary>Voir les {result.trace.length} évaluations moteur</summary>
            <table>
              <thead>
                <tr>
                  <th scope="col">Point</th>
                  <th scope="col">Valeur</th>
                  <th scope="col">Faisable</th>
                </tr>
              </thead>
              <tbody>
                {result.trace.map((entry, index) => (
                  <tr key={`${index}-${entry.value}`}>
                    <td>
                      {Object.entries(entry.point)
                        .map(
                          ([key, value]) =>
                            `${ASSUMPTION_BY_KEY.get(key)?.label ?? key}=${formatNumber(
                              value,
                              4,
                            )}`,
                        )
                        .join(" · ")}
                    </td>
                    <td>{formatMetricValue(resultMetric, entry.value, currency)}</td>
                    <td>{entry.feasible ? "oui" : "non"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>

          <div className="goal-seek__actions">
            <Button
              onClick={apply}
              disabled={applyState.status === "running" || disabled}
            >
              {result.feasible
                ? "Créer une branche et lancer le calcul final"
                : "Créer une branche avec le meilleur compromis"}
            </Button>
          </div>

          {applyState.message ? (
            <InlineAlert
              tone={applyState.status === "error" ? "danger" : "neutral"}
              title={applyState.status === "error" ? "Application impossible" : "Branche"}
            >
              {applyState.message}
            </InlineAlert>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
