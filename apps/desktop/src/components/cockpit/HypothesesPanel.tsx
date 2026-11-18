import type { Hypothesis, Scenario } from "@see/protocol";
import { Badge, EmptyState } from "@see/ui";
import { useRef } from "react";

import {
  ASSUMPTION_BY_KEY,
  ASSUMPTION_GROUPS,
  type AssumptionGroup,
} from "../../lib/assumptions";
import { formatNumber, formatPercent } from "../../lib/format";
import { TriHandleSlider, type TriValue } from "./TriHandleSlider";

export interface BenchmarkReference {
  label: string;
  value: number;
}

export function triFromHypothesis(hypothesis: Hypothesis): TriValue {
  const distribution = hypothesis.distribution;
  const firstValue = distribution?.values?.[0];
  const lastValue = distribution?.values?.at(-1);
  const rawLow = distribution?.low ?? firstValue ?? hypothesis.min ?? hypothesis.value * 0.8;
  const rawHigh = distribution?.high ?? lastValue ?? hypothesis.max ?? hypothesis.value * 1.2;
  const mode = distribution?.mode ?? hypothesis.value;
  return {
    low: Math.min(rawLow, mode),
    mode,
    high: Math.max(rawHigh, mode),
  };
}

/**
 * Écrit les trois poignées dans l'hypothèse sans inventer de distribution :
 * une triangulaire garde low/mode/high, une uniforme low/high, les autres
 * n'obtiennent que des bornes `min`/`max` descriptives.
 */
export function hypothesisFromTri(current: Hypothesis, tri: TriValue): Hypothesis {
  const distribution = current.distribution ? { ...current.distribution } : undefined;
  if (distribution?.kind === "triangular") {
    distribution.low = tri.low;
    distribution.mode = tri.mode;
    distribution.high = tri.high;
  } else if (distribution?.kind === "uniform") {
    distribution.low = tri.low;
    distribution.high = tri.high;
  }
  return {
    ...current,
    value: tri.mode,
    min: tri.low,
    max: tri.high,
    ...(distribution ? { distribution } : {}),
  };
}

function sameTri(left: TriValue, right: TriValue): boolean {
  return left.low === right.low && left.mode === right.mode && left.high === right.high;
}

/**
 * Panneau d'hypothèses du cockpit : groupé par thème, verrou, source et
 * confiance, référence de benchmark optionnelle. Chaque geste remonte au
 * parent, qui pousse une commande coalescée (phase 08).
 */
export function HypothesesPanel({
  scenario,
  locks,
  benchmarks = {},
  disabled = false,
  onToggleLock,
  onChange,
  onResetToBenchmark,
}: {
  scenario: Scenario;
  locks: ReadonlySet<string>;
  benchmarks?: Record<string, BenchmarkReference>;
  disabled?: boolean;
  onToggleLock: (key: string) => void;
  onChange: (key: string, hypothesis: Hypothesis, commit: boolean) => void;
  onResetToBenchmark?: (key: string, reference: BenchmarkReference) => void;
}) {
  const domains = useRef<Record<string, [number, number]>>({});
  const assumptions = scenario.assumptions ?? {};
  const keys = Object.keys(assumptions);

  const domainFor = (key: string, hypothesis: Hypothesis): [number, number] => {
    const cached = domains.current[key];
    if (cached) return cached;
    const spec = ASSUMPTION_BY_KEY.get(key);
    const tri = triFromHypothesis(hypothesis);
    const lower = spec?.min ?? Math.min(0, tri.low * 0.5);
    const upper = spec?.max ?? Math.max(tri.high * 2, tri.mode * 2, 1);
    const domain: [number, number] = [lower, Math.max(upper, tri.high)];
    domains.current[key] = domain;
    return domain;
  };

  if (keys.length === 0) {
    return (
      <EmptyState
        title="Aucune hypothèse"
        description="Enregistrez un scénario dans l'écran Hypothèses pour voir les curseurs du cockpit."
      />
    );
  }

  const groupOf = (key: string): AssumptionGroup | "autres" =>
    ASSUMPTION_BY_KEY.get(key)?.group ?? "autres";

  const groups: Array<{ id: string; label: string; keys: string[] }> = [
    ...ASSUMPTION_GROUPS.map((group) => ({
      id: group.id,
      label: group.label,
      keys: keys.filter((key) => groupOf(key) === group.id),
    })),
    {
      id: "autres",
      label: "Autres",
      keys: keys.filter((key) => groupOf(key) === "autres"),
    },
  ].filter((group) => group.keys.length > 0);

  return (
    <section className="cockpit-hypotheses" aria-label="Hypothèses">
      <header className="cockpit-hypotheses__head">
        <strong>Hypothèses</strong>
        <span className="ui-muted">
          {keys.length} paramètre{keys.length > 1 ? "s" : ""}
        </span>
      </header>

      {groups.map((group) => (
        <div key={group.id} className="cockpit-hypotheses__group">
          <h3 className="cockpit-hypotheses__group-title">{group.label}</h3>
          {group.keys.map((key) => {
            const hypothesis = assumptions[key];
            if (!hypothesis) return null;
            const spec = ASSUMPTION_BY_KEY.get(key);
            const label = spec?.label ?? key;
            const unit = spec?.unit;
            const locked = locks.has(key);
            const tri = triFromHypothesis(hypothesis);
            const reference = benchmarks[key];
            const provenance = hypothesis.provenance;
            return (
              <article key={key} className="cockpit-hypothesis">
                <TriHandleSlider
                  label={label}
                  unit={unit}
                  value={tri}
                  domain={domainFor(key, hypothesis)}
                  disabled={disabled || locked}
                  formatValue={(number) => formatNumber(number, 4)}
                  onChange={(next, commit) => {
                    if (sameTri(next, tri)) return;
                    onChange(key, hypothesisFromTri(hypothesis, next), commit);
                  }}
                />

                <div className="cockpit-hypothesis__meta">
                  {provenance?.kind === "benchmark" ? (
                    <Badge tone="accent">Benchmark · {provenance.label}</Badge>
                  ) : hypothesis.source ? (
                    <Badge tone="neutral">{hypothesis.source}</Badge>
                  ) : null}
                  {hypothesis.confidence !== undefined ? (
                    <Badge tone="neutral">
                      Confiance {formatPercent(hypothesis.confidence)}
                    </Badge>
                  ) : null}
                  <button
                    type="button"
                    className="cockpit-hypothesis__lock"
                    aria-pressed={locked}
                    aria-label={`${locked ? "Déverrouiller" : "Verrouiller"} ${label}`}
                    onClick={() => onToggleLock(key)}
                  >
                    {locked ? "Verrouillé" : "Verrou"}
                  </button>
                </div>

                {reference ? (
                  <div className="cockpit-hypothesis__benchmark">
                    <span className="ui-muted">
                      Référence : {reference.label} · {formatNumber(reference.value, 4)}
                    </span>
                    {onResetToBenchmark ? (
                      <button
                        type="button"
                        className="cockpit-hypothesis__reset"
                        onClick={() => onResetToBenchmark(key, reference)}
                      >
                        Revenir au benchmark
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      ))}
    </section>
  );
}
