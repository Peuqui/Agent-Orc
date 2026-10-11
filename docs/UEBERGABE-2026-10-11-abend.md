# Übergabe vom 11.10.2026, Abend (Sitzung mit Sonnet)

Zuerst lesen: dieses Dokument, dann `docs/TODO.md`; davor `docs/UEBERGABE-2026-10-11.md` (Nachmittag). Der Code ist die Wahrheit.
Stand: `main` = `origin/main`, auf Mini und Aragon eingespielt (maßgeblich ist `git log`).

## Was seit dem Nachmittag dazukam

| Thema | Wo | Kern |
|---|---|---|
| Backends mit einem Befehl | `backends.py`, `cli.py` (`agent-orc backend models\|levels\|run`), `config.py` (`backends:`), `setup.py`, `backend_presets.yaml`, `claude_backend_profile.yaml` | Ersetzt `lclaude`/`qclaude` (liegen unverändert in `~/bin`, sind nicht mehr nötig). Jeder Start ist ein eigener Prozess mit eigener Umgebung: Claude Code, lokal (llama-swap/vLLM) und DashScope laufen parallel. Setup fragt nach Adresse und Schlüssel; der Schlüssel liegt in `~/.config/agent-orc/dashscope.key` (600), nie im Repo. Hooks der Sitzung finden `AGENT_ORC_BACKEND`, `_URL`, `_MODEL`. Geerbte `ANTHROPIC_API_KEY`/`_AUTH_TOKEN` gehen nicht mit. |
| Konfiguration umgestellt | `~/.config/agent-orc/config.yaml` (Mini und Aragon, Sicherungen `*.bak-20261011-backends`), `~/bin/lclaude-free-gpus` (liest die neuen Variablen, Sicherung `.bak-20261011`) | Profile `claude-local`, `claude-dashscope` rufen `agent-orc backend` auf. Auf Aragon liegt auch der DashScope-Schlüssel (Peuqui hat es freigegeben). |
| Installation | `deploy/install.sh` | Auch aus dem ZIP (ohne `.git`, auch Git-Worktree wird erkannt). Als Fremder getestet in einem frischen Debian 13 (Klon und ZIP); Ubuntu 24.04 hing beim Laden des Images. |
| Spaltenbreiten | `useColumnWidths.ts`, `boundaryShift.ts` | Trenner liegt zwischen zwei Nachbarn und verschiebt nur die Grenze (Summe bleibt), mindestens 10 %, höchstens 10 Spalten; Breiten je Gerät im Browser (`localStorage`), nicht auf dem Server; am Touch 18 px breit, der Platz neben dem Jog bleibt frei. |
| Zustandsdateien | `state.py` | `write_atomically` mit eigener Temp-Datei je Schreiber (zwei Anfragen zugleich hatten `workspaces.json` zerstört) und Aufräumen bei Fehlern; `changing_workspaces()` liest, ändert und schreibt unter einer Sperre. |
| Review | – | Unabhängiger Review der Änderungen des Tages: keine kritischen Fehler; alle klaren Punkte behoben (siehe Commit „Review“); `before_start` bekommt bewusst kein Zeitlimit (der Hook hat seine eigene Frist von 600 s). |
| TTS-Suite als Sprachausgabe | `speech_service.py`, `config.py` (`tts_suite:`), `api.py` (`/api/tts`, `/api/tts/speak`), `speech.ts`, `audioFrames.ts` | Optionaler Abschnitt; der Server reicht die Frames des Dienstes unverändert durch (Token bleibt auf dem Server), der Browser dekodiert und spielt sie nacheinander (WebAudio). Im Browser noch nicht gehört (siehe unten). |
| Agentenübersicht | `SessionsView.vue` | Folgt der Schriftgröße der Ansichten. |
| Upload mit 3 GiB | – | Über `/hosts/Aragon/` mit Test-Instanzen (Mini, SSH-Tunnel, Aragon): 37 s, SHA-256 gleich, Speicher flach (~79 und ~77 MB). In `docs/TODO.md`. |

