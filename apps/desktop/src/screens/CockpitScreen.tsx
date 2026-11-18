import type { Project, ProjectDataResult, ScenarioRecord } from "@see/protocol";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  InlineAlert,
  ProgressBar,
} from "@see/ui";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ProfitHistogram, SensitivityTornado } from "../components/Charts";
import { FanChartPanel, fanPointsFromMonthly, type FanMode } from "../components/cockpit/FanChartPanel";
import { GhostLegend } from "../components/cockpit/GhostLegend";
import {
  HypothesesPanel,
  hypothesisFromTri,
  triFromHypothesis,
  type BenchmarkReference,
} from "../components/cockpit/HypothesesPanel";
import { KpiBar } from "../components/cockpit/KpiBar";
import { useLiveSimulation } from "../hooks/useLiveSimulation";
import { formatCurrency, formatNumber } from "../lib/format";
import { PanelGrid } from "../components/layout/PanelGrid";
import { CockpitProvider, useCockpitContext } from "../store/CockpitProvider";
import { useCockpit, type RunState } from "../store/cockpitStore";
import { snapshotCommand } from "../store/commands";
import { loadLayout } from "../store/layout";

export interface CockpitScreenProps {
  project: Project;
  scenario: ScenarioRecord | null;
  run: ProjectDataResult["run"];
  onBack: () => void;
  onOpenHypotheses: () => void;
}

function latestResult(runs: Record<string, RunState>): RunState | null {
  const ids = Object.keys(runs);
  for (let index = ids.length - 1; index >= 0; index -= 1) {
    const run = runs[ids[index]];
    if (run?.result) return run;
  }
  return null;
}

/**
 * Cockpit 2D : composition KPI / hypothèses / éventail / secondaire / frise.
 *
 * Toutes les valeurs viennent du store, alimenté par les agrégats du moteur
 * (partiels et finaux). Aucun chiffre n'est recalculé dans React ; le seuil
 * n'interroge que la CDF fournie.
 */
export function CockpitScreen({
  project,
  scenario,
  run,
  onBack,
  onOpenHypotheses,
}: CockpitScreenProps) {
  const initialLayout = useMemo(() => loadLayout(project.id), [project.id]);
  const seed = run?.result?.seed ?? run?.seed ?? 42;

  if (!scenario) {
    return (
      <Card>
        <CardHeader title="Cockpit" description="Aucun scénario enregistré pour ce projet." />
        <EmptyState
          title="Rien à simuler"
          description="Enregistrez d'abord un scénario d'hypothèses ; le cockpit affichera ensuite l'éventail P10–P90."
          action={<Button onClick={onOpenHypotheses}>Ouvrir les hypothèses</Button>}
        />
      </Card>
    );
  }

  return (
    <CockpitProvider
      key={`${project.id}:${scenario.id}`}
      projectId={project.id}
      scenario={scenario.scenario}
      seed={seed}
      initialLayout={initialLayout}
    >
      <CockpitBody
        project={project}
        record={scenario}
        initialRun={run}
        onBack={onBack}
        onOpenHypotheses={onOpenHypotheses}
      />
    </CockpitProvider>
  );
}

