"""The error taxonomy and retry policy of app/services/ollama_service.py.

Nothing here reaches a real model: every test installs a StubClient as
`ollama_service._client`, which is the same global `get_client()` populates, so
`_chat` picks it up without any patching of the ollama package itself. The
autouse `_reset_singletons` fixture in conftest.py drops it afterwards.

The retry backoff is recorded rather than served, so the suite asserts on the
sleep schedule instead of spending 3s per exhausted-retry test waiting for it.
"""

import importlib.util
import json
from types import SimpleNamespace

import httpx
import pytest
from ollama import ResponseError
from pydantic import BaseModel, ValidationError

from app.services import ollama_service
from app.services.ollama_service import (
    RETRIES,
    OllamaBadOutput,
    OllamaError,
    OllamaTimeout,
    OllamaUnavailable,
    ask_ollama,
    ask_ollama_json,
    get_client,
)


ATTEMPTS = RETRIES + 1

# _chat sleeps 2 ** attempt between attempts and never after the last one, so
# an exhausted retry sequence is one sleep short of the attempt count.
FULL_BACKOFF = [2 ** attempt for attempt in range(RETRIES)]

# httpx raises ValueError casting the port. Anything the ollama client accepts
# (even "ftp://...") is no use here -- the constructor has to actually fail.
MALFORMED_HOST = "http://127.0.0.1:not-a-port"


class Postcard(BaseModel):
    """The smallest possible stand-in for TripPlan: something to validate."""

    place: str
    nights: int


VALID_JSON = '{"place": "Barcelona", "nights": 4}'


# ============================================================
# STUBS AND FIXTURES
# ============================================================

class StubClient:
    """Stands in for ollama.Client, replaying a scripted list of outcomes.

    An outcome is either an exception to raise or a response to return. The
    last one repeats forever, so "fails on every attempt" is a single entry
    rather than ATTEMPTS copies of it; a test that cares how many attempts
    happened asserts on len(calls), which is never capped.
    """

    def __init__(self, *outcomes):
        self.outcomes = outcomes
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes[min(len(self.calls), len(self.outcomes)) - 1]

        if isinstance(outcome, BaseException):
            raise outcome

        return outcome


@pytest.fixture
def sleeps(monkeypatch):
    """Record the retry backoff instead of serving it.

    Replaces the module's whole `time` reference rather than reaching into the
    real time module, so patching the backoff here cannot stop anything else
    in the process from sleeping.
    """
    recorded = []
    monkeypatch.setattr(
        ollama_service, "time", SimpleNamespace(sleep=recorded.append)
    )

    return recorded


@pytest.fixture
def make_client(sleeps):
    """Install a scripted StubClient and hand it back for inspection.

    Depends on `sleeps` so that installing a stub always disarms the backoff:
    a test that forgets to ask for the schedule still cannot sleep for real.
    """
    def build(*outcomes):
        ollama_service._client = StubClient(*outcomes)

        return ollama_service._client

    return build


