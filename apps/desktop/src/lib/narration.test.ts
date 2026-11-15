import { describe, expect, it } from "vitest";

import { verifyNarration } from "./narration";
import { simulationResult } from "../test/fixtures";

describe("verifyNarration", () => {
  it("accepte les nombres présents dans le résultat du moteur", () => {
    expect(
      verifyNarration(
        "Le profit moyen atteint 250 000 FCFA, avec P10 à 150 000 et P90 à 350 000.",
        simulationResult,
      ),
    ).toEqual([]);
  });

  it("accepte les pourcentages dérivés d'une probabilité", () => {
    expect(verifyNarration("La probabilité de perte est de 12 %.", simulationResult)).toEqual(
      [],
    );
  });

  it("signale les nombres inventés", () => {
    const unknown = verifyNarration(
      "Le profit moyen sera de 123 456 789 FCFA.",
      simulationResult,
    );
    expect(unknown).toHaveLength(1);
    expect(unknown[0]).toContain("123");
  });
});
