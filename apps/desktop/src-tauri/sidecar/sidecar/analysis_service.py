"""Jobs asynchrones de surface et de recherche d'objectif (phase 11).

Le service reprend les invariants du service de simulation :

- un seul worker exécute les analyses, jamais le thread RPC ;
- un job est annulable et remplaçable par un nouveau job **du même projet** ;
- les notifications de progression et de lignes peuvent être jetées, jamais les
  messages terminaux ;
- aucune valeur n'est calculée ici : les résultats viennent du moteur.

Il ne dépend pas de ``rpc.py`` ; les handlers traduisent
``AnalysisServiceError`` en erreur JSON-RPC.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from engine import (
    AxisSpec,
    CancelToken,
    EngineError,
    Lever,
    Objective,
    Scenario,
    SimulationCancelled,
    SimulationConfig,
    goal_seek,
    surface,
)
from pydantic import ValidationError

from .simulation_service import Notifier, _payload_size

logger = logging.getLogger("see.sidecar.analysis")

MAX_JOBS = 20
MAX_WAITING = 20
JOB_TTL_SECONDS = 15 * 60
THROTTLE_SECONDS = 0.05
MAX_MESSAGE_BYTES = 1_000_000
MAX_EVALUATIONS = 500
MAX_RUNS = 50_000

TERMINAL_STATUSES = frozenset({"done", "cancelled", "error"})
ACTIVE_STATUSES = frozenset({"queued", "running", "cancelling"})

SURFACE_METRICS: frozenset[str] = frozenset(
    {
        "profit_p50",
        "profit_p10",
        "profit_p90",
        "break_even_months_p50",
        "financing_need_p90",
        "loss_probability",
    }
)
QUALITIES = frozenset({"draft", "final"})


class AnalysisServiceError(Exception):
    """Erreur métier destinée à être traduite en erreur JSON-RPC."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass
class AnalysisJob:
    """Un job d'analyse suivi par le registre et exécuté par l'unique worker."""

    job_id: str
    project_id: str
    kind: str
    cancel: CancelToken
    notify: Notifier
    created_at: float
    scenario: Scenario
    config: SimulationConfig
    seed: int
    runs: int
    quality: str = "draft"
    axis_x: AxisSpec | None = None
    axis_y: AxisSpec | None = None
    metric: str = "profit_p50"
    grid: tuple[int, int] = (15, 15)
    objective: Objective | None = None
    levers: list[Lever] = field(default_factory=list)
    locked: list[str] = field(default_factory=list)
    max_evaluations: int = 80
    confirm_quality: str | None = "final"
    confirm_runs: int = 5_000
    seq: int = 0
    status: str = "queued"
    updated_at: float = 0.0
    reason: str | None = None
    notified: bool = False


