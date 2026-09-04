"""Groq wrapper, timeout, retry — §15, §15.1.

`openai/gpt-oss-20b` (see C-013 — the original `llama-3.3-70b-versatile` was
retired from Groq's catalogue between Phase 0 and Phase 6), 20s default
timeout. The provider is swappable in
exactly one place: everything downstream depends on the tiny `ChatModel`
protocol below (`complete(system, user, timeout_s) -> str`), never on the Groq
SDK directly. That is also what lets the failure-injection scenarios (§24)
drop in a scripted model without touching `propose()`.

Nothing here raises the three pipeline exceptions (`ConfigurationError` etc.).
API trouble surfaces as `LLMUnavailable` / `LLMTimeout`, which the hypothesis
stage catches and turns into a reason code (§15.4) — the pipeline always
completes.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class LLMUnavailable(Exception):
    """The client itself cannot be reached at all: connection error, 5xx, bad
    credentials, or no client configured. Every subsequent call is certain to
    fail identically (docs/challenges-log.md C-017), so `propose()` stops
    trying further clusters — HYPOTHESIS_LAYER_UNAVAILABLE (§15.4), the
    pipeline still completes.
    """


class LLMCallFailed(Exception):
    """This one call failed for a reason specific to it — a rate limit, or a
    single generation the API itself rejected (e.g. Groq's
    `json_validate_failed` when the model hits max completion tokens before
    finishing valid JSON). Unlike `LLMUnavailable`, this says nothing about
    whether the *next* cluster's call will succeed, so `propose()` skips only
    this cluster and continues (docs/challenges-log.md C-017) — §15.3's "one
    call per cluster" independence would otherwise be undermined by treating
    a single call's failure as if the whole client were down.
    """


class LLMTimeout(Exception):
    """A single call exceeded its timeout budget. Maps to
    `HYPOTHESIS_TIMEOUT` (§15.4). No retry.
    """


@runtime_checkable
class ChatModel(Protocol):
    """The one surface the hypothesis layer depends on. A real Groq client is
    adapted to this by `GroqChatModel`; injection scenarios implement it
    directly.
    """

    def complete(self, system: str, user: str, timeout_s: int) -> str:
        """Return the model's raw response text. Raise `LLMTimeout` on
        timeout, `LLMUnavailable` when the client itself cannot be reached
        (stops the whole hypothesis stage), or `LLMCallFailed` for any other
        single-call API failure (skips just this cluster).
        """
        ...


class GroqChatModel:
    """Adapts a `groq.Groq` client to `ChatModel`. Temperature 0 and a JSON
    response format — the task is structured extraction, not generation
    (§15.1).
    """

    def __init__(self, client: object, model: str) -> None:
        self._client = client
        self._model = model

    def complete(self, system: str, user: str, timeout_s: int) -> str:
        try:
            import groq
        except ImportError as exc:  # pragma: no cover - groq is a pinned dep
            raise LLMUnavailable("groq SDK not importable") from exc

        try:
            resp = self._client.chat.completions.create(  # type: ignore[attr-defined]
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0,
                response_format={"type": "json_object"},
                timeout=timeout_s,
            )
        except groq.APITimeoutError as exc:
            raise LLMTimeout(str(exc)) from exc
        except (groq.APIConnectionError, groq.AuthenticationError) as exc:
            # Dead connection or bad credentials: every future call on this
            # client fails identically. Genuinely "the client is unreachable".
            raise LLMUnavailable(str(exc)) from exc
        except (groq.RateLimitError, groq.APIStatusError, groq.APIError) as exc:
            # This call, specifically — a 429, or the API rejecting this one
            # generation. Says nothing about the next call's prospects.
            raise LLMCallFailed(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - any SDK surprise, treated as this-call-only
            raise LLMCallFailed(f"unexpected LLM client error: {exc}") from exc

        content = resp.choices[0].message.content
        return content or ""


def build_chat_model(api_key: str | None, model: str) -> ChatModel | None:
    """Return a ready `ChatModel`, or `None` when no key is configured — in
    which case the hypothesis stage is skipped and the run completes normally
    (§12.4, `.env.example`).
    """
    if not api_key:
        return None
    try:
        import groq

        client = groq.Groq(api_key=api_key)
    except Exception:  # noqa: BLE001 - a bad key/SDK state must not crash the run
        return None
    return GroqChatModel(client, model)
