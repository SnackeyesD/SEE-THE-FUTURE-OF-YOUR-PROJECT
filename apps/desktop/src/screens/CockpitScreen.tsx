import type {
  GoalSeekResult,
  Project,
  ProjectDataResult,
  Scenario,
  ScenarioEvent,
} from "@see/protocol";
import { EVENT_CATALOG, EVENT_CATALOG_BY_TYPE } from "@see/protocol";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  InlineAlert,
  ProgressBar,
  Tabs,
} from "@see/ui";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { CommandPalette, type PaletteAction } from "../components/CommandPalette";
import { ShortcutsHelp } from "../components/ShortcutsHelp";
import { ProfitHistogram } from "../components/Charts";
import { EventCatalog } from "../components/cockpit/EventCatalog";
import { EventEditor } from "../components/cockpit/EventEditor";
import { EventTimeline } from "../components/cockpit/EventTimeline";
import { clampWindow, type EventWindow } from "../components/cockpit/events";
import { FanChartPanel, fanPointsFromMonthly, type FanMode } from "../components/cockpit/FanChartPanel";
import { GhostLegend } from "../components/cockpit/GhostLegend";
import {
  GoalSeekPanel,
  type ApplyState,
  type GoalSeekFormValues,
} from "../components/cockpit/GoalSeekPanel";
import {
  HypothesesPanel,
  hypothesisFromTri,
  triFromHypothesis,
  type BenchmarkReference,
} from "../components/cockpit/HypothesesPanel";
import { KpiBar } from "../components/cockpit/KpiBar";
import { MonthInspector } from "../components/cockpit/MonthInspector";
import {
  SurfacePanel,
  type SurfaceFormValues,
} from "../components/cockpit/SurfacePanel";
import { TimeScrubber } from "../components/cockpit/TimeScrubber";
import { Tornado } from "../components/cockpit/Tornado";
import { PanelGrid } from "../components/layout/PanelGrid";
import { useAnalysis } from "../hooks/useAnalysis";
import { useCockpitHotkeys } from "../hooks/useCockpitHotkeys";
import { useLiveSimulation } from "../hooks/useLiveSimulation";
import { usePlayback } from "../hooks/usePlayback";
import { formatCurrency, formatNumber } from "../lib/format";
import { branchProjectScenario } from "../lib/ipc";
import { CockpitProvider, useCockpitContext } from "../store/CockpitProvider";
import { useCockpit, type RunState } from "../store/cockpitStore";
import { snapshotCommand } from "../store/commands";
import { loadLayout, layoutFromPreset, PRESET_LABELS, PRESET_NAMES } from "../store/layout";

export interface CockpitScreenProps {
  project: Project;
  scenario: ScenarioRecordLike | null;
  run: ProjectDataResult["run"];
  onBack: () => void;
  onOpenHypotheses: () => void;
  /** Enregistre le scénario complet (hypothèses, événements, saisonnalité). */
  onSaveScenario: (name: string, scenario: Scenario) => Promise<boolean>;
  /** Signale les modifications non enregistrées au shell (garde de navigation). */
  onDirtyChange?: (dirty: boolean) => void;
}

type ScenarioRecordLike = NonNullable<ProjectDataResult["scenario"]>;

function latestResult(runs: Record<string, RunState>): RunState | null {
  const ids = Object.keys(runs);
  for (let index = ids.length - 1; index >= 0; index -= 1) {
    const run = runs[ids[index]];
    if (run?.result) return run;
  }
  return null;
}

let eventCounter = 0;

function newEventId(): string {
  eventCounter += 1;
  return `evt-${Date.now().toString(36)}-${eventCounter.toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 6)}`;
}

function cloneMagnitude<T>(value: T): T {
  if (typeof structuredClone === "function") return structuredClone(value);
  return JSON.parse(JSON.stringify(value)) as T;
}

function humanize(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error);
  return text.replace(/^Error:\s*/i, "");
}

function clampMonth(month: number, horizon: number): number {
  return Math.min(Math.max(Math.round(month), 1), Math.max(1, horizon));
}

/**
 * Cockpit 2D : composition KPI / hypothèses / éventail / secondaire / frise.
 *
 * Toutes les valeurs viennent du store, alimenté par les agrégats du moteur
 * (partiels et finaux). Aucun chiffre n'est recalculé dans React ; le seuil
 * n'interroge que la CDF fournie, et l'histogramme du mois vient du résultat.
 */