class AnalysisService:
    """File de jobs, registre et exécution hors du thread principal."""

    def __init__(
        self,
        *,
        throttle_seconds: float = THROTTLE_SECONDS,
        max_jobs: int = MAX_JOBS,
        ttl_seconds: float = JOB_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._throttle_seconds = max(0.0, throttle_seconds)
        self._max_jobs = max(1, max_jobs)
        self._ttl_seconds = max(0.0, ttl_seconds)
        self._clock = clock

        self._lock = threading.RLock()
        self._jobs: dict[str, AnalysisJob] = {}
        self._order: deque[str] = deque()
        self._ready: deque[str] = deque()
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._stop = threading.Event()
        self._closed = False
        self._worker = threading.Thread(
            target=self._worker_loop, name="sidecar-analysis", daemon=True
        )
        self._worker.start()

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------
    def start_surface(
        self, params: dict[str, Any], notify: Notifier
    ) -> dict[str, Any]:
        job = _validate_surface(params, notify, self._clock())
        return self._accept(job)

    def start_goal_seek(
        self, params: dict[str, Any], notify: Notifier
    ) -> dict[str, Any]:
        job = _validate_goal_seek(params, notify, self._clock())
        return self._accept(job)

    def activate(self) -> None:
        """Met en file les jobs acceptés, une fois la réponse écrite."""

        with self._lock:
            while self._ready:
                self._queue.put(self._ready.popleft())

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise AnalysisServiceError(
                    "job_not_found", f"job inconnu: {job_id}"
                )
            if job.status in TERMINAL_STATUSES:
                return {"cancelled": False}
            notification = self._cancel_locked(
                job, "analysis_cancelled", notify_waiting=True
            )
        if notification is not None:
            self._send(notification, job=job)
        return {"cancelled": True}

    def health_stats(self) -> dict[str, Any]:
        with self._lock:
            active = next(
                (
                    job.job_id
                    for job in self._jobs.values()
                    if job.status in {"running", "cancelling"}
                ),
                None,
            )
            return {
                "retainedAnalysisJobs": len(self._jobs),
                "queuedAnalysisJobs": sum(
                    1 for job in self._jobs.values() if job.status == "queued"
                ),
                "activeAnalysisJobId": active,
            }

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            notifications: list[tuple[str, dict[str, Any]]] = []
            for job in self._jobs.values():
                if job.status in TERMINAL_STATUSES:
                    continue
                job.cancel.cancel()
                job.status = "cancelled"
                job.reason = "shutdown"
                job.updated_at = self._clock()
                if not job.notified:
                    job.notified = True
                    notifications.append(self._cancelled_payload(job))
        self._send_all(notifications)
        self._stop.set()
        self._queue.put(None)
        self._worker.join(timeout=2.0)
        if self._worker.is_alive():
            logger.warning("le worker d'analyse ne s'est pas arrêté à temps")

    # ------------------------------------------------------------------
    # Registre et file
    # ------------------------------------------------------------------
    def _accept(self, job: AnalysisJob) -> dict[str, Any]:
        notifications: list[tuple[str, dict[str, Any]]] = []
        with self._lock:
            if self._closed:
                raise AnalysisServiceError(
                    "analysis_busy", "le sidecar est en cours d'arrêt"
                )
            replaced: str | None = None
            for existing in list(self._jobs.values()):
                if (
                    existing.project_id != job.project_id
                    or existing.status not in ACTIVE_STATUSES
                ):
                    continue
                replaced = replaced or existing.job_id
                notification = self._cancel_locked(
                    existing, "analysis_superseded", notify_waiting=True
                )
                if notification is not None:
                    notifications.append(notification)

            waiting = sum(
                1 for existing in self._jobs.values() if existing.status == "queued"
            )
            if waiting >= MAX_WAITING:
                raise AnalysisServiceError(
                    "analysis_busy",
                    "trop d'analyses en attente; attendez la fin du job courant",
                    retryable=True,
                )
            self._evict_locked(self._clock())
            self._jobs[job.job_id] = job
            self._order.append(job.job_id)
            self._ready.append(job.job_id)

        self._send_all(notifications)
        result: dict[str, Any] = {"jobId": job.job_id, "accepted": True}
        if replaced is not None:
            result["replacedJobId"] = replaced
        return result

    def _evict_locked(self, now: float) -> None:
        while self._order and self._order[0] not in self._jobs:
            self._order.popleft()
        expired = [
            job
            for job in self._jobs.values()
            if job.status in TERMINAL_STATUSES
            and now - job.updated_at > self._ttl_seconds
        ]
        for job in expired:
            self._jobs.pop(job.job_id, None)
        if len(self._jobs) < self._max_jobs:
            return
        removable = sorted(
            (job for job in self._jobs.values() if job.status in TERMINAL_STATUSES),
            key=lambda job: job.updated_at,
        )
        while len(self._jobs) >= self._max_jobs and removable:
            victim = removable.pop(0)
            self._jobs.pop(victim.job_id, None)
        if len(self._jobs) >= self._max_jobs:
            raise AnalysisServiceError(
                "analysis_busy",
                "limite d'analyses simultanées atteinte; attendez la fin d'un job",
                retryable=True,
            )

    # ------------------------------------------------------------------
    # Worker et exécution
    # ------------------------------------------------------------------
    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                job_id = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if job_id is None:
                return
            with self._lock:
                job = self._jobs.get(job_id)
                if job is None or job.status in TERMINAL_STATUSES:
                    continue
                if job.cancel.is_cancelled():
                    job.status = "cancelled"
                    job.reason = job.reason or "analysis_cancelled"
                    job.updated_at = self._clock()
                    notification = self._take_cancelled_locked(job)
                else:
                    job.status = "running"
                    job.updated_at = self._clock()
                    notification = None
            if notification is not None:
                self._send(notification, job=job)
                continue
            self._execute(job)

    def _execute(self, job: AnalysisJob) -> None:
        try:
            result = (
                self._run_surface(job)
                if job.kind == "surface"
                else self._run_goal_seek(job)
            )
        except SimulationCancelled:
            self._finish_cancelled(job)
            return
        except EngineError as exc:
            self._emit_error(
                job,
                "analysis_invalid",
                str(exc),
                retryable=False,
            )
            return
        except Exception:
            logger.exception("échec du job d'analyse %s", job.job_id)
            self._emit_error(
                job,
                "analysis_failed",
                "l'analyse a échoué; consultez les journaux du sidecar",
                retryable=True,
            )
            return

        if job.cancel.is_cancelled():
            self._finish_cancelled(job)
            return
        self._emit_done(job, result)

    def _run_surface(self, job: AnalysisJob) -> Any:
        total = job.grid[0] * job.grid[1]
        columns = job.grid[0]
        last_progress_at = 0.0

        def on_progress(fraction: float) -> None:
            nonlocal last_progress_at
            now = self._clock()
            complete = fraction >= 1.0
            if not complete and now - last_progress_at < self._throttle_seconds:
                return
            last_progress_at = now
            completed = min(total, max(0, round(fraction * total)))
            self._emit_progress(job, completed, total, fraction)

        def on_row(
            row_index: int,
            values: list[float],
            p10: list[float] | None,
            p90: list[float] | None,
        ) -> None:
            with self._lock:
                if job.status in TERMINAL_STATUSES or job.cancel.is_cancelled():
                    return
                job.seq += 1
                seq = job.seq
                job.updated_at = self._clock()
            payload: dict[str, Any] = {
                "jobId": job.job_id,
                "seq": seq,
                "rowIndex": row_index,
                "values": values,
                "completedPoints": min(total, (row_index + 1) * columns),
                "totalPoints": total,
            }
            if p10 is not None:
                payload["p10"] = p10
            if p90 is not None:
                payload["p90"] = p90
            if _payload_size(payload) <= MAX_MESSAGE_BYTES:
                job.notify("simulation.surface.partial", payload)

        assert job.axis_x is not None and job.axis_y is not None
        return surface(
            job.scenario,
            job.config,
            axis_x=job.axis_x,
            axis_y=job.axis_y,
            metric=job.metric,  # type: ignore[arg-type]
            grid=job.grid,
            runs=job.runs,
            seed=job.seed,
            on_progress=on_progress,
            on_row=on_row,
            cancel=job.cancel,
            quality=job.quality,  # type: ignore[arg-type]
        )

    def _run_goal_seek(self, job: AnalysisJob) -> Any:
        assert job.objective is not None

        def on_progress(completed: int, total: int) -> None:
            fraction = completed / total if total else 0.0
            self._emit_progress(job, completed, total, fraction)

        return goal_seek(
            job.scenario,
            job.objective,
            job.levers,
            locked=job.locked,
            seed=job.seed,
            max_evaluations=job.max_evaluations,
            runs=job.runs,
            config=job.config,
            cancel=job.cancel,
            on_progress=on_progress,
            confirm_quality=job.confirm_quality,  # type: ignore[arg-type]
            confirm_runs=job.confirm_runs,
        )

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    def _emit_progress(
        self, job: AnalysisJob, completed: int, total: int, fraction: float
    ) -> None:
        with self._lock:
            if job.status in TERMINAL_STATUSES or job.cancel.is_cancelled():
                return
            job.updated_at = self._clock()
        job.notify(
            "simulation.progress",
            {
                "jobId": job.job_id,
                "kind": job.kind,
                "completed": completed,
                "total": total,
                "fraction": round(min(1.0, max(0.0, fraction)), 6),
            },
        )

    def _emit_done(self, job: AnalysisJob, result: Any) -> None:
        payload = {
            "jobId": job.job_id,
            "kind": job.kind,
            "result": result.model_dump(by_alias=True, mode="json"),
        }
        if _payload_size(payload) > MAX_MESSAGE_BYTES:
            self._emit_error(
                job,
                "analysis_failed",
                "le résultat dépasse la limite d'un message de 1 Mo",
                retryable=False,
            )
            return
        with self._lock:
            if job.notified:
                return
            job.notified = True
            job.status = "done"
            job.updated_at = self._clock()
        job.notify("simulation.done", payload)

    def _emit_error(
        self, job: AnalysisJob, code: str, message: str, *, retryable: bool
    ) -> None:
        with self._lock:
            if job.notified:
                return
            job.notified = True
            job.status = "error"
            job.reason = code
            job.updated_at = self._clock()
        job.notify(
            "simulation.error",
            {
                "jobId": job.job_id,
                "kind": job.kind,
                "code": code,
                "message": message,
                "retryable": retryable,
            },
        )

    def _finish_cancelled(self, job: AnalysisJob) -> None:
        with self._lock:
            job.status = "cancelled"
            job.reason = job.reason or "analysis_cancelled"
            job.updated_at = self._clock()
            notification = self._take_cancelled_locked(job)
        if notification is not None:
            self._send(notification, job=job)

    def _cancel_locked(
        self, job: AnalysisJob, reason: str, *, notify_waiting: bool
    ) -> tuple[str, dict[str, Any]] | None:
        job.cancel.cancel()
        job.reason = reason
        job.updated_at = self._clock()
        if job.status != "queued":
            job.status = "cancelling"
            return None
        job.status = "cancelled"
        if not notify_waiting:
            return None
        return self._take_cancelled_locked(job)

    def _take_cancelled_locked(
        self, job: AnalysisJob
    ) -> tuple[str, dict[str, Any]] | None:
        if job.notified:
            return None
        job.notified = True
        return self._cancelled_payload(job)

    def _cancelled_payload(
        self, job: AnalysisJob
    ) -> tuple[str, dict[str, Any]]:
        return (
            "simulation.cancelled",
            {
                "jobId": job.job_id,
                "kind": job.kind,
                "reason": job.reason or "analysis_cancelled",
            },
        )

    def _send(
        self,
        notification: tuple[str, dict[str, Any]],
        *,
        job: AnalysisJob | None = None,
    ) -> None:
        method, params = notification
        try:
            if job is not None:
                job.notify(method, params)
            else:
                self._notify_any(method, params)
        except Exception:  # pragma: no cover - writer fermé
            logger.exception("notification %s impossible", method)

    def _send_all(self, notifications: list[tuple[str, dict[str, Any]]]) -> None:
        for notification in notifications:
            self._send(notification)

    def _notify_any(self, method: str, params: dict[str, Any]) -> None:
        with self._lock:
            notifier = next(
                (job.notify for job in self._jobs.values() if job.notify is not None),
                None,
            )
        if notifier is not None:
            notifier(method, params)


# ----------------------------------------------------------------------
# Validation des paramètres
# ----------------------------------------------------------------------
def _text(params: dict[str, Any], name: str, *, default: str | None = None) -> str:
    value = params.get(name, default)
    if not isinstance(value, str) or not value.strip():
        raise AnalysisServiceError(
            "analysis_invalid", f"{name} doit être une chaîne non vide"
        )
    return value.strip()


def _int(
    value: Any,
    name: str,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AnalysisServiceError(
            "analysis_invalid", f"{name} doit être un entier"
        )
    if value < minimum or (maximum is not None and value > maximum):
        bounds = f"[{minimum}, {maximum}]" if maximum is not None else f"≥ {minimum}"
        raise AnalysisServiceError(
            "analysis_invalid", f"{name} hors limites {bounds}"
        )
    return value


def _scenario(params: dict[str, Any]) -> Scenario:
    raw = params.get("scenario")
    if not isinstance(raw, dict):
        raise AnalysisServiceError("analysis_invalid", "scenario doit être un objet")
    try:
        return Scenario.model_validate(raw)
    except ValidationError as exc:
        raise AnalysisServiceError(
            "analysis_invalid", "scénario invalide: " + _details(exc)
        ) from exc


def _config(params: dict[str, Any]) -> SimulationConfig:
    raw = params.get("config") or {}
    if not isinstance(raw, dict):
        raise AnalysisServiceError("analysis_invalid", "config doit être un objet")
    try:
        return SimulationConfig.model_validate(raw)
    except ValidationError as exc:
        raise AnalysisServiceError(
            "analysis_invalid", "configuration invalide: " + _details(exc)
        ) from exc


def _details(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exc.errors(include_url=False)
    )


def _axis(params: dict[str, Any], name: str) -> AxisSpec:
    raw = params.get(name)
    if not isinstance(raw, dict):
        raise AnalysisServiceError("analysis_invalid", f"{name} doit être un objet")
    try:
        return AxisSpec.model_validate(raw)
    except ValidationError as exc:
        raise AnalysisServiceError(
            "analysis_invalid", f"{name} invalide: " + _details(exc)
        ) from exc


def _grid(params: dict[str, Any]) -> tuple[int, int]:
    raw = params.get("grid", [15, 15])
    if (
        not isinstance(raw, (list, tuple))
        or len(raw) != 2
        or any(isinstance(value, bool) or not isinstance(value, int) for value in raw)
    ):
        raise AnalysisServiceError(
            "analysis_invalid", "grid doit être un couple d'entiers [colonnes, lignes]"
        )
    columns, rows = int(raw[0]), int(raw[1])
    if columns < 2 or rows < 2 or columns > 60 or rows > 60:
        raise AnalysisServiceError(
            "analysis_invalid", "grid doit être comprise entre 2×2 et 60×60"
        )
    return columns, rows


def _quality(params: dict[str, Any], name: str, *, default: str) -> str:
    value = params.get(name, default)
    if value not in QUALITIES:
        raise AnalysisServiceError(
            "analysis_invalid", f"{name} doit valoir draft ou final"
        )
    return value


def _validate_surface(
    params: dict[str, Any], notify: Notifier, now: float
) -> AnalysisJob:
    project_id = _text(params, "projectId")
    scenario = _scenario(params)
    config = _config(params)
    axis_x = _axis(params, "axisX")
    axis_y = _axis(params, "axisY")
    if axis_x.key == axis_y.key:
        raise AnalysisServiceError(
            "analysis_invalid", "les deux axes doivent porter sur des hypothèses différentes"
        )
    metric = params.get("metric", "profit_p50")
    if metric not in SURFACE_METRICS:
        raise AnalysisServiceError("analysis_invalid", f"métrique inconnue: {metric!r}")
    grid = _grid(params)
    runs = _int(params.get("runs", 200), "runs", minimum=1, maximum=MAX_RUNS)
    seed = _int(
        params.get("seed", config.seed),
        "seed",
        minimum=0,
        maximum=2**63 - 1,
    )
    quality = _quality(params, "quality", default="draft")
    return AnalysisJob(
        job_id=uuid.uuid4().hex,
        project_id=project_id,
        kind="surface",
        cancel=CancelToken(),
        notify=notify,
        created_at=now,
        updated_at=now,
        scenario=scenario,
        config=config,
        seed=seed,
        runs=runs,
        quality=quality,
        axis_x=axis_x,
        axis_y=axis_y,
        metric=metric,
        grid=grid,
    )


def _validate_goal_seek(
    params: dict[str, Any], notify: Notifier, now: float
) -> AnalysisJob:
    project_id = _text(params, "projectId")
    scenario = _scenario(params)
    config = _config(params)

    raw_objective = params.get("objective")
    if not isinstance(raw_objective, dict):
        raise AnalysisServiceError(
            "analysis_invalid", "objective doit être un objet"
        )
    try:
        objective = Objective.model_validate(raw_objective)
    except ValidationError as exc:
        raise AnalysisServiceError(
            "analysis_invalid", "objectif invalide: " + _details(exc)
        ) from exc

    raw_levers = params.get("levers")
    if not isinstance(raw_levers, list) or not raw_levers:
        raise AnalysisServiceError(
            "analysis_invalid", "levers doit être une liste non vide"
        )
    levers: list[Lever] = []
    for index, raw_lever in enumerate(raw_levers):
        if not isinstance(raw_lever, dict):
            raise AnalysisServiceError(
                "analysis_invalid", f"levers[{index}] doit être un objet"
            )
        try:
            levers.append(Lever.model_validate(raw_lever))
        except ValidationError as exc:
            raise AnalysisServiceError(
                "analysis_invalid",
                f"levers[{index}] invalide: " + _details(exc),
            ) from exc
    if len({lever.key for lever in levers}) != len(levers):
        raise AnalysisServiceError(
            "analysis_invalid", "les leviers doivent porter sur des hypothèses distinctes"
        )

    raw_locked = params.get("locked", [])
    if not isinstance(raw_locked, list) or any(
        not isinstance(key, str) for key in raw_locked
    ):
        raise AnalysisServiceError(
            "analysis_invalid", "locked doit être une liste de clés"
        )

    max_evaluations = _int(
        params.get("maxEvaluations", 80),
        "maxEvaluations",
        minimum=1,
        maximum=MAX_EVALUATIONS,
    )
    runs = _int(params.get("runs", 500), "runs", minimum=1, maximum=MAX_RUNS)
    seed = _int(
        params.get("seed", config.seed),
        "seed",
        minimum=0,
        maximum=2**63 - 1,
    )
    confirm_quality = params.get("confirmQuality", "final")
    if confirm_quality is not None and confirm_quality not in QUALITIES:
        raise AnalysisServiceError(
            "analysis_invalid", "confirmQuality doit valoir draft, final ou null"
        )
    confirm_runs = _int(
        params.get("confirmRuns", 5_000),
        "confirmRuns",
        minimum=1,
        maximum=MAX_RUNS,
    )
    return AnalysisJob(
        job_id=uuid.uuid4().hex,
        project_id=project_id,
        kind="goalseek",
        cancel=CancelToken(),
        notify=notify,
        created_at=now,
        updated_at=now,
        scenario=scenario,
        config=config,
        seed=seed,
        runs=runs,
        objective=objective,
        levers=levers,
        locked=list(raw_locked),
        max_evaluations=max_evaluations,
        confirm_quality=confirm_quality,
        confirm_runs=confirm_runs,
    )


__all__ = [
    "AnalysisJob",
    "AnalysisService",
    "AnalysisServiceError",
]
