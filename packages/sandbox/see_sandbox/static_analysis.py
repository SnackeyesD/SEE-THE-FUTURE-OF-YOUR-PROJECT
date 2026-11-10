from __future__ import annotations

import ast
from dataclasses import dataclass

from .audit import code_hash
from .limits import LIMITS, MAX_AST_NODES, MAX_CODE_BYTES, MAX_LITERAL_CHARS

ALLOWED_IMPORTS = (
    "collections",
    "datetime",
    "decimal",
    "fractions",
    "functools",
    "itertools",
    "json",
    "math",
    "numpy",
    "pandas",
    "random",
    "statistics",
)

FORBIDDEN_MODULES = frozenset(
    {
        "asyncio",
        "builtins",
        "code",
        "ctypes",
        "ftplib",
        "glob",
        "http",
        "importlib",
        "io",
        "marshal",
        "multiprocessing",
        "os",
        "pathlib",
        "pickle",
        "platform",
        "pty",
        "requests",
        "resource",
        "shelve",
        "shutil",
        "signal",
        "smtplib",
        "socket",
        "sqlite3",
        "ssl",
        "subprocess",
        "sys",
        "tempfile",
        "threading",
        "tkinter",
        "urllib",
        "webbrowser",
    }
)

FORBIDDEN_CALLS = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "delattr",
        "dir",
        "eval",
        "exec",
        "exit",
        "getattr",
        "globals",
        "hasattr",
        "help",
        "input",
        "locals",
        "open",
        "quit",
        "setattr",
        "vars",
    }
)


@dataclass(frozen=True, slots=True)
class AnalysisIssue:
    code: str
    message: str
    line: int | None = None
    column: int | None = None
    severity: str = "error"

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    ok: bool
    codeHash: str
    issues: tuple[AnalysisIssue, ...]
    allowedImports: tuple[str, ...]
    limits: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "codeHash": self.codeHash,
            "issues": [issue.to_dict() for issue in self.issues],
            "allowedImports": list(self.allowedImports),
            "limits": dict(self.limits),
        }


class _PolicyVisitor(ast.NodeVisitor):
    def __init__(self, code: str) -> None:
        self.code = code
        self.issues: list[AnalysisIssue] = []

    def issue(
        self,
        code: str,
        message: str,
        node: ast.AST | None = None,
        *,
        severity: str = "error",
    ) -> None:
        line = getattr(node, "lineno", None)
        column = getattr(node, "col_offset", None)
        self.issues.append(
            AnalysisIssue(code=code, message=message, line=line, column=column, severity=severity)
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".", 1)[0]
            if root not in ALLOWED_IMPORTS:
                self.issue(
                    "import_not_allowed",
                    f"import interdit: {alias.name}",
                    node,
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = (node.module or "").split(".", 1)[0]
        if node.level:
            self.issue("relative_import", "les imports relatifs sont interdits", node)
        elif module not in ALLOWED_IMPORTS:
            self.issue("import_not_allowed", f"import interdit: {node.module or '?'}", node)
        for alias in node.names:
            if alias.name == "*":
                self.issue("star_import", "les imports génériques sont interdits", node)
            elif alias.name.startswith("_"):
                self.issue("private_import", f"import privé interdit: {alias.name}", node)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in FORBIDDEN_CALLS:
            self.issue("forbidden_name", f"nom interdit: {node.id}", node)
        elif node.id.startswith("__"):
            self.issue("dunder_name", f"accès de type dunder interdit: {node.id}", node)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_"):
            self.issue("private_attribute", f"attribut privé interdit: {node.attr}", node)
        elif node.attr in FORBIDDEN_CALLS:
            self.issue("forbidden_attribute", f"attribut interdit: {node.attr}", node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        target = node.func
        name = target.id if isinstance(target, ast.Name) else None
        if name is None and isinstance(target, ast.Attribute):
            name = target.attr
        if name in FORBIDDEN_CALLS:
            self.issue("forbidden_call", f"appel interdit: {name}", node)
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        if node.arg.startswith("__"):
            self.issue("dunder_argument", f"nom de paramètre interdit: {node.arg}", node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name.startswith("__"):
            self.issue("dunder_function", f"nom de fonction interdit: {node.name}", node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node.name.startswith("__"):
            self.issue("dunder_function", f"nom de fonction interdit: {node.name}", node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name.startswith("__"):
            self.issue("dunder_class", f"nom de classe interdit: {node.name}", node)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and len(node.value) > MAX_LITERAL_CHARS:
            self.issue(
                "literal_too_large",
                f"chaîne littérale trop longue (max {MAX_LITERAL_CHARS})",
                node,
            )
        self.generic_visit(node)


def _main_function(tree: ast.Module) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    return None


def analyze_code(code: str) -> AnalysisResult:
    digest = code_hash(code)
    issues: list[AnalysisIssue] = []
    encoded = code.encode("utf-8")
    if len(encoded) > MAX_CODE_BYTES:
        issues.append(
            AnalysisIssue(
                code="code_too_large",
                message=f"code trop volumineux (max {MAX_CODE_BYTES} octets)",
            )
        )
        return AnalysisResult(
            ok=False,
            codeHash=digest,
            issues=tuple(issues),
            allowedImports=ALLOWED_IMPORTS,
            limits=LIMITS,
        )

    try:
        tree = ast.parse(code, filename="<script>", mode="exec")
    except SyntaxError as error:
        issues.append(
            AnalysisIssue(
                code="invalid_syntax",
                message=f"syntaxe Python invalide: {error.msg}",
                line=error.lineno,
                column=error.offset,
            )
        )
        return AnalysisResult(
            ok=False,
            codeHash=digest,
            issues=tuple(issues),
            allowedImports=ALLOWED_IMPORTS,
            limits=LIMITS,
        )

    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        issues.append(
            AnalysisIssue(
                code="ast_too_large",
                message=f"script trop complexe (max {MAX_AST_NODES} nœuds)",
            )
        )

    main = _main_function(tree)
    if main is None:
        issues.append(
            AnalysisIssue(
                code="missing_main",
                message="le script doit définir une fonction main(data)",
            )
        )
    elif not main.args.posonlyargs and not main.args.args:
        issues.append(
            AnalysisIssue(
                code="invalid_main",
                message="main doit accepter les données en argument",
                line=main.lineno,
                column=main.col_offset,
            )
        )

    visitor = _PolicyVisitor(code)
    visitor.visit(tree)
    issues.extend(visitor.issues)
    ok = not any(issue.severity == "error" for issue in issues)
    return AnalysisResult(
        ok=ok,
        codeHash=digest,
        issues=tuple(issues),
        allowedImports=ALLOWED_IMPORTS,
        limits=LIMITS,
    )
