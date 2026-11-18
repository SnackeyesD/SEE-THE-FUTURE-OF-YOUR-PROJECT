import { describe, expect, it } from "vitest";

import {
  cdfProbabilityAt,
  fanBandPath,
  fanDomain,
  fanLinePath,
  nearestMonth,
  normalizeCdf,
  normalizeFanPoints,
  thresholdStep,
  type FanPoint,
} from "@see/ui";

const points: FanPoint[] = [
  { month: 3, p10: 30, p50: 50, p90: 70 },
  { month: 1, p10: 10, p50: 20, p90: 40 },
  { month: 2, p10: 20, p50: 35, p90: 60 },
];

const project = (month: number, value: number): [number, number] => [month, value];

describe("normalizeFanPoints", () => {
  it("trie par mois et copie les points", () => {
    const result = normalizeFanPoints(points);
    expect(result.map((point) => point.month)).toEqual([1, 2, 3]);
    expect(result[0]).not.toBe(points[1]);
  });

  it("écarte les points non finis", () => {
    const dirty = [
      { month: 1, p10: 1, p50: 2, p90: 3 },
      { month: 2, p10: Number.NaN, p50: 2, p90: 3 },
      { month: Number.POSITIVE_INFINITY, p10: 1, p50: 2, p90: 3 },
    ];
    expect(normalizeFanPoints(dirty)).toEqual([{ month: 1, p10: 1, p50: 2, p90: 3 }]);
  });
});

describe("fanDomain", () => {
  it("couvre les bandes et n'ajoute pas zéro à un domaine positif", () => {
    expect(fanDomain(points)).toEqual({ min: 10, max: 70 });
  });

  it("inclut zéro et le seuil quand une valeur est négative", () => {
    const negative: FanPoint[] = [{ month: 1, p10: -50, p50: 10, p90: 80 }];
    expect(fanDomain(negative, [], [-120])).toEqual({ min: -120, max: 80 });
  });

  it("remonte un domaine entièrement négatif à zéro", () => {
    const negative: FanPoint[] = [{ month: 1, p10: -80, p50: -50, p90: -10 }];
    expect(fanDomain(negative)).toEqual({ min: -80, max: 0 });
  });

  it("élargit un domaine plat pour rester dessinable", () => {
    const flat: FanPoint[] = [{ month: 1, p10: 0, p50: 0, p90: 0 }];
    expect(fanDomain(flat)).toEqual({ min: -1, max: 1 });
  });

  it("prend en compte les fantômes", () => {
    const ghosts = [
      {
        id: "g",
        label: "g",
        seed: 7,
        points: [{ month: 1, p10: 5, p50: 100, p90: 200 }],
      },
    ];
    expect(fanDomain(points, ghosts)).toEqual({ min: 5, max: 200 });
  });
});

describe("fan paths", () => {
  it("referme la surface P10–P90 dans l'ordre des mois", () => {
    const path = fanBandPath(points, project);
    expect(path.startsWith("M 1 40 L 2 60 L 3 70")).toBe(true);
    expect(path).toContain("L 3 30 L 2 20 L 1 10 Z");
  });

  it("retourne une chaîne vide avec moins de deux points", () => {
    expect(fanBandPath([{ month: 1, p10: 1, p50: 2, p90: 3 }], project)).toBe("");
    expect(fanBandPath([], project)).toBe("");
  });

  it("trace la médiane et accepte un point unique", () => {
    expect(fanLinePath(points, "p50", project)).toBe("M 1 20 L 2 35 L 3 50");
    expect(
      fanLinePath([{ month: 4, p10: 1, p50: 2, p90: 3 }], "p90", project),
    ).toBe("M 4 3");
  });
});

describe("cdfProbabilityAt", () => {
  const cdf = [
    { value: 0, probability: 0.1 },
    { value: 100, probability: 0.5 },
    { value: 200, probability: 1 },
  ];

  it("retourne null sans CDF", () => {
    expect(cdfProbabilityAt(null, 10)).toBeNull();
    expect(cdfProbabilityAt([], 10)).toBeNull();
  });

  it("borne sous le premier et au-delà du dernier point", () => {
    expect(cdfProbabilityAt(cdf, -10)).toBe(0);
    expect(cdfProbabilityAt(cdf, 200)).toBe(1);
    expect(cdfProbabilityAt(cdf, 500)).toBe(1);
  });

  it("interpole linéairement entre deux points", () => {
    expect(cdfProbabilityAt(cdf, 50)).toBeCloseTo(0.3);
    expect(cdfProbabilityAt(cdf, 150)).toBeCloseTo(0.75);
  });

  it("accepte une CDF non triée et normalise les probabilités", () => {
    const shuffled = [
      { value: 100, probability: 0.5 },
      { value: 0, probability: 0.1 },
    ];
    expect(cdfProbabilityAt(shuffled, 50)).toBeCloseTo(0.3);
    expect(normalizeCdf([{ value: 0, probability: 1.4 }, { value: 0, probability: 0.2 }])).toEqual([
      { value: 0, probability: 0.2 },
    ]);
  });
});

describe("nearestMonth", () => {
  it("choisit le mois le plus proche et gère le vide", () => {
    expect(nearestMonth(points, 2.4)).toBe(2);
    expect(nearestMonth(points, 99)).toBe(3);
    expect(nearestMonth([], 2)).toBeNull();
  });
});

describe("thresholdStep", () => {
  it("propose 1 % du domaine", () => {
    expect(thresholdStep({ min: 0, max: 1000 })).toBe(10);
    expect(thresholdStep({ min: 5, max: 5 })).toBe(1);
  });
});
