import type { Project, ProjectDataResult, ScenarioRecord } from "@see/protocol";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Field,
  InlineAlert,
  ProgressBar,
  Stat,
} from "@see/ui";
import { useState } from "react";
import { formatCurrency, formatDuration, formatNumber } from "../lib/format";

interface Props {
  project: Project;
  scenario: ScenarioRecord | null;
  run: ProjectDataResult["run"];
  progress: number | null;
  busy: boolean;
  error: string;
  onRun: (config: { runs: number; seed: number; histogramBins: number }) => Promise<void>;
  onOpenResults: () => void;
  onBack: () => void;
}

export function SimulationScreen({
  project,
  scenario,
  run,
  progress,
  busy,
  error,
  onRun,
  onOpenResults,
  onBack,
}: Props) {
  const [runs, setRuns] = useState("10000");
  const [seed, setSeed] = useState("42");
  const [bins, setBins] = useState("40");
  const parsedRuns = Number(runs.replace(/\s/g, ""));
  const parsedSeed = Number(seed);
  const parsedBins = Number(bins);
  const valid =
    Number.isInteger(parsedRuns) &&
    parsedRuns >= 1 &&
    parsedRuns <= 1_000_000 &&
    Number.isInteger(parsedSeed) &&
    parsedSeed >= 0 &&
    Number.isInteger(parsedBins) &&
    parsedBins >= 1 &&
    parsedBins <= 200;

  return (
    <div className="screen">
      <div className="screen__heading">
        <div>
          <p className="ui-eyebrow">Simulation</p>
          <h1>Monte Carlo local</h1>
          <p className="ui-muted">
            Le moteur exécute le scénario sur cet appareil. Aucun appel IA, aucun coût fournisseur.
          </p>
        </div>
        <Badge tone="ok">Moteur local</Badge>
      </div>

      {error ? <InlineAlert tone="danger" title="Action impossible">{error}</InlineAlert> : null}

      {!scenario ? (
        <Card>
          <EmptyState
            title="Hypothèses requises"
            description="Enregistrez d'abord un scénario avec au moins une hypothèse."
            action={
              <Button variant="secondary" onClick={onBack}>
                Retour aux hypothèses
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="split">
          <Card>
            <CardHeader
              eyebrow="Paramètres"
              title={scenario.name}
              description={`Scénario ${scenario.scenario.currency} · ${scenario.scenario.horizonMonths} mois · ${Object.keys(scenario.scenario.assumptions ?? {}).length} hypothèses`}
            />
            <div className="ui-field-grid">
              <Field
                label="Nombre de simulations"
                value={runs}
                inputMode="numeric"
                onChange={(event) => setRuns(event.target.value)}
                hint="De 1 à 1 000 000. 10 000 est un bon départ."
              />
              <Field
                label="Graine aléatoire"
                value={seed}
                inputMode="numeric"
                onChange={(event) => setSeed(event.target.value)}
                hint="Même graine = mêmes résultats."
              />
              <Field
                label="Classes d'histogramme"
                value={bins}
                inputMode="numeric"
                onChange={(event) => setBins(event.target.value)}
                hint="Entre 1 et 200."
              />
            </div>
            <InlineAlert tone="neutral" title="Coût">
              Cette étape ne consomme aucun token. Le coût IA éventuel reste visible dans les
              réglages et le plafond du projet.
            </InlineAlert>
            <div className="ui-actions ui-actions--end">
              <Button
                onClick={() =>
                  void onRun({ runs: parsedRuns, seed: parsedSeed, histogramBins: parsedBins })
                }
                disabled={busy || !valid}
              >
                Lancer la simulation
              </Button>
            </div>
            {busy ? <ProgressBar value={progress ?? undefined} label="Calcul des scénarios" /> : null}
          </Card>

          <Card>
            <CardHeader eyebrow="Dernier passage" title="Résumé" />
            {run ? (
              <div className="ui-stack">
                <Stat
                  label="Profit moyen"
                  value={formatCurrency(run.result?.metrics.meanProfit ?? 0, project.currency)}
                />
                <Stat
                  label="Probabilité de perte"
                  value={`${Math.round((run.result?.metrics.lossProbability ?? 0) * 1000) / 10} %`}
                  tone={(run.result?.metrics.lossProbability ?? 0) > 0.3 ? "danger" : "ok"}
                />
                <Stat label="Simulations" value={formatNumber(run.runs)} />
                <Stat label="Durée moteur" value={formatDuration(run.durationMs)} />
                <Button variant="secondary" onClick={onOpenResults}>
                  Voir les graphiques
                </Button>
              </div>
            ) : (
              <EmptyState
                title="Aucun résultat"
                description="Lancez une simulation pour afficher la distribution, la sensibilité et la rentabilité."
              />
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
