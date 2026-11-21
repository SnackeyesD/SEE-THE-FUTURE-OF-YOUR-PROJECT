import type {
  GoalLever,
  GoalObjective,
  GoalSeekResult,
  Scenario,
  SimulationQuality,
  SurfaceAxis,
  SurfaceMetric,
  SurfaceResult,
} from "@see/protocol";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  cancelAnalysis,
  onAnalysisEvent,
  startGoalSeek,
  startSurface,
  type AnalysisEvent,
} from "../lib/ipc";

export type AnalysisStatus =
  | "idle"
  | "running"
  | "cancelling"
  | "done"
  | "cancelled"
  | "error";

export interface SurfaceRequest {
  projectId: string;
  scenario: Scenario;
  axisX: SurfaceAxis;
  axisY: SurfaceAxis;
  metric?: SurfaceMetric;
  grid?: [number, number];
  runs?: number;
  seed?: number;
  quality?: SimulationQuality;
}

export interface GoalSeekRequest {
  projectId: string;
  scenario: Scenario;
  objective: GoalObjective;
  levers: GoalLever[];
  locked?: string[];
  maxEvaluations?: number;
  runs?: number;
  seed?: number;
  confirmQuality?: SimulationQuality | null;
  confirmRuns?: number;
}

export interface SurfaceState {
  jobId: string | null;
  status: AnalysisStatus;
  fraction: number;
  completedPoints: number;
  totalPoints: number;
  /** Lignes z[ligneY][colonneX] déjà reçues ; `null` tant que non calculé. */
  rows: Array<Array<number | null>>;
  result: SurfaceResult | null;
  error: string | null;
  replacedJobId: string | null;
}

export interface GoalSeekState {
  jobId: string | null;
  status: AnalysisStatus;
  fraction: number;
  completed: number;
  total: number;
  result: GoalSeekResult | null;
  error: string | null;
  replacedJobId: string | null;
}

export interface AnalysisDeps {
  startSurface: typeof startSurface;
  startGoalSeek: typeof startGoalSeek;
  cancel: typeof cancelAnalysis;
  subscribe: typeof onAnalysisEvent;
}

export interface UseAnalysisOptions {
  deps?: Partial<AnalysisDeps>;
}

export interface AnalysisController {
  surface: SurfaceState;
  goal: GoalSeekState;
  runSurface: (request: SurfaceRequest) => Promise<boolean>;
  runGoalSeek: (request: GoalSeekRequest) => Promise<boolean>;
  cancelSurface: () => void;
  cancelGoalSeek: () => void;
}

function emptyMatrix(rows: number, columns: number): Array<Array<number | null>> {
  return Array.from({ length: Math.max(0, rows) }, () =>
    Array.from({ length: Math.max(0, columns) }, () => null),
  );
}

export function initialSurfaceState(): SurfaceState {
  return {
    jobId: null,
    status: "idle",
    fraction: 0,
    completedPoints: 0,
    totalPoints: 0,
    rows: [],
    result: null,
    error: null,
    replacedJobId: null,
  };
}

export function initialGoalSeekState(): GoalSeekState {
  return {
    jobId: null,
    status: "idle",
    fraction: 0,
    completed: 0,
    total: 0,
    result: null,
    error: null,
    replacedJobId: null,
  };
}

function humanize(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error);
  return text.replace(/^Error:\s*/i, "");
}

function cancellationMessage(reason: "analysis_cancelled" | "analysis_superseded" | "shutdown"): string {
  if (reason === "analysis_superseded") return "Remplacée par une nouvelle analyse.";
  if (reason === "shutdown") return "Le moteur s'est arrêté.";
  return "Analyse annulée.";
}

/**
 * Pilote les jobs d'analyse du sidecar (surface, recherche d'objectif).
 *
 * Aucun chiffre n'est calculé ici : le hook ne fait que router les
 * notifications moteur, conserver les lignes partielles et exposer l'état.
 * Les événements arrivés avant l'abonnement sont rejoués par `ipc.ts`.
 */
