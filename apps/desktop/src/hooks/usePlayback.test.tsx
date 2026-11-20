import { act, renderHook } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PLAYBACK_INTERVAL_MS, usePlayback } from "./usePlayback";

function harness(horizon: number, initialMonth: number | null, disabled = false) {
  return renderHook(() => {
    const [month, setMonth] = useState<number | null>(initialMonth);
    const playback = usePlayback({
      horizon,
      month,
      onMonthChange: setMonth,
      disabled,
    });
    return { month, ...playback };
  });
}

async function advance(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("usePlayback", () => {
  it("avance d'un mois par intervalle puis s'arrête à la fin", async () => {
    const { result } = harness(3, 1);

    act(() => result.current.toggle());
    expect(result.current.playing).toBe(true);

    await advance(PLAYBACK_INTERVAL_MS);
    expect(result.current.month).toBe(2);

    await advance(PLAYBACK_INTERVAL_MS);
    expect(result.current.month).toBe(3);

    await advance(PLAYBACK_INTERVAL_MS);
    expect(result.current.month).toBe(3);
    expect(result.current.playing).toBe(false);
  });

  it("relance depuis le premier mois quand on est déjà au bout", async () => {
    const { result } = harness(3, 3);

    act(() => result.current.toggle());
    expect(result.current.month).toBe(1);
    expect(result.current.playing).toBe(true);

    act(() => result.current.toggle());
    expect(result.current.playing).toBe(false);
  });

  it("met en pause quand la fenêtre perd le focus", async () => {
    const { result } = harness(6, 1);
    act(() => result.current.toggle());
    expect(result.current.playing).toBe(true);

    act(() => {
      window.dispatchEvent(new Event("blur"));
    });

    expect(result.current.playing).toBe(false);
  });

  it("ne démarre pas pendant un calcul", () => {
    const { result } = harness(6, 2, true);
    act(() => result.current.toggle());
    expect(result.current.playing).toBe(false);
    expect(result.current.month).toBe(2);
  });

  it("s'arrête sans effet quand l'horizon est nul", () => {
    const { result } = harness(0, null);
    act(() => result.current.toggle());
    expect(result.current.playing).toBe(false);
  });
});
