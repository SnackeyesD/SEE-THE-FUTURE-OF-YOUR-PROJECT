import type {
  BenchmarkProvenance,
  BenchmarkRecord,
  BriefRecord,
  DistributionSpec,
  Hypothesis,
  Project,
  Scenario,
  ScenarioRecord,
} from "@see/protocol";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  InlineAlert,
  SelectField,
} from "@see/ui";
import { useEffect, useMemo, useState } from "react";
import { formatDateTime } from "../lib/format";
import { benchmarkLookup, ipcAvailable } from "../lib/ipc";

interface Props {
  project: Project;
  brief: BriefRecord | null;
  scenario: ScenarioRecord | null;
  busy: boolean;
  error: string;
  onSave: (name: string, scenario: Scenario) => Promise<boolean>;
  onNext: () => void;
  onBack: () => void;
}

interface AssumptionSpec {
  key: string;
  label: string;
  unit: string;
  defaultValue: number;
  required: boolean;
  min?: number;
  max?: number;
}

const SPECS: AssumptionSpec[] = [
  { key: "initial_cash", label: "Trésorerie initiale", unit: "FCFA", defaultValue: 500_000, required: true, min: 0 },
  { key: "unit_price", label: "Prix de vente unitaire", unit: "FCFA/unité", defaultValue: 5_000, required: true, min: 0 },
  { key: "unit_cost", label: "Coût d'achat unitaire", unit: "FCFA/unité", defaultValue: 3_000, required: true, min: 0 },
  { key: "fixed_costs_monthly", label: "Coûts fixes mensuels", unit: "FCFA/mois", defaultValue: 300_000, required: true, min: 0 },
  { key: "demand_mean_monthly", label: "Demande moyenne mensuelle", unit: "unités/mois", defaultValue: 200, required: true, min: 0 },
  { key: "demand_cv", label: "Variation de la demande", unit: "coefficient", defaultValue: 0.2, required: false, min: 0, max: 5 },
  { key: "loss_rate", label: "Taux de perte mensuel", unit: "fraction", defaultValue: 0.02, required: false, min: 0, max: 1 },
  { key: "logistics_cost_per_unit", label: "Coût logistique unitaire", unit: "FCFA/unité", defaultValue: 0, required: false, min: 0 },
  { key: "target_stock_months", label: "Stock cible", unit: "mois de demande", defaultValue: 1, required: false, min: 0, max: 24 },
  { key: "reorder_lead_time_months", label: "Délai de réapprovisionnement", unit: "mois", defaultValue: 1, required: false, min: 0, max: 24 },
  { key: "initial_stock", label: "Stock initial", unit: "unités", defaultValue: 0, required: false, min: 0 },
  { key: "tax_rate", label: "Taux d'imposition", unit: "fraction", defaultValue: 0, required: false, min: 0, max: 1 },
];

const DISTRIBUTIONS = [
  ["none", "Valeur fixe"],
  ["normal", "Normale"],
  ["lognormal", "Log-normale"],
  ["triangular", "Triangulaire"],
  ["uniform", "Uniforme"],
  ["poisson", "Poisson"],
] as const;

interface Row {
  value: string;
  kind: string;
  low: string;
  high: string;
  spread: string;
}

type Rows = Record<string, Row>;

function defaultRows(): Rows {
  const rows: Rows = {};
  for (const spec of SPECS) {
    rows[spec.key] = {
      value: String(spec.defaultValue),
      kind: "none",
      low: String(Number((spec.defaultValue * 0.8).toFixed(4))),
      high: String(Number((spec.defaultValue * 1.2).toFixed(4))),
      spread: String(Number((spec.defaultValue * 0.1).toFixed(4))),
    };
  }
  return rows;
}

function rowsFromScenario(scenario: Scenario | null): Rows {
  const rows = defaultRows();
  if (!scenario) return rows;
  for (const spec of SPECS) {
    const hypothesis = scenario.assumptions?.[spec.key];
    if (!hypothesis) continue;
    const distribution = hypothesis.distribution;
    rows[spec.key] = {
      value: String(hypothesis.value),
      kind: distribution?.kind ?? "none",
      low: String(distribution?.low ?? hypothesis.min ?? spec.defaultValue * 0.8),
      high: String(distribution?.high ?? hypothesis.max ?? spec.defaultValue * 1.2),
      spread: String(distribution?.std ?? distribution?.sigma ?? spec.defaultValue * 0.1),
    };
  }
  return rows;
}

function parseNumber(raw: string): number {
  return Number(raw.replace(",", "."));
}

