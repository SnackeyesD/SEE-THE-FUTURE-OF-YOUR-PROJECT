import type { Trajectory } from "@see/protocol";
import { describe, expect, it } from "vitest";

import { breakEvenMonth, buildPointCloud, cumulativeProfit } from "./pointCloud";

function trajectory(index: number, profit: number[], cash: number[]): Trajectory {
  return {
    index,
    profitMonthly: profit,
    cashMonthly: cash,
    revenueMonthly: profit.map(() => 0),
  };
}

describe("cumulativeProfit", () => {
  it("accumule les profits mois par mois", () => {
    expect(cumulativeProfit([10, -5, 3])).toEqual([10, 5, 8]);
    expect(cumulativeProfit([Number.NaN, 2])).toEqual([0, 2]);
    expect(cumulativeProfit([])).toEqual([]);
  });
});

describe("breakEvenMonth", () => {
  it("retourne le premier mois positif ou nul", () => {
    expect(breakEvenMonth([-10, -1, 0, 4])).toBe(3);
    expect(breakEvenMonth([1])).toBe(1);
  });

  it("retourne null si le point mort n'est jamais atteint", () => {
    expect(breakEvenMonth([-4, -3, -2])).toBeNull();
    expect(breakEvenMonth([])).toBeNull();
  });
});

describe("buildPointCloud", () => {
  it("dérive un point par trajectoire sans simuler", () => {
    const cloud = buildPointCloud({
      horizonMonths: 3,
      trajectories: [
        trajectory(0, [10, 10, 10], [-50, 10, 20]),
        trajectory(1, [-5, -5, -5], [100, 80, 60]),
      ],
    });

    expect(cloud.points).toHaveLength(2);
    expect(cloud.points[0]).toMatchObject({
      index: 0,
      financingNeed: 50,
      breakEvenMonth: 1,
      finalProfit: 30,
      minimumCash: -50,
    });
    expect(cloud.points[1]).toMatchObject({
      index: 1,
      financingNeed: 0,
      breakEvenMonth: null,
      finalProfit: -15,
    });
    expect(cloud.positions).toHaveLength(6);
    expect(cloud.heatSteps).toHaveLength(2);
    expect(cloud.minimumProfit).toBe(-15);
    expect(cloud.maximumProfit).toBe(30);
    expect(cloud.maximumFinancingNeed).toBe(50);

    for (const value of cloud.positions) {
      expect(value).toBeGreaterThanOrEqual(-1);
      expect(value).toBeLessThanOrEqual(1);
    }
  });

  it("ignore les trajectoires sans profit mensuel", () => {
    const cloud = buildPointCloud({
      trajectories: [trajectory(0, [], [])],
      horizonMonths: 12,
    });
    expect(cloud.points).toEqual([]);
    expect(cloud.positions).toHaveLength(0);
  });
});
