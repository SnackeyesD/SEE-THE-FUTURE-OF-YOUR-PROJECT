import type { Scenario, SimulationConfig } from "@see/protocol";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { useUndoRedoHotkeys } from "../hooks/useUndoRedoHotkeys";
import { createCockpitStore, type CockpitStore } from "./cockpitStore";
import { CommandStack } from "./commands";
import {
  saveLayout,
  type LayoutState,
  type StorageLike,
} from "./layout";

export interface CockpitContextValue {
  store: CockpitStore;
  inputs: CommandStack;
  layout: CommandStack;
  applyLayout: (next: LayoutState) => void;
}

const CockpitContext = createContext<CockpitContextValue | null>(null);

function sameLayout(left: LayoutState, right: LayoutState): boolean {
  return (
    left.preset === right.preset &&
    left.fullscreen === right.fullscreen &&
    left.fractions.left === right.fractions.left &&
    left.fractions.main === right.fractions.main &&
    left.fractions.right === right.fractions.right
  );
}

export interface CockpitProviderProps {
  projectId: string;
  scenario: Scenario;
  seed?: number;
  config?: SimulationConfig;
  initialLayout?: LayoutState;
  storage?: StorageLike;
  /** Appelé après toute commande, undo ou redo : le contrôleur relance le calcul. */
  onInputsChanged?: () => void;
  hotkeys?: boolean;
  children: ReactNode;
}

/**
 * Un store par application (un par projet monté). Pour changer de projet,
 * remonter le provider avec une `key={projectId}`.
 */
export function CockpitProvider({
  projectId,
  scenario,
  seed,
  config,
  initialLayout,
  storage,
  onInputsChanged,
  hotkeys = true,
  children,
}: CockpitProviderProps) {
  const [store] = useState<CockpitStore>(() =>
    createCockpitStore({
      projectId,
      scenario,
      seed,
      config,
      layout: initialLayout,
    }),
  );
  const [inputs] = useState(() => new CommandStack());
  const [layout] = useState(() => new CommandStack());

  useEffect(() => {
    return inputs.subscribe(() => onInputsChanged?.());
  }, [inputs, onInputsChanged]);

  useEffect(() => {
    return store.subscribe((state, previous) => {
      if (state.layout === previous.layout) return;
      if (storage) saveLayout(projectId, state.layout, storage);
      else saveLayout(projectId, state.layout);
    });
  }, [projectId, storage, store]);

  const applyLayout = useCallback(
    (next: LayoutState) => {
      const before = store.getState().layout;
      if (sameLayout(before, next)) return;
      layout.dispatch({
        label: "Disposition",
        coalesceKey: "layout",
        undo: () => store.getState().setLayout(before),
        redo: () => store.getState().setLayout(next),
      });
    },
    [layout, store],
  );

  useUndoRedoHotkeys(inputs, hotkeys);

  const value = useMemo<CockpitContextValue>(
    () => ({ store, inputs, layout, applyLayout }),
    [applyLayout, inputs, layout, store],
  );

  return <CockpitContext.Provider value={value}>{children}</CockpitContext.Provider>;
}

export function useCockpitContext(): CockpitContextValue {
  const value = useContext(CockpitContext);
  if (!value) {
    throw new Error("useCockpitContext doit être utilisé dans un CockpitProvider");
  }
  return value;
}
