"""Explication en langage naturel d'un chiffre, ancrée sur sa provenance.

Le LLM ne calcule jamais : il ne reçoit que le payload de provenance sérialisé
et sa réponse est vérifiée avant affichage. Toute valeur absente du payload
déclenche jusqu'à deux réparations, puis un repli déterministe construit par le
moteur.

Le cache est en mémoire, borné (LRU 100), expire après 24 h et reste cloisonné
par projet. Il ne conserve jamais le payload brut ni la réponse brute du
fournisseur.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from engine import deterministic_explanation, validate_explanation
from providers import (
    BudgetExceeded,
    ChatMessage,
    ChatRequest,
    ProviderError,
    capabilities_for,
    create_adapter,
    estimate_tokens,
    estimate_usage,
)
from see_storage import ProjectStore

from . import provider_service
from .provenance_service import ProvenanceServiceError
from .provenance_service import build as build_provenance
from .simulation_service import SimulationService, SimulationServiceError

logger = logging.getLogger("see.sidecar.explain")

PROMPT_VERSION = "provenance-v1"
CACHE_LIMIT = 100
CACHE_TTL_SECONDS = 24 * 60 * 60
MAX_REPAIRS = 2
TIMEOUT_SECONDS = 30.0
MAX_TEXT_CHARS = 4_000

_EXPLAIN_ROLE = "narrator"
_KNOWN_REFERENCES = frozenset(
    {
        "value",
        "range",
        "seed",
        "runs",
        "point",
        "metric",
        "definition",
        "formula",
        "unit",
        "engineVersion",
        "p10",
        "p50",
        "p90",
    }
)

SYSTEM_PROMPT = """Tu expliques un chiffre déjà calculé par un moteur de simulation.

Règles absolues :
- tu ne calcules rien et tu n'inventes aucun nombre ;
- chaque nombre de ta réponse doit apparaître tel quel (ou arrondi à 0,1 %)
  dans le payload de provenance fourni ;
- tu ne cites aucun nom de projet, chemin de fichier, secret ou donnée absente
  du payload ;
- tu réponds uniquement avec un objet JSON valide, sans texte autour :
  {"summary": "...", "points": [{"text": "...", "references": ["..."]}],
   "caveats": ["..."]}
- les nombres sont formatés en français (espace fine pour les milliers,
  virgule décimale) ;
- "references" ne contient que des clés du payload ou des clés d'hypothèses.

