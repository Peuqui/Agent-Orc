<p align="center"><img src="frontend/brand/logo.svg" alt="Agent-Ørc — Agent Orchestrator" width="440"></p>

[English](README.md)

> **Status: früh, aber benutzbar.** Getestet unter Linux mit Claude Code; weitere
> Agent-Profile (Codex, Aider) sind vorbereitet, aber ungetestet.

Agent-Orc startet, beobachtet und beendet Sitzungen von Coding-Agenten
(Claude Code, Codex, Aider, …) auf dem eigenen Linux-Rechner, bedient über
eine handytaugliche Web-App (PWA).

Jeder Agent läuft in einer eigenen `tmux`-Sitzung in einem Projektordner.
Vom Handy aus kannst du:

- Projektordner anlegen und per Fingertipp einen Agenten darin starten,
- ein Terminal auf jeden laufenden Agenten öffnen, mit einer Sondertasten-Leiste
  (Esc, Tab, Shift+Tab, Pfeile, einrastendes Strg/Alt) über der Bildschirmtastatur,
- Text über ein normales Eingabefeld schicken, damit Spracheingabe und
  Autokorrektur funktionieren,
- Sitzungen beenden und fortsetzen,
- Dateien im Projektordner durchsuchen, bearbeiten und in den Papierkorb legen.

Claude-Code-Sitzungen werden mit Remote Control gestartet und erscheinen
dadurch zusätzlich in der Claude-App auf dem Handy.

## Voraussetzungen

- Linux
- Python 3.12+
- `tmux`
- die Agent-CLIs, die du nutzen willst

## Installation

Agent-Orc ist ein Python-Paket, das die gebaute Web-App mitbringt. Bis es veröffentlicht ist,
wird es aus dem Repository installiert:

```
git clone https://github.com/Peuqui/Agent-Orc.git && cd Agent-Orc
deploy/install.sh          # baut die Web-App, installiert nach ~/.local/share/agent-orc/venv
agent-orc init             # schreibt ~/.config/agent-orc/config.yaml
agent-orc set-password     # schreibt ~/.config/agent-orc/credentials.json
agent-orc serve            # http://127.0.0.1:8770
```

`deploy/install.sh` verlinkt den Befehl nach `~/.local/bin`, das im `PATH` liegen muss. Nach
`git pull` erneut aufrufen, um zu aktualisieren; es installiert nur committeten Code.

Vor dem ersten Start `~/.config/agent-orc/config.yaml` anpassen, mindestens `files.base_dir`
(der Ordner mit deinen Projekten). Für einen ersten Test über reines HTTP
`server.cookie_secure: false` setzen; hinter HTTPS bleibt es `true`.

### Als Dienst

`deploy/agent-orc@.service` startet Agent-Orc für einen Benutzer (`agent-orc` muss in dessen
`PATH` liegen):

```
sudo cp deploy/agent-orc@.service /etc/systemd/system/
sudo systemctl enable --now agent-orc@$USER
```

Ein Neustart des Dienstes lässt laufende Agenten am Leben; sie werden wieder aufgegriffen.

### Hinter nginx

`deploy/nginx-location.conf` stellt Agent-Orc unter `/agent-orc/` in einem HTTPS-Server-Block
bereit, einschließlich des Terminal-WebSockets.

## Sicherheit

Agent-Orc ermöglicht Fernzugriff auf Shell-Ebene. Es bringt einen eigenen Login
mit und lauscht nur auf `127.0.0.1`. Ins Internet gehört es nur hinter HTTPS,
am besten hinter einem Reverse Proxy mit zusätzlicher Authentifizierung.

## Lizenz

[MIT](LICENSE)
