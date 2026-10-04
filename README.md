<p align="center"><img src="frontend/brand/logo.svg" alt="Agent-Ørc — Agent Orchestrator" width="440"></p>

[Deutsch](README.de.md)

> **Status: early, but in daily use.** Tested on Linux with Claude Code; the profiles for
> Codex and Aider are prepared but untested.

Agent-Orc starts, watches and stops coding agents (Claude Code, Codex, Aider, …) on your own
Linux machine, from a web app that works on the phone as well as on the desktop (PWA).

Every agent runs in its own `tmux` session inside a project folder. Closing the browser only
detaches: the agents keep working, and you pick them up again from any device.

<p align="center">
  <img src="docs/screenshots/overview-en.png" alt="Overview: agent cards with context ring, effort slider and Claude usage" width="860">
</p>

## What it does

**Agents**
- Pick a folder and start an agent with one tap; stop, resume, or resume an older Claude
  conversation of that folder.
- Every card shows the agent's model, how full its context is (ring: green, amber, red from
  70 %), whether it is working right now, and the reasoning effort as a slider with an
  ultracode switch (Claude, per project folder).
- Claude's 5-hour and weekly usage at the top; cards can be dragged into your own order.

**Workspaces**
- Several agents side by side as columns; drag the column heads to sort them and the dividers
  to set their width.
- Every browser tab has its own workspace. Give it a name and it is saved, shows up in the
  overview and in the bar of every workspace, and one click jumps to the tab that shows it –
  handy for spreading workspaces over several monitors. On the phone the bar switches in place.

<p align="center">
  <img src="docs/screenshots/workspace-en.png" alt="Workspace with two agents side by side" width="860">
</p>

**Terminal**
- A plain input field below the terminal, so phone keyboards, autocorrect and dictation work;
  Enter sends, Shift+Enter starts a new line.
- Dictation through a local Whisper service ([whisper-stt](https://github.com/Peuqui/whisper-stt),
  GPU or CPU) or the browser's own speech recognition.
- Attach a photo or file: it lands in the project folder and its `@path` goes into the input field.
- Extra-keys bar (Esc, Tab, Shift+Tab, arrows, sticky Ctrl/Alt, …) for the on-screen keyboard,
  a jog grip for fast scrolling, font size per terminal, a text view for selecting and copying,
  clickable links.

**Files and more**
- Browse, edit and trash files in your project folders.
- Settings per device (font, size, line spacing, scroll speed) and a help dialog (light bulb).
- Claude Code sessions start with Remote Control, so they also show up in the Claude app.

<p align="center">
  <img src="docs/screenshots/phone-overview-en.png" alt="Overview on the phone" width="280">
  &nbsp;&nbsp;
  <img src="docs/screenshots/phone-terminal-en.png" alt="Terminal on the phone with input field and extra keys" width="280">
</p>

## Requirements

- Linux with `git` and `tmux`
- Python 3.12 or newer
- Node.js 20.19 or newer with npm (builds the web app during installation)
- the agent CLIs you want to use, e.g. [Claude Code](https://docs.claude.com/en/docs/claude-code)
- optional, for dictation: [whisper-stt](https://github.com/Peuqui/whisper-stt) (local speech
  recognition)

## Installation

```bash
git clone https://github.com/Peuqui/Agent-Orc.git && cd Agent-Orc
deploy/install.sh          # builds the web app, installs into ~/.local/share/agent-orc/venv
agent-orc init             # writes ~/.config/agent-orc/config.yaml
agent-orc set-password     # writes ~/.config/agent-orc/credentials.json
agent-orc serve            # http://127.0.0.1:8770
```

`deploy/install.sh` links the `agent-orc` command into `~/.local/bin`, which must be on your
`PATH`.

Before the first start, adapt `~/.config/agent-orc/config.yaml`:

- `files.base_dir`: the folder that holds your projects (default `~/projects`).
- `server.cookie_secure`: `false` for a first test on plain HTTP (`http://127.0.0.1:8770`);
  keep `true` behind HTTPS.
- `dictation.whisper_url`: `null` if you run no Whisper service; the microphone then uses the
  browser's own speech recognition (Chrome).

Then open `http://127.0.0.1:8770` and log in with your password.

### Updating

```bash
git pull && deploy/install.sh
```

The script installs only committed code and restarts a running `agent-orc@<user>` service;
for that the user needs the right to restart it (e.g. a polkit rule), otherwise restart it
yourself. Running agents keep running across the restart.

### As a service

`deploy/agent-orc@.service` runs Agent-Orc for one user (`agent-orc` must be on that user's
`PATH`):

```bash
sudo cp deploy/agent-orc@.service /etc/systemd/system/
sudo systemctl enable --now agent-orc@$USER
```

### Behind nginx

`deploy/nginx-location.conf` serves Agent-Orc under `/agent-orc/` inside an HTTPS server block,
including the terminal WebSocket. Behind HTTPS the app can be installed on the phone's home
screen.

### Tip: let new agents get going at once

A Claude Code agent waits for your first message. Its start command in the config takes a first
request at the end, e.g. to run the steps your hooks ask for:

```yaml
agents:
  claude:
    start: [claude, --settings, ..., --remote-control, "{name}",
      "Session start: run the mandatory steps from your start context, then say in one sentence that you are ready."]
```

Resuming does not repeat it.

## Security

Agent-Orc gives shell-level access to your machine. It has its own login and listens on
`127.0.0.1` only. Expose it to the internet only behind HTTPS, ideally behind a reverse proxy
with additional authentication.

## License

[MIT](LICENSE)
