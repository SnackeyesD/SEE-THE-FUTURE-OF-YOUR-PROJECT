import { useCallback, useEffect, useState } from "react";

import {
  loadLayout,
  saveLayout,
  type LayoutState,
  type StorageLike,
} from "../store/layout";

/**
 * Charge la disposition du projet et la persiste à chaque changement.
 * Un layout illisible retombe silencieusement sur le preset par défaut.
 */
export function usePersistentLayout(
  projectId: string | null,
  storage?: StorageLike,
): [LayoutState, (next: LayoutState) => void] {
  const read = useCallback(
    () => (storage ? loadLayout(projectId, storage) : loadLayout(projectId)),
    [projectId, storage],
  );
  const [layout, setLayoutState] = useState<LayoutState>(read);

  useEffect(() => {
    setLayoutState(read());
  }, [read]);

  const setLayout = useCallback(
    (next: LayoutState) => {
      setLayoutState(next);
      if (storage) saveLayout(projectId, next, storage);
      else saveLayout(projectId, next);
    },
    [projectId, storage],
  );

  return [layout, setLayout];
}
