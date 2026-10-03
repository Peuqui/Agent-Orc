<p align="center"><img src="frontend/brand/logo.svg" alt="AI-Ørc — Agent Orchestrator" width="440"></p>

[English](README.md)

> **Status: früh, aber benutzbar.** Getestet unter Linux mit Claude Code; weitere
> Agent-Profile (Codex, Aider) sind vorbereitet, aber ungetestet.

AI-Orc startet, beobachtet und beendet Sitzungen von Coding-Agenten
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

AI-Orc ist ein Python-Paket, das die gebaute Web-App mitbringt. Bis es veröffentlicht ist,
wird es aus dem Repository installiert:

```
git clone https://github.com/Peuqui/AI-Orc.git && cd AI-Orc
(cd frontend && npm ci && npm run build)    # erst die Web-App bauen; pip packt sie mit ein
python3 -m venv venv && venv/bin/pip install .
venv/bin/ai-orc init            # schreibt ~/.config/ai-orc/config.yaml
venv/bin/ai-orc set-password    # schreibt ~/.config/ai-orc/credentials.json
venv/bin/ai-orc serve           # http://127.0.0.1:8770
```

Vor dem ersten Start `~/.config/ai-orc/config.yaml` anpassen, mindestens `files.base_dir`
(der Ordner mit deinen Projekten). Für einen ersten Test über reines HTTP
`server.cookie_secure: false` setzen; hinter HTTPS bleibt es `true`.

### Als Dienst

`deploy/ai-orc@.service` startet AI-Orc für einen Benutzer (`ai-orc` muss in dessen
`PATH` liegen):

```
sudo cp deploy/ai-orc@.service /etc/systemd/system/
sudo systemctl enable --now ai-orc@$USER
```

Ein Neustart des Dienstes lässt laufende Agenten am Leben; sie werden wieder aufgegriffen.

### Hinter nginx

`deploy/nginx-location.conf` stellt AI-Orc unter `/orc/` in einem HTTPS-Server-Block
bereit, einschließlich des Terminal-WebSockets.

## Sicherheit

AI-Orc ermöglicht Fernzugriff auf Shell-Ebene. Es bringt einen eigenen Login
mit und lauscht nur auf `127.0.0.1`. Ins Internet gehört es nur hinter HTTPS,
am besten hinter einem Reverse Proxy mit zusätzlicher Authentifizierung.

## Lizenz

[MIT](LICENSE)
