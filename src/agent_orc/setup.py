"""First-run setup (`agent-orc setup`): asks the few things every installation differs in,
checks the machine, and writes the config and the password.

The config is the shipped default (default_config.yaml) with the answers filled in, so its
comments stay and explain every other setting.
"""

import getpass
import glob
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from agent_orc.auth import new_credentials, save_credentials
from agent_orc.backends import BackendError, fetch_json, listed_models
from agent_orc.config import (
    CONFIG_FILE_NAME,
    CREDENTIALS_FILE_NAME,
    BackendConfig,
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
# The kinds of backend that can be set up, and the profile that starts Claude Code on one.
BACKEND_PRESETS_FILE = "backend_presets.yaml"
PROFILE_TEMPLATE_FILE = "claude_backend_profile.yaml"
BACKEND_KEY_FILE_MODE = 0o600


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
    # Backends to set up: kind (a key of the presets) to its `backends` entry.
    backends: dict[str, dict[str, Any]] = field(default_factory=dict)


def backend_presets() -> dict[str, Any]:
    text = files("agent_orc").joinpath(BACKEND_PRESETS_FILE).read_text(encoding="utf-8")
    presets: dict[str, Any] = yaml.safe_load(text)
    return presets


def backend_entry(preset: dict[str, Any], address: str, listed: list[str]) -> dict[str, Any]:
    """The `backends` entry of a kind: what the preset fixes, the address asked for, and the
    models the preset names, otherwise those the server lists."""
    entry = dict(preset["backend"])
    entry["base_urls"] = [address]
    # The names are patterns in the config: what the server calls a model is taken literally.
    entry.setdefault("models", {glob.escape(name): {} for name in listed})
    return entry


def profile_text(kind: str, preset: dict[str, Any]) -> str:
    """The profile that starts Claude Code on the backend `kind`, from the shipped template."""
    text = files("agent_orc").joinpath(PROFILE_TEMPLATE_FILE).read_text(encoding="utf-8")
    profile = preset["profile"]
    values = {"profile": f"claude-{kind}", "backend": kind, **profile}
    lines = []
    for line in text.splitlines(keepends=True):
        names = re.findall(r"@(\w+)@", line)
        if any(name not in values for name in names):
            continue  # an optional line (the hint) the preset does not give
        lines.append(re.sub(r"@(\w+)@", lambda match: str(values[match.group(1)]), line))
    return "".join(lines)


def with_backends(text: str, backends: dict[str, dict[str, Any]]) -> str:
    """The config text with the `backends` section and a profile per backend added: the section
    before `agents:`, the profiles after the others, before `shell:`."""
    if not backends:
        return text
    presets = backend_presets()
    section = "backends:\n" + "".join(
        f"  {line}\n" if line else "\n"
        for line in yaml.safe_dump(backends, sort_keys=False, allow_unicode=True).splitlines()
    )
    profiles = "".join(profile_text(kind, presets[kind]) for kind in backends)
    text, sections = re.subn(
        r"^agents:\n", lambda _: f"{section}\nagents:\n", text, count=1, flags=re.MULTILINE
    )
    text, shells = re.subn(
        r"^  shell:\n", lambda _: f"{profiles}  shell:\n", text, count=1, flags=re.MULTILINE
    )
    if sections != 1 or shells != 1:
        raise ValueError("the config has no `agents:` section with a `shell` profile to add to")
    return text


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
    return with_backends(text, answers.backends)


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


def write_key(path: Path, key: str) -> None:
    """The API key in a file readable for the user alone."""
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, BACKEND_KEY_FILE_MODE)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        # The mode of `os.open` holds only for a new file; a file that is there keeps its own.
        os.fchmod(descriptor, BACKEND_KEY_FILE_MODE)
        handle.write(key + "\n")


def ask_backend(preset: dict[str, Any]) -> dict[str, Any] | None:
    """Ask whether to run Claude Code on a kind of backend, and where. None: not wanted, or the
    server does not answer (said so; nothing is written for it)."""
    if not ask_yes(f"Run Claude Code on {preset['label']}?", False):
        return None
    address = ask("Address of the server", preset["address"])
    fixed = preset["backend"]
    key = fixed.get("key")
    if "key_file" in fixed:
        key = getpass.getpass(f"API key (kept in {fixed['key_file']}, readable for you alone): ")
        if not key:
            print("No key given; skipped.")
            return None
        write_key(Path(fixed["key_file"]), key)
    try:
        listed = listed_models(
            BackendConfig.model_validate(backend_entry(preset, address, [])),
            address,
            key,
            fetch_json,
        )
    except BackendError as error:
        print(f"Skipped: {error}")
        return None
    if not listed:
        print(f"Skipped: {address} lists no models.")
        return None
    return backend_entry(preset, address, listed)


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
    if ask_yes("Do you run a speech-to-text service (STT-Suite) for dictation?", False):
        whisper_url = ask("Its address", defaults["dictation"]["whisper_url"])
        if not whisper_reachable(whisper_url):
            print(f"Note: {whisper_url} does not answer right now; dictation needs it running.")

    backends = {}
    for kind, preset in backend_presets().items():
        entry = ask_backend(preset)
        if entry is not None:
            backends[kind] = entry

    contact = input("Your e-mail address for the push services (Enter: skip): ").strip()
    push_contact = f"mailto:{contact}" if contact else None

    password = ask_password() if socket is None else None

    answers = SetupAnswers(base_dir, behind_https, whisper_url, push_contact, socket, backends)
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
