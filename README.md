# AI-Ørc — Agent Orchestrator

[Deutsch](README.de.md)

> **Status: early development.** Nothing here is usable yet.

AI-Orc lets you start, watch and stop coding-agent CLI sessions
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
- the agent CLIs you want to use

## Security

AI-Orc gives remote shell-level access to your machine. It ships with its
own login and listens on `127.0.0.1` only. Expose it to the internet only
behind HTTPS, ideally behind a reverse proxy with additional authentication.

## License

[MIT](LICENSE)
