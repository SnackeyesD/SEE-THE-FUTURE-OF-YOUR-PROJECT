"""Service de runs asynchrones du sidecar (phase 06).

Invariants :

- un seul worker exécute les simulations ; le thread principal garde la
  lecture RPC et la persistance SQLite ;
- un seul writer sérialise stdout ; les partiels peuvent être jetés quand la
  file sortante sature, jamais les messages terminaux ;
- ``draft`` ne touche jamais SQLite ; ``final`` est persisté une seule fois,
  sur le thread principal, après le calcul ;
- chaque run possède son propre jeton d'annulation et un ``seq`` strictement
  croissant.

Ce module ne dépend pas de ``rpc.py`` : les handlers traduisent
``SimulationServiceError`` en erreur JSON-RPC.
"""

from __future__ import annotations

import json
import logging
import queue
import sys
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from engine import (
    SAMPLE_LIMIT,
    CancelToken,
    ConvergenceState,
    PartialAggregates,
    Scenario,
    SimulationCancelled,
    SimulationConfig,
    SimulationResult,
    resolve_execution,
    scenario_hash,
    simulate,
)
from pydantic import ValidationError

logger = logging.getLogger("see.sidecar.simulation")

Notifier = Callable[[str, dict[str, Any]], None]
Persistence = Callable[["Job", SimulationResult], None]

DEFAULT_MAX_QUEUE = 512
MAX_RUNS = 20
MAX_WAITING = 20
RUN_TTL_SECONDS = 15 * 60
THROTTLE_SECONDS = 0.05
MAX_PARTIAL_BYTES = 500_000
MAX_MESSAGE_BYTES = 1_000_000
MAX_TRAJECTORIES = 200
MAX_RETAINED_SAMPLES = 4
"""Nombre de runs dont l'échantillon complet reste disponible pour les trajectoires.

Au-delà, seuls les agrégats du résultat sont conservés : la demande de
trajectoires renvoie explicitement ``run_sample_unavailable``.
"""

TERMINAL_STATUSES = frozenset({"done", "cancelled", "error"})
ACTIVE_STATUSES = frozenset({"queued", "running", "cancelling"})

DROP_NOTIFICATIONS = frozenset(
    {
        "simulation.partial",
        "simulation.surface.partial",
        "simulation.progress",
        "simulate.progress",
    }
)


class SimulationServiceError(Exception):
    """Erreur métier destinée à être traduite en erreur JSON-RPC."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class OutboundWriter:
    """Unique point d'écriture stdout, protégé par une file bornée.

    Les messages marqués ``droppable`` (progression et partiels) sont perdus
    en priorité quand la file est pleine. Les messages terminaux ne sont
    jamais jetés : le producteur attend qu'une place se libère.
    """

    def __init__(
        self,
        stream: Any | None = None,
        *,
        max_queue: int = DEFAULT_MAX_QUEUE,
        name: str = "sidecar-writer",
    ) -> None:
        self._stream = stream if stream is not None else sys.stdout.buffer
        self._max_queue = max(1, max_queue)
        self._condition = threading.Condition()
        self._entries: deque[tuple[bytes, bool]] = deque()
        self._closed = False
        self._dropped = 0
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    @property
    def dropped(self) -> int:
        with self._condition:
            return self._dropped

    @property
    def pending(self) -> int:
        with self._condition:
            return len(self._entries)

    @property
    def closed(self) -> bool:
        with self._condition:
            return self._closed

    def send(self, payload: dict[str, Any], *, droppable: bool = False) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        line = encoded.encode("utf-8") + b"\n"
        with self._condition:
            if self._closed:
                return
            if len(self._entries) >= self._max_queue:
                if droppable and not self._drop_one_locked():
                    self._dropped += 1
                    return
                if not droppable:
                    # Backpressure sur les messages critiques : on attend une
                    # place sans jamais jeter done/cancelled/error.
                    while len(self._entries) >= self._max_queue and not self._closed:
                        self._condition.wait(0.05)
                    if self._closed:
                        return
            self._entries.append((line, droppable))
            self._condition.notify_all()

    def close(self, *, drain: bool = True, timeout: float = 2.0) -> None:
        deadline = time.monotonic() + max(0.0, timeout)
        with self._condition:
            if drain:
                while self._entries and not self._closed:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    self._condition.wait(remaining)
            self._closed = True
            self._condition.notify_all()
        self._thread.join(timeout=max(0.0, timeout))

    def _drop_one_locked(self) -> bool:
        for index, (_, droppable) in enumerate(self._entries):
            if droppable:
                del self._entries[index]
                self._dropped += 1
                return True
        return False

    def _run(self) -> None:
        while True:
            with self._condition:
                while not self._entries and not self._closed:
                    self._condition.wait()
                if not self._entries:
                    if self._closed:
                        return
                    continue
                line, _ = self._entries.popleft()
                self._condition.notify_all()
            try:
                self._stream.write(line)
                self._stream.flush()
            except Exception:  # pragma: no cover - stdout fermé / pipe cassé
                logger.exception("écriture stdout impossible, writer arrêté")
                with self._condition:
                    self._closed = True
                    self._condition.notify_all()
                return


@dataclass
class Job:
    """Un run suivi par le registre et exécuté par l'unique worker."""

    run_id: str
    project_id: str
    quality: str
    cancel: CancelToken
    notify: Notifier
    scenario: Scenario
    config: SimulationConfig
    seed: int
    created_at: float
    seq: int = 0
    status: str = "queued"
    updated_at: float = 0.0
    reason: str | None = None
    notified: bool = False
    result: SimulationResult | None = None
    last_convergence: ConvergenceState = field(
        default_factory=lambda: ConvergenceState(
            converged=False,
            stability=0.0,
            max_relative_change=0.0,
            stable_blocks=0,
        )
    )
    run_token: str | None = None
    scenario_id: str | None = None


