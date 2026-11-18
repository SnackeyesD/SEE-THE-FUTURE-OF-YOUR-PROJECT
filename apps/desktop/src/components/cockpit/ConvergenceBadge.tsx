import type { ConvergenceState } from "@see/protocol";
import { Badge } from "@see/ui";

import type { SessionStatus } from "../../store/cockpitStore";

/**
 * Badge de convergence : la couleur ne porte jamais seule l'information, le
 * libellé et la variation relative sont toujours présents.
 */
export function ConvergenceBadge({
  convergence,
  status,
}: {
  convergence?: ConvergenceState | null;
  status?: SessionStatus;
}) {
  if (!convergence) {
    return <Badge tone="neutral">Convergence inconnue</Badge>;
  }
  const stability = Math.round(convergence.stability * 100);
  const label = convergence.converged
    ? "Convergé"
    : status === "drafting" || status === "finalizing"
      ? `Stabilisation ${stability} %`
      : `Stabilité ${stability} %`;
  const tone = convergence.converged ? "ok" : stability >= 60 ? "warn" : "neutral";
  const detail = `Variation relative max ${(convergence.maxRelativeChange * 100).toFixed(
    1,
  )} % · ${convergence.stableBlocks} blocs stables`;
  return (
    <span title={detail}>
      <Badge tone={tone}>{label}</Badge>
    </span>
  );
}
