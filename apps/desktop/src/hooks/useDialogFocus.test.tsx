import { fireEvent, render, screen } from "@testing-library/react";
import { useRef, useState } from "react";
import { describe, expect, it } from "vitest";

import { useDialogFocus } from "./useDialogFocus";

function Dialog({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useDialogFocus(ref, onClose);
  return (
    <div ref={ref} role="dialog" aria-label="Dialogue">
      <button type="button">Premier</button>
      <button type="button">Dernier</button>
    </div>
  );
}

function Harness() {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>
        Ouvrir
      </button>
      {open ? <Dialog onClose={() => setOpen(false)} /> : null}
    </div>
  );
}

describe("useDialogFocus", () => {
  it("place le focus dans le dialogue et le restitue à la fermeture", () => {
    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "Ouvrir" });

    // En jsdom un clic synthétique ne déplace pas le focus : on le simule,
    // comme le ferait un navigateur avant l'ouverture du dialogue.
    trigger.focus();
    fireEvent.click(trigger);
    expect(screen.getByRole("button", { name: "Premier" })).toHaveFocus();

    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("piège la tabulation entre le premier et le dernier élément", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Ouvrir" }));

    const first = screen.getByRole("button", { name: "Premier" });
    const last = screen.getByRole("button", { name: "Dernier" });
    last.focus();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Tab" });
    expect(first).toHaveFocus();

    first.focus();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Tab", shiftKey: true });
    expect(last).toHaveFocus();
  });
});
