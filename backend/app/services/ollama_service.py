import json
import logging
import os
import threading
import time
from typing import Type, TypeVar

import httpx
from dotenv import load_dotenv
from ollama import Client, ResponseError
from pydantic import BaseModel, ValidationError


load_dotenv()

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ============================================================
# ERRORS
# ============================================================

class OllamaError(RuntimeError):
    """Base for every Ollama failure surfaced to callers."""


class OllamaUnavailable(OllamaError):
    """Could not reach the Ollama server."""


class OllamaTimeout(OllamaError):
    """Ollama did not respond within the configured timeout."""


class OllamaBadOutput(OllamaError):
    """Ollama responded but the payload was empty, truncated or off-schema."""


# ============================================================
# CONFIG
# ============================================================

MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

# Always include the port: with a scheme but no port the ollama client
# silently targets port 80, not 11434.
HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")

# The ollama client's default timeout is None -- i.e. wait forever -- which
# would pin a Starlette worker thread indefinitely on a hung model. Connect
# fast, read slow: a cold model load plus a full itinerary legitimately takes
# over a minute (measured 38-71s for 2-5 day plans on llama3.2).
TIMEOUT = httpx.Timeout(
    connect=5.0,
    read=float(os.getenv("OLLAMA_READ_TIMEOUT", "300")),
    write=30.0,
    pool=5.0,
)

RETRIES = 2  # transport retries; total attempts = RETRIES + 1


_client = None
_client_lock = threading.Lock()


# ============================================================
# CLIENT
# ============================================================

def get_client() -> Client:
    """Return the shared client, built on first use for connection pooling.

    Built lazily, not at import: a malformed host raises ValueError inside the
    Client constructor, which at import time would kill the whole process.
    """
    global _client

    if _client is None:
        with _client_lock:
            if _client is None:
                try:
                    _client = Client(host=HOST, timeout=TIMEOUT)
                except ValueError as exc:
                    raise OllamaUnavailable(
                        f"Invalid OLLAMA_HOST {HOST!r}: {exc}"
                    ) from exc

    return _client


def close_client():
    """Release the httpx connection pool. Called on app shutdown."""
    global _client

    with _client_lock:
        if _client is not None:
            _client.close()
            _client = None


# ============================================================
# CHAT
# ============================================================

def _chat(
    messages,
    fmt=None,
    num_predict: int = 4096,
    seed: int = 42,
    temperature: float = 0.0,
):
    """Call Ollama once, retrying only transient transport failures."""
    client = get_client()
    last = None

    for attempt in range(RETRIES + 1):
        try:
            return client.chat(
                model=MODEL,
                messages=messages,
                format=fmt,  # a JSON-schema dict passes straight through
                stream=False,
                options={
                    # Deterministic by default, but the seed is caller-supplied:
                    # a caller that rejects a response and asks again needs a
                    # DIFFERENT sample, and temperature 0 with a fixed seed
                    # returns the same bytes forever.
                    "temperature": temperature,
                    "top_p": 1.0,
                    "seed": seed,
                    "num_predict": num_predict,
                    "num_ctx": 8192,
                },
            )

        except ResponseError as exc:
            # 4xx (missing model, bad request) is never transient.
            if (
                exc.status_code
                and 500 <= exc.status_code < 600
                and attempt < RETRIES
            ):
                last = exc
                time.sleep(2 ** attempt)
                continue

            raise OllamaError(
                f"Ollama returned {exc.status_code}: {exc.error}"
            ) from exc

        # MUST precede httpx.HTTPError -- TimeoutException is a subclass of it.
        except httpx.TimeoutException as exc:
            last = exc

            if attempt < RETRIES:
                logger.warning("Ollama timed out (attempt %d)", attempt + 1)
                time.sleep(2 ** attempt)
                continue

            raise OllamaTimeout(
                f"Ollama did not respond within {TIMEOUT.read}s"
            ) from exc

        # ollama converts httpx.ConnectError into the BUILTIN ConnectionError.
        except ConnectionError as exc:
            last = exc

            if attempt < RETRIES:
                time.sleep(2 ** attempt)
                continue

            raise OllamaUnavailable(
                f"Could not reach Ollama at {HOST}"
            ) from exc

        # Every other httpx transport error escapes chat() unwrapped.
        except httpx.HTTPError as exc:
            last = exc

            if attempt < RETRIES:
                time.sleep(2 ** attempt)
                continue

            raise OllamaUnavailable(f"{type(exc).__name__}: {exc}") from exc

        # Bad arguments (e.g. OLLAMA_MODEL="") surface as pydantic errors.
        except ValidationError as exc:
            raise OllamaError(f"Invalid Ollama request: {exc}") from exc

    raise OllamaError(f"Ollama failed after {RETRIES + 1} attempts: {last}")


