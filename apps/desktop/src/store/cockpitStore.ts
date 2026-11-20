import type {
  Hypothesis,
  PartialAggregates,
  Scenario,
  ScenarioEvent,
  SimulationConfig,
  SimulationError,
  SimulationQuality,
  SimulationResult,
} from "@see/protocol";
import { useStore } from "zustand";
import { createStore, type StoreApi } from "zustand/vanilla";

import { DEFAULT_LAYOUT, cloneLayout, type LayoutState } from "./layout";

export type RunStatus = "running" | "done" | "cancelled" | "error";
export type SessionStatus = "idle" | "drafting" | "finalizing" | "error";

export interface RunState {
  runId: string;
  quality: SimulationQuality;
  status: RunStatus;
  aggregates: PartialAggregates | null;
  result: SimulationResult | null;
  seq: number;
  seed: number;
  engineVersion: string;
  /** Horodatage du résultat (run persisté ou fin de calcul local). */
  computedAt: string | null;
  stale: boolean;
  error?: { code: SimulationError["code"]; message: string };
}

export interface SelectionState {
  month: number | null;
  runIndex: number | null;
  focusedParam: string | null;
}

export interface SessionState {
  projectId: string;
  scenario: Scenario;
  seed: number;
  config: SimulationConfig;
  quality: SimulationQuality;
  status: SessionStatus;
  activeRunId: string | null;
  lastSeq: number;
  error: string;
}

export interface StartRunInput {
  runId: string;
  quality: SimulationQuality;
  seed: number;
}

export interface ApplyPartialInput {
  runId: string;
  seq: number;
  aggregates: PartialAggregates;
}

export interface ApplyFinalInput {
  runId: string;
  seq: number;
  result: SimulationResult;
}

export interface CockpitState {
  session: SessionState;
  runs: Record<string, RunState>;
  pinned: string[];
  selection: SelectionState;
  layout: LayoutState;
  setScenario: (scenario: Scenario) => void;
  setParam: (key: string, hypothesis: Hypothesis) => void;
  setSeed: (seed: number) => void;
  setConfig: (config: SimulationConfig) => void;
  addEvent: (event: ScenarioEvent) => void;
  updateEvent: (eventId: string, patch: Partial<ScenarioEvent>) => void;
  removeEvent: (eventId: string) => void;
  /** Injecte un résultat déjà calculé (ouverture d'un run persisté). */
  hydrateRun: (result: SimulationResult, computedAt?: string | null) => void;
  startRun: (input: StartRunInput) => void;
  applyPartial: (input: ApplyPartialInput) => void;
  applyFinal: (input: ApplyFinalInput) => void;
  cancelRun: (runId: string) => void;
  failRun: (
    runId: string,
    error: { code: SimulationError["code"]; message: string },
  ) => void;
  failSession: (message: string) => void;
  pinRun: (runId: string, pinned?: boolean) => void;
  markStale: () => void;
  setSelection: (patch: Partial<SelectionState>) => void;
  setLayout: (layout: LayoutState) => void;
  reset: () => void;
}

export interface CockpitStoreOptions {
  projectId: string;
  scenario: Scenario;
  seed?: number;
  config?: SimulationConfig;
  layout?: LayoutState;
}

export type CockpitStore = StoreApi<CockpitState>;

/**
 * La taille du calcul est pilotée par la qualité (`draft` 500, `final` 5 000).
 * Ne pas renseigner `runs` ici : un champ explicite écraserait le profil.
 */
const DEFAULT_CONFIG: SimulationConfig = { histogramBins: 40 };
const DEFAULT_SEED = 42;

function cloneValue<T>(value: T): T {
  if (typeof structuredClone === "function") return structuredClone(value);
  return JSON.parse(JSON.stringify(value)) as T;
}

function cloneScenario(scenario: Scenario): Scenario {
  return cloneValue(scenario);
}

