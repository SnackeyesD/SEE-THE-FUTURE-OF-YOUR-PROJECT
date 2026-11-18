import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  DEFAULT_LAYOUT,
  layoutFromPreset,
  layoutStorageKey,
  type StorageLike,
} from "../store/layout";
import { usePersistentLayout } from "./usePersistentLayout";

function memoryStorage(): StorageLike & { entries: Map<string, string> } {
  const entries = new Map<string, string>();
  return {
    entries,
    getItem: (key) => entries.get(key) ?? null,
    setItem: (key, value) => {
      entries.set(key, value);
    },
  };
}

describe("usePersistentLayout", () => {
  it("restaure la disposition du projet au montage", () => {
    const storage = memoryStorage();
    storage.setItem(
      layoutStorageKey("p1"),
      JSON.stringify(layoutFromPreset("presentation")),
    );

    const { result } = renderHook(() => usePersistentLayout("p1", storage));

    expect(result.current[0]).toEqual(layoutFromPreset("presentation"));
  });

  it("persiste chaque changement et le relit après remontage", () => {
    const storage = memoryStorage();
    const first = renderHook(() => usePersistentLayout("p1", storage));

    act(() => first.result.current[1](layoutFromPreset("pilotage")));
    first.unmount();

    const second = renderHook(() => usePersistentLayout("p1", storage));
    expect(second.result.current[0]).toEqual(layoutFromPreset("pilotage"));
  });

  it("ignore une disposition corrompue", () => {
    const storage = memoryStorage();
    storage.setItem(layoutStorageKey("p1"), "{corrompu");

    const { result } = renderHook(() => usePersistentLayout("p1", storage));

    expect(result.current[0]).toEqual(DEFAULT_LAYOUT);
  });

  it("change de projet sans mélanger les dispositions", () => {
    const storage = memoryStorage();
    storage.setItem(layoutStorageKey("p2"), JSON.stringify(layoutFromPreset("pilotage")));

    const { result, rerender } = renderHook(({ id }) => usePersistentLayout(id, storage), {
      initialProps: { id: "p1" },
    });
    expect(result.current[0]).toEqual(DEFAULT_LAYOUT);

    rerender({ id: "p2" });
    expect(result.current[0]).toEqual(layoutFromPreset("pilotage"));
  });
});
