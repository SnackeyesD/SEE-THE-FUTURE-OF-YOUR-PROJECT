import type {
  BranchRef,
  Project,
  ProjectRunCompareResult,
  RunRef,
  Scenario,
  ScenarioVersionRef,
} from "@see/protocol";
import { Badge, Button, InlineAlert, Tabs } from "@see/ui";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useUndoRedoHotkeys } from "../hooks/useUndoRedoHotkeys";
import {
  archiveScenario,
  branchProjectScenario,
  compareRuns,
  createVersion,
  deleteVersion,
  getScenario,
  listBranches,
  listRuns,
  listVersions,
  pinRun,
  renameScenario,
  restoreVersion,
  unarchiveScenario,
} from "../lib/ipc";
import { diffScenarios, type DiffEntry } from "../lib/scenarioDiff";
import { CommandStack } from "../store/commands";
import { BranchDiff } from "../components/branches/BranchDiff";
import { BranchList } from "../components/branches/BranchList";
import { ComparisonView } from "../components/branches/ComparisonView";
import { VersionList } from "../components/branches/VersionList";

export interface BranchesScreenProps {
  project: Project;
  activeScenarioId: string | null;
  currency: string;
  onOpenBranch: (scenarioId: string) => Promise<void> | void;
  onChanged?: () => void;
}

const TABS = [
  { id: "branches", label: "Branches & diff" },
  { id: "compare", label: "Comparer" },
  { id: "versions", label: "Versions" },
];

function humanize(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error);
  return text.replace(/^Error:\s*/i, "");
}

function displayName(branch: BranchRef): string {
  return branch.branchLabel?.trim() || branch.name;
}

/**
 * Écran « Branches & comparaison » (phase 13).
 *
 * Il ne calcule rien : il pilote les méthodes `project.scenario.*`,
 * `project.run.*` et `project.version.*`, affiche le diff pur de
 * `lib/scenarioDiff` et laisse le sidecar refuser les comparaisons
 * incohérentes (graine, moteur).
 */
