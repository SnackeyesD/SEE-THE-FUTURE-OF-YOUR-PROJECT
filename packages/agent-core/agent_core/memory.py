from __future__ import annotations

from providers import ChatMessage, estimate_tokens, normalize_messages

from .guardrails import scrub_secrets


def normalize_thread(messages: list[ChatMessage | dict]) -> list[ChatMessage]:
    normalized = normalize_messages(messages)
    return [
        message.model_copy(update={"content": scrub_secrets(message.content)})
        for message in normalized
    ]


def estimate_messages(messages: list[ChatMessage]) -> int:
    return sum(estimate_tokens(message.content) for message in messages)


def trim_messages(
    messages: list[ChatMessage],
    *,
    max_tokens: int = 24_000,
    summary: str | None = None,
) -> list[ChatMessage]:
    if max_tokens <= 0:
        raise ValueError("max_tokens doit être strictement positif")
    system = [message for message in messages if message.role == "system"]
    conversation = [message for message in messages if message.role != "system"]
    budget = max_tokens - estimate_messages(system)
    if budget <= 0:
        return system[-1:]
    kept: list[ChatMessage] = []
    used = 0
    for message in reversed(conversation):
        cost = estimate_tokens(message.content)
        if kept and used + cost > budget:
            break
        kept.append(message)
        used += cost
    kept.reverse()
    omitted = len(conversation) - len(kept)
    if omitted > 0:
        note = summary or (
            f"[{omitted} messages antérieurs omis pour respecter la fenêtre de contexte]"
        )
        kept.insert(0, ChatMessage(role="system", content=scrub_secrets(note)))
    return [*system, *kept]
