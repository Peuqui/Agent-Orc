# AI-Ørc — Agent Orchestrator

[English](README.md)

> **Status: frühe Entwicklung.** Noch nichts davon ist benutzbar.

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

## Sicherheit

AI-Orc ermöglicht Fernzugriff auf Shell-Ebene. Es bringt einen eigenen Login
mit und lauscht nur auf `127.0.0.1`. Ins Internet gehört es nur hinter HTTPS,
am besten hinter einem Reverse Proxy mit zusätzlicher Authentifizierung.

## Lizenz

[MIT](LICENSE)
