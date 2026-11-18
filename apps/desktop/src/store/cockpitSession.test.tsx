import type { Scenario } from "@see/protocol";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { usePersistentLayout } from "../hooks/usePersistentLayout";
import {
  layoutFromPreset,
  layoutStorageKey,
  type StorageLike,
} from "./layout";
import { CockpitProvider, useCockpitContext } from "./CockpitProvider";
import { useCockpit } from "./cockpitStore";
import { snapshotCommand } from "./commands";

const scenario: Scenario = {
  schemaVersion: "1.1.0",
  name: "Base",
  model: "retail_depot",
  assumptions: { demand: { value: 100 } },
  events: [],
};

function memoryStorage(): StorageLike & { entries: Map<string, string> } {
  const entries = new Map<string, string>();
  return {
    entries,
    getItem: (key) => entries.get(key) ?? null,
    setItem: (key, value) => {
      entries.set(key, value);
    },
  };
}

function Probe() {
  const { store, inputs, applyLayout } = useCockpitContext();
  const value = useCockpit(
    store,
    (state) => state.session.scenario.assumptions?.demand.value ?? 0,
  );
  const preset = useCockpit(store, (state) => state.layout.preset);

  const increase = () => {
    const before = store.getState().session.scenario;
    const after: Scenario = {
      ...before,
      assumptions: {
        ...before.assumptions,
        demand: { value: (before.assumptions?.demand.value ?? 0) + 1 },
      },
    };
    inputs.dispatch(
      snapshotCommand({
        label: "Demande",
        before,
        after,
        apply: (next) => store.getState().setScenario(next),
        coalesceKey: "demand",
      }),
    );
  };

  return (
    <div>
      <output data-testid="value">{value}</output>
      <output data-testid="preset">{preset}</output>
      <button type="button" onClick={increase}>
        Augmenter
      </button>
      <button type="button" onClick={() => applyLayout(layoutFromPreset("pilotage"))}>
        Pilotage
      </button>
      <input aria-label="champ" defaultValue="" />
    </div>
  );
}

function renderApp(storage = memoryStorage()) {
  const onInputsChanged = vi.fn();
  const view = render(
    <CockpitProvider
      projectId="p1"
      scenario={scenario}
      storage={storage}
      onInputsChanged={onInputsChanged}
    >
      <Probe />
    </CockpitProvider>,
  );
  return { ...view, storage, onInputsChanged };
}

describe("session cockpit — commandes et disposition", () => {
  it("Ctrl+Z et Ctrl+Y restaurent les entrées et notifient le contrôleur", async () => {
    const user = userEvent.setup();
    const { onInputsChanged } = renderApp();

    expect(screen.getByTestId("value")).toHaveTextContent("100");
    await user.click(screen.getByRole("button", { name: "Augmenter" }));
    expect(screen.getByTestId("value")).toHaveTextContent("101");
    expect(onInputsChanged).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(window, { key: "z", ctrlKey: true });
    expect(screen.getByTestId("value")).toHaveTextContent("100");
    expect(onInputsChanged).toHaveBeenCalledTimes(2);

    fireEvent.keyDown(window, { key: "y", ctrlKey: true });
    expect(screen.getByTestId("value")).toHaveTextContent("101");
    expect(onInputsChanged).toHaveBeenCalledTimes(3);
  });

  it("laisse l'undo natif aux champs de saisie", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.click(screen.getByRole("button", { name: "Augmenter" }));
    const field = screen.getByLabelText("champ");
    field.focus();
    fireEvent.keyDown(field, { key: "z", ctrlKey: true });

    expect(screen.getByTestId("value")).toHaveTextContent("101");
  });

  it("garde la disposition hors de l'historique des hypothèses", async () => {
    const user = userEvent.setup();
    const { storage } = renderApp();

    await user.click(screen.getByRole("button", { name: "Augmenter" }));
    await user.click(screen.getByRole("button", { name: "Pilotage" }));
    expect(screen.getByTestId("preset")).toHaveTextContent("pilotage");

    fireEvent.keyDown(window, { key: "z", ctrlKey: true });

    expect(screen.getByTestId("value")).toHaveTextContent("100");
    expect(screen.getByTestId("preset")).toHaveTextContent("pilotage");
    expect(storage.entries.has(layoutStorageKey("p1"))).toBe(true);
    expect(storage.getItem(layoutStorageKey("p1"))).toContain('"preset":"pilotage"');
  });

  it("persiste la disposition hors du provider via le hook", () => {
    const storage = memoryStorage();

    function LayoutProbe() {
      const [layout, setLayout] = usePersistentLayout("p1", storage);
      return (
        <button type="button" onClick={() => setLayout(layoutFromPreset("presentation"))}>
          {layout.preset}
        </button>
      );
    }

    render(<LayoutProbe />);
    fireEvent.click(screen.getByRole("button", { name: "analyse" }));
    expect(storage.getItem(layoutStorageKey("p1"))).toContain('"preset":"presentation"');
  });
});
