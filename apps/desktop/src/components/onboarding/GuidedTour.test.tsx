import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GuidedTour, TOUR_STEPS } from "./GuidedTour";

beforeEach(() => {
  window.localStorage.clear();
});

describe("GuidedTour", () => {
  it("propose la première étape et avance vers la vue suivante", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(<GuidedTour projectId="project-1" onNavigate={onNavigate} />);

    expect(screen.getByText(TOUR_STEPS[0].title)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Suivant" }));

    expect(screen.getByText(TOUR_STEPS[1].title)).toBeInTheDocument();
    expect(onNavigate).toHaveBeenCalledWith(TOUR_STEPS[1].view);
  });

  it("se ferme et ne réapparaît plus pour le même projet", async () => {
    const user = userEvent.setup();
    const { unmount } = render(
      <GuidedTour projectId="project-1" onNavigate={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "Passer le parcours" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(window.localStorage.getItem("seefuture.tour.project-1")).toBe("done");

    unmount();
    render(<GuidedTour projectId="project-1" onNavigate={vi.fn()} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("reste réinitialisable pour un autre projet", () => {
    window.localStorage.setItem("seefuture.tour.project-1", "done");
    render(<GuidedTour projectId="project-2" onNavigate={vi.fn()} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("se ferme avec Échap sans naviguer", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(<GuidedTour projectId="project-3" onNavigate={onNavigate} />);

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(onNavigate).not.toHaveBeenCalled();
  });
});
