import { useCallback, useEffect, useRef, useState } from "react";

export const PLAYBACK_INTERVAL_MS = 400;

/**
 * Lecture mois par mois du cockpit.
 *
 * - un seul intervalle, jamais de calcul moteur : `onMonthChange` ne fait que
 *   déplacer la sélection ;
 * - arrêt automatique en fin d'horizon ;
 * - pause quand la fenêtre perd le focus ou devient invisible (spec §6) ;
 * - `disabled` (calcul final en cours) suspend la lecture sans la relancer.
 */
export function usePlayback({
  horizon,
  month,
  onMonthChange,
  disabled = false,
}: {
  horizon: number;
  month: number | null;
  onMonthChange: (month: number) => void;
  disabled?: boolean;
}): { playing: boolean; toggle: () => void; stop: () => void } {
  const [playing, setPlaying] = useState(false);
  const monthRef = useRef(month);
  const onChangeRef = useRef(onMonthChange);
  const horizonRef = useRef(horizon);

  monthRef.current = month;
  onChangeRef.current = onMonthChange;
  horizonRef.current = horizon;

  const stop = useCallback(() => setPlaying(false), []);

  const toggle = useCallback(() => {
    if (disabled || horizonRef.current <= 0) return;
    setPlaying((current) => {
      if (current) return false;
      // Relancer depuis la fin ramène au premier mois.
      if ((monthRef.current ?? 0) >= horizonRef.current) onChangeRef.current(1);
      return true;
    });
  }, [disabled]);

  useEffect(() => {
    if (disabled) setPlaying(false);
  }, [disabled]);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      const current = monthRef.current ?? 0;
      const next = current + 1;
      if (next > horizonRef.current) {
        setPlaying(false);
        return;
      }
      onChangeRef.current(next);
    }, PLAYBACK_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [playing]);

  useEffect(() => {
    if (!playing) return;
    const pause = (): void => setPlaying(false);
    const pauseIfHidden = (): void => {
      if (document.visibilityState === "hidden") setPlaying(false);
    };
    window.addEventListener("blur", pause);
    document.addEventListener("visibilitychange", pauseIfHidden);
    return () => {
      window.removeEventListener("blur", pause);
      document.removeEventListener("visibilitychange", pauseIfHidden);
    };
  }, [playing]);

  return { playing, toggle, stop };
}
