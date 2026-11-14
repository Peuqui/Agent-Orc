import stat
from pathlib import Path

import pytest

from agent_orc.gate_token import GATE_SECRET_FILE, GateSecretError, session_token, token_session
from agent_orc.state import state_dir


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))


def test_token_leads_back_to_its_session() -> None:
    assert token_session(session_token("horarium-a1b2c3")) == "horarium-a1b2c3"


def test_session_id_with_a_dot() -> None:
    assert token_session(session_token("odd.id")) == "odd.id"


def test_forged_cut_or_foreign_token_is_refused() -> None:
    token = session_token("horarium-a1b2c3")
    session_id, signature = token.rsplit(".", 1)
    assert token_session(f"other-id.{signature}") is None
    assert token_session(f"{session_id}.{'0' * len(signature)}") is None
    assert token_session(token[:-1]) is None
    assert token_session(session_id) is None
    assert token_session("") is None
    assert token_session("sk-no-key-required") is None


def test_token_of_another_secret_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    token = session_token("horarium-a1b2c3")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "other"))
    assert token_session(token) is None


def test_secret_is_created_once_and_closed_to_others() -> None:
    first = session_token("horarium-a1b2c3")
    assert session_token("horarium-a1b2c3") == first
    mode = stat.S_IMODE((state_dir() / GATE_SECRET_FILE).stat().st_mode)
    assert mode == 0o600


def test_secret_open_to_others_is_an_error() -> None:
    session_token("horarium-a1b2c3")
    (state_dir() / GATE_SECRET_FILE).chmod(0o644)
    with pytest.raises(GateSecretError, match="chmod 600"):
        session_token("horarium-a1b2c3")


def test_a_secret_created_meanwhile_is_kept_and_no_temporary_file_stays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent_orc import gate_token

    # Another start links its secret into place between this one's look and its own link.
    first = gate_token._create_secret

    def racing(path: Path) -> None:
        first(path)
        first(path)

    monkeypatch.setattr(gate_token, "_create_secret", racing)
    token = session_token("horarium-a1b2c3")
    monkeypatch.setattr(gate_token, "_create_secret", first)
    assert session_token("horarium-a1b2c3") == token
    assert [p.name for p in state_dir().iterdir()] == [GATE_SECRET_FILE]