class SimulationService:
    """File de jobs, registre de runs et exécution hors du thread principal."""

    def __init__(
        self,
        *,
        persist: Persistence | None = None,
        throttle_seconds: float = THROTTLE_SECONDS,
        max_runs: int = MAX_RUNS,
        ttl_seconds: float = RUN_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._persist = persist
        self._throttle_seconds = max(0.0, throttle_seconds)
        self._max_runs = max(1, max_runs)
        self._ttl_seconds = max(0.0, ttl_seconds)
        self._clock = clock

        self._lock = threading.RLock()
        self._runs: dict[str, Job] = {}
        self._order: deque[str] = deque()
        self._ready: deque[str] = deque()
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._completed: queue.Queue[str] = queue.Queue()
        self._stop = threading.Event()
        self._closed = False
        self._worker = threading.Thread(
            target=self._worker_loop, name="sidecar-simulation", daemon=True
        )
        self._worker.start()

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------
    def start(self, params: dict[str, Any], notify: Notifier) -> dict[str, Any]:
        scenario, config, quality, seed, project_id, run_token, scenario_id = _validate_start(
            params
        )
        now = self._clock()
        notifications: list[tuple[str, dict[str, Any]]] = []

        with self._lock:
            if self._closed:
                raise SimulationServiceError(
                    "simulation_busy", "le sidecar est en cours d'arrêt"
                )
            replaced_run_id: str | None = None
            for job in list(self._runs.values()):
                if job.project_id != project_id or job.status not in ACTIVE_STATUSES:
                    continue
                replaced_run_id = replaced_run_id or job.run_id
                notification = self._cancel_locked(
                    job, "simulation_superseded", notify_waiting=True
                )
                if notification is not None:
                    notifications.append(notification)

            waiting = sum(
                1 for job in self._runs.values() if job.status == "queued"
            )
            if waiting >= MAX_WAITING:
                raise SimulationServiceError(
                    "simulation_busy",
                    "trop de simulations en attente; attendez la fin du run courant",
                    retryable=True,
                )
            self._evict_locked(now)

            run_id = uuid.uuid4().hex
            job = Job(
                run_id=run_id,
                project_id=project_id,
                quality=quality,
                cancel=CancelToken(),
                notify=notify,
                scenario=scenario,
                config=config,
                seed=seed,
                created_at=now,
                updated_at=now,
                run_token=run_token,
                scenario_id=scenario_id,
            )
            self._runs[run_id] = job
            self._order.append(run_id)
            # Le job n'est mis en file qu'après l'écriture de la réponse
            # ``simulation.start`` (voir ``activate``), pour que le client
            # connaisse le runId avant le premier événement.
            self._ready.append(run_id)

        self._send_all(notifications)
        result: dict[str, Any] = {"runId": run_id, "accepted": True}
        if replaced_run_id is not None:
            result["replacedRunId"] = replaced_run_id
        return result

    def activate(self) -> None:
        """Met en file les runs acceptés, une fois la réponse écrite."""

        with self._lock:
            while self._ready:
                self._queue.put(self._ready.popleft())

    def cancel(self, run_id: str) -> dict[str, Any]:
        notifications: list[tuple[str, dict[str, Any]]] = []
        with self._lock:
            job = self._runs.get(run_id)
            if job is None:
                raise SimulationServiceError(
                    "run_not_found", f"run inconnu: {run_id}"
                )
            if job.status in TERMINAL_STATUSES:
                return {"cancelled": False}
            notification = self._cancel_locked(
                job, "simulation_cancelled", notify_waiting=True
            )
            if notification is not None:
                notifications.append(notification)
        self._send_all(notifications)
        return {"cancelled": True}

    # ------------------------------------------------------------------
    # Accès à la demande (trajectoires, paramètres, provenance)
    # ------------------------------------------------------------------
    def job_for(self, run_id: str) -> Job:
        with self._lock:
            job = self._runs.get(run_id)
        if job is None:
            raise SimulationServiceError(
                "run_not_found",
                f"run inconnu ou expiré: {run_id}",
            )
        return job

    def _sample_for(self, run_id: str) -> tuple[Job, Any]:
        job = self.job_for(run_id)
        result = job.result
        if result is None:
            raise SimulationServiceError(
                "run_sample_unavailable",
                "l'échantillon de ce run n'est plus disponible; relancez un calcul",
            )
        if result.runs > SAMPLE_LIMIT:
            raise SimulationServiceError(
                "run_sample_unavailable",
                f"le run dépasse {SAMPLE_LIMIT} runs : seuls les agrégats sont conservés",
            )
        sample = result.run_sample
        if sample is None or int(sample.indices.size) == 0:
            raise SimulationServiceError(
                "run_sample_unavailable",
                "l'échantillon de ce run a été évincé; relancez un calcul",
            )
        return job, sample

    def trajectories(self, params: dict[str, Any]) -> dict[str, Any]:
        run_id = _required_text(params, "runId")
        job, sample = self._sample_for(run_id)
        result = job.result
        assert result is not None
        retained = int(sample.indices.size)

        raw_indices = params.get("indices")
        truncated = False
        if raw_indices is not None:
            if not isinstance(raw_indices, list):
                raise SimulationServiceError(
                    "trajectory_invalid", "indices doit être une liste d'entiers"
                )
            if len(raw_indices) > MAX_TRAJECTORIES:
                truncated = True
            selected: list[int] = []
            for value in raw_indices[:MAX_TRAJECTORIES]:
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise SimulationServiceError(
                        "trajectory_invalid", "chaque index doit être un entier positif"
                    )
                if value >= retained:
                    raise SimulationServiceError(
                        "trajectory_invalid",
                        f"index {value} hors de l'échantillon conservé ({retained} runs)",
                    )
                if value not in selected:
                    selected.append(value)
        else:
            count = params.get("count", MAX_TRAJECTORIES)
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                raise SimulationServiceError(
                    "trajectory_invalid", "count doit être un entier positif"
                )
            if count > MAX_TRAJECTORIES:
                count = MAX_TRAJECTORIES
                truncated = True
            selected = list(range(min(count, retained)))
            truncated = truncated or count > len(selected)

        trajectories = [
            {
                "index": index,
                "profitMonthly": sample.profit_monthly[index].tolist(),
                "cashMonthly": sample.cash_monthly[index].tolist(),
                "revenueMonthly": sample.revenue_monthly[index].tolist(),
            }
            for index in selected
        ]
        return {
            "runId": run_id,
            "seed": result.seed,
            "engineVersion": result.engine_version,
            "runs": result.runs,
            "runsRetained": retained,
            "horizonMonths": result.horizon_months,
            "currency": result.currency,
            "truncated": truncated,
            "trajectories": trajectories,
        }

    def run_params(self, params: dict[str, Any]) -> dict[str, Any]:
        run_id = _required_text(params, "runId")
        index = params.get("index")
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise SimulationServiceError(
                "trajectory_invalid", "index doit être un entier positif"
            )
        job, sample = self._sample_for(run_id)
        result = job.result
        assert result is not None
        retained = int(sample.indices.size)
        if index >= retained:
            raise SimulationServiceError(
                "trajectory_invalid",
                f"index {index} hors de l'échantillon conservé ({retained} runs)",
            )
        return {
            "runId": run_id,
            "index": index,
            "seed": result.seed,
            "engineVersion": result.engine_version,
            "scenariosHash": scenario_hash(job.scenario),
            "parameters": {
                key: float(values[index]) for key, values in sample.parameters.items()
            },
        }

    def process_completed(self) -> int:
        """Persiste et termine les runs calculés (appelé sur le thread principal)."""

        processed = 0
        while True:
            try:
                run_id = self._completed.get_nowait()
            except queue.Empty:
                return processed
            with self._lock:
                job = self._runs.get(run_id)
                result = job.result if job is not None else None
            if job is None or result is None:
                continue
            if job.quality == "draft":
                self._emit_done(job, result, persisted=False)
            else:
                try:
                    if self._persist is not None:
                        self._persist(job, result)
                except Exception:
                    logger.exception("persistance du run %s impossible", run_id)
                    self._emit_error(
                        job,
                        "simulation_failed",
                        "la persistance du résultat a échoué; consultez les journaux",
                        retryable=True,
                    )
                else:
                    self._emit_done(job, result, persisted=True)
            processed += 1

    def health_stats(self) -> dict[str, Any]:
        with self._lock:
            active = next(
                (
                    job.run_id
                    for job in self._runs.values()
                    if job.status in {"running", "cancelling"}
                ),
                None,
            )
            return {
                "retainedRuns": len(self._runs),
                "queuedRuns": sum(
                    1 for job in self._runs.values() if job.status == "queued"
                ),
                "activeRunId": active,
            }

    def shutdown(self) -> None:
        notifications: list[tuple[str, dict[str, Any]]] = []
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for job in self._runs.values():
                if job.status in TERMINAL_STATUSES:
                    continue
                job.cancel.cancel()
                job.status = "cancelled"
                job.reason = "shutdown"
                job.updated_at = self._clock()
                if not job.notified:
                    job.notified = True
                    notifications.append(
                        (
                            "simulation.cancelled",
                            {"runId": job.run_id, "reason": "shutdown"},
                        )
                    )
        self._send_all(notifications)
        self._stop.set()
        self._queue.put(None)
        self._worker.join(timeout=2.0)
        if self._worker.is_alive():
            logger.warning("le worker de simulation ne s'est pas arrêté à temps")

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------
    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                run_id = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if run_id is None:
                return

            with self._lock:
                job = self._runs.get(run_id)
                if job is None or job.status in TERMINAL_STATUSES:
                    continue
                if job.cancel.is_cancelled():
                    job.status = "cancelled"
                    job.reason = job.reason or "simulation_cancelled"
                    job.updated_at = self._clock()
                    notification = self._take_cancelled_notification_locked(job)
                else:
                    job.status = "running"
                    job.updated_at = self._clock()
                    notification = None
            if notification is not None:
                self._send_all([notification])
                continue
            self._execute(job)

    def _execute(self, job: Job) -> None:
        plan = resolve_execution(job.config, job.quality)
        last_partial_at = 0.0
        last_progress_at = 0.0

        def on_partial(partial: PartialAggregates) -> None:
            nonlocal last_partial_at
            job.last_convergence = partial.convergence
            now = self._clock()
            if now - last_partial_at < self._throttle_seconds:
                return
            last_partial_at = now
            with self._lock:
                if job.status in TERMINAL_STATUSES or job.cancel.is_cancelled():
                    return
                job.seq += 1
                seq = job.seq
                job.updated_at = now
                payload = {
                    "runId": job.run_id,
                    "seq": seq,
                    "aggregates": partial.to_dict(),
                }
            if _payload_size(payload) > MAX_PARTIAL_BYTES:
                logger.warning("partiel %s trop volumineux, ignoré", job.run_id)
                return
            job.notify("simulation.partial", payload)

        def on_progress(fraction: float) -> None:
            nonlocal last_progress_at
            now = self._clock()
            complete = fraction >= 1.0
            if not complete and now - last_progress_at < self._throttle_seconds:
                return
            last_progress_at = now
            with self._lock:
                if job.status in TERMINAL_STATUSES or job.cancel.is_cancelled():
                    return
                convergence = job.last_convergence
            completed_runs = min(plan.runs, max(0, round(fraction * plan.runs)))
            job.notify(
                "simulation.progress",
                {
                    "runId": job.run_id,
                    "completedRuns": completed_runs,
                    "totalRuns": plan.runs,
                    "fraction": round(fraction, 6),
                    "block": completed_runs // plan.block_size,
                    "convergence": convergence.model_dump(
                        by_alias=True, mode="json"
                    ),
                },
            )

        try:
            result = simulate(
                job.scenario,
                job.config,
                quality=job.quality,
                on_progress=on_progress,
                on_partial=on_partial,
                cancel=job.cancel,
            )
        except SimulationCancelled:
            self._finish_cancelled(job)
            return
        except Exception:
            logger.exception("échec du run %s", job.run_id)
            self._emit_error(
                job,
                "simulation_failed",
                "la simulation a échoué; consultez les journaux du sidecar",
                retryable=True,
            )
            return

        if job.cancel.is_cancelled():
            self._finish_cancelled(job)
            return

        result.run_id = job.run_id
        with self._lock:
            if job.status in TERMINAL_STATUSES:
                return
            job.result = result
            job.status = "completed"
            job.updated_at = self._clock()
        self._completed.put(job.run_id)

    def _finish_cancelled(self, job: Job) -> None:
        with self._lock:
            job.status = "cancelled"
            job.reason = job.reason or "simulation_cancelled"
            job.updated_at = self._clock()
            notification = self._take_cancelled_notification_locked(job)
        if notification is not None:
            self._send_all([notification])

    # ------------------------------------------------------------------
    # Notifications terminales
    # ------------------------------------------------------------------
    def _emit_done(
        self, job: Job, result: SimulationResult, *, persisted: bool
    ) -> None:
        with self._lock:
            if job.notified:
                return
            seq = job.seq
        payload = {
            "runId": job.run_id,
            "seq": seq,
            "result": result.to_dict(),
            "persisted": persisted,
        }
        if _payload_size(payload) > MAX_MESSAGE_BYTES:
            self._emit_error(
                job,
                "simulation_failed",
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
            # Le résultat reste disponible pour la provenance et les
            # trajectoires demandées après la fin du run. Seuls les
            # échantillons des derniers runs sont conservés.
            self._trim_samples_locked()
        job.notify("simulation.done", payload)

    def _trim_samples_locked(self) -> None:
        """Évince les échantillons des runs terminés les plus anciens.

        Le résultat et ses agrégats restent disponibles : seule la matière
        brute des trajectoires est libérée. Un run évincé répond
        ``run_sample_unavailable`` plutôt que de renvoyer un échantillon
        partiel ou incohérent.
        """

        with_samples = sorted(
            (
                job
                for job in self._runs.values()
                if job.status in TERMINAL_STATUSES
                and job.result is not None
                and job.result.run_sample is not None
            ),
            key=lambda job: job.updated_at,
        )
        excess = len(with_samples) - MAX_RETAINED_SAMPLES
        for job in with_samples[: max(0, excess)]:
            if job.result is not None:
                job.result.detach_sample()

    def _emit_error(
        self,
        job: Job,
        code: str,
        message: str,
        *,
        retryable: bool,
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
                "runId": job.run_id,
                "code": code,
                "message": message,
                "retryable": retryable,
            },
        )

    def _cancel_locked(
        self, job: Job, reason: str, *, notify_waiting: bool
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
        return self._take_cancelled_notification_locked(job)

    def _take_cancelled_notification_locked(
        self, job: Job
    ) -> tuple[str, dict[str, Any]] | None:
        if job.notified:
            return None
        job.notified = True
        return (
            "simulation.cancelled",
            {"runId": job.run_id, "reason": job.reason or "simulation_cancelled"},
        )

    def _send_all(
        self, notifications: list[tuple[str, dict[str, Any]]]
    ) -> None:
        for method, params in notifications:
            try:
                # Les notifications de fin ne dépendent pas d'un notifier de
                # requête particulier : le premier job les porte déjà.
                self._notify_any(method, params)
            except Exception:  # pragma: no cover - writer fermé
                logger.exception("notification %s impossible", method)

    def _notify_any(self, method: str, params: dict[str, Any]) -> None:
        with self._lock:
            notifier = next(
                (job.notify for job in self._runs.values() if job.notify is not None),
                None,
            )
        if notifier is not None:
            notifier(method, params)

    # ------------------------------------------------------------------
    # Registre
    # ------------------------------------------------------------------
    def _evict_locked(self, now: float) -> None:
        while self._order and self._order[0] not in self._runs:
            self._order.popleft()

        expired = [
            job
            for job in self._runs.values()
            if job.status in TERMINAL_STATUSES
            and now - job.updated_at > self._ttl_seconds
        ]
        for job in expired:
            self._drop_locked(job.run_id)

        if len(self._runs) < self._max_runs:
            return
        removable = sorted(
            (
                job
                for job in self._runs.values()
                if job.status in TERMINAL_STATUSES
            ),
            key=lambda job: job.updated_at,
        )
        while len(self._runs) >= self._max_runs and removable:
            victim = removable.pop(0)
            self._drop_locked(victim.run_id)
        if len(self._runs) >= self._max_runs:
            raise SimulationServiceError(
                "simulation_busy",
                "limite de runs simultanés atteinte; attendez la fin d'un calcul",
                retryable=True,
            )

    def _drop_locked(self, run_id: str) -> None:
        """Retire un run du registre et libère son échantillon."""

        job = self._runs.pop(run_id, None)
        if job is not None and job.result is not None:
            job.result.detach_sample()


def _payload_size(payload: dict[str, Any]) -> int:
    return len(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def _required_text(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SimulationServiceError(
            "simulation_invalid", f"{key} doit être une chaîne non vide"
        )
    return value.strip()


def _validate_start(
    params: dict[str, Any],
) -> tuple[Scenario, SimulationConfig, str, int, str, str | None, str | None]:
    project_id = params.get("projectId")
    if not isinstance(project_id, str) or not project_id.strip():
        raise SimulationServiceError(
            "simulation_invalid", "projectId doit être une chaîne non vide"
        )
    raw_scenario = params.get("scenario")
    if not isinstance(raw_scenario, dict):
        raise SimulationServiceError(
            "simulation_invalid", "scenario doit être un objet"
        )
    try:
        scenario = Scenario.model_validate(raw_scenario)
    except ValidationError as exc:
        raise SimulationServiceError(
            "simulation_invalid",
            "scénario invalide: " + _validation_details(exc),
        ) from exc

    raw_config = params.get("config") or {}
    if not isinstance(raw_config, dict):
        raise SimulationServiceError(
            "simulation_invalid", "config doit être un objet"
        )
    try:
        config = SimulationConfig.model_validate(raw_config)
    except ValidationError as exc:
        raise SimulationServiceError(
            "simulation_invalid",
            "configuration invalide: " + _validation_details(exc),
        ) from exc

    quality = params.get("quality")
    if quality not in ("draft", "final"):
        raise SimulationServiceError(
            "simulation_invalid", "quality doit valoir draft ou final"
        )

    seed = params.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise SimulationServiceError(
            "simulation_invalid", "seed doit être un entier"
        )
    if seed < 0 or seed > 2**63 - 1:
        raise SimulationServiceError(
            "simulation_invalid", "seed hors limites"
        )

    run_token = params.get("runToken")
    if run_token is not None and not isinstance(run_token, str):
        raise SimulationServiceError(
            "simulation_invalid", "runToken doit être une chaîne"
        )

    raw_scenario_id = params.get("scenarioId")
    scenario_id: str | None = None
    if raw_scenario_id is not None:
        if not isinstance(raw_scenario_id, str) or not raw_scenario_id.strip():
            raise SimulationServiceError(
                "simulation_invalid", "scenarioId doit être une chaîne non vide"
            )
        scenario_id = raw_scenario_id.strip()

    config = config.model_copy(
        update={
            "seed": seed,
            # Les distributions mensuelles de tous les mois sont réservées au
            # calcul final : les partiels restent légers (bandes seules).
            "include_monthly_histograms": quality == "final",
        }
    )
    return scenario, config, quality, seed, project_id.strip(), run_token, scenario_id


def _validation_details(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exc.errors(include_url=False)
    )
