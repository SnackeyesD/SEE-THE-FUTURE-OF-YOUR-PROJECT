/**
 * Géométrie pure de la frise d'événements.
 *
 * Toutes les API du moteur sont **1-based** et les durées sont **inclusives** :
 * un événement `{ startMonth: 3, durationMonths: 2 }` couvre les mois 3 et 4.
 * Aucune de ces fonctions ne touche au DOM ni au store : elles sont testées
 * seules et réutilisées par `EventTimeline`.
 */

export interface EventWindow {
  startMonth: number;
  durationMonths: number;
}

export function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}

/** Dernier mois couvert (inclusif). */
export function lastMonth(window: EventWindow): number {
  return window.startMonth + window.durationMonths - 1;
}

/** Ramène une fenêtre dans `[1, horizon]`, durée minimale 1 mois. */
export function clampWindow(window: EventWindow, horizon: number): EventWindow {
  const safeHorizon = Math.max(1, Math.floor(horizon));
  const start = Math.round(clamp(window.startMonth, 1, safeHorizon));
  const duration = Math.round(
    clamp(window.durationMonths, 1, safeHorizon - start + 1),
  );
  return { startMonth: start, durationMonths: duration };
}

/** Déplace la fenêtre de `delta` mois sans changer sa durée. */
export function moveWindow(
  window: EventWindow,
  delta: number,
  horizon: number,
): EventWindow {
  const current = clampWindow(window, horizon);
  const start = clamp(current.startMonth + delta, 1, horizon - current.durationMonths + 1);
  return { startMonth: start, durationMonths: current.durationMonths };
}

/** Déplace la poignée gauche ; la fin reste ancrée. */
export function resizeStart(
  window: EventWindow,
  delta: number,
  horizon: number,
): EventWindow {
  const current = clampWindow(window, horizon);
  const end = lastMonth(current);
  const start = clamp(current.startMonth + delta, 1, end);
  return { startMonth: start, durationMonths: end - start + 1 };
}

/** Déplace la poignée droite ; le début reste ancré. */
export function resizeEnd(
  window: EventWindow,
  delta: number,
  horizon: number,
): EventWindow {
  const current = clampWindow(window, horizon);
  const end = clamp(lastMonth(current) + delta, current.startMonth, horizon);
  return { startMonth: current.startMonth, durationMonths: end - current.startMonth + 1 };
}

/** Bord gauche d'un mois en pixels (le mois `m` occupe `[m-1, m]`). */
export function monthToX(month: number, horizon: number, width: number): number {
  if (horizon <= 0) return 0;
  return ((clamp(month, 1, horizon + 1) - 1) / horizon) * width;
}

/** Largeur en pixels d'une fenêtre inclusive. */
export function windowToPx(
  window: EventWindow,
  horizon: number,
  width: number,
): { left: number; width: number } {
  const safe = clampWindow(window, horizon);
  const left = monthToX(safe.startMonth, horizon, width);
  const right = monthToX(safe.startMonth + safe.durationMonths, horizon, width);
  return { left, width: Math.max(1, right - left) };
}

/** Position et largeur en pourcentage, indépendantes de la mesure DOM. */
export function windowToPercent(
  window: EventWindow,
  horizon: number,
): { left: number; width: number } {
  const safeHorizon = Math.max(1, horizon);
  const safe = clampWindow(window, safeHorizon);
  return {
    left: ((safe.startMonth - 1) / safeHorizon) * 100,
    width: (safe.durationMonths / safeHorizon) * 100,
  };
}

/** Mois (1-based) sous une position en pixels. */
export function xToMonth(x: number, horizon: number, width: number): number {
  if (horizon <= 0 || width <= 0) return 1;
  return clamp(Math.floor((x / width) * horizon) + 1, 1, horizon);
}

/** Empilement glouton : les fenêtres qui se chevauchent changent de ligne. */
export function laneAssignment(
  events: ReadonlyArray<{ id: string } & EventWindow>,
): { lanes: Map<string, number>; count: number } {
  const lanes: Map<string, number> = new Map();
  const ends: number[] = [];
  const ordered = [...events].sort(
    (left, right) =>
      left.startMonth - right.startMonth ||
      left.durationMonths - right.durationMonths ||
      left.id.localeCompare(right.id),
  );
  for (const event of ordered) {
    const start = event.startMonth;
    let lane = ends.findIndex((end) => end < start);
    if (lane === -1) {
      lane = ends.length;
      ends.push(lastMonth(event));
    } else {
      ends[lane] = lastMonth(event);
    }
    lanes.set(event.id, lane);
  }
  return { lanes, count: Math.max(1, ends.length) };
}
