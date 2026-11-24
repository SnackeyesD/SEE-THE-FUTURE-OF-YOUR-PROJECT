import type { Scenario, SimulationQuality } from "@see/protocol";
import { useCallback, useEffect, useMemo, useRef } from "react";

import {
  cancelSimulation,
  onSimulationEvent,
  startSimulation,
  type SimulationEvent,
} from "../lib/ipc";
import type { CockpitStore } from "../store/cockpitStore";

export interface LiveSimulationDeps {
  start: typeof startSimulation;
  cancel: typeof cancelSimulation;
  subscribe: typeof onSimulationEvent;
}

export interface LiveSimulationOptions {
  store: CockpitStore;
  enabled?: boolean;
  deps?: Partial<LiveSimulationDeps>;
  /** Intervalle minimal entre deux drafts pendant un geste. */
  draftThrottleMs?: number;
  /** Délai d'inactivité avant le final automatique. */
  finalDelayMs?: number;
}

export interface LiveSimulationController {
  /** À appeler après toute modification d'entrée (commande, saisie, undo). */
  invalidate: () => void;
  beginGesture: () => void;
  endGesture: () => void;
  /** `true` si le sidecar a accepté le run ; `false` sur refus ou annulation. */
  runFinal: () => Promise<boolean>;
  cancel: () => void;
}

const DEFAULT_DRAFT_THROTTLE_MS = 50;
const DEFAULT_FINAL_DELAY_MS = 400;

function humanize(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error);
  return text.replace(/^Error:\s*/i, "");
}

export function scenarioIsRunnable(scenario: Scenario | null | undefined): boolean {
  if (!scenario || !scenario.name?.trim()) return false;
  const assumptions = Object.values(scenario.assumptions ?? {});
  if (assumptions.length === 0) return false;
  return assumptions.every((hypothesis) => Number.isFinite(hypothesis.value));
}