function CockpitBody({
  project,
  record,
  initialRun,
  onBack,
  onOpenHypotheses,
}: {
  project: Project;
  record: ScenarioRecord;
  initialRun: ProjectDataResult["run"];
  onBack: () => void;
  onOpenHypotheses: () => void;
}) {
  const { store, inputs, applyLayout } = useCockpitContext();
  const session = useCockpit(store, (state) => state.session);
  const runs = useCockpit(store, (state) => state.runs);
  const pinned = useCockpit(store, (state) => state.pinned);
  const layout = useCockpit(store, (state) => state.layout);
  const selection = useCockpit(store, (state) => state.selection);

  const live = useLiveSimulation({ store });
  const [mode, setMode] = useState<FanMode>("cash");
  const [thresholdOverride, setThresholdOverride] = useState<number | null>(null);
  const [locks, setLocks] = useState<ReadonlySet<string>>(() => new Set<string>());
  const gesture = useRef(false);

  useEffect(() => {
    const result = initialRun?.result;
    if (!result) return;
    if (!store.getState().runs[result.runId]) store.getState().hydrateRun(result);
  }, [initialRun, store]);

  useEffect(() => inputs.subscribe(() => live.invalidate()), [inputs, live.invalidate]);

  const active = session.activeRunId ? runs[session.activeRunId] ?? null : null;
  const latest = useMemo(() => latestResult(runs), [runs]);
  const display = active ?? latest;
  const result = display?.result ?? null;
  const aggregates = display?.aggregates ?? null;

  const metrics = result?.metrics ?? aggregates?.metrics ?? null;
  const monthly = result?.monthly?.values ?? aggregates?.monthly?.values ?? [];
  const histogram = result?.histogram ?? aggregates?.histogram ?? null;
  const sensitivity = result?.sensitivity ?? [];
  const convergence = result?.convergence ?? aggregates?.convergence ?? null;
  const currency = result?.currency ?? record.scenario.currency ?? project.currency ?? "XOF";
  const quality = display?.quality ?? result?.quality ?? null;
  const threshold = thresholdOverride ?? metrics?.minCashP50 ?? 0;

  const pinnedRuns = useMemo(
    () => pinned.map((runId) => runs[runId]).filter((run): run is RunState => Boolean(run?.result)),
    [pinned, runs],
  );
  const ghosts = useMemo(
    () =>
      pinnedRuns.slice(-3).map((run) => ({
        id: run.runId,
        label: `${run.result?.scenarioName ?? "Run"} · ${
          run.quality === "draft" ? "brouillon" : "final"
        }`,
        seed: run.seed,
        points: fanPointsFromMonthly(run.result?.monthly.values ?? [], "cash"),
      })),
    [pinnedRuns],
  );
  const mixedSeeds = ghosts.some((ghost) => ghost.seed !== session.seed);

  const handleHypothesis = useCallback(
    (key: string, hypothesis: Parameters<typeof hypothesisFromTri>[0], commit: boolean) => {
      if (!commit && !gesture.current) {
        gesture.current = true;
        live.beginGesture();
      }
      const before = store.getState().session.scenario;
      const after = {
        ...before,
        assumptions: { ...(before.assumptions ?? {}), [key]: hypothesis },
      };
      inputs.dispatch(
        snapshotCommand({
          label: `Hypothèse ${key}`,
          before,
          after,
          apply: (scenario) => store.getState().setScenario(scenario),
          coalesceKey: `param:${key}`,
        }),
      );
      if (commit && gesture.current) {
        gesture.current = false;
        live.endGesture();
      }
    },
    [inputs, live, store],
  );

  const handleSeed = useCallback(
    (seed: number) => {
      const before = store.getState().session.seed;
      if (seed === before) return;
      inputs.dispatch({
        label: "Graine",
        undo: () => store.getState().setSeed(before),
        redo: () => store.getState().setSeed(seed),
      });
      live.runFinal();
    },
    [inputs, live, store],
  );

  const handleThreshold = useCallback((value: number, _commit: boolean) => {
    setThresholdOverride(value);
  }, []);

  const pinCurrent = useCallback(() => {
    const current = store.getState();
    const target = current.session.activeRunId
      ? current.runs[current.session.activeRunId]
      : latestResult(current.runs);
    if (!target?.result) return;
    current.pinRun(target.runId, !current.pinned.includes(target.runId));
  }, [store]);

  const selectedRun = display;
  const isPinned = selectedRun ? pinned.includes(selectedRun.runId) : false;
  const horizon = monthly.length > 0 ? monthly[monthly.length - 1].index : 0;

  const benchmarkReferences = useMemo(() => {
    const references: Record<string, BenchmarkReference> = {};
    for (const [key, hypothesis] of Object.entries(session.scenario.assumptions ?? {})) {
      const provenance = hypothesis.provenance;
      if (provenance?.kind !== "benchmark" || !provenance.label) continue;
      const tri = triFromHypothesis(hypothesis);
      references[key] = { label: provenance.label, value: tri.mode };
    }
    return references;
  }, [session.scenario.assumptions]);

  const resetToBenchmark = useCallback(
    (key: string, reference: BenchmarkReference) => {
      const before = store.getState().session.scenario;
      const current = before.assumptions?.[key];
      if (!current) return;
      const tri = triFromHypothesis(current);
      const next = hypothesisFromTri(current, { ...tri, mode: reference.value });
      const after = { ...before, assumptions: { ...before.assumptions, [key]: next } };
      inputs.dispatch(
        snapshotCommand({
          label: `Retour benchmark ${key}`,
          before,
          after,
          apply: (scenario) => store.getState().setScenario(scenario),
          coalesceKey: `param:${key}`,
        }),
      );
      live.runFinal();
    },
    [inputs, live, store],
  );

  const toggleLock = (key: string): void => {
    setLocks((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const running = session.activeRunId !== null;
  const progress =
    aggregates && aggregates.totalRuns > 0
      ? aggregates.completedRuns / aggregates.totalRuns
      : null;

  const header = (
    <>
      <KpiBar
        currency={currency}
        metrics={metrics}
        monthly={monthly}
        convergence={convergence}
        status={session.status}
        quality={quality}
        seed={session.seed}
        runs={result?.runs ?? aggregates?.totalRuns}
        runsRetained={result?.runsRetained}
        engineVersion={display?.engineVersion || undefined}
        disabled={running}
        onSeedChange={handleSeed}
      />
      {session.error ? (
        <InlineAlert tone="danger" title="Calcul impossible">
          {session.error}
        </InlineAlert>
      ) : null}
      {selectedRun?.stale ? (
        <InlineAlert tone="warn" title="Résultat périmé">
          Les hypothèses ont changé depuis ce calcul. Relancez pour aligner les chiffres.
        </InlineAlert>
      ) : null}
      {running ? (
        <div className="cockpit-progress" role="status" aria-live="polite">
          <ProgressBar
            value={progress ?? undefined}
            label={session.quality === "draft" ? "Aperçu en cours" : "Calcul final en cours"}
          />
        </div>
      ) : null}
    </>
  );

  const footer = (
    <div className="cockpit-footer">
      <div className="cockpit-timeline" role="group" aria-label="Sélection du mois">
        {monthly.map((entry) => (
          <button
            key={entry.index}
            type="button"
            className="cockpit-timeline__month"
            aria-pressed={selection.month === entry.index}
            onClick={() => store.getState().setSelection({ month: entry.index })}
            title={`Mois ${entry.index}`}
          >
            {entry.index}
          </button>
        ))}
      </div>

      <div className="cockpit-footer__actions">
        <Button
          variant="secondary"
          size="small"
          onClick={pinCurrent}
          disabled={!result || running}
        >
          {isPinned ? "Désépingler le run" : "Épingler le run"}
        </Button>
        <Button variant="ghost" size="small" onClick={() => live.runFinal()} disabled={running}>
          Relancer
        </Button>
        <Button variant="ghost" size="small" onClick={onBack}>
          Retour aux résultats
        </Button>
      </div>
    </div>
  );

  return (
    <div className="cockpit-screen">
      <div className="cockpit-screen__bar">
        <div>
          <strong>{record.name}</strong>
          <span className="ui-muted">
            {horizon > 0 ? ` · ${horizon} mois` : ""} · graine {session.seed}
          </span>
        </div>
        <div className="cockpit-screen__bar-actions">
          {mixedSeeds ? (
            <Badge tone="warn">Graines différentes : comparaison signalée</Badge>
          ) : null}
          <Badge tone="neutral">{formatNumber(monthly.length)} points</Badge>
          <Button variant="ghost" size="small" onClick={onOpenHypotheses}>
            Hypothèses
          </Button>
        </div>
      </div>

      <GhostLegend
        ghosts={pinnedRuns.slice(-3).map((run) => ({
          runId: run.runId,
          label: `${run.result?.scenarioName ?? "Run"} · ${
            run.quality === "draft" ? "brouillon" : "final"
          }`,
          seed: run.seed,
          stale: run.stale,
        }))}
        onUnpin={(runId) => store.getState().pinRun(runId, false)}
      />

      <PanelGrid
        layout={layout}
        onLayoutChange={applyLayout}
        header={header}
        footer={footer}
        left={
          <HypothesesPanel
            scenario={session.scenario}
            locks={locks}
            benchmarks={benchmarkReferences}
            disabled={running}
            onToggleLock={toggleLock}
            onChange={(key, hypothesis, commit) => handleHypothesis(key, hypothesis, commit)}
            onResetToBenchmark={resetToBenchmark}
          />
        }
        main={
          <FanChartPanel
            monthly={monthly}
            currency={currency}
            cdf={metrics?.minCashCdf}
            mode={mode}
            ghosts={ghosts}
            threshold={threshold}
            selectedMonth={selection.month}
            onModeChange={setMode}
            onThresholdChange={handleThreshold}
            onSelectMonth={(month) => store.getState().setSelection({ month })}
          />
        }
        right={
          <div className="cockpit-secondary">
            <Card>
              <CardHeader
                title="Distribution du profit"
                description={result ? `${formatNumber(result.runs)} runs` : "En cours de calcul"}
              />
              {histogram && metrics ? (
                <ProfitHistogram
                  histogram={histogram}
                  currency={currency}
                  p10={metrics.p10}
                  p50={metrics.p50}
                  p90={metrics.p90}
                />
              ) : (
                <p className="ui-muted">Distribution disponible après un calcul.</p>
              )}
            </Card>
            <Card>
              <CardHeader title="Sensibilité" description="Contribution à la variance du profit" />
              {sensitivity.length > 0 ? (
                <SensitivityTornado entries={sensitivity} currency={currency} />
              ) : (
                <p className="ui-muted">Analyse disponible après un calcul final.</p>
              )}
            </Card>
            {!result && !aggregates ? (
              <EmptyState
                title="Aucun résultat"
                description="Lancez un calcul pour afficher l'éventail et les indicateurs."
                action={
                  <Button variant="secondary" onClick={() => live.runFinal()}>
                    Lancer le calcul
                  </Button>
                }
              />
            ) : null}
            <p className="ui-muted">
              Seuil affiché : {formatCurrency(threshold, currency)} · devise {currency}
            </p>
          </div>
        }
      />
    </div>
  );
}
