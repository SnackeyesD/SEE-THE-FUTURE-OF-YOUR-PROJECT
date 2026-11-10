export interface SandboxMetric {
  label: string;
  value: number;
  unit?: string;
}

export interface SandboxSeries {
  label: string;
  x: number[];
  y: number[];
}

export interface SandboxTable {
  name: string;
  columns: string[];
  rows: Array<Array<string | number | boolean | null>>;
}

export interface SandboxResult {
  summary?: string;
  metrics?: SandboxMetric[];
  series?: SandboxSeries[];
  tables?: SandboxTable[];
}

export interface SandboxRunLimits {
  timeoutMs: number;
  workerStartTimeoutMs: number;
  maxCodeBytes: number;
  maxInputBytes: number;
  maxOutputBytes: number;
  maxLogBytes: number;
}

export const DEFAULT_SANDBOX_LIMITS: SandboxRunLimits = {
  timeoutMs: 10_000,
  workerStartTimeoutMs: 60_000,
  maxCodeBytes: 32_768,
  maxInputBytes: 262_144,
  maxOutputBytes: 262_144,
  maxLogBytes: 8_192,
};

export interface SandboxRunRequest {
  code: string;
  codeHash: string;
  data?: Record<string, unknown>;
  limits?: Partial<SandboxRunLimits>;
  signal?: AbortSignal;
}

export interface SandboxRunOutput {
  result: SandboxResult;
  logs: string;
  durationMs: number;
}

export type SandboxWorkerStatus = "loading" | "packages" | "running";

export type SandboxWorkerInbound = {
  type: "run";
  code: string;
  codeHash: string;
  data: Record<string, unknown>;
  limits: SandboxRunLimits;
};

export type SandboxWorkerOutbound =
  | { type: "status"; status: SandboxWorkerStatus }
  | { type: "logs"; logs: string }
  | { type: "result"; result: SandboxResult; durationMs: number }
  | { type: "error"; code: SandboxErrorCode; message: string };

export type SandboxErrorCode =
  | "invalid_request"
  | "hash_mismatch"
  | "code_too_large"
  | "input_too_large"
  | "output_too_large"
  | "contract"
  | "runtime"
  | "timeout"
  | "cancelled"
  | "worker";

export class SandboxError extends Error {
  readonly code: SandboxErrorCode;

  constructor(code: SandboxErrorCode, message: string) {
    super(message);
    this.name = "SandboxError";
    this.code = code;
  }
}

const CONTROL_CHARACTER = /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/;
const HTML_TAG = /<\s*\/?\s*(script|iframe|object|embed|style|img|svg|math|link|meta)\b/i;
const RESULT_KEYS = new Set(["summary", "metrics", "series", "tables"]);
const METRIC_KEYS = new Set(["label", "value", "unit"]);
const SERIES_KEYS = new Set(["label", "x", "y"]);
const TABLE_KEYS = new Set(["name", "columns", "rows"]);

function contractError(message: string): never {
  throw new SandboxError("contract", message);
}

function checkObject(
  value: unknown,
  field: string,
  allowed: Set<string>,
): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    contractError(`${field} doit être un objet`);
  }
  const record = value as Record<string, unknown>;
  for (const key of Object.keys(record)) {
    if (!allowed.has(key)) contractError(`${field} contient une clé inconnue: ${key}`);
  }
  return record;
}

function checkNumber(value: unknown, field: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    contractError(`${field} doit être un nombre fini`);
  }
  return value;
}

function checkText(value: unknown, field: string, maxLength = 4_000): string {
  if (typeof value !== "string") contractError(`${field} doit être une chaîne`);
  if (value.length > maxLength) contractError(`${field} dépasse ${maxLength} caractères`);
  if (CONTROL_CHARACTER.test(value)) contractError(`${field} contient des caractères de contrôle`);
  if (HTML_TAG.test(value)) contractError(`${field} ne peut pas contenir de HTML`);
  return value;
}

function checkList(value: unknown, field: string, maximum: number): unknown[] {
  if (!Array.isArray(value)) contractError(`${field} doit être une liste`);
  if (value.length > maximum) contractError(`${field} dépasse ${maximum} éléments`);
  return value;
}