export function BranchesScreen({
  project,
  activeScenarioId,
  currency,
  onOpenBranch,
  onChanged,
}: BranchesScreenProps) {
  const stackRef = useRef<CommandStack | null>(null);
  if (stackRef.current === null) stackRef.current = new CommandStack();
  const stack = stackRef.current;
  useUndoRedoHotkeys(stack);

  const [tab, setTab] = useState("branches");
  const [branches, setBranches] = useState<BranchRef[]>([]);
  const [versions, setVersions] = useState<ScenarioVersionRef[]>([]);
  const [runs, setRuns] = useState<RunRef[]>([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [diff, setDiff] = useState<DiffEntry[]>([]);
  const [runIds, setRunIds] = useState<[string | null, string | null]>([null, null]);
  const [comparison, setComparison] = useState<ProjectRunCompareResult | null>(null);
  const [comparing, setComparing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pendingArchive, setPendingArchive] = useState<BranchRef | null>(null);
  const [stackTick, setStackTick] = useState(0);

  useEffect(() => stack.subscribe(() => setStackTick((value) => value + 1)), [stack]);

  const reload = useCallback(async () => {
    const [branchResult, versionResult, runResult] = await Promise.all([
      listBranches({ projectId: project.id, includeArchived }),
      listVersions({ projectId: project.id }),
      listRuns({ projectId: project.id, limit: 200 }),
    ]);
    setBranches(branchResult.branches);
    setVersions(versionResult.versions);
    setRuns(runResult.runs);
  }, [includeArchived, project.id]);

  useEffect(() => {
    let cancelled = false;
    reload().catch((reason) => {
      if (!cancelled) setError(humanize(reason));
    });
    return () => {
      cancelled = true;
    };
  }, [reload]);

  // Diff des deux branches sélectionnées.
  useEffect(() => {
    let cancelled = false;
    if (compareIds.length !== 2) {
      setDiff([]);
      return;
    }
    Promise.all(
      compareIds.map((scenarioId) =>
        getScenario({ projectId: project.id, scenarioId }).then(
          (result) => result.scenario.scenario as Scenario,
        ),
      ),
    )
      .then(([left, right]) => {
        if (!cancelled) setDiff(diffScenarios(left, right));
      })
      .catch((reason) => {
        if (!cancelled) setError(humanize(reason));
      });
    return () => {
      cancelled = true;
    };
  }, [compareIds, project.id]);

  // Sélection par défaut de deux runs comparables.
  useEffect(() => {
    setRunIds((current) => {
      const stillThere = (id: string | null) =>
        id !== null && runs.some((run) => run.id === id);
      if (stillThere(current[0]) && stillThere(current[1])) return current;
      const first = runs[0]?.id ?? null;
      const second =
        runs.find((run) => run.id !== first && run.seed === runs[0]?.seed)?.id ??
        runs.find((run) => run.id !== first)?.id ??
        null;
      return [first, second];
    });
  }, [runs]);

  useEffect(() => {
    let cancelled = false;
    const [left, right] = runIds;
    if (!left || !right) {
      setComparison(null);
      return;
    }
    setComparing(true);
    compareRuns({ projectId: project.id, runIds: [left, right] })
      .then((result) => {
        if (!cancelled) setComparison(result);
      })
      .catch((reason) => {
        if (!cancelled) setError(humanize(reason));
      })
      .finally(() => {
        if (!cancelled) setComparing(false);
      });
    return () => {
      cancelled = true;
    };
  }, [project.id, runIds]);

  const refreshAll = useCallback(async () => {
    await reload();
    onChanged?.();
  }, [onChanged, reload]);

  const toggleCompare = useCallback((scenarioId: string) => {
    setCompareIds((current) => {
      if (current.includes(scenarioId)) {
        return current.filter((id) => id !== scenarioId);
      }
      if (current.length < 2) return [...current, scenarioId];
      return [current[1], scenarioId];
    });
  }, []);

  const duplicateBranch = useCallback(
    async (branch: BranchRef, label: string) => {
      setBusy(true);
      setError(null);
      try {
        const created = await branchProjectScenario({
          projectId: project.id,
          scenarioId: branch.scenarioId,
          label,
        });
        const createdId = created.scenario.id;
        let firstRun = true;
        stack.dispatch({
          label: `Créer la branche ${label}`,
          undo: () => {
            void archiveScenario({
              projectId: project.id,
              scenarioId: createdId,
              confirmPinned: true,
            })
              .then(refreshAll)
              .catch((reason) => setError(humanize(reason)));
          },
          redo: () => {
            if (firstRun) {
              firstRun = false;
              return;
            }
            void unarchiveScenario({
              projectId: project.id,
              scenarioId: createdId,
            })
              .then(refreshAll)
              .catch((reason) => setError(humanize(reason)));
          },
        });
        setNotice(`Branche « ${label} » créée.`);
        await refreshAll();
        await onOpenBranch(createdId);
      } catch (reason) {
        setError(humanize(reason));
      } finally {
        setBusy(false);
      }
    },
    [onOpenBranch, project.id, refreshAll, stack],
  );

  const renameBranch = useCallback(
    (branch: BranchRef, newName: string) => {
      const previousName = branch.name;
      const previousLabel = branch.branchLabel;
      setError(null);
      stack.dispatch({
        label: "Renommer la branche",
        undo: () => {
          void renameScenario({
            projectId: project.id,
            scenarioId: branch.scenarioId,
            name: previousName,
            branchLabel: previousLabel,
          })
            .then(refreshAll)
            .catch((reason) => setError(humanize(reason)));
        },
        redo: () => {
          void renameScenario({
            projectId: project.id,
            scenarioId: branch.scenarioId,
            name: newName,
            branchLabel: newName,
          })
            .then(refreshAll)
            .catch((reason) => setError(humanize(reason)));
        },
      });
      setNotice(`Branche renommée en « ${newName} ».`);
    },
    [project.id, refreshAll, stack],
  );

  const archiveBranch = useCallback(
    (branch: BranchRef, confirmPinned: boolean) => {
      setError(null);
      setPendingArchive(null);
      stack.dispatch({
        label: `Archiver ${displayName(branch)}`,
        undo: () => {
          void unarchiveScenario({
            projectId: project.id,
            scenarioId: branch.scenarioId,
          })
            .then(refreshAll)
            .catch((reason) => setError(humanize(reason)));
        },
        redo: () => {
          void archiveScenario({
            projectId: project.id,
            scenarioId: branch.scenarioId,
            confirmPinned,
          })
            .then(refreshAll)
            .catch((reason) => setError(humanize(reason)));
        },
      });
      setNotice(`Branche « ${displayName(branch)} » archivée.`);
    },
    [project.id, refreshAll, stack],
  );

  const requestArchive = useCallback(
    (branch: BranchRef) => {
      const pinned = runs.filter(
        (run) => run.scenarioId === branch.scenarioId && run.pinned,
      );
      if (pinned.length > 0) {
        setPendingArchive(branch);
        return;
      }
      archiveBranch(branch, false);
    },
    [archiveBranch, runs],
  );

  const restoreArchived = useCallback(
    (branch: BranchRef) => {
      setError(null);
      stack.dispatch({
        label: `Restaurer ${displayName(branch)}`,
        undo: () => {
          void archiveScenario({
            projectId: project.id,
            scenarioId: branch.scenarioId,
            confirmPinned: true,
          })
            .then(refreshAll)
            .catch((reason) => setError(humanize(reason)));
        },
        redo: () => {
          void unarchiveScenario({
            projectId: project.id,
            scenarioId: branch.scenarioId,
          })
            .then(refreshAll)
            .catch((reason) => setError(humanize(reason)));
        },
      });
      setNotice(`Branche « ${displayName(branch)} » restaurée.`);
    },
    [project.id, refreshAll, stack],
  );

  const saveVersion = useCallback(
    (label: string) => {
      setError(null);
      void createVersion({ projectId: project.id, label })
        .then((created) => {
          let versionId = created.version.id;
          let firstRun = true;
          stack.dispatch({
            label: `Créer la version ${label}`,
            undo: () => {
              void deleteVersion({ projectId: project.id, versionId })
                .then(refreshAll)
                .catch((reason) => setError(humanize(reason)));
            },
            redo: () => {
              if (firstRun) {
                firstRun = false;
                return;
              }
              void createVersion({ projectId: project.id, label })
                .then((result) => {
                  versionId = result.version.id;
                  return refreshAll();
                })
                .catch((reason) => setError(humanize(reason)));
            },
          });
          setNotice(`Version « ${label} » enregistrée.`);
          return refreshAll();
        })
        .catch((reason) => setError(humanize(reason)));
    },
    [project.id, refreshAll, stack],
  );

  const restoreSavedVersion = useCallback(
    (version: ScenarioVersionRef) => {
      setError(null);
      void restoreVersion({ projectId: project.id, versionId: version.id })
        .then((restored) => {
          const createdId = restored.scenario.id;
          let firstRun = true;
          stack.dispatch({
            label: `Restaurer la version ${version.label}`,
            undo: () => {
              void archiveScenario({
                projectId: project.id,
                scenarioId: createdId,
                confirmPinned: true,
              })
                .then(refreshAll)
                .catch((reason) => setError(humanize(reason)));
            },
            redo: () => {
              if (firstRun) {
                firstRun = false;
                return;
              }
              void unarchiveScenario({
                projectId: project.id,
                scenarioId: createdId,
              })
                .then(refreshAll)
                .catch((reason) => setError(humanize(reason)));
            },
          });
          setNotice(`Version « ${version.label} » restaurée en nouvelle branche.`);
          return refreshAll();
        })
        .catch((reason) => setError(humanize(reason)));
    },
    [project.id, refreshAll, stack],
  );

  const removeVersion = useCallback(
    (version: ScenarioVersionRef) => {
      setError(null);
      void deleteVersion({ projectId: project.id, versionId: version.id })
        .then(() => {
          setNotice(`Version « ${version.label} » supprimée.`);
          return refreshAll();
        })
        .catch((reason) => setError(humanize(reason)));
    },
    [project.id, refreshAll],
  );

  const togglePin = useCallback(
    (run: RunRef, pinned: boolean) => {
      setError(null);
      void pinRun({ projectId: project.id, runId: run.id, pinned })
        .then(refreshAll)
        .catch((reason) => setError(humanize(reason)));
    },
    [project.id, refreshAll],
  );

  const openBranch = useCallback(
    (branch: BranchRef) => {
      void Promise.resolve(onOpenBranch(branch.scenarioId)).catch((reason) =>
        setError(humanize(reason)),
      );
    },
    [onOpenBranch],
  );

  const leftBranch = branches.find((branch) => branch.scenarioId === compareIds[0]);
  const rightBranch = branches.find((branch) => branch.scenarioId === compareIds[1]);
  const limitReached = branches.filter((branch) => branch.archivedAt === null).length >= 20;
  const historyLabel = useMemo(() => {
    void stackTick;
    return {
      canUndo: stack.canUndo,
      canRedo: stack.canRedo,
      undoLabel: stack.undoLabel,
      redoLabel: stack.redoLabel,
    };
  }, [stack, stackTick]);

  return (
    <section className="screen branches-screen" aria-labelledby="branches-title">
      <header className="screen__heading">
        <div>
          <h1 id="branches-title">Branches &amp; comparaison</h1>
          <p className="ui-muted">
            Dupliquez un scénario, comparez deux branches ou deux runs avec la même
            graine, et figez des versions. Les calculs restent dans le moteur.
          </p>
        </div>
        <div className="ui-actions">
          <Button
            variant="ghost"
            size="small"
            disabled={!historyLabel.canUndo}
            title={historyLabel.undoLabel ?? undefined}
            onClick={() => stack.undo()}
          >
            Annuler
          </Button>
          <Button
            variant="ghost"
            size="small"
            disabled={!historyLabel.canRedo}
            title={historyLabel.redoLabel ?? undefined}
            onClick={() => stack.redo()}
          >
            Refaire
          </Button>
        </div>
      </header>

      {error ? (
        <InlineAlert tone="danger" title="Action impossible">
          {error}
          <div className="ui-actions">
            <Button variant="ghost" size="small" onClick={() => setError(null)}>
              Fermer
            </Button>
          </div>
        </InlineAlert>
      ) : null}
      {notice ? (
        <InlineAlert tone="ok" title="Action effectuée">
          {notice}
          <div className="ui-actions">
            <Button variant="ghost" size="small" onClick={() => setNotice(null)}>
              Fermer
            </Button>
          </div>
        </InlineAlert>
      ) : null}
      {pendingArchive ? (
        <InlineAlert tone="warn" title="Des runs épinglés référencent cette branche">
          Archiver «&nbsp;{displayName(pendingArchive)}&nbsp;» conserve les runs, mais la
          branche disparaîtra de la liste. Confirmez-vous ?
          <div className="ui-actions">
            <Button
              variant="danger"
              size="small"
              disabled={busy}
              onClick={() => archiveBranch(pendingArchive, true)}
            >
              Confirmer l'archivage
            </Button>
            <Button
              variant="ghost"
              size="small"
              onClick={() => setPendingArchive(null)}
            >
              Annuler
            </Button>
          </div>
        </InlineAlert>
      ) : null}

      <Tabs items={TABS} value={tab} onChange={setTab} ariaLabel="Sections branches" />

      <div hidden={tab !== "branches"} className="branches-screen__panel">
        <div className="branches-screen__toolbar">
          <label className="ui-field ui-field--checkbox">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(event) => setIncludeArchived(event.target.checked)}
            />
            <span>Afficher les branches archivées</span>
          </label>
          <Badge tone={limitReached ? "warn" : "neutral"}>
            {branches.filter((branch) => branch.archivedAt === null).length} / 20 branches
            actives
          </Badge>
        </div>

        <BranchList
          branches={branches}
          activeBranchId={activeScenarioId}
          compareIds={compareIds}
          limitReached={limitReached}
          busy={busy}
          onSelectCompare={toggleCompare}
          onOpen={openBranch}
          onDuplicate={(branch, label) => void duplicateBranch(branch, label)}
          onRename={renameBranch}
          onArchive={requestArchive}
          onUnarchive={restoreArchived}
        />

        {compareIds.length === 2 ? (
          <section className="branches-screen__diff" aria-label="Diff des branches">
            <h2>
              Diff : {leftBranch ? displayName(leftBranch) : "branche A"} →{" "}
              {rightBranch ? displayName(rightBranch) : "branche B"}
            </h2>
            <BranchDiff
              entries={diff}
              leftLabel={leftBranch ? displayName(leftBranch) : "Branche A"}
              rightLabel={rightBranch ? displayName(rightBranch) : "Branche B"}
            />
          </section>
        ) : (
          <p className="ui-muted">
            Sélectionnez deux branches avec « Comparer » pour afficher leur diff.
          </p>
        )}
      </div>

      <div hidden={tab !== "compare"} className="branches-screen__panel">
        <ComparisonView
          runs={runs}
          runIds={runIds}
          comparison={comparison}
          currency={currency}
          loading={comparing}
          error={null}
          onSelect={(side, runId) =>
            setRunIds((current) =>
              side === 0 ? [runId, current[1]] : [current[0], runId],
            )
          }
          onPin={togglePin}
        />
      </div>

      <div hidden={tab !== "versions"} className="branches-screen__panel">
        <VersionList
          versions={versions}
          busy={busy}
          suggestedLabel={`Version du ${new Date().toLocaleDateString("fr-FR")}`}
          onCreate={saveVersion}
          onRestore={restoreSavedVersion}
          onDelete={removeVersion}
        />
      </div>
    </section>
  );
}
