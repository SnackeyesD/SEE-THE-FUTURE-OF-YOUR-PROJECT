import type { BranchRef } from "@see/protocol";
import { Badge, Button } from "@see/ui";
import { useState } from "react";

import { formatDateTime, formatNumber } from "../../lib/format";

export interface BranchListProps {
  branches: readonly BranchRef[];
  activeBranchId: string | null;
  compareIds: readonly string[];
  limitReached: boolean;
  busy?: boolean;
  onSelectCompare?: (scenarioId: string) => void;
  onOpen?: (branch: BranchRef) => void;
  onDuplicate?: (branch: BranchRef, label: string) => void;
  onRename?: (branch: BranchRef, name: string) => void;
  onArchive?: (branch: BranchRef) => void;
  onUnarchive?: (branch: BranchRef) => void;
}

function displayName(branch: BranchRef): string {
  return branch.branchLabel?.trim() || branch.name;
}

/**
 * Liste plate des branches (phase 13). Pas de hiérarchie complexe : un badge
 * « branche de … » suffit, et les actions sont explicites. Les formulaires
 * de renommage et de duplication restent locaux au composant.
 */
export function BranchList({
  branches,
  activeBranchId,
  compareIds,
  limitReached,
  busy = false,
  onSelectCompare,
  onOpen,
  onDuplicate,
  onRename,
  onArchive,
  onUnarchive,
}: BranchListProps) {
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [duplicatingId, setDuplicatingId] = useState<string | null>(null);
  const [duplicateDraft, setDuplicateDraft] = useState("");

  const parentNames = new Map(
    branches.map((branch) => [branch.scenarioId, displayName(branch)]),
  );

  function startRename(branch: BranchRef): void {
    setRenamingId(branch.scenarioId);
    setRenameDraft(displayName(branch));
  }

  function submitRename(branch: BranchRef): void {
    const name = renameDraft.trim();
    if (!name) return;
    onRename?.(branch, name);
    setRenamingId(null);
  }

  function startDuplicate(branch: BranchRef): void {
    setDuplicatingId(branch.scenarioId);
    setDuplicateDraft(`${displayName(branch)} — variante`);
  }

  function submitDuplicate(branch: BranchRef): void {
    const label = duplicateDraft.trim();
    if (!label) return;
    onDuplicate?.(branch, label);
    setDuplicatingId(null);
  }

  return (
    <div className="branch-list">
      <ul className="branch-list__items">
        {branches.map((branch) => {
          const archived = branch.archivedAt !== null;
          const selected = compareIds.includes(branch.scenarioId);
          return (
            <li
              key={branch.scenarioId}
              className="branch-list__item"
              data-active={branch.scenarioId === activeBranchId}
            >
              <div className="branch-list__head">
                <div>
                  <strong>{displayName(branch)}</strong>
                  {branch.scenarioId === activeBranchId ? (
                    <Badge tone="ok">branche courante</Badge>
                  ) : null}
                  {archived ? <Badge tone="neutral">archivée</Badge> : null}
                  {branch.parentId ? (
                    <span className="ui-muted">
                      branche de {parentNames.get(branch.parentId) ?? "scénario source"}
                    </span>
                  ) : (
                    <span className="ui-muted">scénario racine</span>
                  )}
                </div>
                <div className="ui-actions">
                  <Button
                    variant={selected ? "primary" : "ghost"}
                    size="small"
                    aria-pressed={selected}
                    aria-label={`Comparer la branche ${displayName(branch)}`}
                    onClick={() => onSelectCompare?.(branch.scenarioId)}
                  >
                    {selected ? "Comparée" : "Comparer"}
                  </Button>
                  <Button
                    variant="secondary"
                    size="small"
                    disabled={busy || archived}
                    onClick={() => onOpen?.(branch)}
                  >
                    Ouvrir
                  </Button>
                  <Button
                    variant="ghost"
                    size="small"
                    disabled={busy || archived}
                    onClick={() => startRename(branch)}
                  >
                    Renommer
                  </Button>
                  <Button
                    variant="ghost"
                    size="small"
                    disabled={busy || archived || limitReached}
                    title={
                      limitReached
                        ? "Limite de 20 branches actives atteinte"
                        : undefined
                    }
                    onClick={() => startDuplicate(branch)}
                  >
                    Dupliquer
                  </Button>
                  {archived ? (
                    <Button
                      variant="ghost"
                      size="small"
                      disabled={busy}
                      onClick={() => onUnarchive?.(branch)}
                    >
                      Restaurer
                    </Button>
                  ) : (
                    <Button
                      variant="danger"
                      size="small"
                      disabled={busy}
                      onClick={() => onArchive?.(branch)}
                    >
                      Archiver
                    </Button>
                  )}
                </div>
              </div>
              <div className="branch-list__meta ui-muted">
                <span>Mise à jour {formatDateTime(branch.updatedAt)}</span>
                {branch.seed === null ? (
                  <span>Aucun run final</span>
                ) : (
                  <span>Graine du dernier run final : {formatNumber(branch.seed)}</span>
                )}
                {branch.lastFinalRunId ? (
                  <span>Run {branch.lastFinalRunId.slice(0, 8)}…</span>
                ) : null}
              </div>

              {renamingId === branch.scenarioId ? (
                <form
                  className="branch-list__form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    submitRename(branch);
                  }}
                >
                  <label>
                    <span>Nouveau nom</span>
                    <input
                      value={renameDraft}
                      onChange={(event) => setRenameDraft(event.target.value)}
                      aria-label={`Nouveau nom pour ${displayName(branch)}`}
                    />
                  </label>
                  <Button type="submit" size="small" disabled={!renameDraft.trim()}>
                    Valider
                  </Button>
                  <Button
                    variant="ghost"
                    size="small"
                    onClick={() => setRenamingId(null)}
                  >
                    Annuler
                  </Button>
                </form>
              ) : null}

              {duplicatingId === branch.scenarioId ? (
                <form
                  className="branch-list__form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    submitDuplicate(branch);
                  }}
                >
                  <label>
                    <span>Libellé de la branche</span>
                    <input
                      value={duplicateDraft}
                      onChange={(event) => setDuplicateDraft(event.target.value)}
                      aria-label={`Libellé de la branche issue de ${displayName(branch)}`}
                    />
                  </label>
                  <Button type="submit" size="small" disabled={!duplicateDraft.trim()}>
                    Créer la branche
                  </Button>
                  <Button
                    variant="ghost"
                    size="small"
                    onClick={() => setDuplicatingId(null)}
                  >
                    Annuler
                  </Button>
                </form>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
