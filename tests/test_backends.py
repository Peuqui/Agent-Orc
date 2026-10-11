"""Claude Code on other backends: levels, the offered models, the environment, the start."""

import json
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from agent_orc import cli
from agent_orc.backends import (
    BackendError,
    Launch,
    choose_model,
    claude_environment,
    entry_of,
    free_note,
    level_arguments,
    levels_of,
    models_lines,
    offered,
    prepare_launch,
    reachable_base_url,
    resolve_key,
    split_effort,
    translate_level,
)
from agent_orc.config import BackendConfig, BackendModelConfig

TODAY = date(2026, 10, 11)


def backend(**changes: Any) -> BackendConfig:
    fields: dict[str, Any] = {
        "label": "Local models",
        "base_urls": ["http://one", "http://two"],
        "key": "no-key",
        "models": {
            "Qwen-27B-vllm": {"levels": ["low", "medium", "xhigh"]},
            "Qwen-Flash*": {"levels": ["low", "xhigh"], "free_until": date(2026, 11, 24)},
            "Plain-model": {},
        },
    }
    return BackendConfig.model_validate({**fields, **changes})


def server_listing(*names: str) -> dict[str, Any]:
    return {"data": [{"id": name} for name in names]}


class FakeServer:
    """Answers per address and path from a dictionary; an address not in it does not answer."""

    def __init__(self, answers: dict[str, Any]) -> None:
        self.answers = answers
        self.asked: list[tuple[str, str | None]] = []

    def __call__(self, url: str, key: str | None, timeout: float) -> Any:
        self.asked.append((url, key))
        if url not in self.answers:
            raise OSError(f"no answer from {url}")
        return self.answers[url]


def test_a_level_the_model_takes_is_kept() -> None:
    assert translate_level("medium", ["low", "medium", "xhigh"]) == "medium"


def test_a_level_the_model_does_not_take_becomes_the_next_higher_one() -> None:
    assert translate_level("high", ["low", "medium", "xhigh"]) == "xhigh"


def test_without_a_higher_level_the_highest_one_is_taken() -> None:
    assert translate_level("max", ["high", "xhigh"]) == "xhigh"


def test_an_unknown_level_is_refused() -> None:
    with pytest.raises(BackendError, match="unknown level"):
        translate_level("ultra", ["low"])


def test_the_first_entry_that_fits_a_name_counts() -> None:
    config = backend()
    assert entry_of(config, "Qwen-Flash-Next-180B") == config.models["Qwen-Flash*"]
    assert entry_of(config, "Qwen-27B-vllm") == config.models["Qwen-27B-vllm"]
    assert entry_of(config, "Something-else") is None


def test_only_configured_models_are_offered_and_not_after_their_quota() -> None:
    listed = ["Zed-unconfigured", "Qwen-Flash-1", "Qwen-27B-vllm", "Plain-model"]
    assert offered(listed, backend(), TODAY) == ["Plain-model", "Qwen-27B-vllm", "Qwen-Flash-1"]
    # On the last free day it is still offered, the day after it is not.
    assert "Qwen-Flash-1" in offered(listed, backend(), date(2026, 11, 24))
    assert "Qwen-Flash-1" not in offered(listed, backend(), date(2026, 11, 25))


def test_the_note_says_how_long_a_model_is_free() -> None:
    entry = BackendModelConfig(free_until=date(2026, 11, 24))
    assert free_note(entry, TODAY) == "free until 2026-11-24 (44 days left)"
    assert free_note(entry, date(2026, 11, 23)) == "free until 2026-11-24 (1 day left)"
    assert free_note(BackendModelConfig(), TODAY) == ""


def test_the_key_is_exactly_one_of_a_value_a_file_and_a_variable() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        backend(key=None)
    with pytest.raises(ValidationError, match="exactly one"):
        backend(key_env="SOME_KEY")


def test_the_key_comes_from_where_it_is_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert resolve_key(backend()) == "no-key"
    monkeypatch.setenv("TEST_BACKEND_KEY", "from-environment")
    assert resolve_key(backend(key=None, key_env="TEST_BACKEND_KEY")) == "from-environment"
    key_file = tmp_path / "backend.key"
    key_file.write_text("from-file\n", encoding="utf-8")
    assert resolve_key(backend(key=None, key_file=str(key_file))) == "from-file"


def test_a_missing_key_is_said_and_not_made_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TEST_BACKEND_KEY", raising=False)
    with pytest.raises(BackendError, match="TEST_BACKEND_KEY"):
        resolve_key(backend(key=None, key_env="TEST_BACKEND_KEY"))
    with pytest.raises(BackendError, match="cannot be read"):
        resolve_key(backend(key=None, key_file=str(tmp_path / "missing.key")))


