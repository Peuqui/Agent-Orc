<p align="center"><img src="frontend/brand/logo.svg" alt="Agent-Ørc — Agent Orchestrator" width="440"></p>

[Deutsch](README.de.md)

> **Status: early, but usable.** Tested on Linux with Claude Code; other agent profiles
> (Codex, Aider) are prepared but untested.

Agent-Orc lets you start, watch and stop coding-agent CLI sessions
(Claude Code, Codex, Aider, …) on your own Linux machine from a
mobile-friendly web app (PWA).

Every agent runs in its own `tmux` session inside a project folder.
From your phone you can:

- create project folders and start an agent in them with one tap,
- open a terminal on any running agent, with an extra-keys bar
  (Esc, Tab, Shift+Tab, arrows, sticky Ctrl/Alt) above the on-screen keyboard,
- send text through a plain input field, so dictation and autocorrect work,
- stop and resume sessions,
- browse, edit and trash files in the project folder.

Claude Code sessions are started with Remote Control, so they also show up
in the Claude mobile app.

## Requirements

- Linux
- Python 3.12+
- `tmux`
- Node.js with npm (builds the web app during installation)
- the agent CLIs you want to use
- optional, for dictation in the terminal: [whisper-stt](https://github.com/Peuqui/whisper-stt)
  (local speech recognition); without it the browser's own recognition is used where it has
  one (Chrome)

## Installation

Agent-Orc is a Python package that ships the built web app. Until it is published, install it
from the repository:

```
git clone https://github.com/Peuqui/Agent-Orc.git && cd Agent-Orc
deploy/install.sh          # builds the web app, installs into ~/.local/share/agent-orc/venv
agent-orc init             # writes ~/.config/agent-orc/config.yaml
agent-orc set-password     # writes ~/.config/agent-orc/credentials.json
agent-orc serve            # http://127.0.0.1:8770
```

`deploy/install.sh` links the command into `~/.local/bin`, which must be on your `PATH`. Run it
again after `git pull` to update; it installs only committed code and restarts a running
`agent-orc@<user>` service (the user needs the right to restart it, e.g. a polkit rule).

Adapt `~/.config/agent-orc/config.yaml` before the first start, at least `files.base_dir`
(the folder that holds your projects). For a first test on plain HTTP, set
`server.cookie_secure: false`; behind HTTPS keep it `true`.

### As a service

`deploy/agent-orc@.service` runs Agent-Orc for one user (`agent-orc` must be on that user's `PATH`):

```
sudo cp deploy/agent-orc@.service /etc/systemd/system/
sudo systemctl enable --now agent-orc@$USER
```

Restarting the service keeps running agents alive; they are picked up again.

### Behind nginx

`deploy/nginx-location.conf` serves Agent-Orc under `/agent-orc/` inside an HTTPS server block,
including the terminal WebSocket.

## Security

Agent-Orc gives remote shell-level access to your machine. It ships with its
own login and listens on `127.0.0.1` only. Expose it to the internet only
behind HTTPS, ideally behind a reverse proxy with additional authentication.

## License

[MIT](LICENSE)
