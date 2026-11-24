import { describe, expect, it } from "vitest";

import { buildDiagnostic, diagnosticFilename, scrubDiagnosticText } from "./diagnostic";

describe("scrubDiagnosticText", () => {
  it("masque les clés API et les jetons", () => {
    const text = scrubDiagnosticText(
      "clé sk-abcdefgh12345678 et bearer Bearer abcdefgh12345678; apiKey=supersecret",
    );
    expect(text).not.toContain("sk-abcdefgh12345678");
    expect(text).not.toContain("abcdefgh12345678");
    expect(text).not.toContain("supersecret");
    expect(text).toContain("[clé masquée]");
    expect(text).toContain("[masqué]");
  });

  it("masque les chemins locaux et les courriels", () => {
    const text = scrubDiagnosticText(
      "C:\\Users\\Alice\\projet\\data.db /home/alice/secret.txt alice@example.com",
    );
    expect(text).not.toContain("Alice");
    expect(text).not.toContain("/home/alice");
    expect(text).not.toContain("alice@example.com");
    expect(text).toContain("[chemin masqué]");
    expect(text).toContain("[courriel masqué]");
  });

  it("masque le nom du projet sans tenir compte de la casse", () => {
    const text = scrubDiagnosticText(
      "Projet « Dépôt Brazza » rechargé; dépôt brazza est prêt.",
      ["Dépôt Brazza"],
    );
    expect(text.toLowerCase()).not.toContain("dépôt brazza");
    expect(text.match(/\[projet masqué\]/gi)?.length).toBe(2);
  });
});

describe("buildDiagnostic", () => {
  it("produit un JSON borné et nettoyé", () => {
    const content = buildDiagnostic({
      appVersion: "3.0.0",
      locale: "fr",
      userAgent: "jsdom",
      status: { running: true, pid: 42 },
      health: {
        status: "ok",
        sidecarVersion: "0.1.0",
        protocolVersion: "1.15.0",
        python: "3.11",
        pid: 42,
      },
      logs: Array.from({ length: 60 }, (_, index) => ({
        at: `2026-11-24T10:${String(index).padStart(2, "0")}:00Z`,
        level: "error",
        message: `C:\\Users\\Alice\\projet-${index} sk-abcdefgh12345678`,
      })),
      projectNames: ["Projet secret"],
      crashes: [
        {
          at: "2026-11-24T11:00:00.000Z",
          kind: "error",
          message: "C:\\Users\\Alice\\boom sk-abcdefgh12345678",
        },
      ],
      generatedAt: "2026-11-24T12:00:00.000Z",
    });

    const parsed = JSON.parse(content) as {
      logs: unknown[];
      crashes: Array<{ message: string }>;
      generatedAt: string;
    };
    expect(parsed.generatedAt).toBe("2026-11-24T12:00:00.000Z");
    expect(parsed.logs).toHaveLength(50);
    expect(parsed.crashes).toHaveLength(1);
    expect(parsed.crashes[0].message).not.toContain("Alice");
    expect(parsed.crashes[0].message).not.toContain("sk-abcdefgh12345678");
    expect(content).not.toContain("Alice");
    expect(content).not.toContain("sk-abcdefgh12345678");
    expect(content).toContain("[chemin masqué]");
  });

  it("nomme le fichier avec la date locale", () => {
    expect(diagnosticFilename(new Date(2026, 10, 24, 9, 5))).toBe(
      "diagnostic-seetfuture-20261124-0905.json",
    );
  });
});
