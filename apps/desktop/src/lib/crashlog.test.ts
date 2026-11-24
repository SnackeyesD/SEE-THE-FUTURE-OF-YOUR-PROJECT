import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearCrashEntries,
  isCrashLogEnabled,
  readCrashEntries,
  recordCrash,
  setCrashLogEnabled,
} from "./crashlog";

beforeEach(() => {
  window.localStorage.clear();
});

describe("journal local des erreurs", () => {
  it("est désactivé par défaut et n'enregistre rien", () => {
    expect(isCrashLogEnabled()).toBe(false);
    recordCrash("error", new Error("C:\\Users\\Alice\\secret.txt"));
    expect(readCrashEntries()).toHaveLength(0);
  });

  it("enregistre un message nettoyé quand il est activé", () => {
    setCrashLogEnabled(true);
    recordCrash(
      "rejection",
      new Error("apiKey=supersecret dans C:\\Users\\Alice\\projet"),
      "2026-11-24T10:00:00.000Z",
    );
    const entries = readCrashEntries();
    expect(entries).toHaveLength(1);
    expect(entries[0].kind).toBe("rejection");
    expect(entries[0].at).toBe("2026-11-24T10:00:00.000Z");
    expect(entries[0].message).not.toContain("supersecret");
    expect(entries[0].message).not.toContain("Alice");
    expect(entries[0].message).toContain("[masqué]");
    expect(entries[0].message).toContain("[chemin masqué]");
  });

  it("borne le journal et l'efface à la désactivation", () => {
    setCrashLogEnabled(true);
    for (let index = 0; index < 15; index += 1) {
      recordCrash("error", `erreur ${index}`);
    }
    expect(readCrashEntries()).toHaveLength(10);
    expect(readCrashEntries()[0].message).toBe("erreur 5");

    setCrashLogEnabled(false);
    expect(readCrashEntries()).toHaveLength(0);
    expect(isCrashLogEnabled()).toBe(false);
  });

  it("tolère un stockage corrompu", () => {
    window.localStorage.setItem("seefuture.crashLog.entries", "{pas du json");
    expect(readCrashEntries()).toEqual([]);
    clearCrashEntries();
    expect(readCrashEntries()).toEqual([]);
  });

  it("écoute les erreurs globales quand le journal est actif", async () => {
    setCrashLogEnabled(true);
    const { installCrashLogger } = await import("./crashlog");
    const uninstall = installCrashLogger();
    window.dispatchEvent(new ErrorEvent("error", { message: "boum (42)" }));
    expect(readCrashEntries().some((entry) => entry.message.includes("boum"))).toBe(true);
    uninstall();
    window.dispatchEvent(new ErrorEvent("error", { message: "après retrait" }));
    expect(readCrashEntries().some((entry) => entry.message.includes("après retrait"))).toBe(
      false,
    );
    vi.restoreAllMocks();
  });
});