def _load_module_afresh(name):
    """Execute ollama_service.py again under a throwaway module name.

    importlib.reload() is unusable here: it rebinds the live module's globals
    in place, which hands trip_service -- which did `from ... import
    OllamaBadOutput` -- a stale class object and silently breaks its except
    clause for every test that runs afterwards.
    """
    spec = importlib.util.spec_from_file_location(name, ollama_service.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def _validation_error():
    """A real pydantic ValidationError, as a bad request argument produces."""
    try:
        Postcard(place="Barcelona", nights="not a number")
    except ValidationError as exc:
        return exc


# ============================================================
# TAXONOMY
# ============================================================

def test_every_module_exception_is_an_ollama_error():
    """Callers catch OllamaError alone, so nothing may escape that base."""
    defined = {
        name: obj
        for name, obj in vars(ollama_service).items()
        if isinstance(obj, type)
        and issubclass(obj, BaseException)
        and obj.__module__ == ollama_service.__name__
    }

    # Guards the loop below against passing because it found nothing.
    assert {
        "OllamaError",
        "OllamaUnavailable",
        "OllamaTimeout",
        "OllamaBadOutput",
    } <= set(defined)

    for name, exception in defined.items():
        assert issubclass(exception, OllamaError), name


def test_timeout_raises_ollama_timeout_after_every_attempt(make_client, sleeps):
    """The except-clause order in _chat is load-bearing.

    httpx.TimeoutException is a SUBCLASS of httpx.HTTPError, so swapping the
    two handlers reports a slow model as OllamaUnavailable -- telling the user
    the server is down when it is merely thinking.
    """
    assert issubclass(httpx.TimeoutException, httpx.HTTPError)  # the premise

    timeout = httpx.ReadTimeout("model still loading")
    client = make_client(timeout)

    with pytest.raises(OllamaTimeout) as excinfo:
        ask_ollama("Plan me a trip.")

    assert type(excinfo.value) is OllamaTimeout
    assert excinfo.value.__cause__ is timeout
    assert len(client.calls) == ATTEMPTS
    assert sleeps == FULL_BACKOFF


def test_builtin_connection_error_raises_unavailable(make_client, sleeps):
    """The ollama client converts httpx.ConnectError into the BUILTIN
    ConnectionError, which is not an httpx type at all -- drop that handler
    and a refused connection escapes _chat completely unwrapped.
    """
    assert not issubclass(ConnectionError, httpx.HTTPError)  # the premise

    refused = ConnectionError("connection refused")
    client = make_client(refused)

    with pytest.raises(OllamaUnavailable) as excinfo:
        ask_ollama("Plan me a trip.")

    assert excinfo.value.__cause__ is refused
    assert len(client.calls) == ATTEMPTS
    assert sleeps == FULL_BACKOFF


def test_other_httpx_error_raises_unavailable(make_client, sleeps):
    """Any remaining httpx transport error is a reachability problem."""
    broken = httpx.RemoteProtocolError("server disconnected mid-response")
    client = make_client(broken)

    with pytest.raises(OllamaUnavailable) as excinfo:
        ask_ollama("Plan me a trip.")

    # The handler names the concrete type so the log says which one it was.
    assert "RemoteProtocolError" in str(excinfo.value)
    assert excinfo.value.__cause__ is broken
    assert len(client.calls) == ATTEMPTS
    assert sleeps == FULL_BACKOFF


def test_response_error_5xx_is_retried(make_client, sleeps):
    """A 5xx is the server having a bad moment, so it gets the full budget."""
    client = make_client(ResponseError("server overloaded", status_code=503))

    with pytest.raises(OllamaError) as excinfo:
        ask_ollama("Plan me a trip.")

    # Not OllamaUnavailable: the server answered, it just answered badly.
    assert type(excinfo.value) is OllamaError
    assert "503" in str(excinfo.value)
    assert len(client.calls) == ATTEMPTS
    assert sleeps == FULL_BACKOFF


def test_response_error_4xx_is_not_retried(make_client, sleeps):
    """A missing model or a bad request will fail identically forever, so
    retrying it just triples the latency before the same error surfaces.
    """
    client = make_client(ResponseError("model not found", status_code=404))

    with pytest.raises(OllamaError) as excinfo:
        ask_ollama("Plan me a trip.")

    assert type(excinfo.value) is OllamaError
    assert "404" in str(excinfo.value)
    assert "model not found" in str(excinfo.value)
    assert len(client.calls) == 1
    assert sleeps == []


def test_response_error_without_a_status_code_is_not_retried(make_client, sleeps):
    """ResponseError defaults status_code to -1, which is truthy. Only the
    explicit 500-599 range may retry, or an unclassifiable error would too.
    """
    client = make_client(ResponseError("something went wrong"))

    with pytest.raises(OllamaError):
        ask_ollama("Plan me a trip.")

    assert len(client.calls) == 1
    assert sleeps == []


def test_invalid_request_arguments_are_not_retried(make_client, sleeps):
    """A pydantic failure means the request we built is wrong, not the server."""
    client = make_client(_validation_error())

    with pytest.raises(OllamaError) as excinfo:
        ask_ollama("Plan me a trip.")

    assert type(excinfo.value) is OllamaError
    assert len(client.calls) == 1
    assert sleeps == []


# ============================================================
# RETRY RECOVERY
# ============================================================

def test_transient_failure_then_success_returns_the_success(
    make_client, sleeps, make_chat_response
):
    """Retrying is only worth its latency if a recovered call is actually
    returned rather than the failure being remembered and raised anyway.
    """
    client = make_client(
        httpx.ReadTimeout("first call timed out"),
        make_chat_response("Barcelona in five days."),
    )

    assert ask_ollama("Plan me a trip.") == "Barcelona in five days."
    assert len(client.calls) == 2
    assert sleeps == [1]


def test_success_on_the_final_permitted_attempt_does_not_raise(
    make_client, sleeps, make_chat_response
):
    """The off-by-one boundary: the last attempt still counts as a success."""
    client = make_client(
        httpx.ReadTimeout("cold model"),
        httpx.ReadTimeout("still cold"),
        make_chat_response("Barcelona in five days."),
    )

    assert ask_ollama("Plan me a trip.") == "Barcelona in five days."
    assert len(client.calls) == ATTEMPTS
    assert sleeps == FULL_BACKOFF


def test_first_attempt_success_never_sleeps(make_client, sleeps, make_chat_response):
    """The backoff must not be paid on the happy path."""
    client = make_client(make_chat_response("Barcelona in five days."))

    ask_ollama("Plan me a trip.")

    assert len(client.calls) == 1
    assert sleeps == []


# ============================================================
# ask_ollama
# ============================================================

def test_ask_ollama_returns_stripped_content(make_client, make_chat_response):
    client = make_client(make_chat_response("  Barcelona in five days.\n\n"))

    assert ask_ollama("Plan me a trip.") == "Barcelona in five days."

    # Free text must not be schema-constrained, and the code reads
    # .message.content, which only exists on a non-streamed response.
    assert client.calls[0]["format"] is None
    assert client.calls[0]["stream"] is False


@pytest.mark.parametrize("content", ["", "   ", "\n\t ", None])
def test_ask_ollama_rejects_blank_content(make_client, make_chat_response, content):
    """content is Optional[str], so None is a real response, not a test-ism."""
    make_client(make_chat_response(content))

    with pytest.raises(OllamaBadOutput):
        ask_ollama("Plan me a trip.")


def test_ask_ollama_uses_the_deterministic_default_options(
    make_client, make_chat_response
):
    client = make_client(make_chat_response("Barcelona in five days."))

    ask_ollama("Plan me a trip.")

    options = client.calls[0]["options"]
    assert options["seed"] == 42
    assert options["temperature"] == 0.0
    assert options["num_predict"] == 4096


# ============================================================
# ask_ollama_json
# ============================================================

def test_ask_ollama_json_parses_and_validates(make_client, make_chat_response):
    make_client(make_chat_response(VALID_JSON))

    postcard = ask_ollama_json("Plan me a trip.", Postcard)

    assert postcard == Postcard(place="Barcelona", nights=4)


def test_ask_ollama_json_rejects_a_truncated_response(
    make_client, make_chat_response
):
    """format=<schema> constrains the sampler but does not guarantee complete
    JSON: hitting num_predict yields done_reason == "length".

    The content here is deliberately VALID JSON. Truncated content would raise
    OllamaBadOutput from the parse step regardless, so this test would pass
    even with the done_reason check deleted -- and the real failure mode is a
    plan that parses but silently stops at day three.
    """
    make_client(make_chat_response(VALID_JSON, done_reason="length"))

    with pytest.raises(OllamaBadOutput) as excinfo:
        ask_ollama_json("Plan me a trip.", Postcard)

    assert "cut off" in str(excinfo.value)


def test_ask_ollama_json_rejects_malformed_json(make_client, make_chat_response):
    make_client(make_chat_response('{"place": "Barcelona", "nights":'))

    with pytest.raises(OllamaBadOutput) as excinfo:
        ask_ollama_json("Plan me a trip.", Postcard)

    assert isinstance(excinfo.value.__cause__, json.JSONDecodeError)


def test_ask_ollama_json_rejects_off_schema_json(make_client, make_chat_response):
    """Parseable is not the same as usable -- the caller gets a typed model
    back, so a wrong-shaped payload has to fail here, not at attribute access.
    """
    make_client(make_chat_response('{"place": "Barcelona", "nights": "a few"}'))

    with pytest.raises(OllamaBadOutput) as excinfo:
        ask_ollama_json("Plan me a trip.", Postcard)

    assert isinstance(excinfo.value.__cause__, ValidationError)


@pytest.mark.parametrize("content", ["", "   ", "\n\t ", None])
def test_ask_ollama_json_rejects_blank_content(
    make_client, make_chat_response, content
):
    make_client(make_chat_response(content))

    with pytest.raises(OllamaBadOutput):
        ask_ollama_json("Plan me a trip.", Postcard)


def test_ask_ollama_json_passes_the_caller_schema_straight_through(
    make_client, make_chat_response
):
    """Callers hand-tune the schema they send (trimming it changes what the
    sampler will emit), so it must arrive at the client unrewritten.
    """
    schema = {"type": "object", "required": ["place"]}
    client = make_client(make_chat_response(VALID_JSON))

    ask_ollama_json("Plan me a trip.", Postcard, schema=schema)

    assert client.calls[0]["format"] is schema


def test_ask_ollama_json_falls_back_to_the_model_schema(
    make_client, make_chat_response
):
    client = make_client(make_chat_response(VALID_JSON))

    ask_ollama_json("Plan me a trip.", Postcard)

    assert client.calls[0]["format"] == Postcard.model_json_schema()


def test_ask_ollama_json_forwards_the_sampler_options(
    make_client, make_chat_response
):
    """A caller that rejects a plan and asks again needs a DIFFERENT sample;
    at temperature 0 only a new seed can produce one, so a dropped seed
    argument turns a retry into the same bytes forever.
    """
    client = make_client(make_chat_response(VALID_JSON))

    ask_ollama_json(
        "Plan me a trip.",
        Postcard,
        num_predict=512,
        seed=99,
        temperature=0.7,
    )

    options = client.calls[0]["options"]
    assert options["seed"] == 99
    assert options["temperature"] == 0.7
    assert options["num_predict"] == 512


# ============================================================
# get_client
# ============================================================

def test_get_client_memoises_the_client():
    """The client owns the httpx connection pool; rebuilding it per call
    throws the pooling away and reconnects on every request.
    """
    assert ollama_service._client is None  # no stub installed here

    assert get_client() is get_client()


def test_get_client_wraps_a_malformed_host(monkeypatch):
    """A bad OLLAMA_HOST is a reachability problem the caller can report, not
    a ValueError escaping from three layers down.
    """
    monkeypatch.setattr(ollama_service, "HOST", MALFORMED_HOST)

    with pytest.raises(OllamaUnavailable) as excinfo:
        get_client()

    assert isinstance(excinfo.value.__cause__, ValueError)

    # A half-built client must not be cached: the next call has to be free to
    # succeed once the host is corrected.
    assert ollama_service._client is None


def test_a_malformed_host_does_not_break_import(monkeypatch):
    """Building the client at import time made a typo'd OLLAMA_HOST kill the
    whole process on startup, with a ValueError and no usable context. It has
    to stay lazy: importing must succeed and the error must wait for a caller.
    """
    monkeypatch.setenv("OLLAMA_HOST", MALFORMED_HOST)

    fresh = _load_module_afresh("ollama_service_malformed_host")

    assert fresh.HOST == MALFORMED_HOST  # the env var really did land
    assert fresh._client is None

    with pytest.raises(fresh.OllamaUnavailable):
        fresh.get_client()
