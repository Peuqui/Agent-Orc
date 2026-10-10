"""First-run setup (`agent-orc setup`): asks the few things every installation differs in,
checks the machine, and writes the config and the password.

The config is the shipped default (default_config.yaml) with the answers filled in, so its
comments stay and explain every other setting.
"""

import getpass
import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import yaml

from agent_orc.auth import new_credentials, save_credentials
from agent_orc.config import (
    CONFIG_FILE_NAME,
    CREDENTIALS_FILE_NAME,
    config_dir,
    default_config_text,
    load_config,
)

# Programs looked for on the PATH: required ones, and the agent CLIs a profile may start.
REQUIRED_PROGRAMS = ("tmux", "git")
AGENT_PROGRAMS = ("claude", "codex", "aider")
WHISPER_HEALTH_PATH = "/health"
WHISPER_CHECK_SECONDS = 5
# Where a machine controlled by another Agent-Orc listens; the folder is the user's alone.
DEFAULT_SOCKET = "~/.local/state/agent-orc/run/agent-orc.sock"


@dataclass(frozen=True)
class SetupAnswers:
    base_dir: str
    # False: plain HTTP for a first local test; True behind HTTPS. Unused with a socket.
    behind_https: bool
    # None: no Whisper service, the browser's own speech recognition listens.
    whisper_url: str | None
    # None: the default placeholder stays.
    push_contact: str | None
    # A socket to listen on instead of a port (another Agent-Orc controls this machine through
    # SSH, nobody logs in); None: the port with a login.
    socket: str | None = None


def set_value(text: str, section: str, key: str, value: str | bool | None) -> str:
    """Set `key` in the top-level `section` of a YAML text, keeping everything else as it is."""
    section_match = re.search(rf"^{re.escape(section)}:\n", text, re.MULTILINE)
    if section_match is None:
        raise ValueError(f"section {section!r} not in the config")
    following = re.search(r"^\S", text[section_match.end() :], re.MULTILINE)
    end = section_match.end() + following.start() if following else len(text)
    body = text[section_match.end() : end]
    rendered = "null" if value is None else json.dumps(value)
    new_body, count = re.subn(
        rf"^(  {re.escape(key)}:) .*$", rf"\g<1> {rendered}", body, count=1, flags=re.MULTILINE
    )
    if count == 0:
        raise ValueError(f"{section}.{key} not in the config")
    return text[: section_match.end()] + new_body + text[end:]


def listen_on_socket(text: str, socket: str) -> str:
    """The `server` section replaced by one that listens on `socket`."""
    section = re.search(r"^server:\n(?:(?:[ #].*)?\n)*", text, re.MULTILINE)
    if section is None:
        raise ValueError("section 'server' not in the config")
    replacement = (
        "server:\n"
        "  # No login: the folder of the socket is the user's alone, and the Agent-Orc that\n"
        "  # controls this machine reaches it through SSH.\n"
        f"  socket: {json.dumps(socket)}\n\n"
    )
    return text[: section.start()] + replacement + text[section.end() :].lstrip("\n")


def configured_text(answers: SetupAnswers) -> str:
    text = default_config_text()
    text = set_value(text, "files", "base_dir", answers.base_dir)
    if answers.socket is not None:
        text = listen_on_socket(text, answers.socket)
    else:
        text = set_value(text, "server", "cookie_secure", answers.behind_https)
    text = set_value(text, "dictation", "whisper_url", answers.whisper_url)
    if answers.push_contact is not None:
        text = set_value(text, "push", "contact", answers.push_contact)
    return text


def whisper_reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(
            url.rstrip("/") + WHISPER_HEALTH_PATH, timeout=WHISPER_CHECK_SECONDS
        ):
            return True
    except (urllib.error.URLError, OSError):
        return False


def ask(question: str, default: str) -> str:
    answer = input(f"{question} [{default}]: ").strip()
    return answer or default


def ask_yes(question: str, default: bool) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = input(f"{question} [{hint}]: ").strip().lower()
    # German answers count too.
    return default if answer == "" else answer in ("y", "yes", "j", "ja")


def check_programs() -> None:
    missing = [program for program in REQUIRED_PROGRAMS if shutil.which(program) is None]
    if missing:
        sys.exit(f"Missing on this machine: {', '.join(missing)}. Install it first.")
    agents = [program for program in AGENT_PROGRAMS if shutil.which(program) is not None]
    print(f"Agent CLIs found: {', '.join(agents) if agents else 'none yet (install one later)'}")


def ask_password() -> str:
    while True:
        password = getpass.getpass("Password for the web app: ")
        if not password:
            print("The password must not be empty.")
        elif password != getpass.getpass("Repeat the password: "):
            print("The passwords do not match.")
        else:
            return password


def run_setup() -> None:
    directory = config_dir()
    config_path = directory / CONFIG_FILE_NAME
    if config_path.exists():
        sys.exit(f"Config already exists: {config_path} (change it there, or delete it first)")
    print("Agent-Orc setup\n")
    check_programs()
    # The suggestions are the shipped defaults.
    defaults = yaml.safe_load(default_config_text())

    base_dir = ask("Folder that holds your projects", defaults["files"]["base_dir"])
    projects = Path(base_dir).expanduser()
    if not projects.is_dir() and ask_yes(f"{projects} does not exist. Create it?", True):
        projects.mkdir(parents=True)

    socket: str | None = None
    behind_https = False
    if ask_yes(
        "Does another Agent-Orc control this machine through SSH (listen on a socket, no login)?",
        False,
    ):
        socket = ask("Socket", DEFAULT_SOCKET)
    else:
        behind_https = ask_yes(
            "Will Agent-Orc run behind HTTPS (reverse proxy)? No: plain HTTP for a local test",
            False,
        )

    whisper_url: str | None = None
    if ask_yes("Do you run a Whisper service (whisper-stt) for dictation?", False):
        whisper_url = ask("Its address", defaults["dictation"]["whisper_url"])
        if not whisper_reachable(whisper_url):
            print(f"Note: {whisper_url} does not answer right now; dictation needs it running.")

    contact = input("Your e-mail address for the push services (Enter: skip): ").strip()
    push_contact = f"mailto:{contact}" if contact else None

    password = ask_password() if socket is None else None

    answers = SetupAnswers(base_dir, behind_https, whisper_url, push_contact, socket)
    directory.mkdir(parents=True, exist_ok=True)
    config_path.write_text(configured_text(answers), encoding="utf-8")
    # Written config must be valid, or the first `agent-orc serve` would fail.
    config = load_config(config_path)
    if password is None:
        print(f"\nWrote {config_path}. Start it with `agent-orc serve`; it listens on {socket}.")
        return
    save_credentials(directory / CREDENTIALS_FILE_NAME, new_credentials(password))

    print(f"\nWrote {config_path} and the password.")
    print(
        f"Start it with `agent-orc serve`, then open http://{config.server.host}:{config.server.port}"
    )