export function CockpitScreen({
  project,
  scenario,
  run,
  onBack,
  onOpenHypotheses,
  onSaveScenario,
  onDirtyChange,
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
      // Clé stable : un enregistrement crée un nouveau `ScenarioRecord`, mais
      // ne doit pas remonter le provider (l'historique des runs serait perdu).
      key={project.id}
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
        onSaveScenario={onSaveScenario}
        onDirtyChange={onDirtyChange}
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
  onSaveScenario,
  onDirtyChange,
}: {
  project: Project;
  record: ScenarioRecordLike;
  initialRun: ProjectDataResult["run"];
  onBack: () => void;
  onOpenHypotheses: () => void;
  onSaveScenario: (name: string, scenario: Scenario) => Promise<boolean>;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const { store, inputs, applyLayout } = useCockpitContext();
  const session = useCockpit(store, (state) => state.session);
  const runs = useCockpit(store, (state) => state.runs);
  const pinned = useCockpit(store, (state) => state.pinned);
  const layout = useCockpit(store, (state) => state.layout);
  const selection = useCockpit(store, (state) => state.selection);

  const live = useLiveSimulation({ store });
  const analysis = useAnalysis();
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [analysisTab, setAnalysisTab] = useState<"surface" | "objective">("surface");
  const [applyState, setApplyState] = useState<ApplyState>({
    status: "idle",
    message: null,
  });
  const [mode, setMode] = useState<FanMode>("cash");
  const [thresholdOverride, setThresholdOverride] = useState<number | null>(null);
  const [locks, setLocks] = useState<ReadonlySet<string>>(() => new Set<string>());
  const [focusedHypothesis, setFocusedHypothesis] = useState<string | null>(null);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [monthNotice, setMonthNotice] = useState("");
  const [dirty, setDirty] = useState(false);
  const gesture = useRef(false);
  const suppressInvalidate = useRef(false);
  const savedScenario = useRef<string>(JSON.stringify(record.scenario));

  useEffect(() => {
    const result = initialRun?.result;
    if (!result) return;
    if (!store.getState().runs[result.runId]) {
      store.getState().hydrateRun(result, initialRun?.createdAt ?? null);
    }
  }, [initialRun, store]);

  useEffect(
    () =>
      inputs.subscribe(() => {
        // Un drop d'événement déclenche nous-mêmes un unique `runFinal` :
        // l'invalidation automatique est neutralisée pour cette commande.
        if (suppressInvalidate.current) return;
        live.invalidate();
      }),
    [inputs, live.invalidate],
  );

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
  const horizon = monthly.length > 0 ? monthly[monthly.length - 1].index : 0;

  // Le mois survit aux nouveaux résultats tant que l'horizon le permet.
  useEffect(() => {
    if (horizon <= 0) return;
    const current = store.getState().selection.month;
    if (current === null) {
      store.getState().setSelection({ month: clampMonth(12, horizon) });
      return;
    }
    if (current < 1 || current > horizon) {
      const next = clampMonth(current, horizon);
      store.getState().setSelection({ month: next });
      setMonthNotice(
        `L'horizon est passé à ${horizon} mois : le mois ${current} a été ramené au mois ${next}.`,
      );
    }
  }, [horizon, store]);

  useEffect(() => {
    const next = JSON.stringify(session.scenario) !== savedScenario.current;
    setDirty(next);
  }, [session.scenario]);

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  const selectedMonth = selection.month ?? (horizon > 0 ? clampMonth(12, horizon) : null);
  const inspectorEntry = useMemo(
    () => monthly.find((entry) => entry.index === selectedMonth) ?? null,
    [monthly, selectedMonth],
  );

  const changeMonth = useCallback(
    (month: number) => {
      if (horizon <= 0) return;
      store.getState().setSelection({ month: clampMonth(month, horizon) });
      setMonthNotice("");
    },
    [horizon, store],
  );

  const playback = usePlayback({
    horizon,
    month: selectedMonth,
    onMonthChange: changeMonth,
    disabled: session.activeRunId !== null,
  });

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

  /** Commande de scénario + un seul calcul final (partiels neutralisés). */
  const mutateScenario = useCallback(
    (
      label: string,
      change: (scenario: Scenario) => Scenario,
      coalesceKey?: string,
      runFinal = true,
    ): boolean => {
      const before = store.getState().session.scenario;
      const after = change(before);
      if (after === before) return false;
      suppressInvalidate.current = true;
      try {
        inputs.dispatch(
          snapshotCommand({
            label,
            before,
            after,
            apply: (scenario) => store.getState().setScenario(scenario),
            coalesceKey,
          }),
        );
      } finally {
        suppressInvalidate.current = false;
      }
      if (runFinal) void live.runFinal();
      return true;
    },
    [inputs, live, store],
  );

  const changeEventWindow = useCallback(
    (id: string, window: EventWindow) => {
      const target = store
        .getState()
        .session.scenario.events?.find((event) => event.id === id);
      const safe = clampWindow(window, Math.max(1, horizon));
      mutateScenario(
        `Événement ${EVENT_CATALOG_BY_TYPE[target?.type ?? "supply_disruption"]?.label ?? ""} : fenêtre`,
        (scenario) => ({
          ...scenario,
          events: (scenario.events ?? []).map((event) =>
            event.id === id ? { ...event, ...safe } : event,
          ),
        }),
        `event:${id}:window`,
      );
    },
    [horizon, mutateScenario, store],
  );

  const addEvent = useCallback(
    (type: ScenarioEvent["type"]) => {
      const entry = EVENT_CATALOG_BY_TYPE[type];
      const start = selectedMonth ?? 1;
      const duration = Math.min(3, Math.max(1, horizon - start + 1));
      const event: ScenarioEvent = {
        id: newEventId(),
        type,
        startMonth: start,
        durationMonths: duration,
        target: entry.target,
        mode: entry.mode,
        probability: 1,
        magnitude: cloneMagnitude(entry.defaultMagnitude),
        enabled: true,
      };
      mutateScenario(`Ajouter ${entry.label}`, (scenario) => ({
        ...scenario,
        schemaVersion: "1.1.0",
        events: [...(scenario.events ?? []), event],
      }));
      setCatalogOpen(false);
    },
    [horizon, mutateScenario, selectedMonth],
  );

  const toggleEvent = useCallback(
    (id: string) => {
      mutateScenario(
        "Activer/désactiver l'événement",
        (scenario) => ({
          ...scenario,
          events: (scenario.events ?? []).map((event) =>
            event.id === id ? { ...event, enabled: event.enabled === false } : event,
          ),
        }),
        `event:${id}:enabled`,
      );
    },
    [mutateScenario],
  );

  const duplicateEvent = useCallback(
    (id: string) => {
      const source = store.getState().session.scenario.events?.find((event) => event.id === id);
      if (!source) return;
      const copy: ScenarioEvent = {
        ...cloneMagnitude(source),
        id: newEventId(),
        startMonth: clampMonth(
          source.startMonth + source.durationMonths,
          Math.max(1, horizon - source.durationMonths + 1),
        ),
      };
      mutateScenario(`Dupliquer ${EVENT_CATALOG_BY_TYPE[source.type]?.label ?? "l'événement"}`, (scenario) => ({
        ...scenario,
        events: [...(scenario.events ?? []), copy],
      }));
    },
    [horizon, mutateScenario, store],
  );

  const deleteEvent = useCallback(
    (id: string) => {
      mutateScenario("Supprimer l'événement", (scenario) => ({
        ...scenario,
        events: (scenario.events ?? []).filter((event) => event.id !== id),
      }));
      setEditingId(null);
      setSelectedEventId(null);
    },
    [mutateScenario],
  );

  const applyEditor = useCallback(
    async (id: string, patch: Partial<ScenarioEvent>): Promise<boolean> => {
      const changed = mutateScenario(
        "Éditer l'événement",
        (scenario) => ({
          ...scenario,
          events: (scenario.events ?? []).map((event) =>
            event.id === id ? { ...event, ...patch } : event,
          ),
        }),
        `event:${id}:edit`,
        false,
      );
      if (!changed) {
        setEditingId(null);
        setSelectedEventId(null);
        return true;
      }
      // L'éditeur reste ouvert tant que le sidecar n'a pas accepté le run :
      // un refus doit rester corrigeable dans le formulaire.
      const accepted = await live.runFinal();
      if (accepted) {
        setEditingId(null);
        setSelectedEventId(null);
      }
      return accepted;
    },
    [live, mutateScenario],
  );

  const pinCurrent = useCallback(() => {
    const current = store.getState();
    const target = current.session.activeRunId
      ? current.runs[current.session.activeRunId]
      : latestResult(current.runs);
    if (!target?.result) return;
    current.pinRun(target.runId, !current.pinned.includes(target.runId));
  }, [store]);

  const handleSave = useCallback(async () => {
    if (saving) return;
    const snapshot = store.getState().session.scenario;
    const serialized = JSON.stringify(snapshot);
    setSaving(true);
    setSaveMessage("");
    try {
      const ok = await onSaveScenario(record.name, snapshot);
      if (ok) {
        savedScenario.current = serialized;
        // Une modification peut être survenue pendant l'IPC : on compare le
        // scénario courant à l'instantané réellement sauvegardé.
        const current = store.getState().session.scenario;
        const pending = JSON.stringify(current) !== serialized;
        setDirty(pending);
        setSaveMessage(
          pending
            ? "Scénario enregistré ; de nouvelles modifications restent à enregistrer."
            : "Scénario enregistré.",
        );
      }
    } finally {
      setSaving(false);
    }
  }, [onSaveScenario, record.name, saving, store]);

  const toggleFullscreen = useCallback(() => {
    const current = store.getState().layout;
    applyLayout({ ...current, fullscreen: current.fullscreen ? null : "main" });
  }, [applyLayout, store]);

  useCockpitHotkeys({
    onTogglePlayback: playback.toggle,
    onMonthStep: (delta) => changeMonth((selectedMonth ?? 1) + delta),
    onMonthEdge: (edge) => changeMonth(edge === "first" ? 1 : horizon),
    onToggleFullscreen: toggleFullscreen,
    onOpenPalette: () => setPaletteOpen(true),
    onOpenHelp: () => setHelpOpen(true),
    onSave: () => {
      void handleSave();
    },
    onEscape: () => {
      if (store.getState().layout.fullscreen) toggleFullscreen();
    },
  });

  const selectedRun = display;
  const isPinned = selectedRun ? pinned.includes(selectedRun.runId) : false;

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

  const handleRunSurface = useCallback(
    (values: SurfaceFormValues) => {
      setAnalysisOpen(true);
      setApplyState({ status: "idle", message: null });
      void analysis.runSurface({
        projectId: project.id,
        scenario: store.getState().session.scenario,
        axisX: values.axisX,
        axisY: values.axisY,
        metric: values.metric,
        grid: values.grid,
        runs: values.runs,
        seed: store.getState().session.seed,
        quality: "draft",
      });
    },
    [analysis, project.id, store],
  );

  const handleRunGoalSeek = useCallback(
    (values: GoalSeekFormValues) => {
      setAnalysisOpen(true);
      setApplyState({ status: "idle", message: null });
      void analysis.runGoalSeek({
        projectId: project.id,
        scenario: store.getState().session.scenario,
        objective: values.objective,
        levers: values.levers,
        locked: [...locks],
        maxEvaluations: values.maxEvaluations,
        runs: values.runs,
        seed: store.getState().session.seed,
        confirmQuality: values.confirmQuality,
      });
    },
    [analysis, locks, project.id, store],
  );

  /** Clic sur une cellule : applique les deux axes comme toute autre entrée. */
  const handleApplySurfacePoint = useCallback(
    (points: Record<string, number>) => {
      mutateScenario("Appliquer un point de surface", (scenario) => {
        const assumptions = { ...(scenario.assumptions ?? {}) };
        for (const [key, value] of Object.entries(points)) {
          assumptions[key] = { value };
        }
        return { ...scenario, assumptions };
      });
    },
    [mutateScenario],
  );

  /**
   * Applique le meilleur point : création d'une branche côté stockage, puis
   * calcul final avec la même graine que la recherche. Le scénario courant
   * reçoit les valeurs du moteur, sans recalcul dans React.
   */
  const handleApplyGoal = useCallback(
    async (best: GoalSeekResult, label: string) => {
      setApplyState({ status: "running", message: "Création de la branche…" });
      const base = store.getState().session.scenario;
      const assumptions = { ...(base.assumptions ?? {}) };
      for (const [key, value] of Object.entries(best.best)) {
        assumptions[key] = { value };
      }
      const scenario: Scenario = { ...base, assumptions };
      try {
        const branch = await branchProjectScenario({
          projectId: project.id,
          scenarioId: record.id,
          label,
          scenario,
        });
        mutateScenario("Appliquer l'objectif", () => branch.scenario.scenario);
        setApplyState({
          status: "done",
          message: `Branche « ${label} » créée. Calcul final lancé avec la graine ${session.seed}.`,
        });
      } catch (error) {
        setApplyState({ status: "error", message: humanize(error) });
      }
    },
    [mutateScenario, project.id, record.id, session.seed, store],
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
  const events = session.scenario.events ?? [];
  const editing = editingId ? events.find((event) => event.id === editingId) ?? null : null;

  const paletteActions = useMemo<PaletteAction[]>(() => {
    const actions: PaletteAction[] = [
      {
        id: "save",
        label: "Enregistrer le scénario",
        hint: dirty ? "modifications en attente" : "à jour",
        run: () => {
          void handleSave();
        },
      },
      { id: "relaunch", label: "Relancer le calcul final", run: () => live.runFinal() },
      { id: "pin", label: isPinned ? "Désépingler le run" : "Épingler le run", run: pinCurrent },
      { id: "help", label: "Afficher les raccourcis", run: () => setHelpOpen(true) },
      {
        id: "fullscreen",
        label: layout.fullscreen ? "Quitter le plein écran" : "Plein écran du panneau principal",
        run: toggleFullscreen,
      },
      {
        id: "month-first",
        label: "Aller au premier mois",
        run: () => changeMonth(1),
      },
      {
        id: "month-middle",
        label: "Aller au milieu de l'horizon",
        run: () => changeMonth(Math.round(horizon / 2)),
      },
      {
        id: "month-last",
        label: "Aller au dernier mois",
        run: () => changeMonth(horizon),
      },
      { id: "hypotheses", label: "Ouvrir les hypothèses", run: onOpenHypotheses },
    ];
    for (const preset of PRESET_NAMES) {
      actions.push({
        id: `layout-${preset}`,
        label: `Disposition ${PRESET_LABELS[preset]}`,
        run: () => applyLayout(layoutFromPreset(preset)),
      });
    }
    for (const entry of EVENT_CATALOG) {
      actions.push({
        id: `event-${entry.type}`,
        label: `Ajouter : ${entry.label}`,
        hint: `mois ${selectedMonth ?? "—"}`,
        run: () => addEvent(entry.type),
      });
    }
    return actions;
  }, [
    addEvent,
    applyLayout,
    changeMonth,
    dirty,
    handleSave,
    horizon,
    isPinned,
    layout.fullscreen,
    live,
    onOpenHypotheses,
    pinCurrent,
    selectedMonth,
    toggleFullscreen,
  ]);

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
        month={selectedMonth}
        onMonthChange={changeMonth}
        onSeedChange={handleSeed}
      />
      <div className="cockpit-save" aria-live="polite">
        {dirty ? (
          <Badge tone="warn">Modifications non enregistrées</Badge>
        ) : (
          <Badge tone="neutral">Scénario à jour</Badge>
        )}
        <Button
          variant={dirty ? "primary" : "secondary"}
          size="small"
          onClick={() => {
            void handleSave();
          }}
          disabled={saving}
        >
          {saving ? "Enregistrement…" : "Enregistrer le scénario"}
        </Button>
        {saveMessage ? <span className="ui-muted">{saveMessage}</span> : null}
      </div>
      {monthNotice ? (
        <p className="cockpit-month-notice" role="status">
          {monthNotice}
        </p>
      ) : null}
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
      <TimeScrubber
        month={selectedMonth}
        horizon={horizon}
        playing={playback.playing}
        disabled={running}
        onMonthChange={changeMonth}
        onTogglePlay={playback.toggle}
      />

      <EventTimeline
        events={events}
        horizon={Math.max(1, horizon)}
        selectedId={selectedEventId}
        disabled={running}
        onSelect={setSelectedEventId}
        onChange={changeEventWindow}
        onToggle={toggleEvent}
        onDuplicate={duplicateEvent}
        onDelete={deleteEvent}
        onEdit={(id) => {
          setSelectedEventId(id);
          setEditingId(id);
        }}
        onOpenCatalog={() => setCatalogOpen(true)}
        onSelectMonth={changeMonth}
      />

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

  const right = (
    <div className="cockpit-secondary">
      <MonthInspector
        month={selectedMonth}
        entry={inspectorEntry}
        currency={currency}
        quality={quality}
        seed={display?.seed ?? session.seed}
        runs={result?.runs ?? aggregates?.totalRuns}
        computedAt={display?.computedAt}
        stale={selectedRun?.stale ?? false}
        onRelaunch={() => live.runFinal()}
      />
      <Card>
        <CardHeader
          title="Distribution du profit"
          description={result ? `${formatNumber(result.runs)} runs · horizon complet` : "En cours de calcul"}
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
          <Tornado
            entries={sensitivity}
            currency={currency}
            selected={focusedHypothesis}
            onSelect={setFocusedHypothesis}
          />
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
  );

  const hypotheses = useMemo(
    () => (
      <HypothesesPanel
        scenario={session.scenario}
        locks={locks}
        benchmarks={benchmarkReferences}
        disabled={running}
        focusKey={focusedHypothesis}
        onToggleLock={toggleLock}
        onChange={(key, hypothesis, commit) => handleHypothesis(key, hypothesis, commit)}
        onResetToBenchmark={resetToBenchmark}
      />
    ),
    [
      benchmarkReferences,
      focusedHypothesis,
      handleHypothesis,
      locks,
      resetToBenchmark,
      running,
      session.scenario,
    ],
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
          <Button variant="ghost" size="small" onClick={() => setPaletteOpen(true)}>
            Commandes (Ctrl+K)
          </Button>
          <Button
            variant={analysisOpen ? "secondary" : "ghost"}
            size="small"
            aria-expanded={analysisOpen}
            onClick={() => setAnalysisOpen((current) => !current)}
          >
            Analyse interactive
          </Button>
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
        left={hypotheses}
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
            onSelectMonth={changeMonth}
          />
        }
        right={right}
      />

      <section className="cockpit-analysis" aria-label="Analyse interactive" hidden={!analysisOpen}>
        <Tabs
          items={[
            { id: "surface", label: "Surface 2D" },
            { id: "objective", label: "Recherche d'objectif" },
          ]}
          value={analysisTab}
          onChange={(id) => setAnalysisTab(id === "objective" ? "objective" : "surface")}
          ariaLabel="Type d'analyse interactive"
        />
        <div hidden={analysisTab !== "surface"}>
          <SurfacePanel
            scenario={session.scenario}
            currency={currency}
            state={analysis.surface}
            seed={session.seed}
            disabled={running}
            onRun={handleRunSurface}
            onCancel={analysis.cancelSurface}
            onApplyPoint={handleApplySurfacePoint}
          />
        </div>
        <div hidden={analysisTab !== "objective"}>
          <GoalSeekPanel
            scenario={session.scenario}
            currency={currency}
            state={analysis.goal}
            seed={session.seed}
            disabled={running}
            locked={locks}
            applyState={applyState}
            onRun={handleRunGoalSeek}
            onCancel={analysis.cancelGoalSeek}
            onApply={(goalResult, label) => void handleApplyGoal(goalResult, label)}
          />
        </div>
      </section>

      {catalogOpen ? (
        <EventCatalog
          month={selectedMonth ?? 1}
          horizon={Math.max(1, horizon)}
          onPick={addEvent}
          onClose={() => setCatalogOpen(false)}
        />
      ) : null}

      {editing ? (
        <EventEditor
          event={editing}
          horizon={Math.max(1, horizon)}
          error={session.status === "error" ? session.error : ""}
          onApply={(patch) => applyEditor(editing.id, patch)}
          onClose={() => setEditingId(null)}
        />
      ) : null}

      {paletteOpen ? (
        <CommandPalette actions={paletteActions} onClose={() => setPaletteOpen(false)} />
      ) : null}

      {helpOpen ? <ShortcutsHelp onClose={() => setHelpOpen(false)} /> : null}
    </div>
  );
}
