import type { ProjectRunCompareResult, RunRef } from "@see/protocol";
import { Badge, Button, EmptyState, InlineAlert } from "@see/ui";
import { useMemo } from "react";

import { formatCurrency, formatDateTime, formatNumber, formatPercent } from "../../lib/format";
import { compareMetrics } from "../../lib/scenarioDiff";

export interface ComparisonViewProps {
  runs: readonly RunRef[];
  runIds: readonly [string | null, string | null];
  comparison: ProjectRunCompareResult | null;
  currency: string;
  loading?: boolean;
  error?: string | null;
  onSelect: (side: 0 | 1, runId: string) => void;
  onPin?: (run: RunRef, pinned: boolean) => void;
}

function formatMetric(
  value: number | null,
  unit: "currency" | "percent",
  currency: string,
): string {
  if (value === null) return "—";
  return unit === "percent"
    ? formatPercent(value, 1)
    : formatCurrency(value, currency);
}

function formatDelta(
  value: number | null,
  unit: "currency" | "percent",
  currency: string,
): string {
  if (value === null) return "—";
  const sign = value > 0 ? "+" : "";
  return unit === "percent"
    ? `${sign}${formatPercent(value, 1)}`
    : `${sign}${formatCurrency(value, currency)}`;
}

function runLabel(run: RunRef): string {
  const seed = run.seed === null ? "graine —" : `graine ${formatNumber(run.seed)}`;
  const pinned = run.pinned ? " · épinglé" : "";
  return `${formatDateTime(run.createdAt)} · ${seed} · ${run.engineVersion}${pinned}`;
}

/**
 * Comparaison côte à côte de deux runs finaux. Les valeurs et deltas portent
 * sur les payloads du moteur ; aucune simulation n'est relancée. Une graine
 * ou une version de moteur différente bloque la lecture silencieuse.
 */
export function ComparisonView({
  runs,
  runIds,
  comparison,
  currency,
  loading = false,
  error = null,
  onSelect,
  onPin,
}: ComparisonViewProps) {
  const selected = useMemo(
    () =>
      runIds.map((id) => runs.find((run) => run.id === id) ?? null) as Array<
        RunRef | null
      >,
    [runs, runIds],
  );
  const deltas = useMemo(() => {
    if (!comparison) return [];
    return compareMetrics(
      comparison.runs[0].result.metrics,
      comparison.runs[1].result.metrics,
    );
  }, [comparison]);

  if (runs.length === 0) {
    return (
      <EmptyState
        title="Aucun run final à comparer"
        description="Lancez un calcul final sur deux branches avec la même graine pour comparer leurs résultats."
      />
    );
  }

  return (
    <div className="comparison-view">
      <div className="comparison-view__pickers">
        {[0, 1].map((side) => {
          const index = side as 0 | 1;
          const current = selected[index];
          return (
            <div key={index} className="comparison-view__picker">
              <label className="ui-field">
                <span>{index === 0 ? "Run A" : "Run B"}</span>
                <select
                  value={runIds[index] ?? ""}
                  onChange={(event) => onSelect(index, event.target.value)}
                  aria-label={`Sélection du run ${index === 0 ? "A" : "B"}`}
                >
                  <option value="">Choisir un run final…</option>
                  {runs.map((run) => (
                    <option key={run.id} value={run.id}>
                      {runLabel(run)}
                    </option>
                  ))}
                </select>
              </label>
              {current ? (
                <div className="comparison-view__pin">
                  <span className="ui-muted">Run {current.id.slice(0, 8)}…</span>
                  {onPin ? (
                    <Button
                      variant="ghost"
                      size="small"
                      onClick={() => onPin(current, !current.pinned)}
                    >
                      {current.pinned ? "Désépingler" : "Épingler ce run"}
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      {loading ? <p className="ui-muted">Chargement de la comparaison…</p> : null}
      {error ? (
        <InlineAlert tone="danger" title="Comparaison impossible">
          {error}
        </InlineAlert>
      ) : null}

      {comparison && !comparison.sameSeed ? (
        <InlineAlert tone="warn" title="Graines différentes">
          Les deux runs n'ont pas la même graine (
          {comparison.runs.map((run) => formatNumber(run.seed ?? 0)).join(" vs ")}). Un
          écart de graine est du bruit, pas une différence de scénario : relancez les
          deux branches avec la même graine avant de conclure.
        </InlineAlert>
      ) : null}

      {comparison && comparison.sameSeed && !comparison.sameEngineVersion ? (
        <InlineAlert tone="warn" title="Versions de moteur différentes">
          Les runs ont été calculés par des versions du moteur différentes (
          {comparison.runs[0].engineVersion} vs {comparison.runs[1].engineVersion}).
          Recalculez avec la version courante pour comparer.
        </InlineAlert>
      ) : null}

      {comparison ? (
        <div className="comparison-view__table">
          <table>
            <caption>
              Deltas des métriques — run B par rapport au run A
            </caption>
            <thead>
              <tr>
                <th scope="col">Métrique</th>
                <th scope="col">Run A</th>
                <th scope="col">Run B</th>
                <th scope="col">Delta</th>
                <th scope="col">Delta relatif</th>
              </tr>
            </thead>
            <tbody>
              {deltas.map((row) => (
                <tr key={row.key}>
                  <th scope="row">{row.label}</th>
                  <td>{formatMetric(row.before, row.unit, currency)}</td>
                  <td>{formatMetric(row.after, row.unit, currency)}</td>
                  <td
                    data-tone={
                      row.delta === null ? "neutral" : row.delta >= 0 ? "ok" : "danger"
                    }
                  >
                    {formatDelta(row.delta, row.unit, currency)}
                  </td>
                  <td>
                    {row.deltaPercent === null
                      ? "—"
                      : `${row.deltaPercent > 0 ? "+" : ""}${formatPercent(row.deltaPercent, 1)}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="ui-muted comparison-view__badges">
            <Badge tone={comparison.sameSeed ? "ok" : "warn"}>
              {comparison.sameSeed ? "graine identique" : "graine différente"}
            </Badge>
            <Badge tone={comparison.sameEngineVersion ? "ok" : "warn"}>
              {comparison.sameEngineVersion
                ? "même version de moteur"
                : "versions de moteur différentes"}
            </Badge>
          </div>
        </div>
      ) : null}
    </div>
  );
}
