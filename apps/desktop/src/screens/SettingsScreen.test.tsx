import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { isCrashLogEnabled } from "../lib/crashlog";
import { downloadText } from "../lib/download";
import { project } from "../test/fixtures";
import { SettingsScreen } from "./SettingsScreen";

vi.mock("../lib/download", () => ({
  downloadText: vi.fn(() => true),
  downloadBase64: vi.fn(() => true),
}));

function renderScreen() {
  const props = {
    project,
    disabled: true,
    status: { running: true, pid: 4321 },
    health: {
      status: "ok",
      sidecarVersion: "0.1.0",
      protocolVersion: "1.16.0",
      pid: 4321,
      python: "3.11",
    },
    locale: "fr" as const,
    logs: [
      {
        id: 1,
        at: "2026-11-24T10:00:00.000Z",
        level: "error" as const,
        message: "Échec dans C:\\Users\\Alice\\projet apiKey=supersecret",
      },
    ],
    onLog: vi.fn(),
    onLocale: vi.fn(),
    onPing: vi.fn().mockResolvedValue(undefined),
    onRestart: vi.fn().mockResolvedValue(undefined),
  };
  render(<SettingsScreen {...props} />);
  return props;
}

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(downloadText).mockClear();
});

describe("SettingsScreen — diagnostic et transparence", () => {
  it("exporte un diagnostic borné et nettoyé", async () => {
    const user = userEvent.setup();
    const props = renderScreen();

    await user.click(screen.getByRole("button", { name: "Exporter le diagnostic" }));

    expect(downloadText).toHaveBeenCalledTimes(1);
    const [filename, content, mime] = vi.mocked(downloadText).mock.calls[0];
    expect(filename).toMatch(/^diagnostic-seetfuture-\d{8}-\d{4}\.json$/);
    expect(mime).toContain("application/json");
    expect(content).not.toContain("Alice");
    expect(content).not.toContain("supersecret");
    expect(content).not.toContain(project.name);
    const parsed = JSON.parse(content) as {
      formatVersion: string;
      sidecar: { running: boolean };
      health: { protocolVersion: string };
      logs: Array<{ message: string }>;
      crashes: unknown[];
    };
    expect(parsed.formatVersion).toBe("1");
    expect(parsed.sidecar.running).toBe(true);
    expect(parsed.health.protocolVersion).toBe("1.16.0");
    expect(parsed.logs).toHaveLength(1);
    expect(parsed.logs[0].message).toContain("[chemin masqué]");
    expect(parsed.logs[0].message).toContain("[masqué]");
    expect(parsed.crashes).toEqual([]);
    expect(props.onLog).toHaveBeenCalledWith(
      "success",
      "Diagnostic local exporté (sans projet ni clé).",
    );
  });

  it("active et désactive le journal local des erreurs", async () => {
    const user = userEvent.setup();
    renderScreen();

    const toggle = screen.getByRole("checkbox", {
      name: /Journal local des erreurs/,
    });
    expect(toggle).not.toBeChecked();
    expect(isCrashLogEnabled()).toBe(false);

    await user.click(toggle);
    expect(toggle).toBeChecked();
    expect(isCrashLogEnabled()).toBe(true);

    await user.click(toggle);
    expect(toggle).not.toBeChecked();
    expect(isCrashLogEnabled()).toBe(false);
  });

  it("affiche les versions, la licence et les mentions de transparence", () => {
    renderScreen();

    expect(screen.getByText("Version de l'application")).toBeInTheDocument();
    expect(screen.getByText("Protocole IPC")).toBeInTheDocument();
    expect(screen.getByText("MIT")).toBeInTheDocument();
    expect(screen.getByText("Mentions de transparence")).toBeInTheDocument();
    expect(
      screen.getByText("Confidentialité et conditions d'utilisation (provisoires)"),
    ).toBeInTheDocument();
    expect(screen.getByText(/aucun envoi automatique/i)).toBeInTheDocument();
  });
});
