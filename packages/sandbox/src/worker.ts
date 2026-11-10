import type { PyodideInterface } from "pyodide";

import {
  SandboxError,
  byteLength,
  sha256Hex,
  validateSandboxResult,
} from "./index";
import type {
  SandboxErrorCode,
  SandboxResult,
  SandboxRunLimits,
  SandboxWorkerInbound,
  SandboxWorkerOutbound,
} from "./index";

interface SandboxWorkerScope {
  location: { origin: string };
  postMessage(message: SandboxWorkerOutbound): void;
  onmessage: ((event: MessageEvent<SandboxWorkerInbound>) => void) | null;
}

const scope = globalThis as unknown as SandboxWorkerScope;

async function loadRuntime(): Promise<PyodideInterface> {
  const base = `${scope.location.origin}/pyodide/`;
  await import(/* @vite-ignore */ `${base}pyodide.asm.js`);
  const module = (await import(/* @vite-ignore */ `${base}pyodide.mjs`)) as {
    loadPyodide(options?: { indexURL?: string }): Promise<PyodideInterface>;
  };
  return module.loadPyodide({ indexURL: base });
}

const RUNNER_SOURCE = String.raw`
import builtins as _see_builtins
import json as _see_json

_BLOCKED_IMPORTS = {
    "_pyodide",
    "js",
    "micropip",
    "pyodide",
    "pyodide_js",
}
_original_import = _see_builtins.__import__


def _see_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".")[0]
    if root in _BLOCKED_IMPORTS:
        raise ImportError(f"import interdit dans la sandbox: {root}")
    return _original_import(name, globals, locals, fromlist, level)


_see_builtins.__import__ = _see_import


def _see_main(input_json, code):
    data = _see_json.loads(input_json)
    namespace = {"__name__": "see_sandbox", "__builtins__": _see_builtins}
    exec(compile(code, "<script>", "exec"), namespace)
    entrypoint = namespace.get("main")
    if not callable(entrypoint):
        raise ValueError("le script doit définir une fonction main(data)")
    output = entrypoint(data)
    return _see_json.dumps(output, ensure_ascii=False, allow_nan=False)
`;

function errorCode(error: unknown): SandboxErrorCode {
  return error instanceof SandboxError ? error.code : "runtime";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

scope.onmessage = async (event) => {
  const message = event.data;
  if (message.type !== "run") return;

  const limits: SandboxRunLimits = message.limits;
  let logs = "";
  const appendLog = (text: string) => {
    logs = (logs + text).slice(-limits.maxLogBytes);
  };
  const send = (payload: SandboxWorkerOutbound) => scope.postMessage(payload);

  try {
    if (byteLength(message.code) > limits.maxCodeBytes) {
      throw new SandboxError("code_too_large", "script trop volumineux");
    }
    const input = JSON.stringify(message.data);
    if (byteLength(input) > limits.maxInputBytes) {
      throw new SandboxError("input_too_large", "données trop volumineuses");
    }
    const digest = await sha256Hex(message.code);
    if (digest !== message.codeHash.toLowerCase()) {
      throw new SandboxError("hash_mismatch", "le script ne correspond pas au code audité");
    }

    send({ type: "status", status: "loading" });
    const pyodide = await loadRuntime();

    send({ type: "status", status: "packages" });
    await pyodide.loadPackage(["numpy", "pandas"]);

    pyodide.setStdout({ batched: appendLog });
    pyodide.setStderr({ batched: appendLog });

    const blocked = () => {
      throw new Error("réseau désactivé dans le bac à sable");
    };
    for (const name of ["fetch", "WebSocket", "XMLHttpRequest", "EventSource"]) {
      try {
        Object.defineProperty(globalThis, name, {
          value: blocked,
          writable: false,
          configurable: false,
        });
      } catch {
        continue;
      }
    }

    send({ type: "status", status: "running" });
    const startedAt = performance.now();
    pyodide.globals.set("_see_input", input);
    pyodide.globals.set("_see_code", message.code);
    pyodide.runPython(RUNNER_SOURCE);
    const raw = await pyodide.runPythonAsync("_see_main(_see_input, _see_code)");
    const result: unknown = JSON.parse(String(raw));
    const validated: SandboxResult = validateSandboxResult(result);
    const encoded = JSON.stringify(validated);
    if (byteLength(encoded) > limits.maxOutputBytes) {
      throw new SandboxError("output_too_large", "résultat trop volumineux");
    }
    send({ type: "logs", logs });
    send({ type: "result", result: validated, durationMs: performance.now() - startedAt });
  } catch (error) {
    send({ type: "logs", logs });
    const messageText = errorMessage(error);
    const safeMessage =
      messageText.length > 2_000 ? `${messageText.slice(0, 2_000)}…` : messageText;
    send({ type: "error", code: errorCode(error), message: safeMessage });
  }
};