function initialSession(options: CockpitStoreOptions): SessionState {
  return {
    projectId: options.projectId,
    scenario: cloneScenario(options.scenario),
    seed: options.seed ?? DEFAULT_SEED,
    config: { ...DEFAULT_CONFIG, ...options.config },
    quality: "final",
    status: "idle",
    activeRunId: null,
    lastSeq: 0,
    error: "",
  };
}

function staleRuns(
  runs: Record<string, RunState>,
  pinned: string[],
): Record<string, RunState> {
  let changed = false;
  const next: Record<string, RunState> = {};
  for (const [runId, run] of Object.entries(runs)) {
    if (run.status === "done" && !run.stale && !pinned.includes(runId)) {
      next[runId] = { ...run, stale: true };
      changed = true;
    } else {
      next[runId] = run;
    }
  }
  return changed ? next : runs;
}

export function createCockpitStore(options: CockpitStoreOptions): CockpitStore {
  return createStore<CockpitState>()((set) => ({
    session: initialSession(options),
    runs: {},
    pinned: [],
    selection: { month: null, runIndex: null, focusedParam: null },
    layout: cloneLayout(options.layout ?? DEFAULT_LAYOUT),

    setScenario: (scenario) =>
      set((state) => ({
        session: { ...state.session, scenario: cloneScenario(scenario) },
        runs: staleRuns(state.runs, state.pinned),
      })),

    setParam: (key, hypothesis) =>
      set((state) => ({
        session: {
          ...state.session,
          scenario: {
            ...state.session.scenario,
            assumptions: {
              ...(state.session.scenario.assumptions ?? {}),
              [key]: cloneValue(hypothesis),
            },
          },
        },
        runs: staleRuns(state.runs, state.pinned),
      })),

    setSeed: (seed) =>
      set((state) => ({
        session: { ...state.session, seed },
        runs: staleRuns(state.runs, state.pinned),
      })),

    setConfig: (config) =>
      set((state) => ({ session: { ...state.session, config: { ...config } } })),

    addEvent: (event) =>
      set((state) => ({
        session: {
          ...state.session,
          scenario: {
            ...state.session.scenario,
            events: [...(state.session.scenario.events ?? []), cloneValue(event)],
          },
        },
        runs: staleRuns(state.runs, state.pinned),
      })),

    updateEvent: (eventId, patch) =>
      set((state) => ({
        session: {
          ...state.session,
          scenario: {
            ...state.session.scenario,
            events: (state.session.scenario.events ?? []).map((event) =>
              event.id === eventId ? { ...event, ...cloneValue(patch) } : event,
            ),
          },
        },
        runs: staleRuns(state.runs, state.pinned),
      })),

    removeEvent: (eventId) =>
      set((state) => ({
        session: {
          ...state.session,
          scenario: {
            ...state.session.scenario,
            events: (state.session.scenario.events ?? []).filter(
              (event) => event.id !== eventId,
            ),
          },
        },
        runs: staleRuns(state.runs, state.pinned),
      })),

    hydrateRun: (result, computedAt = null) =>
      set((state) => ({
        runs: {
          ...state.runs,
          [result.runId]: {
            runId: result.runId,
            quality: result.quality ?? "final",
            status: "done",
            aggregates: null,
            result,
            seq: 0,
            seed: result.seed,
            engineVersion: result.engineVersion,
            computedAt,
            stale: false,
          },
        },
      })),

    startRun: ({ runId, quality, seed }) =>
      set((state) => ({
        session: {
          ...state.session,
          quality,
          seed,
          status: quality === "draft" ? "drafting" : "finalizing",
          activeRunId: runId,
          lastSeq: 0,
          error: "",
        },
        runs: {
          ...state.runs,
          [runId]: {
            runId,
            quality,
            status: "running",
            aggregates: null,
            result: null,
            seq: 0,
            seed,
            engineVersion: "",
            computedAt: null,
            stale: false,
          },
        },
      })),

    applyPartial: ({ runId, seq, aggregates }) =>
      set((state) => {
        if (state.session.activeRunId !== runId) return state;
        if (seq <= state.session.lastSeq) return state;
        const current = state.runs[runId];
        if (!current) return state;
        return {
          session: { ...state.session, lastSeq: seq },
          runs: {
            ...state.runs,
            [runId]: { ...current, status: "running", seq, aggregates },
          },
        };
      }),

    applyFinal: ({ runId, seq, result }) =>
      set((state) => {
        if (state.session.activeRunId !== runId) return state;
        if (seq < state.session.lastSeq) return state;
        const current = state.runs[runId];
        if (!current) return state;
        return {
          session: {
            ...state.session,
            status: "idle",
            activeRunId: null,
            lastSeq: Math.max(state.session.lastSeq, seq),
          },
          runs: {
            ...state.runs,
            [runId]: {
              ...current,
              status: "done",
              seq: Math.max(current.seq, seq),
              result,
              engineVersion: result.engineVersion,
              computedAt: new Date().toISOString(),
              stale: false,
            },
          },
        };
      }),

    cancelRun: (runId) =>
      set((state) => {
        const current = state.runs[runId];
        if (!current) return state;
        return {
          session:
            state.session.activeRunId === runId
              ? { ...state.session, status: "idle", activeRunId: null }
              : state.session,
          runs: {
            ...state.runs,
            [runId]: { ...current, status: "cancelled" },
          },
        };
      }),

    failRun: (runId, error) =>
      set((state) => {
        const current = state.runs[runId];
        const runs = current
          ? { ...state.runs, [runId]: { ...current, status: "error" as const, error } }
          : state.runs;
        return {
          session: {
            ...state.session,
            status: "error",
            error: error.message,
            activeRunId: null,
          },
          runs,
        };
      }),

    failSession: (message) =>
      set((state) => ({
        session: { ...state.session, status: "error", error: message, activeRunId: null },
      })),

    pinRun: (runId, pinned = true) =>
      set((state) => {
        const run = state.runs[runId];
        if (!run) return state;
        const already = state.pinned.includes(runId);
        if (pinned && (already || run.status !== "done")) return state;
        if (!pinned && !already) return state;
        return {
          pinned: pinned
            ? [...state.pinned, runId]
            : state.pinned.filter((item) => item !== runId),
        };
      }),

    markStale: () =>
      set((state) => ({ runs: staleRuns(state.runs, state.pinned) })),

    setSelection: (patch) =>
      set((state) => ({ selection: { ...state.selection, ...patch } })),

    setLayout: (layout) => set({ layout: cloneLayout(layout) }),

    reset: () =>
      set(() => ({
        session: initialSession(options),
        runs: {},
        pinned: [],
        selection: { month: null, runIndex: null, focusedParam: null },
        layout: cloneLayout(options.layout ?? DEFAULT_LAYOUT),
      })),
  }));
}

export function selectActiveRun(state: CockpitState): RunState | null {
  if (!state.session.activeRunId) return null;
  return state.runs[state.session.activeRunId] ?? null;
}

/**
 * Run affiché par le cockpit : le run actif, sinon le dernier run terminé
 * (ordre d'insertion). Aucune donnée n'est recalculée ici.
 */
export function selectLatestRun(state: CockpitState): RunState | null {
  const active = selectActiveRun(state);
  if (active) return active;
  const ids = Object.keys(state.runs);
  for (let index = ids.length - 1; index >= 0; index -= 1) {
    const run = state.runs[ids[index]];
    if (run?.result) return run;
  }
  return null;
}

export function selectPinnedRuns(state: CockpitState): RunState[] {
  return state.pinned
    .map((runId) => state.runs[runId])
    .filter((run): run is RunState => run !== undefined);
}

export function selectRun(runId: string) {
  return (state: CockpitState): RunState | null => state.runs[runId] ?? null;
}

export function useCockpit<T>(store: CockpitStore, selector: (state: CockpitState) => T): T {
  return useStore(store, selector);
}