## TTS-Suite und STT-Suite (eigene Repos unter `~/Projekte`)

- **STT-Suite** (`~/Projekte/STT-Suite`, vorher `whisper-stt`): README Deutsch und Englisch auf das Suite-Konzept, Container heißt weiter
  `whisper-stt` (Compose-Name gepinnt). AIfred nutzt `STT_SUITE_DIR`/`STT_SUITE_REPO_URL`.
- **TTS-Suite** (`~/Projekte/TTS-Suite`, öffentlich): Engine-Schicht von **Mini:AIfred-Intelligence** (Pakete, eigenes Paket `src/tts_suite`),
  **Dienstschicht von mir** (`src/tts_suite/service/`, FastAPI): `POST /speak` und `WS /speak/stream` mit denselben Frames, `/engines`, `/voices`,
  `/config` (eine JSON-Datei `~/.config/tts-suite/config.json`), Token für ändernde Befehle immer und für alles im Netz, Obergrenze für die
  Textlänge (413). Schnittstelle: `docs/INTERFACE.md`/`.de.md`. Entwurfsentscheidungen: Variante B (Systemdienst auf dem Mini), Platzierung der
  GPU nach Regeln in der Konfiguration (kein Rückruf), Audio immer als Strom von Frames.
- **Läuft gerade** (per `nohup`, noch kein systemd-Dienst): `python -m tts_suite.service serve` auf `127.0.0.1:5090` mit der venv von Agent-Orc und
  `PYTHONPATH=src`; Token `~/.config/tts-suite/token`. AIfred prüft damit gegen echte Container (Karte 4, Fenster bis 21:53 von vllm-research).
- AIfreds große Umbauten (dünner Client, Einstellungen nach `/config`) gehören auf einen **Branch** in seinem Repo (Peuqui, 11.10.).

## Regeln, die heute galten

- Umbauten, die Production berühren, zuerst auf einem **Branch** testen; Peuqui testet selbst. Designfragen immer ihm stellen.
- Neue Sperren und `try/except` nur nach Absprache (heute freigegeben: Sperre der Arbeitsflächen, Aufräumen bei Schreibfehlern).
- Tests im Entwicklungs-venv mit `PYTHONPATH=src` (dort liegt eine alte Kopie des Pakets; nicht neu installieren).
- `pkill -f` mit Mustern, die den eigenen Befehl treffen, beendet die eigene Shell: nur eigene PIDs.
- Chrome: vor jedem Test AIfred und FreeEchoDot2 einzeln fragen; vllm-research meldet Messfenster mit „MESSENDE“.

## Offen

1. **TTS-Suite im Browser hören:** `tts_suite:` in der Konfiguration eintragen (Adresse `http://127.0.0.1:5090`) und die Sprachausgabe „TTS-Suite“ wählen;
   nicht im Browser geprüft (nur mit Attrappen und Tests). Dienst als systemd-Benutzerdienst einrichten (Peuqui fragen: eigene venv für `tts-suite`).
2. **Hinweis „frei bis …“** steht im Start-Dialog auf Englisch; Vorschlag: der Befehl gibt nur das Datum aus, die Oberfläche formatiert (wartet auf Peuquis Ja).
3. **Installationstest:** Ubuntu 24.04 und STT-Suite nach der Umbenennung.
4. **Reddit-Beitrag:** erst ganz zum Schluss, Entwurf `.agent-orc/reddit-entwurf.txt` auf den neuen Stand bringen (Backends mit einem Befehl, Setup, ZIP, TTS-/STT-Suite).
5. Echo-Dot-Punkte zurückgestellt; Gespräche-Tab nach Bridge-Neustart nicht überprüfbar (Beobachter-Client gesperrt).
6. vllm-research darf weitermachen, sobald TTS-Suite-Test und Aufräumen fertig sind (Peuqui hat angeordnet, dass wir ihr das melden).