export function validateSandboxResult(value: unknown): SandboxResult {
  const result = checkObject(value, "result", RESULT_KEYS);
  if ("summary" in result) checkText(result.summary, "summary", 2_000);

  if ("metrics" in result) {
    for (const [index, metric] of checkList(result.metrics, "metrics", 100).entries()) {
      const item = checkObject(metric, `metrics[${index}]`, METRIC_KEYS);
      checkText(item.label, `metrics[${index}].label`, 200);
      checkNumber(item.value, `metrics[${index}].value`);
      if ("unit" in item) checkText(item.unit, `metrics[${index}].unit`, 40);
    }
  }

  if ("series" in result) {
    for (const [index, series] of checkList(result.series, "series", 20).entries()) {
      const item = checkObject(series, `series[${index}]`, SERIES_KEYS);
      checkText(item.label, `series[${index}].label`, 200);
      const x = checkList(item.x, `series[${index}].x`, 1_000);
      const y = checkList(item.y, `series[${index}].y`, 1_000);
      if (x.length !== y.length) contractError(`series[${index}] doit avoir autant de x que de y`);
      x.forEach((number, point) => checkNumber(number, `series[${index}].x[${point}]`));
      y.forEach((number, point) => checkNumber(number, `series[${index}].y[${point}]`));
    }
  }

  if ("tables" in result) {
    for (const [index, table] of checkList(result.tables, "tables", 10).entries()) {
      const item = checkObject(table, `tables[${index}]`, TABLE_KEYS);
      checkText(item.name, `tables[${index}].name`, 200);
      const columns = checkList(item.columns, `tables[${index}].columns`, 30);
      columns.forEach((name, column) =>
        checkText(name, `tables[${index}].columns[${column}]`, 100),
      );
      const rows = checkList(item.rows, `tables[${index}].rows`, 500);
      rows.forEach((row, rowIndex) => {
        if (!Array.isArray(row) || row.length !== columns.length) {
          contractError(`tables[${index}].rows[${rowIndex}] doit avoir ${columns.length} cellules`);
        }
        row.forEach((cell, cellIndex) => {
          const field = `tables[${index}].rows[${rowIndex}][${cellIndex}]`;
          if (cell === null || typeof cell === "boolean") return;
          if (typeof cell === "string") checkText(cell, field, 500);
          else checkNumber(cell, field);
        });
      });
    }
  }

  const encoded = new TextEncoder().encode(JSON.stringify(result));
  if (encoded.byteLength > DEFAULT_SANDBOX_LIMITS.maxOutputBytes) {
    contractError(`résultat trop volumineux (max ${DEFAULT_SANDBOX_LIMITS.maxOutputBytes} octets)`);
  }
  return result as SandboxResult;
}

export function byteLength(value: string): number {
  return new TextEncoder().encode(value).byteLength;
}

export async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function runSandboxScript(request: SandboxRunRequest): Promise<SandboxRunOutput> {
  const limits = { ...DEFAULT_SANDBOX_LIMITS, ...request.limits };
  if (byteLength(request.code) > limits.maxCodeBytes) {
    return Promise.reject(
      new SandboxError("code_too_large", `script trop volumineux (max ${limits.maxCodeBytes} octets)`),
    );
  }
  const data = request.data ?? {};
  if (byteLength(JSON.stringify(data)) > limits.maxInputBytes) {
    return Promise.reject(
      new SandboxError("input_too_large", `données trop volumineuses (max ${limits.maxInputBytes} octets)`),
    );
  }
  if (request.signal?.aborted) {
    return Promise.reject(new SandboxError("cancelled", "exécution annulée"));
  }

  return new Promise<SandboxRunOutput>((resolve, reject) => {
    const worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
    let settled = false;
    let startedAt = performance.now();
    let startupTimer: ReturnType<typeof setTimeout> | undefined;
    let executionTimer: ReturnType<typeof setTimeout> | undefined;
    let logs = "";

    const clearTimers = () => {
      if (startupTimer !== undefined) clearTimeout(startupTimer);
      if (executionTimer !== undefined) clearTimeout(executionTimer);
    };

    const finish = (callback: () => void) => {
      if (settled) return;
      settled = true;
      clearTimers();
      request.signal?.removeEventListener("abort", onAbort);
      worker.terminate();
      callback();
    };

    const fail = (error: SandboxError) => finish(() => reject(error));
    const onAbort = () => fail(new SandboxError("cancelled", "exécution annulée"));

    startupTimer = setTimeout(
      () =>
        fail(
          new SandboxError(
            "timeout",
            `démarrage du bac à sable trop long (max ${limits.workerStartTimeoutMs} ms)`,
          ),
        ),
      limits.workerStartTimeoutMs,
    );
    request.signal?.addEventListener("abort", onAbort, { once: true });

    worker.onerror = (event) => {
      event.preventDefault();
      fail(new SandboxError("worker", event.message || "le worker du bac à sable a échoué"));
    };
    worker.onmessage = (event: MessageEvent<SandboxWorkerOutbound>) => {
      const message = event.data;
      if (message.type === "status") {
        if (message.status === "running") {
          startedAt = performance.now();
          if (startupTimer !== undefined) clearTimeout(startupTimer);
          executionTimer = setTimeout(
            () =>
              fail(
                new SandboxError("timeout", `exécution interrompue après ${limits.timeoutMs} ms`),
              ),
            limits.timeoutMs,
          );
        }
        return;
      }
      if (message.type === "logs") {
        logs = message.logs.slice(-limits.maxLogBytes);
        return;
      }
      if (message.type === "error") {
        fail(new SandboxError(message.code, message.message));
        return;
      }
      let result: SandboxResult;
      try {
        result = validateSandboxResult(message.result);
      } catch (error) {
        fail(
          error instanceof SandboxError
            ? error
            : new SandboxError("contract", "résultat invalide"),
        );
        return;
      }
      const durationMs = Math.max(0, performance.now() - startedAt);
      finish(() => resolve({ result, logs, durationMs }));
    };

    worker.postMessage({
      type: "run",
      code: request.code,
      codeHash: request.codeHash,
      data,
      limits,
    } satisfies SandboxWorkerInbound);
  });
}