def test_the_first_address_that_answers_is_used() -> None:
    fetch = FakeServer({"http://two/v1/models": server_listing()})
    assert reachable_base_url(backend(), "k", fetch) == "http://two"
    assert [url for url, _ in fetch.asked] == ["http://one/v1/models", "http://two/v1/models"]


def test_no_answering_address_is_said() -> None:
    with pytest.raises(BackendError, match="does not answer at http://one, http://two"):
        reachable_base_url(backend(), "k", FakeServer({}))


def test_the_models_to_choose_from_carry_their_note() -> None:
    fetch = FakeServer(
        {"http://one/v1/models": server_listing("Qwen-Flash-1", "Qwen-27B-vllm", "Other")}
    )
    assert models_lines(backend(), TODAY, fetch) == [
        "Qwen-27B-vllm",
        "Qwen-Flash-1\tfree until 2026-11-24 (44 days left)",
    ]


def test_the_levels_of_a_model_are_those_in_the_configuration() -> None:
    assert levels_of(backend(), "Qwen-27B-vllm") == ["low", "medium", "xhigh"]
    assert levels_of(backend(), "Plain-model") == []
    assert levels_of(backend(), "Unknown") == []


def test_a_model_without_levels_gets_no_effort_and_one_with_levels_the_translated_one() -> None:
    config = backend()
    assert level_arguments(entry_of(config, "Plain-model"), "high") == []
    assert level_arguments(entry_of(config, "Qwen-27B-vllm"), "high") == ["--effort", "xhigh"]
    # Without a wish Claude Code's own default counts.
    assert level_arguments(entry_of(config, "Qwen-27B-vllm"), None) == ["--effort", "xhigh"]


def test_efforts_in_the_arguments_and_in_the_environment_are_told_from_the_rest() -> None:
    assert split_effort(["--settings", "s.json", "--effort", "low", "prompt"], None) == (
        "low",
        ["--settings", "s.json", "prompt"],
    )
    assert split_effort(["--effort=max"], "low") == ("max", [])
    assert split_effort(["--continue"], "medium") == ("medium", ["--continue"])
    assert split_effort([], None) == (None, [])


def test_claude_code_is_pointed_at_the_backend_and_every_alias_at_the_model() -> None:
    config = backend(
        anthropic_path="/apps/anthropic",
        key_variable="ANTHROPIC_AUTH_TOKEN",
        background_model="Qwen-Flash-1",
        api_timeout_ms=600000,
    )
    environment = claude_environment(config, "http://one", "Qwen-27B-vllm", "secret", 262144)
    assert environment == {
        "AGENT_ORC_BACKEND_URL": "http://one",
        "AGENT_ORC_BACKEND_MODEL": "Qwen-27B-vllm",
        "ANTHROPIC_BASE_URL": "http://one/apps/anthropic",
        "ANTHROPIC_AUTH_TOKEN": "secret",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "Qwen-Flash-1",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "Qwen-27B-vllm",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "Qwen-27B-vllm",
        "CLAUDE_CODE_SUBAGENT_MODEL": "Qwen-27B-vllm",
        "API_TIMEOUT_MS": "600000",
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "262144",
    }


