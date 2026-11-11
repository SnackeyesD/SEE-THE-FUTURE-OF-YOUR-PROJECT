import type { ProjectDataResult } from "@see/protocol";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  InlineAlert,
  Stat,
  Table,
} from "@see/ui";
import { useMemo } from "react";
import { MonthlyProfitChart, ProfitHistogram, SensitivityTornado } from "../components/Charts";
import {
  formatCurrency,
  formatDateTime,
  formatDuration,
  formatNumber,
  formatPercent,
} from "../lib/format";
import { verifyNarration } from "../lib/narration";

interface Props {
  run: ProjectDataResult["run"];
  narration: string;
  narrationBusy: boolean;
  error: string;
  onNarrate: () => Promise<void>;
  onBack: () => void;
}

export function ResultsScreen({
  run,
  narration,
  narrationBusy,
  error,
  onNarrate,
  onBack,
}: Props) {
  const result = run?.result ?? null;
  const unknownNumbers = useMemo(
    () => (result && narration ? verifyNarration(narration, result) : []),
    [narration, result],
  );

  if (!run || !result) {
    return (
      <div className="screen">
        <Card>
          <EmptyState
            title="Aucun résultat à afficher"
            description="Lancez une simulation pour obtenir les graphiques et la narration."
            action={
              <Button variant="secondary" onClick={onBack}>
                Retour à la simulation
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  const metrics = result.metrics;
  return (
    <div className="screen">
      <div className="screen__heading">
        <div>
          <p className="ui-eyebrow">Résultats</p>
          <h1>{result.scenarioName}</h1>
          <p className="ui-muted">
            {formatNumber(result.runs)} simulations · graine {result.seed} · horizon{" "}
            {result.horizonMonths} mois · {formatDuration(result.durationMs)}
          </p>
        </div>
        <div className="ui-actions">
          <Badge tone="accent">Moteur {result.engineVersion}</Badge>
          <Badge>{formatDateTime(run.createdAt)}</Badge>
        </div>
      </div>

      {error ? <InlineAlert tone="danger" title="Action impossible">{error}</InlineAlert> : null}

      <div className="stat-grid">
        <Stat
          label="Profit moyen"
          value={formatCurrency(metrics.meanProfit, result.currency)}
          hint={`Médiane ${formatCurrency(metrics.medianProfit, result.currency)}`}
        />
        <Stat
          label="P10 – P90"
          value={`${formatCurrency(metrics.p10, result.currency, { compact: true })} – ${formatCurrency(metrics.p90, result.currency, { compact: true })}`}
          hint="Fourchette de 80 % des résultats"
        />
        <Stat
          label="Probabilité de perte"
          value={formatPercent(metrics.lossProbability)}
          tone={metrics.lossProbability > 0.3 ? "danger" : "ok"}
          hint={`Gain positif : ${formatPercent(metrics.profitPositiveProbability)}`}
        />
        <Stat
          label="Chiffre d'affaires moyen"
          value={formatCurrency(metrics.meanRevenue, result.currency)}
          hint={`Coûts ${formatCurrency(metrics.meanCosts, result.currency, { compact: true })}`}
        />
        <Stat
          label="Marge moyenne"
          value={formatPercent(metrics.meanProfitMargin)}
          hint={`TVA/impôt ${formatCurrency(metrics.meanTax, result.currency, { compact: true })}`}
        />
        <Stat
          label="Seuil de rentabilité"
          value={
            result.breakEven.breakEvenUnitsMonthly === null
              ? "Non atteint"
              : `${formatNumber(result.breakEven.breakEvenUnitsMonthly, 1)} unités/mois`
          }
          hint={
            result.breakEven.breakEvenRevenueMonthly === null
              ? "Marge unitaire insuffisante"
              : formatCurrency(result.breakEven.breakEvenRevenueMonthly, result.currency)
          }
        />
      </div>

      <div className="chart-grid">
        <Card className="chart-card">
          <ProfitHistogram
            histogram={result.histogram}
            currency={result.currency}
            p10={metrics.p10}
            p50={metrics.p50}
            p90={metrics.p90}
          />
        </Card>
        <Card className="chart-card">
          <SensitivityTornado entries={result.sensitivity} currency={result.currency} />
        </Card>
        <Card className="chart-card chart-card--wide">
          <MonthlyProfitChart values={result.monthly.values} currency={result.currency} />
        </Card>
      </div>

      <Card>
        <CardHeader
          eyebrow="Sensibilité"
          title="Contribution des hypothèses"
          description="Valeurs calculées par le moteur, triées par impact absolu sur le profit."
        />
        <Table
          columns={[
            { key: "hypothesis", header: "Hypothèse" },
            { key: "contribution", header: "Contribution", mono: true },
            { key: "correlation", header: "Corrélation", mono: true },
          ]}
          rows={[...result.sensitivity]
            .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
            .slice(0, 8)
            .map((entry) => ({
              hypothesis: entry.hypothesis,
              contribution: formatCurrency(entry.contribution, result.currency, { compact: true }),
              correlation: entry.correlation.toFixed(2),
            }))}
          rowKey={(row) => row.hypothesis}
        />
      </Card>

      <Card>
        <CardHeader
          eyebrow="Narration"
          title="Lecture pédagogique"
          description="Texte produit par l'agent narrateur. Les chiffres sont vérifiés contre le résultat du moteur."
          action={
            <Button onClick={() => void onNarrate()} disabled={narrationBusy}>
              {narration ? "Regénérer" : "Générer la narration"}
            </Button>
          }
        />
        {narrationBusy ? <p className="ui-muted">L'agent prépare la narration…</p> : null}
        {narration ? (
          <>
            {unknownNumbers.length > 0 ? (
              <InlineAlert tone="danger" title="Chiffres non reconnus">
                Cette narration contient des nombres absents du résultat du moteur :{" "}
                {unknownNumbers.join(", ")}. Régénérez-la ou vérifiez ces valeurs.
              </InlineAlert>
            ) : (
              <InlineAlert tone="ok" title="Cohérence vérifiée">
                Tous les nombres cités existent dans le résultat du moteur.
              </InlineAlert>
            )}
            <div className="narration">
              {narration.split(/\n{2,}/).map((paragraph, index) => (
                <p key={index}>{paragraph}</p>
              ))}
            </div>
          </>
        ) : (
          <EmptyState
            title="Pas encore de narration"
            description="Demandez une lecture des résultats en français simple, centrée sur les décisions."
          />
        )}
      </Card>
    </div>
  );
}