const RELIABILITY_CONFIDENCE: Record<BenchmarkRecord["reliability"], number> = {
  official: 0.9,
  study: 0.8,
  field: 0.7,
  estimate: 0.45,
};

function provenanceFromScenario(
  scenario: Scenario | null,
): Record<string, BenchmarkProvenance> {
  const result: Record<string, BenchmarkProvenance> = {};
  for (const [key, hypothesis] of Object.entries(scenario?.assumptions ?? {})) {
    if (hypothesis.provenance?.kind === "benchmark") {
      result[key] = hypothesis.provenance;
    }
  }
  return result;
}

function provenanceFromRecord(record: BenchmarkRecord): BenchmarkProvenance {
  return {
    kind: "benchmark",
    label: record.source,
    indicator: record.indicator,
    source: record.source,
    sourceUrl: record.sourceUrl,
    sourceDate: record.sourceDate,
    reliability: record.reliability,
    freshness: record.freshness,
    packId: record.packId,
    packVersion: record.packVersion,
    packPublishedAt: record.packPublishedAt,
    keyId: record.keyId,
    checksum: record.checksum,
    fallback: record.fallback,
    conflicts: record.conflicts,
  };
}

function geographyFromBrief(content: Record<string, unknown>): {
  country?: string;
  region?: string;
} {
  const geography = typeof content.geography === "string" ? content.geography : "";
  const normalized = geography.toLowerCase();
  if (normalized.includes("brazzaville")) {
    return { country: "CG", region: "Brazzaville" };
  }
  if (normalized.includes("bangui")) {
    return { country: "CF", region: "Bangui" };
  }
  if (normalized.includes("centrafrique") || normalized.includes("rca")) {
    return { country: "CF" };
  }
  if (normalized.includes("congo")) {
    return { country: "CG" };
  }
  return {};
}

function distributionFrom(row: Row, value: number): DistributionSpec | undefined {
  switch (row.kind) {
    case "normal":
      return { kind: "normal", mean: value, std: Math.max(parseNumber(row.spread) || 0, 1e-9) };
    case "lognormal":
      return { kind: "lognormal", mean: value, sigma: Math.max(parseNumber(row.spread) || 0, 1e-9) };
    case "triangular":
      return {
        kind: "triangular",
        low: parseNumber(row.low),
        mode: value,
        high: parseNumber(row.high),
      };
    case "uniform":
      return { kind: "uniform", low: parseNumber(row.low), high: parseNumber(row.high) };
    case "poisson":
      return { kind: "poisson", mean: Math.max(value, 1e-9) };
    default:
      return undefined;
  }
}

