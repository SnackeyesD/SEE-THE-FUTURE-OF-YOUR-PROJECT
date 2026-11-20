import { describe, expect, it } from "vitest";

import {
  clampWindow,
  laneAssignment,
  lastMonth,
  monthToX,
  moveWindow,
  resizeEnd,
  resizeStart,
  windowToPercent,
  xToMonth,
} from "./events";

const HORIZON = 12;

describe("géométrie de la frise", () => {
  it("traite la durée comme inclusive", () => {
    expect(lastMonth({ startMonth: 3, durationMonths: 2 })).toBe(4);
    expect(lastMonth({ startMonth: 12, durationMonths: 1 })).toBe(12);
  });

  it("borne une fenêtre dans l'horizon avec une durée minimale de 1", () => {
    expect(clampWindow({ startMonth: 0, durationMonths: 3 }, HORIZON)).toEqual({
      startMonth: 1,
      durationMonths: 3,
    });
    expect(clampWindow({ startMonth: 11, durationMonths: 8 }, HORIZON)).toEqual({
      startMonth: 11,
      durationMonths: 2,
    });
    expect(clampWindow({ startMonth: 5, durationMonths: 0 }, HORIZON)).toEqual({
      startMonth: 5,
      durationMonths: 1,
    });
  });

  it("déplace sans changer la durée et sans sortir de l'horizon", () => {
    expect(moveWindow({ startMonth: 5, durationMonths: 3 }, 2, HORIZON)).toEqual({
      startMonth: 7,
      durationMonths: 3,
    });
    expect(moveWindow({ startMonth: 2, durationMonths: 3 }, -5, HORIZON)).toEqual({
      startMonth: 1,
      durationMonths: 3,
    });
    expect(moveWindow({ startMonth: 10, durationMonths: 3 }, 5, HORIZON)).toEqual({
      startMonth: 10,
      durationMonths: 3,
    });
  });

  it("redimensionne le début en gardant la fin ancrée", () => {
    expect(resizeStart({ startMonth: 4, durationMonths: 4 }, -2, HORIZON)).toEqual({
      startMonth: 2,
      durationMonths: 6,
    });
    expect(resizeStart({ startMonth: 4, durationMonths: 4 }, 9, HORIZON)).toEqual({
      startMonth: 7,
      durationMonths: 1,
    });
  });

  it("redimensionne la fin en gardant le début ancré", () => {
    expect(resizeEnd({ startMonth: 4, durationMonths: 4 }, 3, HORIZON)).toEqual({
      startMonth: 4,
      durationMonths: 7,
    });
    expect(resizeEnd({ startMonth: 4, durationMonths: 4 }, -10, HORIZON)).toEqual({
      startMonth: 4,
      durationMonths: 1,
    });
    expect(resizeEnd({ startMonth: 10, durationMonths: 1 }, 9, HORIZON)).toEqual({
      startMonth: 10,
      durationMonths: 3,
    });
  });

  it("convertit les mois et les positions en pourcentage", () => {
    const single = windowToPercent({ startMonth: 1, durationMonths: 1 }, HORIZON);
    expect(single.left).toBe(0);
    expect(single.width).toBeCloseTo(100 / HORIZON);
    expect(windowToPercent({ startMonth: 3, durationMonths: 4 }, HORIZON)).toEqual({
      left: (2 / HORIZON) * 100,
      width: (4 / HORIZON) * 100,
    });
    expect(monthToX(1, HORIZON, 1200)).toBe(0);
    expect(monthToX(13, HORIZON, 1200)).toBe(1200);
  });

  it("retrouve le mois sous une position, borné aux extrémités", () => {
    expect(xToMonth(0, HORIZON, 1200)).toBe(1);
    expect(xToMonth(599, HORIZON, 1200)).toBe(6);
    expect(xToMonth(600, HORIZON, 1200)).toBe(7);
    expect(xToMonth(5000, HORIZON, 1200)).toBe(12);
    expect(xToMonth(-10, HORIZON, 1200)).toBe(1);
    expect(xToMonth(10, 0, 1200)).toBe(1);
  });

  it("empile les fenêtres qui se chevauchent et réutilise les lignes libres", () => {
    const { lanes, count } = laneAssignment([
      { id: "a", startMonth: 1, durationMonths: 3 },
      { id: "b", startMonth: 3, durationMonths: 2 },
      { id: "c", startMonth: 6, durationMonths: 2 },
      { id: "d", startMonth: 6, durationMonths: 2 },
      { id: "e", startMonth: 8, durationMonths: 2 },
    ]);

    expect(count).toBe(2);
    expect(lanes.get("a")).toBe(0);
    expect(lanes.get("b")).toBe(1);
    // « c » démarre après la fin de « a » : la ligne 0 est réutilisée.
    expect(lanes.get("c")).toBe(0);
    // « d » chevauche « c » : la ligne 1 redevient nécessaire.
    expect(lanes.get("d")).toBe(1);
    // « e » démarre après « c » et « d » : retour sur la ligne 0.
    expect(lanes.get("e")).toBe(0);
  });

  it("donne au moins une ligne sans événement", () => {
    expect(laneAssignment([]).count).toBe(1);
  });
});