export function useLiveSimulation(options: LiveSimulationOptions): LiveSimulationController {
  const { store } = options;
  const draftThrottleMs = options.draftThrottleMs ?? DEFAULT_DRAFT_THROTTLE_MS;
  const finalDelayMs = options.finalDelayMs ?? DEFAULT_FINAL_DELAY_MS;

  const depsRef = useRef<LiveSimulationDeps>({
    start: startSimulation,
    cancel: cancelSimulation,
    subscribe: onSimulationEvent,
  });
  depsRef.current = {
    start: options.deps?.start ?? startSimulation,
    cancel: options.deps?.cancel ?? cancelSimulation,
    subscribe: options.deps?.subscribe ?? onSimulationEvent,
  };

  const enabledRef = useRef(options.enabled ?? true);
  enabledRef.current = options.enabled ?? true;

  const draftTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const finalTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastDraftAt = useRef(Number.NEGATIVE_INFINITY);
  const gesture = useRef(false);
  /** Le geste courant a modifié au moins une entrée. */
  const gestureDirty = useRef(false);
  const generation = useRef(0);

  const clearDraft = useCallback(() => {
    if (draftTimer.current !== null) {
      clearTimeout(draftTimer.current);
      draftTimer.current = null;
    }
  }, []);

  const clearFinal = useCallback(() => {
    if (finalTimer.current !== null) {
      clearTimeout(finalTimer.current);
      finalTimer.current = null;
    }
  }, []);

  const start = useCallback(
    async (quality: SimulationQuality): Promise<boolean> => {
      if (!enabledRef.current) return false;
      const session = store.getState().session;
      if (!scenarioIsRunnable(session.scenario)) return false;
      if (session.activeRunId) {
        const previousRunId = session.activeRunId;
        store.getState().cancelRun(previousRunId);
        void depsRef.current.cancel(previousRunId).catch(() => undefined);
      }
      const token = ++generation.current;
      if (quality === "draft") lastDraftAt.current = Date.now();
      try {
        const result = await depsRef.current.start({
          projectId: session.projectId,
          scenarioId: session.scenarioId ?? undefined,
          scenario: session.scenario,
          config: session.config,
          seed: session.seed,
          quality,
        });
        if (token !== generation.current) {
          void depsRef.current.cancel(result.runId).catch(() => undefined);
          return false;
        }
        store.getState().startRun({
          runId: result.runId,
          quality,
          seed: session.seed,
        });
        return true;
      } catch (error) {
        if (token !== generation.current) return false;
        store.getState().failSession(humanize(error));
        return false;
      }
    },
    [store],
  );

  const scheduleDraft = useCallback(() => {
    if (draftTimer.current !== null) return;
    const elapsed = Date.now() - lastDraftAt.current;
    const wait = Math.max(0, draftThrottleMs - elapsed);
    draftTimer.current = setTimeout(() => {
      draftTimer.current = null;
      void start("draft");
    }, wait);
  }, [draftThrottleMs, start]);

  const scheduleFinal = useCallback(() => {
    clearFinal();
    finalTimer.current = setTimeout(() => {
      finalTimer.current = null;
      void start("final");
    }, finalDelayMs);
  }, [clearFinal, finalDelayMs, start]);

  const invalidate = useCallback(() => {
    if (!enabledRef.current) return;
    if (gesture.current) gestureDirty.current = true;
    store.getState().markStale();
    // Pendant un geste : drafts throttlés pour un aperçu vivant, pas de final
    // avant le relâchement. Hors geste : draft puis final automatique.
    scheduleDraft();
    if (!gesture.current) scheduleFinal();
  }, [scheduleDraft, scheduleFinal, store]);

  const beginGesture = useCallback(() => {
    gesture.current = true;
    gestureDirty.current = false;
    clearFinal();
  }, [clearFinal]);

  const endGesture = useCallback(() => {
    gesture.current = false;
    clearDraft();
    clearFinal();
    if (!gestureDirty.current) return;
    gestureDirty.current = false;
    void start("final");
  }, [clearDraft, clearFinal, start]);

  const runFinal = useCallback((): Promise<boolean> => {
    gesture.current = false;
    gestureDirty.current = false;
    clearDraft();
    clearFinal();
    return start("final");
  }, [clearDraft, clearFinal, start]);

  const cancel = useCallback(() => {
    generation.current += 1;
    clearDraft();
    clearFinal();
    gesture.current = false;
    gestureDirty.current = false;
    const activeRunId = store.getState().session.activeRunId;
    if (!activeRunId) return;
    void depsRef.current.cancel(activeRunId).catch(() => undefined);
    store.getState().cancelRun(activeRunId);
  }, [clearDraft, clearFinal, store]);

  // Un démontage ne doit jamais laisser un draft ou un final programmé lancer
  // une simulation dans un composant disparu.
  useEffect(
    () => () => {
      generation.current += 1;
      clearDraft();
      clearFinal();
      gesture.current = false;
      gestureDirty.current = false;
    },
    [clearDraft, clearFinal],
  );

  useEffect(() => {
    const subscribe = depsRef.current.subscribe;
    let disposed = false;
    let unlisten: (() => void) | undefined;

    const handle = (event: SimulationEvent): void => {
      const state = store.getState();
      const runId = event.params.runId;
      if (state.session.activeRunId !== runId) return;
      switch (event.method) {
        case "simulation.partial":
          state.applyPartial({
            runId,
            seq: event.params.seq,
            aggregates: event.params.aggregates,
          });
          break;
        case "simulation.done":
          state.applyFinal({
            runId,
            seq: event.params.seq,
            result: event.params.result,
          });
          break;
        case "simulation.cancelled":
          state.cancelRun(runId);
          break;
        case "simulation.error":
          state.failRun(runId, {
            code: event.params.code,
            message: event.params.message,
          });
          break;
        default:
          break;
      }
    };

    void subscribe(handle).then((stop) => {
      if (disposed) {
        stop();
        return;
      }
      unlisten = stop;
    });

    return () => {
      disposed = true;
      unlisten?.();
      const activeRunId = store.getState().session.activeRunId;
      if (activeRunId) {
        void depsRef.current.cancel(activeRunId).catch(() => undefined);
        store.getState().cancelRun(activeRunId);
      }
    };
  }, [store]);

  return useMemo(
    () => ({ invalidate, beginGesture, endGesture, runFinal, cancel }),
    [cancel, endGesture, invalidate, runFinal],
  );
}