export function HypothesesScreen({
  project,
  brief,
  scenario,
  busy,
  error,
  onSave,
  onNext,
  onBack,
}: Props) {
  const [name, setName] = useState(scenario?.name ?? `${project.name} — base`);
  const [rows, setRows] = useState<Rows>(() => rowsFromScenario(scenario?.scenario ?? null));
  const [showOptional, setShowOptional] = useState(false);
  const [localError, setLocalError] = useState("");
  const [benchmarks, setBenchmarks] = useState<Record<string, BenchmarkRecord>>({});
  const [savedProvenance, setSavedProvenance] = useState<Record<string, BenchmarkProvenance>>(
    () => provenanceFromScenario(scenario?.scenario ?? null),
  );
  const [applied, setApplied] = useState<Set<string>>(
    () => new Set(Object.keys(provenanceFromScenario(scenario?.scenario ?? null))),
  );

  useEffect(() => {
    setName(scenario?.name ?? `${project.name} - base`);
    setRows(rowsFromScenario(scenario?.scenario ?? null));
    const provenance = provenanceFromScenario(scenario?.scenario ?? null);
    setSavedProvenance(provenance);
    setApplied(new Set(Object.keys(provenance)));
  }, [scenario, project.name]);

  const geography = useMemo(
    () => geographyFromBrief(brief?.content ?? {}),
    [brief?.content],
  );

  useEffect(() => {
    if (!ipcAvailable || !geography.country) {
      setBenchmarks({});
      return;
    }
    let cancelled = false;
    void Promise.all(
      SPECS.map(async (spec): Promise<[string, BenchmarkRecord] | null> => {
        try {
          const result = await benchmarkLookup({
            indicator: spec.key,
            country: geography.country,
            region: geography.region,
            sector: "retail",
            subsector: "alimentation_generale",
          });
          return result.found && result.record ? [spec.key, result.record] : null;
        } catch {
          return null;
        }
      }),
    ).then((entries) => {
      if (cancelled) return;
      setBenchmarks(
        Object.fromEntries(entries.filter((entry): entry is [string, BenchmarkRecord] => entry !== null)),
      );
    });
    return () => {
      cancelled = true;
    };
  }, [geography.country, geography.region]);

  const scope = useMemo(() => {
    const content = brief?.content ?? {};
    const briefCurrency =
      typeof content.currency === "string" && content.currency.trim()
        ? content.currency.trim()
        : project.currency;
    const briefHorizon = Number(content.horizonMonths);
    const rawCurrency = scenario?.scenario.currency ?? briefCurrency;
    return {
      currency: /^[A-Za-z]{3}$/.test(rawCurrency) ? rawCurrency.toUpperCase() : project.currency,
      horizonMonths:
        scenario?.scenario.horizonMonths ??
        (Number.isFinite(briefHorizon) && briefHorizon > 0 ? briefHorizon : 12),
    };
  }, [brief, project.currency, scenario]);

  const update = (key: string, patch: Partial<Row>) => {
    setRows((current) => ({ ...current, [key]: { ...current[key], ...patch } }));
    setApplied((current) => {
      if (!current.has(key)) return current;
      const next = new Set(current);
      next.delete(key);
      return next;
    });
    setSavedProvenance((current) => {
      if (!(key in current)) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  };

  const applyBenchmark = (key: string) => {
    const record = benchmarks[key];
    if (!record) return;
    setRows((current) => ({
      ...current,
      [key]: { ...current[key], value: String(record.value) },
    }));
    setApplied((current) => new Set(current).add(key));
  };

  const applyAllBenchmarks = () => {
    setRows((current) => {
      const next = { ...current };
      for (const [key, record] of Object.entries(benchmarks)) {
        next[key] = { ...next[key], value: String(record.value) };
      }
      return next;
    });
    setApplied(new Set(Object.keys(benchmarks)));
  };

  const assumptions = useMemo(() => {
    const result: Record<string, Hypothesis> = {};
    for (const spec of SPECS) {
      const row = rows[spec.key];
      const value = parseNumber(row.value);
      if (!Number.isFinite(value)) continue;
      const distribution = distributionFrom(row, value);
      const record = applied.has(spec.key) ? benchmarks[spec.key] : undefined;
      const provenance = record
        ? provenanceFromRecord(record)
        : applied.has(spec.key)
          ? savedProvenance[spec.key]
          : undefined;
      result[spec.key] = {
        value,
        source: provenance?.source ?? "utilisateur",
        confidence: provenance?.reliability
          ? RELIABILITY_CONFIDENCE[provenance.reliability]
          : spec.required
            ? 0.7
            : 0.5,
        ...(provenance ? { provenance } : {}),
        ...(distribution ? { distribution } : {}),
      };
    }
    return result;
  }, [applied, benchmarks, rows, savedProvenance]);

  const validate = (): string => {
    for (const spec of SPECS) {
      const row = rows[spec.key];
      const value = parseNumber(row.value);
      if (!Number.isFinite(value)) return `${spec.label}: valeur numérique requise.`;
      if (spec.min !== undefined && value < spec.min) return `${spec.label}: minimum ${spec.min}.`;
      if (spec.max !== undefined && value > spec.max) return `${spec.label}: maximum ${spec.max}.`;
      if (row.kind === "uniform" || row.kind === "triangular") {
        const low = parseNumber(row.low);
        const high = parseNumber(row.high);
        if (!Number.isFinite(low) || !Number.isFinite(high) || low >= high) {
          return `${spec.label}: les bornes basse et haute sont invalides.`;
        }
        if (row.kind === "triangular" && (value < low || value > high)) {
          return `${spec.label}: le mode doit rester entre les bornes.`;
        }
      }
      if ((row.kind === "normal" || row.kind === "lognormal") && !(parseNumber(row.spread) > 0)) {
        return `${spec.label}: l'écart-type doit être strictement positif.`;
      }
    }
    if (!name.trim()) return "Le nom du scénario est requis.";
    return "";
  };

  const save = async (): Promise<boolean> => {
    const problem = validate();
    if (problem) {
      setLocalError(problem);
      return false;
    }
    setLocalError("");
    const content: Scenario = {
      schemaVersion: "1.0.0",
      name: name.trim(),
      model: "retail_depot",
      currency: scope.currency,
      horizonMonths: scope.horizonMonths,
      assumptions,
      seasonality: null,
      notes: "Hypothèses saisies dans l'interface.",
    };
    return onSave(name.trim(), content);
  };

  const visible = showOptional ? SPECS : SPECS.filter((spec) => spec.required);
  const message = localError || error;
  const hasBenchmarks = Object.keys(benchmarks).length > 0;

  return (
    <div className="screen">
      <div className="screen__heading">
        <div>
          <p className="ui-eyebrow">Hypothèses</p>
          <h1>Cadrez l'incertitude</h1>
          <p className="ui-muted">
            Une valeur centrale suffit pour démarrer. Ajoutez une distribution pour simuler la
            variabilité.
          </p>
        </div>
        <div className="ui-actions">
          {scenario ? <Badge tone="ok">Enregistré</Badge> : <Badge tone="warn">À définir</Badge>}
          {scenario ? <Badge>{formatDateTime(scenario.updatedAt)}</Badge> : null}
        </div>
      </div>

      {message ? <InlineAlert tone="danger" title="Action impossible">{message}</InlineAlert> : null}

      <Card>
        <CardHeader
          eyebrow="Scénario"
          title="Nom et périmètre"
          description={`Le moteur retail_depot calcule stock, ventes, coûts et trésorerie sur ${scope.horizonMonths} mois.`}
        />
        <div className="ui-field-grid">
          <Field label="Nom du scénario" value={name} onChange={(event) => setName(event.target.value)} />
          <Field label="Modèle" value="Dépôt de revente (retail_depot)" readOnly />
        </div>
      </Card>

      <Card>
        <CardHeader
          eyebrow="Variables"
          title="Hypothèses du moteur"
          action={
            <div className="ui-actions">
              <Button
                variant="ghost"
                size="small"
                onClick={applyAllBenchmarks}
                disabled={!hasBenchmarks}
              >
                Appliquer les références
              </Button>
              <Button variant="ghost" size="small" onClick={() => setShowOptional((value) => !value)}>
                {showOptional ? "Masquer les options" : "Afficher les options"}
              </Button>
            </div>
          }
        />
        <div className="assumption-list">
          {visible.map((spec) => {
            const row = rows[spec.key];
            const record = benchmarks[spec.key];
            const isApplied = applied.has(spec.key);
            return (
              <div className="assumption-row" key={spec.key}>
                <div className="assumption-row__label">
                  <strong>{spec.label}</strong>
                  <span className="ui-muted">{spec.unit}{spec.required ? " � requis" : ""}</span>
                  {record ? (
                    <div className="ui-actions">
                      <Badge tone="accent">référence signée</Badge>
                      <span className="ui-muted">
                        {record.reliability} · {record.freshness} · {record.sourceDate}
                      </span>
                      {record.fallback !== "none" ? (
                        <Badge tone="warn">fallback {record.fallback}</Badge>
                      ) : null}
                      <Button
                        variant="ghost"
                        size="small"
                        onClick={() => applyBenchmark(spec.key)}
                      >
                        {isApplied ? "Appliquée" : "Utiliser"}
                      </Button>
                    </div>
                  ) : isApplied && savedProvenance[spec.key] ? (
                    <Badge tone="accent">référence enregistrée</Badge>
                  ) : null}
                </div>
                <Field
                  label="Valeur"
                  value={row.value}
                  inputMode="decimal"
                  onChange={(event) => update(spec.key, { value: event.target.value })}
                />
                <SelectField
                  label="Distribution"
                  value={row.kind}
                  onChange={(event) => update(spec.key, { kind: event.target.value })}
                >
                  {DISTRIBUTIONS.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </SelectField>
                {row.kind === "uniform" || row.kind === "triangular" ? (
                  <>
                    <Field
                      label="Borne basse"
                      value={row.low}
                      inputMode="decimal"
                      onChange={(event) => update(spec.key, { low: event.target.value })}
                    />
                    <Field
                      label="Borne haute"
                      value={row.high}
                      inputMode="decimal"
                      onChange={(event) => update(spec.key, { high: event.target.value })}
                    />
                  </>
                ) : null}
                {row.kind === "normal" || row.kind === "lognormal" ? (
                  <Field
                    label={row.kind === "normal" ? "Écart-type" : "Sigma"}
                    value={row.spread}
                    inputMode="decimal"
                    onChange={(event) => update(spec.key, { spread: event.target.value })}
                  />
                ) : null}
              </div>
            );
          })}
        </div>
      </Card>

      <Card>
        <div className="ui-actions ui-actions--end">
          <Button variant="ghost" onClick={onBack} disabled={busy}>
            Retour au brief
          </Button>
          <Button variant="secondary" onClick={() => void save()} disabled={busy}>
            Enregistrer le scénario
          </Button>
          <Button
            onClick={() => void save().then((saved) => (saved ? onNext() : undefined))}
            disabled={busy}
          >
            Enregistrer et simuler
          </Button>
        </div>
      </Card>
    </div>
  );
}
