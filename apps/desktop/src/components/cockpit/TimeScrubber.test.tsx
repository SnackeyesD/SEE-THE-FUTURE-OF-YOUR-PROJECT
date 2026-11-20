import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TimeScrubber } from "./TimeScrubber";

function renderScrubber(
  overrides: Partial<Parameters<typeof TimeScrubber>[0]> = {},
) {
  const onMonthChange = vi.fn();
  const onTogglePlay = vi.fn();
  render(
    <TimeScrubber
      month={7}
      horizon={12}
      playing={false}
      onMonthChange={onMonthChange}
      onTogglePlay={onTogglePlay}
      {...overrides}
    />,
  );
  return { onMonthChange, onTogglePlay };
}

describe("TimeScrubber", () => {
  it("affiche le mois sélectionné et les jalons trimestriels", () => {
    renderScrubber();
    expect(screen.getByText(/Mois 7 \/ 12/)).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: "Mois sélectionné" })).toHaveValue("7");
    expect(screen.getByRole("button", { name: "1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "4" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "10" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "12" })).toBeInTheDocument();
  });

  it("remonte un changement de mois sans calcul", () => {
    const { onMonthChange } = renderScrubber();
    fireEvent.change(screen.getByRole("slider", { name: "Mois sélectionné" }), {
      target: { value: "4" },
    });
    expect(onMonthChange).toHaveBeenCalledWith(4);

    fireEvent.click(screen.getByRole("button", { name: "10" }));
    expect(onMonthChange).toHaveBeenCalledWith(10);
  });

  it("bascule lecture/pause", () => {
    const { onTogglePlay } = renderScrubber({ playing: true });
    const toggle = screen.getByRole("button", { name: "Pause" });
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(toggle);
    expect(onTogglePlay).toHaveBeenCalledTimes(1);
  });

  it("se désactive pendant un calcul", () => {
    renderScrubber({ disabled: true });
    expect(screen.getByRole("button", { name: "Lecture" })).toBeDisabled();
    expect(screen.getByRole("slider", { name: "Mois sélectionné" })).toBeDisabled();
  });

  it("borne l'affichage quand l'horizon est nul", () => {
    renderScrubber({ month: null, horizon: 0 });
    expect(screen.getByText(/Mois —/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Lecture" })).toBeDisabled();
  });
});
