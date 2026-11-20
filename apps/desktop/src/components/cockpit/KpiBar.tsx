import type {
  ConvergenceState,
  Metrics,
  MonthlyAverage,
  SimulationQuality,
} from "@see/protocol";
import { Badge, Stat } from "@see/ui";

import { formatCurrency, formatNumber, formatProbability } from "../../lib/format";
import type { SessionStatus } from "../../store/cockpitStore";
import { ConvergenceBadge } from "./ConvergenceBadge";
import { SeedControl } from "./SeedControl";

const NOT_AVAILABLE = "non disponible";

function currencyValue(value: number | null | undefined, currency: string): string {
  return value === null || value === undefined ? NOT_AVAILABLE : formatCurrency(value, currency);
}

/**
 * Barre KPI du cockpit. Aucun chiffre n'est calculé ici : tout vient des
 * agrégats du moteur (`Metrics`, `MonthlyAverages`, `ConvergenceState`).
 * Chaque mesure porte sa définition en infobulle et, quand il y en a un, le
 * nombre de runs retenus.
 */
export function KpiBar({
  currency,
  metrics,
  monthly,
  convergence,
  status,
  quality,
  seed,
  runs,
  runsRetained,
  engineVersion,
  disabled = false,
  month,
  onMonthChange,
  onSeedChange,
  onRerollSeed,
}: {
  currency: string;
  metrics: Metrics | null;
  monthly: readonly MonthlyAverage[];
  convergence?: ConvergenceState | null;
  status: SessionStatus;
  quality?: SimulationQuality | null;
  seed: number;
  runs?: number;
  runsRetained?: number;
  engineVersion?: string;
  disabled?: boolean;
  /** Mois sélectionné dans le cockpit (partagé avec le curseur de temps). */
  month: number | null;
  onMonthChange: (month: number) => void;
  onSeedChange: (seed: number) => void;
  onRerollSeed?: () => void;
}) {
  const horizon = monthly.length > 0 ? monthly[monthly.length - 1].index : 0;
  const candidates = new Set([6, 12, 18, horizon]);
  // Le mois courant peut venir du curseur de temps (valeur arbitraire) :
  // il doit rester lisible dans le sélecteur, sinon la probabilité affichée
  // serait celle de l'horizon au lieu du mois inspecté.
  if (month !== null && month >= 1 && month <= horizon) candidates.add(month);
  const options = horizon
    ? [...candidates]
        .filter((months) => months > 0 && months <= horizon)
        .sort((left, right) => left - right)
    : [];
  const selectedMonth =
    month !== null && options.includes(month)
      ? month
      : (options[options.length - 1] ?? 0);
  const breakEvenMonth = monthly.find((entry) => entry.index === selectedMonth);
  const breakEvenProbability = breakEvenMonth?.breakEvenProbability ?? null;

  const runsLabel =
    runs && runs > 0
      ? `${formatNumber(runsRetained ?? runs)} / ${formatNumber(runs)} runs`
      : "runs non disponibles";

  return (
    <section className="cockpit-kpi" aria-label="Indicateurs clés">
      <div
        className="cockpit-kpi__item"
        title="Probabilité que le point mort soit atteint au plus tard au mois choisi (cumul des runs)."
      >
        <div className="cockpit-kpi__head">
          <label className="cockpit-kpi__label" htmlFor="cockpit-break-even">
            Point mort ≤
          </label>
          <select
            id="cockpit-break-even"
            className="cockpit-kpi__select"
            value={selectedMonth || ""}
            onChange={(event) => onMonthChange(Number(event.target.value))}
            disabled={options.length === 0}
          >
            {options.length === 0 ? <option value="">—</option> : null}
            {options.map((months) => (
              <option key={months} value={months}>
                {months === horizon ? `${months} mois (horizon)` : `${months} mois`}
              </option>
            ))}
          </select>
        </div>
        <Stat
          label="Probabilité"
          value={formatProbability(breakEvenProbability)}
          hint={runsLabel}
        />
      </div>

      <div
        className="cockpit-kpi__item"
        title="Trésorerie minimale projetée : besoin de financement P50 et P90 sur les runs retenus."
      >
        <Stat
          label="Besoin de financement"
          value={currencyValue(metrics?.financingNeedP50, currency)}
          hint={
            metrics?.financingNeedP90 === undefined
              ? undefined
              : `P90 ${formatCurrency(metrics.financingNeedP90, currency)}`
          }
        />
      </div>

      <div
        className="cockpit-kpi__item"
        title="Probabilité que la trésorerie minimale devienne négative sur l'horizon."
      >
        <Stat
          label="P(trésorerie < 0)"
          value={formatProbability(metrics?.cashNegativeProbability)}
          tone={
            metrics?.cashNegativeProbability !== undefined &&
            metrics.cashNegativeProbability > 0.5
              ? "danger"
              : "neutral"
          }
          hint={runsLabel}
        />
      </div>

      <div
        className="cockpit-kpi__item"
        title="Profit cumulé médian (P50) et fourchette P10–P90 sur les runs retenus."
      >
        <Stat
          label="Profit P50"
          value={currencyValue(metrics?.p50, currency)}
          hint={
            metrics === null
              ? undefined
              : `P10 ${formatCurrency(metrics.p10, currency)} · P90 ${formatCurrency(
                  metrics.p90,
                  currency,
                )}`
          }
        />
      </div>

      <div className="cockpit-kpi__item cockpit-kpi__item--status" title="Convergence observée du calcul.">
        <ConvergenceBadge convergence={convergence} status={status} />
        {quality ? (
          <Badge tone={quality === "draft" ? "warn" : "ok"}>
            {quality === "draft" ? "Brouillon" : "Final"}
          </Badge>
        ) : null}
        {engineVersion ? (
          <span className="cockpit-kpi__engine">moteur {engineVersion}</span>
        ) : null}
      </div>

      <div className="cockpit-kpi__item cockpit-kpi__item--seed" title="Graine du calcul en cours.">
        <SeedControl
          seed={seed}
          disabled={disabled}
          onChange={onSeedChange}
          onReroll={onRerollSeed}
        />
      </div>
    </section>
  );
}