Si une information manque, dis-le au lieu de l'estimer. La sensibilité est une
corrélation, jamais une causalité."""


def _payload_json(provenance: dict[str, Any]) -> str:
    return json.dumps(
        provenance, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _cache_key(provenance: dict[str, Any], model: str, prompt_version: str) -> str:
    canonical = _payload_json(provenance)
    digest = hashlib.sha256()
    digest.update(canonical.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(model.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(prompt_version.encode("utf-8"))
    return digest.hexdigest()


def _parse_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(stripped[start : end + 1])
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_explanation(raw: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    summary = raw.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return None, "summary manquant"
    points_raw = raw.get("points", [])
    if not isinstance(points_raw, list):
        return None, "points doit être une liste"
    points: list[dict[str, Any]] = []
    for item in points_raw[:12]:
        if not isinstance(item, dict):
            return None, "chaque point doit être un objet"
        text = item.get("text")
        references = item.get("references", [])
        if not isinstance(text, str) or not text.strip():
            return None, "un point est sans texte"
        if not isinstance(references, list) or not all(
            isinstance(reference, str) for reference in references
        ):
            return None, "references doit être une liste de chaînes"
        points.append(
            {
                "text": text.strip(),
                "references": [reference.strip() for reference in references],
            }
        )
    caveats_raw = raw.get("caveats", [])
    if not isinstance(caveats_raw, list) or not all(
        isinstance(caveat, str) for caveat in caveats_raw
    ):
        return None, "caveats doit être une liste de chaînes"
    return (
        {
            "summary": summary.strip(),
            "points": points,
            "caveats": [caveat.strip() for caveat in caveats_raw[:12]],
        },
        None,
    )


def _known_references(provenance: dict[str, Any]) -> set[str]:
    references = set(_KNOWN_REFERENCES)
    for item in provenance.get("inputs", []):
        key = item.get("key")
        if isinstance(key, str):
            references.add(key)
    return references


def _check_explanation(
    explanation: dict[str, Any], provenance: dict[str, Any]
) -> str | None:
    unknown = validate_explanation(explanation, provenance)
    if unknown:
        return (
            "Les nombres suivants n'apparaissent pas dans le payload : "
            + ", ".join(unknown)
            + ". Réécris l'explication sans les inventer."
        )
    allowed = _known_references(provenance)
    unknown_references = sorted(
        {
            reference
            for point in explanation["points"]
            for reference in point["references"]
            if reference not in allowed
        }
    )
    if unknown_references:
        return (
            "Les références suivantes sont inconnues : "
            + ", ".join(unknown_references)
            + ". Utilise uniquement les clés du payload."
        )
    return None


@dataclass
class _CacheEntry:
    created_at: float
    explanation: dict[str, Any]
    model: str
    repaired: bool


class ExplainService:
    """Explications vérifiées, avec cache mémoire et repli déterministe."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        timeout_seconds: float = TIMEOUT_SECONDS,
        cache_limit: int = CACHE_LIMIT,
        cache_ttl_seconds: float = CACHE_TTL_SECONDS,
    ) -> None:
        self._clock = clock
        self._timeout_seconds = max(1.0, timeout_seconds)
        self._cache_limit = max(1, cache_limit)
        self._cache_ttl_seconds = max(0.0, cache_ttl_seconds)
        # Un cache par projet : une explication ne peut jamais être servie à un
        # autre projet, même si le payload et le modèle sont identiques.
        self._cache: dict[str, OrderedDict[str, _CacheEntry]] = {}

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    def explain(
        self,
        store: ProjectStore,
        simulation: SimulationService,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        project_id = params.get("projectId")
        if not isinstance(project_id, str) or not project_id.strip():
            raise ProvenanceServiceError(
                "explanation_invalid", "projectId doit être une chaîne non vide"
            )
        project_id = project_id.strip()
        store.projects.require(project_id)
        run_id = params.get("runId")
        if not isinstance(run_id, str) or not run_id.strip():
            raise ProvenanceServiceError(
                "explanation_invalid", "runId doit être une chaîne non vide"
            )
        try:
            job = simulation.job_for(run_id.strip())
        except SimulationServiceError as exc:
            raise ProvenanceServiceError(
                exc.code, exc.message, retryable=exc.retryable
            ) from exc
        if job.project_id != project_id:
            raise ProvenanceServiceError(
                "explanation_invalid",
                "ce run n'appartient pas au projet demandé",
            )
        try:
            provenance = build_provenance(simulation, params)["provenance"]
        except ProvenanceServiceError:
            raise

        profile = params.get("profile")
        if profile is None:
            return self._fallback(
                provenance,
                reason="no_provider",
                model=None,
            )
        if not isinstance(profile, dict):
            raise ProvenanceServiceError(
                "explanation_invalid", "profile doit être un objet"
            )
        if profile.get("projectId") != project_id:
            raise ProvenanceServiceError(
                "explanation_invalid",
                "le profil fournisseur appartient à un autre projet",
            )
        provider = profile.get("provider")
        if not isinstance(provider, str) or not provider.strip():
            raise ProvenanceServiceError(
                "explanation_invalid", "profil fournisseur sans fournisseur"
            )
        api_key = params.get("apiKey")
        if api_key is not None and not isinstance(api_key, str):
            raise ProvenanceServiceError(
                "explanation_invalid", "apiKey doit être une chaîne"
            )
        model = self._resolve_model(store, project_id, profile, params)
        if model is None:
            return self._fallback(provenance, reason="no_model", model=None)

        key = _cache_key(provenance, model, PROMPT_VERSION)
        cached = self._cache_get(project_id, key)
        if cached is not None:
            return {
                "explanation": cached.explanation,
                "source": "llm",
                "model": cached.model,
                "promptVersion": PROMPT_VERSION,
                "cached": True,
                "repaired": cached.repaired,
                "reason": None,
                "provenance": provenance,
            }

        try:
            result = asyncio.run(
                asyncio.wait_for(
                    self._ask_provider(
                        store,
                        project_id,
                        profile,
                        model,
                        api_key,
                        provenance,
                    ),
                    timeout=self._timeout_seconds,
                )
            )
        except TimeoutError:
            return self._fallback(provenance, reason="timeout", model=model)
        except BudgetExceeded:
            return self._fallback(provenance, reason="budget_exceeded", model=model)
        except ProviderError:
            logger.warning("fournisseur indisponible pour l'explication", exc_info=True)
            return self._fallback(provenance, reason="provider_error", model=model)
        except Exception:
            logger.exception("échec inattendu de l'explication")
            return self._fallback(provenance, reason="provider_error", model=model)

        if result is None:
            return self._fallback(
                provenance, reason="unverified_numbers", model=model
            )
        explanation, repaired = result
        self._cache_put(
            project_id,
            key,
            _CacheEntry(
                created_at=self._clock(),
                explanation=explanation,
                model=model,
                repaired=repaired,
            ),
        )
        return {
            "explanation": explanation,
            "source": "llm",
            "model": model,
            "promptVersion": PROMPT_VERSION,
            "cached": False,
            "repaired": repaired,
            "reason": None,
            "provenance": provenance,
        }

    # ------------------------------------------------------------------
    # Fournisseur
    # ------------------------------------------------------------------
    def _resolve_model(
        self,
        store: ProjectStore,
        project_id: str,
        profile: dict[str, Any],
        params: dict[str, Any],
    ) -> str | None:
        explicit = params.get("model")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        profile_model = profile.get("model")
        if isinstance(profile_model, str) and profile_model.strip():
            return profile_model.strip()
        assignment = store.roles.get(project_id, _EXPLAIN_ROLE)
        if assignment is not None and assignment.provider_profile_id == profile.get("id"):
            return assignment.model
        return None

    async def _ask_provider(
        self,
        store: ProjectStore,
        project_id: str,
        profile: dict[str, Any],
        model: str,
        api_key: str | None,
        provenance: dict[str, Any],
    ) -> tuple[dict[str, Any], bool] | None:
        messages = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=(
                    "Payload de provenance (seule source autorisée) :\n"
                    + _payload_json(provenance)
                ),
            ),
        ]
        for attempt in range(MAX_REPAIRS + 1):
            text = await self._chat(
                store,
                project_id,
                profile,
                model,
                api_key,
                messages,
            )
            raw = _parse_json_object(text)
            if raw is None:
                issue = "La réponse n'est pas un objet JSON valide."
            else:
                explanation, issue = _normalize_explanation(raw)
                if explanation is not None:
                    issue = _check_explanation(explanation, provenance)
                    if issue is None:
                        return explanation, attempt > 0
            if attempt >= MAX_REPAIRS:
                return None
            messages.append(
                ChatMessage(role="assistant", content=text[:MAX_TEXT_CHARS])
            )
            messages.append(
                ChatMessage(
                    role="user",
                    content=(
                        issue
                        + " Corrige uniquement ces points et réponds avec le "
                        "même format JSON, sans texte autour."
                    ),
                )
            )
        return None

    async def _chat(
        self,
        store: ProjectStore,
        project_id: str,
        profile: dict[str, Any],
        model: str,
        api_key: str | None,
        messages: list[ChatMessage],
    ) -> str:
        provider = str(profile["provider"])
        request = ChatRequest(
            model=model,
            messages=messages,
            temperature=0.2,
            max_tokens=1_200,
            response_format="text",
        )
        provider_service.assert_budget(
            store, project_id, provider=provider, request=request
        )
        adapter = create_adapter(
            provider,
            base_url=profile.get("baseUrl"),
            api_key=api_key,
        )
        parts: list[str] = []
        usage = None
        try:
            async for event in adapter.chat(request):
                if event.type == "text_delta" and event.text:
                    parts.append(event.text)
                elif event.type == "usage" and event.usage is not None:
                    usage = event.usage
        finally:
            await adapter.aclose()
        text = "".join(parts)
        if usage is None:
            capabilities = capabilities_for(provider, model)
            usage = estimate_usage(
                capabilities,
                input_tokens=sum(
                    estimate_tokens(message.content) for message in messages
                ),
                output_tokens=estimate_tokens(text),
            )
        store.usage.add(
            project_id,
            "explain",
            provider_profile_id=profile.get("id"),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_micros=usage.cost_micros,
            metadata={"provider": provider, "model": model},
        )
        return text

    # ------------------------------------------------------------------
    # Cache et repli
    # ------------------------------------------------------------------
    def _cache_get(self, project_id: str, key: str) -> _CacheEntry | None:
        entries = self._cache.get(project_id)
        if not entries:
            return None
        entry = entries.get(key)
        if entry is None:
            return None
        if self._clock() - entry.created_at > self._cache_ttl_seconds:
            entries.pop(key, None)
            return None
        entries.move_to_end(key)
        return entry

    def _cache_put(self, project_id: str, key: str, entry: _CacheEntry) -> None:
        entries = self._cache.setdefault(project_id, OrderedDict())
        entries[key] = entry
        entries.move_to_end(key)
        while len(entries) > self._cache_limit:
            entries.popitem(last=False)

    def _fallback(
        self,
        provenance: dict[str, Any],
        *,
        reason: str,
        model: str | None,
    ) -> dict[str, Any]:
        return {
            "explanation": deterministic_explanation(provenance),
            "source": "fallback",
            "model": model,
            "promptVersion": PROMPT_VERSION,
            "cached": False,
            "repaired": False,
            "reason": reason,
            "provenance": provenance,
        }


__all__ = ["ExplainService", "PROMPT_VERSION"]