export function useAnalysis(options: UseAnalysisOptions = {}): AnalysisController {
  const depsRef = useRef<AnalysisDeps>({
    startSurface,
    startGoalSeek,
    cancel: cancelAnalysis,
    subscribe: onAnalysisEvent,
  });
  depsRef.current = {
    startSurface: options.deps?.startSurface ?? startSurface,
    startGoalSeek: options.deps?.startGoalSeek ?? startGoalSeek,
    cancel: options.deps?.cancel ?? cancelAnalysis,
    subscribe: options.deps?.subscribe ?? onAnalysisEvent,
  };

  const [surface, setSurface] = useState<SurfaceState>(initialSurfaceState);
  const [goal, setGoal] = useState<GoalSeekState>(initialGoalSeekState);

  const surfaceJob = useRef<string | null>(null);
  const goalJob = useRef<string | null>(null);
  const surfaceStop = useRef<(() => void) | null>(null);
  const goalStop = useRef<(() => void) | null>(null);

  const stopSurface = useCallback(() => {
    surfaceStop.current?.();
    surfaceStop.current = null;
  }, []);

  const stopGoal = useCallback(() => {
    goalStop.current?.();
    goalStop.current = null;
  }, []);

  const handleSurfaceEvent = useCallback(
    (jobId: string, grid: [number, number]) => (event: AnalysisEvent) => {
      if (surfaceJob.current !== jobId) return;
      switch (event.method) {
        case "simulation.progress":
          setSurface((state) => ({
            ...state,
            fraction: event.params.fraction,
            completedPoints: event.params.completed,
            totalPoints: event.params.total,
          }));
          break;
        case "simulation.surface.partial":
          setSurface((state) => {
            const rows = state.rows.length > 0 ? state.rows : emptyMatrix(grid[1], grid[0]);
            const next = rows.map((row) => [...row]);
            const values = event.params.values;
            if (event.params.rowIndex < next.length) {
              next[event.params.rowIndex] = values.slice(0, grid[0]);
            }
            return {
              ...state,
              rows: next,
              completedPoints: event.params.completedPoints,
              totalPoints: event.params.totalPoints,
            };
          });
          break;
        case "simulation.done":
          setSurface((state) => ({
            ...state,
            status: "done",
            fraction: 1,
            result: event.params.result as SurfaceResult,
            rows: (event.params.result as SurfaceResult).zP50,
            completedPoints: (event.params.result as SurfaceResult).grid[0] *
              (event.params.result as SurfaceResult).grid[1],
            totalPoints: (event.params.result as SurfaceResult).grid[0] *
              (event.params.result as SurfaceResult).grid[1],
          }));
          break;
        case "simulation.cancelled":
          setSurface((state) => ({
            ...state,
            status: "cancelled",
            error: cancellationMessage(event.params.reason),
          }));
          break;
        case "simulation.error":
          setSurface((state) => ({
            ...state,
            status: "error",
            error: event.params.message,
          }));
          break;
        default:
          break;
      }
    },
    [],
  );

  const handleGoalEvent = useCallback(
    (jobId: string) => (event: AnalysisEvent) => {
      if (goalJob.current !== jobId) return;
      switch (event.method) {
        case "simulation.progress":
          setGoal((state) => ({
            ...state,
            fraction: event.params.fraction,
            completed: event.params.completed,
            total: event.params.total,
          }));
          break;
        case "simulation.done":
          setGoal((state) => ({
            ...state,
            status: "done",
            fraction: 1,
            result: event.params.result as GoalSeekResult,
          }));
          break;
        case "simulation.cancelled":
          setGoal((state) => ({
            ...state,
            status: "cancelled",
            error: cancellationMessage(event.params.reason),
          }));
          break;
        case "simulation.error":
          setGoal((state) => ({
            ...state,
            status: "error",
            error: event.params.message,
          }));
          break;
        default:
          break;
      }
    },
    [],
  );

  const runSurface = useCallback(
    async (request: SurfaceRequest): Promise<boolean> => {
      const previous = surfaceJob.current;
      if (previous) {
        surfaceJob.current = null;
        stopSurface();
        void depsRef.current.cancel(previous).catch(() => undefined);
      }
      const grid = request.grid ?? [15, 15];
      setSurface({
        ...initialSurfaceState(),
        status: "running",
        rows: emptyMatrix(grid[1], grid[0]),
        totalPoints: grid[0] * grid[1],
      });
      let accepted;
      try {
        accepted = await depsRef.current.startSurface({
          projectId: request.projectId,
          scenario: request.scenario,
          axisX: request.axisX,
          axisY: request.axisY,
          metric: request.metric,
          grid,
          runs: request.runs,
          seed: request.seed,
          quality: request.quality,
        });
      } catch (error) {
        setSurface((state) => ({
          ...state,
          status: "error",
          error: humanize(error),
        }));
        return false;
      }
      if (!accepted.accepted) {
        setSurface((state) => ({
          ...state,
          status: "error",
          error: "Le moteur a refusé l'analyse.",
        }));
        return false;
      }
      surfaceJob.current = accepted.jobId;
      setSurface((state) => ({
        ...state,
        jobId: accepted.jobId,
        replacedJobId: accepted.replacedJobId ?? null,
      }));
      const stop = await depsRef.current.subscribe(
        accepted.jobId,
        handleSurfaceEvent(accepted.jobId, grid),
      );
      if (surfaceJob.current === accepted.jobId) {
        surfaceStop.current = stop;
      } else {
        stop();
      }
      return true;
    },
    [handleSurfaceEvent, stopSurface],
  );

  const runGoalSeek = useCallback(
    async (request: GoalSeekRequest): Promise<boolean> => {
      const previous = goalJob.current;
      if (previous) {
        goalJob.current = null;
        stopGoal();
        void depsRef.current.cancel(previous).catch(() => undefined);
      }
      setGoal({
        ...initialGoalSeekState(),
        status: "running",
        total: request.maxEvaluations ?? 80,
      });
      let accepted;
      try {
        accepted = await depsRef.current.startGoalSeek({
          projectId: request.projectId,
          scenario: request.scenario,
          objective: request.objective,
          levers: request.levers,
          locked: request.locked,
          maxEvaluations: request.maxEvaluations,
          runs: request.runs,
          seed: request.seed,
          confirmQuality: request.confirmQuality,
          confirmRuns: request.confirmRuns,
        });
      } catch (error) {
        setGoal((state) => ({
          ...state,
          status: "error",
          error: humanize(error),
        }));
        return false;
      }
      if (!accepted.accepted) {
        setGoal((state) => ({
          ...state,
          status: "error",
          error: "Le moteur a refusé la recherche.",
        }));
        return false;
      }
      goalJob.current = accepted.jobId;
      setGoal((state) => ({
        ...state,
        jobId: accepted.jobId,
        replacedJobId: accepted.replacedJobId ?? null,
      }));
      const stop = await depsRef.current.subscribe(
        accepted.jobId,
        handleGoalEvent(accepted.jobId),
      );
      if (goalJob.current === accepted.jobId) {
        goalStop.current = stop;
      } else {
        stop();
      }
      return true;
    },
    [handleGoalEvent, stopGoal],
  );

  const cancelSurface = useCallback(() => {
    const jobId = surfaceJob.current;
    if (!jobId) return;
    setSurface((state) =>
      state.status === "running" ? { ...state, status: "cancelling" } : state,
    );
    void depsRef.current.cancel(jobId).catch(() => undefined);
  }, []);

  const cancelGoalSeek = useCallback(() => {
    const jobId = goalJob.current;
    if (!jobId) return;
    setGoal((state) =>
      state.status === "running" ? { ...state, status: "cancelling" } : state,
    );
    void depsRef.current.cancel(jobId).catch(() => undefined);
  }, []);

  useEffect(
    () => () => {
      const surfaceId = surfaceJob.current;
      const goalId = goalJob.current;
      surfaceJob.current = null;
      goalJob.current = null;
      stopSurface();
      stopGoal();
      if (surfaceId) void depsRef.current.cancel(surfaceId).catch(() => undefined);
      if (goalId) void depsRef.current.cancel(goalId).catch(() => undefined);
    },
    [stopGoal, stopSurface],
  );

  return useMemo(
    () => ({ surface, goal, runSurface, runGoalSeek, cancelSurface, cancelGoalSeek }),
    [cancelGoalSeek, cancelSurface, goal, runGoalSeek, runSurface, surface],
  );
}
