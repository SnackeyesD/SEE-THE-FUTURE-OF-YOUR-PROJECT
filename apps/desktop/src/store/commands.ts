export interface Command {
  label: string;
  undo: () => void;
  redo: () => void;
  /**
   * Les commandes successives portant la même clé dans la fenêtre de
   * coalescence fusionnent : une seule entrée d'undo pour tout un glissement.
   */
  coalesceKey?: string;
}

export interface CommandStackOptions {
  limit?: number;
  coalesceWindowMs?: number;
  now?: () => number;
}

export interface SnapshotCommandOptions<T> {
  label: string;
  before: T;
  after: T;
  apply: (value: T) => void;
  coalesceKey?: string;
}

export const DEFAULT_COMMAND_LIMIT = 100;
export const DEFAULT_COALESCE_WINDOW_MS = 400;

/**
 * Pile de commandes inversibles, bornée et non persistée. Deux instances
 * séparées (entrées / disposition) garantissent que le layout n'entre pas dans
 * l'historique des hypothèses.
 */
export class CommandStack {
  private readonly limit: number;
  private readonly coalesceWindowMs: number;
  private readonly now: () => number;
  private undoStack: Command[] = [];
  private redoStack: Command[] = [];
  private lastDispatchAt = Number.NEGATIVE_INFINITY;
  private readonly listeners = new Set<() => void>();

  constructor(options: CommandStackOptions = {}) {
    this.limit = Math.max(1, options.limit ?? DEFAULT_COMMAND_LIMIT);
    this.coalesceWindowMs = Math.max(0, options.coalesceWindowMs ?? DEFAULT_COALESCE_WINDOW_MS);
    this.now = options.now ?? (() => Date.now());
  }

  get undoSize(): number {
    return this.undoStack.length;
  }

  get redoSize(): number {
    return this.redoStack.length;
  }

  get canUndo(): boolean {
    return this.undoStack.length > 0;
  }

  get canRedo(): boolean {
    return this.redoStack.length > 0;
  }

  get undoLabel(): string | null {
    return this.undoStack.at(-1)?.label ?? null;
  }

  get redoLabel(): string | null {
    return this.redoStack.at(-1)?.label ?? null;
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify(): void {
    for (const listener of [...this.listeners]) listener();
  }

  dispatch(command: Command): void {
    command.redo();
    this.redoStack = [];
    const now = this.now();
    const top = this.undoStack.at(-1);
    const mergeable =
      command.coalesceKey !== undefined &&
      top?.coalesceKey === command.coalesceKey &&
      now - this.lastDispatchAt <= this.coalesceWindowMs;
    if (mergeable && top) {
      this.undoStack[this.undoStack.length - 1] = {
        label: command.label,
        undo: top.undo,
        redo: command.redo,
        coalesceKey: command.coalesceKey,
      };
    } else {
      this.undoStack.push(command);
      if (this.undoStack.length > this.limit) this.undoStack.shift();
    }
    this.lastDispatchAt = now;
    this.notify();
  }

  undo(): boolean {
    const command = this.undoStack.pop();
    if (!command) return false;
    command.undo();
    this.redoStack.push(command);
    this.lastDispatchAt = Number.NEGATIVE_INFINITY;
    this.notify();
    return true;
  }

  redo(): boolean {
    const command = this.redoStack.pop();
    if (!command) return false;
    command.redo();
    this.undoStack.push(command);
    this.lastDispatchAt = Number.NEGATIVE_INFINITY;
    this.notify();
    return true;
  }

  clear(): void {
    this.undoStack = [];
    this.redoStack = [];
    this.lastDispatchAt = Number.NEGATIVE_INFINITY;
    this.notify();
  }
}

export function snapshotCommand<T>(options: SnapshotCommandOptions<T>): Command {
  return {
    label: options.label,
    coalesceKey: options.coalesceKey,
    undo: () => options.apply(options.before),
    redo: () => options.apply(options.after),
  };
}
