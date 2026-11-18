import { describe, expect, it, vi } from "vitest";

import { CommandStack, snapshotCommand } from "./commands";

function createCounter(initial = 0) {
  const state = { value: initial };
  const apply = (value: number) => {
    state.value = value;
  };
  return { state, apply };
}

describe("CommandStack", () => {
  it("applique une commande puis l'annule et la refait", () => {
    const stack = new CommandStack();
    const counter = createCounter();

    stack.dispatch(
      snapshotCommand({
        label: "Valeur",
        before: 0,
        after: 10,
        apply: counter.apply,
      }),
    );

    expect(counter.state.value).toBe(10);
    expect(stack.undoSize).toBe(1);
    expect(stack.undoLabel).toBe("Valeur");

    expect(stack.undo()).toBe(true);
    expect(counter.state.value).toBe(0);
    expect(stack.canRedo).toBe(true);

    expect(stack.redo()).toBe(true);
    expect(counter.state.value).toBe(10);
  });

  it("fusionne les commandes de même clé dans la fenêtre de coalescence", () => {
    let now = 0;
    const stack = new CommandStack({ now: () => now });
    const counter = createCounter();

    stack.dispatch(
      snapshotCommand({
        label: "Glissement",
        before: 0,
        after: 1,
        apply: counter.apply,
        coalesceKey: "param:demand",
      }),
    );
    now = 100;
    stack.dispatch(
      snapshotCommand({
        label: "Glissement",
        before: 1,
        after: 2,
        apply: counter.apply,
        coalesceKey: "param:demand",
      }),
    );

    expect(stack.undoSize).toBe(1);
    expect(counter.state.value).toBe(2);

    stack.undo();
    expect(counter.state.value).toBe(0);
    stack.redo();
    expect(counter.state.value).toBe(2);
  });

  it("sépare les commandes après la fenêtre ou pour une autre clé", () => {
    let now = 0;
    const stack = new CommandStack({ now: () => now, coalesceWindowMs: 400 });
    const counter = createCounter();

    stack.dispatch(
      snapshotCommand({
        label: "A",
        before: 0,
        after: 1,
        apply: counter.apply,
        coalesceKey: "a",
      }),
    );
    now = 500;
    stack.dispatch(
      snapshotCommand({
        label: "A",
        before: 1,
        after: 2,
        apply: counter.apply,
        coalesceKey: "a",
      }),
    );
    now = 550;
    stack.dispatch(
      snapshotCommand({
        label: "B",
        before: 2,
        after: 3,
        apply: counter.apply,
        coalesceKey: "b",
      }),
    );

    expect(stack.undoSize).toBe(3);
  });

  it("borne la pile et oublie les commandes les plus anciennes", () => {
    const stack = new CommandStack({ limit: 100 });
    const counter = createCounter();

    for (let index = 1; index <= 120; index += 1) {
      stack.dispatch(
        snapshotCommand({
          label: `Commande ${index}`,
          before: index - 1,
          after: index,
          apply: counter.apply,
        }),
      );
    }

    expect(stack.undoSize).toBe(100);
    for (let index = 0; index < 100; index += 1) stack.undo();
    expect(stack.canUndo).toBe(false);
    expect(counter.state.value).toBe(20);
  });

  it("vide la pile de redo dès qu'une nouvelle commande est jouée", () => {
    const stack = new CommandStack();
    const counter = createCounter();

    stack.dispatch(
      snapshotCommand({ label: "A", before: 0, after: 1, apply: counter.apply }),
    );
    stack.undo();
    expect(stack.canRedo).toBe(true);

    stack.dispatch(
      snapshotCommand({ label: "B", before: 0, after: 2, apply: counter.apply }),
    );
    expect(stack.canRedo).toBe(false);
    expect(stack.redo()).toBe(false);
  });

  it("notifie les abonnés à chaque changement", () => {
    const stack = new CommandStack();
    const listener = vi.fn();
    const unsubscribe = stack.subscribe(listener);
    const counter = createCounter();

    stack.dispatch(
      snapshotCommand({ label: "A", before: 0, after: 1, apply: counter.apply }),
    );
    stack.undo();
    stack.redo();

    expect(listener).toHaveBeenCalledTimes(3);

    unsubscribe();
    stack.undo();
    expect(listener).toHaveBeenCalledTimes(3);
  });
});
