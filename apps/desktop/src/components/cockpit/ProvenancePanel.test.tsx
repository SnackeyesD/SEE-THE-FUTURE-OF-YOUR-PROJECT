import type { Provenance, ProviderProfile, SimulationExplainResult } from "@see/protocol";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const ipc = vi.hoisted(() => ({
  getProvenance: vi.fn(),
  explainMetric: vi.fn(),
  listProfiles: vi.fn(),
  listRoles: vi.fn(),
}));

vi.mock("../../lib/ipc", () => ipc);

import { ProvenancePanel } from "./ProvenancePanel";

const provenance: Provenance = {
  runId: "run-1",
  metric: "profit_p50",
  point: null,
  definition: "Profit cumulé médian (P50) sur l'horizon.",
  formula: "Quantile P50 des profits cumulés des runs.",
  value: 12_500,
  unit: "XOF",
  range: [1_000, 20_000],
  seed: 42,
  engineVersion: "0.4.0",
  runs: 500,
  scenariosHash: "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
  inputs: [
    {
      key: "unit_price",
      label: "Prix de vente unitaire",
      value: 15,
      drawnRange: [10, 20],
      source: "user",
      confidence: 0.8,
      benchmark: null,
      correlation: 0.7,
      contribution: 1,
    },
  ],
  caveats: ["La sensibilité est une corrélation, pas une relation causale."],
};

const profile: ProviderProfile = {
  id: "profile-1",
  projectId: "project-1",
  name: "Narrateur",
  provider: "openai",
  baseUrl: null,
  model: "gpt-test",
  keychainRef: null,
  capabilities: {},
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

function fallback(): SimulationExplainResult {
  return {
    explanation: {
      summary: "La valeur vient du calcul du moteur.",
      points: [],
      caveats: [],
    },
    source: "fallback",
    model: null,
    promptVersion: "provenance-v1",
    cached: false,
    repaired: false,
    reason: "no_provider",
    provenance,
  };
}

function llm(): SimulationExplainResult {
  return {
    ...fallback(),
    source: "llm",
    model: "gpt-test",
    reason: null,
  };
}

function renderPanel() {
  return render(
    <ProvenancePanel
      projectId="project-1"
      runId="run-1"
      target={{ metric: "profit_p50", point: null }}
      onClose={() => undefined}
    />,
  );
}

describe("ProvenancePanel", () => {
  it("affiche la provenance du sidecar sans recalcul", async () => {
    ipc.getProvenance.mockResolvedValue({ provenance });
    ipc.listProfiles.mockResolvedValue({ profiles: [] });
    ipc.listRoles.mockResolvedValue({ assignments: [] });

    renderPanel();

    expect(await screen.findByText(provenance.definition)).toBeInTheDocument();
    expect(screen.getByText("Formule : Quantile P50 des profits cumulés des runs.")).toBeInTheDocument();
    expect(screen.getByText("Prix de vente unitaire")).toBeInTheDocument();
    expect(ipc.getProvenance).toHaveBeenCalledWith({
      runId: "run-1",
      metric: "profit_p50",
      point: null,
    });
    await waitFor(() => expect(ipc.listRoles).toHaveBeenCalled());
  });

  it("propose toujours le repli déterministe sans fournisseur", async () => {
    ipc.getProvenance.mockResolvedValue({ provenance });
    ipc.listProfiles.mockResolvedValue({ profiles: [] });
    ipc.listRoles.mockResolvedValue({ assignments: [] });
    ipc.explainMetric.mockResolvedValue(fallback());

    renderPanel();
    await screen.findByText(provenance.definition);
    expect(screen.queryByText("Expliquer avec l'IA")).not.toBeInTheDocument();
    expect(screen.getByText(/l'explication IA\s+est désactivée/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Explication déterministe" }));

    expect(await screen.findByText("La valeur vient du calcul du moteur.")).toBeInTheDocument();
    expect(screen.getByText("repli déterministe")).toBeInTheDocument();
    expect(ipc.explainMetric).toHaveBeenCalledWith({
      projectId: "project-1",
      runId: "run-1",
      metric: "profit_p50",
      point: null,
    });
  });

  it("active l'explication IA seulement avec un fournisseur configuré", async () => {
    ipc.getProvenance.mockResolvedValue({ provenance });
    ipc.listProfiles.mockResolvedValue({ profiles: [profile] });
    ipc.listRoles.mockResolvedValue({
      assignments: [
        {
          id: "role-1",
          projectId: "project-1",
          role: "narrator",
          providerProfileId: "profile-1",
          model: "gpt-test",
          createdAt: "2026-01-01T00:00:00Z",
          updatedAt: "2026-01-01T00:00:00Z",
        },
      ],
    });
    ipc.explainMetric.mockResolvedValue(llm());

    renderPanel();
    await screen.findByText(provenance.definition);
    const button = await screen.findByRole("button", { name: "Expliquer avec l'IA" });
    fireEvent.click(button);

    expect(
      await screen.findByText("généré à partir des données ci-dessus"),
    ).toBeInTheDocument();
    expect(ipc.explainMetric).toHaveBeenCalledWith({
      projectId: "project-1",
      runId: "run-1",
      metric: "profit_p50",
      point: null,
      profile,
      model: "gpt-test",
    });
  });

  it("affiche une erreur explicite quand la provenance échoue", async () => {
    ipc.getProvenance.mockRejectedValue(new Error("run inconnu ou expiré"));
    ipc.listProfiles.mockResolvedValue({ profiles: [] });
    ipc.listRoles.mockResolvedValue({ assignments: [] });

    renderPanel();

    expect(await screen.findByText("Provenance indisponible")).toBeInTheDocument();
    expect(screen.getByText(/run inconnu ou expiré/)).toBeInTheDocument();
  });
});