# ============================================================
# PUBLIC API
# ============================================================

def ask_ollama(prompt: str) -> str:
    """Free-text call. Used by POST /ai/test."""
    response = _chat(
        [
            {
                "role": "user",
                "content": prompt,
            }
        ]
    )

    content = (response.message.content or "").strip()

    if not content:
        raise OllamaBadOutput("Ollama returned an empty response.")

    return content


def ask_ollama_json(
    prompt: str,
    schema_model: Type[T],
    *,
    schema: dict | None = None,
    num_predict: int = 4096,
    seed: int = 42,
    temperature: float = 0.0,
) -> T:
    """Constrain generation to schema_model, then parse and validate.

    format=<schema> constrains the sampler but does NOT guarantee parseable
    JSON: generation cut off at num_predict yields truncated JSON with
    done_reason == "length". So check content, check done_reason, then parse.
    """
    fmt = schema if schema is not None else schema_model.model_json_schema()

    response = _chat(
        [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        fmt=fmt,
        num_predict=num_predict,
        seed=seed,
        temperature=temperature,
    )

    content = (response.message.content or "").strip()  # content is Optional[str]

    if not content:
        raise OllamaBadOutput("Ollama returned an empty response.")

    if response.done_reason == "length":
        raise OllamaBadOutput(
            "Ollama's response was cut off before the JSON was complete. "
            "Try a shorter trip."
        )

    try:
        return schema_model.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("Ollama returned unusable JSON: %.300s", content)
        raise OllamaBadOutput("Ollama returned a malformed trip plan.") from exc


# ============================================================
# STREAMING CHAT
# ============================================================

def _chat_stream(
    messages,
    fmt=None,
    num_predict: int = 4096,
    seed: int = 42,
    temperature: float = 0.0,
):
    """Yield content tokens as they arrive from Ollama.

    No transport-level retries: a broken stream cannot be resumed, so the
    caller (trip_service.stream_trip_plan) handles retry-at-a-higher-level.
    """
    client = get_client()

    try:
        stream = client.chat(
            model=MODEL,
            messages=messages,
            format=fmt,
            stream=True,
            options={
                "temperature": temperature,
                "top_p": 1.0,
                "seed": seed,
                "num_predict": num_predict,
                "num_ctx": 8192,
            },
        )

        done_reason = None

        for chunk in stream:
            content = chunk.message.content or ""

            if content:
                yield content

            # The last chunk carries done_reason.
            if getattr(chunk, "done", False):
                done_reason = getattr(chunk, "done_reason", None)

        if done_reason == "length":
            raise OllamaBadOutput(
                "Ollama's response was cut off before the JSON was complete. "
                "Try a shorter trip."
            )

    except ResponseError as exc:
        raise OllamaError(
            f"Ollama returned {exc.status_code}: {exc.error}"
        ) from exc

    except httpx.TimeoutException as exc:
        raise OllamaTimeout(
            f"Ollama did not respond within {TIMEOUT.read}s"
        ) from exc

    except ConnectionError as exc:
        raise OllamaUnavailable(
            f"Could not reach Ollama at {HOST}"
        ) from exc

    except httpx.HTTPError as exc:
        raise OllamaUnavailable(f"{type(exc).__name__}: {exc}") from exc

    except ValidationError as exc:
        raise OllamaError(f"Invalid Ollama request: {exc}") from exc


def stream_ollama_json(
    prompt: str,
    schema: dict,
    *,
    num_predict: int = 4096,
    seed: int = 42,
    temperature: float = 0.0,
):
    """Yield raw content tokens for SSE streaming.

    Unlike ask_ollama_json, this does NOT parse or validate — the caller
    accumulates and validates after the stream ends.
    """
    fmt = schema

    yield from _chat_stream(
        [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        fmt=fmt,
        num_predict=num_predict,
        seed=seed,
        temperature=temperature,
    )