def test_without_a_background_model_the_chosen_one_does_those_requests() -> None:
    environment = claude_environment(
        backend(key_variable="ANTHROPIC_API_KEY"), "http://one", "Plain-model", "k", None
    )
    assert environment["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "Plain-model"
    assert "ANTHROPIC_API_KEY" in environment
    assert "API_TIMEOUT_MS" not in environment
    assert "CLAUDE_CODE_MAX_CONTEXT_TOKENS" not in environment


def listing_fetch(*extra: tuple[str, Any]) -> FakeServer:
    return FakeServer(
        {"http://one/v1/models": server_listing("Qwen-27B-vllm", "Plain-model"), **dict(extra)}
    )


def test_the_start_runs_claude_on_the_model_with_the_translated_effort() -> None:
    launch = prepare_launch(
        backend(), "Qwen-27B-vllm", "high", ["--settings", "s.json"], TODAY, listing_fetch()
    )
    assert launch.command == [
        "claude",
        "--model",
        "Qwen-27B-vllm",
        "--settings",
        "s.json",
        "--effort",
        "xhigh",
    ]
    assert launch.environment["ANTHROPIC_BASE_URL"] == "http://one"
    assert launch.environment["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "Qwen-27B-vllm"


def test_the_context_length_the_server_reports_is_handed_to_claude_code() -> None:
    config = backend(context_path="/upstream/{model}/v1/models")
    fetch = listing_fetch(
        ("http://one/upstream/Qwen-27B-vllm/v1/models", {"data": [{"max_model_len": 131072}]})
    )
    launch = prepare_launch(config, "Qwen-27B-vllm", None, [], TODAY, fetch)
    assert launch.environment["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] == "131072"


def test_a_server_that_does_not_report_the_context_length_is_not_an_error() -> None:
    config = backend(context_path="/upstream/{model}/v1/models")
    launch = prepare_launch(config, "Qwen-27B-vllm", None, [], TODAY, listing_fetch())
    assert "CLAUDE_CODE_MAX_CONTEXT_TOKENS" not in launch.environment


def test_a_model_that_is_not_on_offer_is_refused() -> None:
    with pytest.raises(BackendError, match="not on offer"):
        prepare_launch(backend(), "Qwen-Flash-1", None, [], TODAY, listing_fetch())


def test_the_command_before_the_start_gets_the_address_and_the_model() -> None:
    ran: list[list[str]] = []

    def run_hook(command: list[str]) -> str | None:
        ran.append(command)
        return None

    config = backend(before_start=["free-gpus", "{base_url}", "{model}"])
    prepare_launch(config, "Qwen-27B-vllm", None, [], TODAY, listing_fetch(), run_hook)
    assert ran == [["free-gpus", "http://one", "Qwen-27B-vllm"]]


def test_a_failing_command_before_the_start_is_reported_and_the_start_goes_on(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = backend(before_start=["free-gpus"])
    launch = prepare_launch(
        config, "Qwen-27B-vllm", None, [], TODAY, listing_fetch(), lambda command: "it failed"
    )
    assert launch.command[:3] == ["claude", "--model", "Qwen-27B-vllm"]
    assert "warning: it failed" in capsys.readouterr().err


def test_the_model_is_chosen_by_number_or_name() -> None:
    models = ["Plain-model", "Qwen-Flash-1\tfree until 2026-11-24 (44 days left)"]
    assert choose_model(models, lambda prompt: "2") == "Qwen-Flash-1"
    assert choose_model(models, lambda prompt: "Plain-model") == "Plain-model"
    with pytest.raises(BackendError, match="no such model"):
        choose_model(models, lambda prompt: "9")


class ModelsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps(server_listing("Qwen-27B-vllm", "Plain-model", "Unlisted")).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *arguments: Any) -> None:  # noqa: A002
        pass


@pytest.fixture
def served_models() -> Any:
    server = HTTPServer(("127.0.0.1", 0), ModelsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def write_config(directory: Path, address: str) -> None:
    from agent_orc.config import default_config_text

    text = default_config_text() + (
        f'\nbackends:\n  local:\n    label: Local\n    base_urls: ["{address}"]\n    key: no-key\n'
        "    models:\n      Qwen-27B-vllm: {levels: [low, medium, xhigh]}\n      Plain-model: {}\n"
    )
    (directory / "agent-orc").mkdir()
    (directory / "agent-orc" / "config.yaml").write_text(text, encoding="utf-8")


def test_the_command_lists_the_models_and_their_levels_from_a_real_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    served_models: str,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_config(tmp_path, served_models)

    cli.run_backend(["models", "local"])
    assert capsys.readouterr().out.splitlines() == ["Plain-model", "Qwen-27B-vllm"]

    cli.run_backend(["levels", "local", "Qwen-27B-vllm"])
    assert capsys.readouterr().out.strip() == "low medium xhigh"


def test_the_command_starts_claude_code_with_what_the_profile_handed_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, served_models: str
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("AGENT_ORC_EFFORT", "low")
    write_config(tmp_path, served_models)
    started: list[Launch] = []
    monkeypatch.setattr(cli, "exec_claude", started.append)

    cli.run_backend(["run", "local", "Qwen-27B-vllm", "--settings", "s.json", "hello"])

    assert started[0].command == [
        "claude",
        "--model",
        "Qwen-27B-vllm",
        "--settings",
        "s.json",
        "hello",
        "--effort",
        "low",
    ]
    assert started[0].environment["ANTHROPIC_BASE_URL"] == served_models


def test_an_unknown_backend_stops_with_a_clear_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_config(tmp_path, "http://127.0.0.1:1")
    with pytest.raises(SystemExit, match="no backend 'nowhere'"):
        cli.run_backend(["models", "nowhere"])


def test_wrong_arguments_print_how_to_call_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_config(tmp_path, "http://127.0.0.1:1")
    with pytest.raises(SystemExit, match="usage: agent-orc backend"):
        cli.run_backend([])
