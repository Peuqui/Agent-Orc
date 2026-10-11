# Übergabe vom 11.10.2026, Abend (Sitzung mit Sonnet)

Zuerst lesen: dieses Dokument, dann `docs/TODO.md`; davor `docs/UEBERGABE-2026-10-11.md` (Nachmittag). Der Code ist die Wahrheit.
Stand: `main` = `origin/main`, auf Mini und Aragon eingespielt (maßgeblich ist `git log`).

## Was seit dem Nachmittag dazukam

| Thema | Wo | Kern |
|---|---|---|
| Backends mit einem Befehl | `backends.py`, `cli.py` (`agent-orc backend models\|levels\|run`), `config.py` (`backends:`), `setup.py`, `backend_presets.yaml`, `claude_backend_profile.yaml` | Ersetzt `lclaude`/`qclaude` (liegen unverändert in `~/bin`, sind nicht mehr nötig). Jeder Start ist ein eigener Prozess mit eigener Umgebung: Claude Code, lokal (llama-swap/vLLM) und DashScope laufen parallel. Setup fragt nach Adresse und Schlüssel; der Schlüssel liegt in `~/.config/agent-orc/dashscope.key` (600), nie im Repo. Hooks der Sitzung finden `AGENT_ORC_BACKEND`, `_URL`, `_MODEL`. Geerbte `ANTHROPIC_API_KEY`/`_AUTH_TOKEN` gehen nicht mit. |
| Konfiguration umgestellt | `~/.config/agent-orc/config.yaml` (Mini und Aragon, Sicherungen `*.bak-20261011-backends`), `~/bin/lclaude-free-gpus` (liest die neuen Variablen, Sicherung `.bak-20261011`) | Profile `claude-local`, `claude-dashscope` rufen `agent-orc backend` auf. Auf Aragon liegt auch der DashScope-Schlüssel (Peuqui hat es freigegeben). |
| Installation | `deploy/install.sh` | Auch aus dem ZIP (ohne `.git`, auch Git-Worktree wird erkannt). Als Fremder getestet (sandbox-install, Klon und ZIP): Debian 13, Ubuntu 24.04 (NodeSource-Weg): Installation, Setup, Start, Anmeldung laufen durch. STT-Suite: der Test fand, dass die Basis-Compose-Datei ohne NVIDIA-Treiber nicht startet; seitdem gibt es `docker-compose.cpu.yml` (README Deutsch und Englisch), geprüft auf Ubuntu 24.04 (Compose 2.40: Start, `/health` 200). |
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
- **Läuft** als systemd-Benutzerdienst `tts-suite.service` (venv `~/.local/share/tts-suite/venv`, editierbar aus dem Klon; `deploy/install.sh`) auf `127.0.0.1:5090`;
  Token `~/.config/tts-suite/token`. Mit AIfred gegen echte Container geprüft (Qwen3 und XTTS auf Karte 4; Ausfall mitten im Text, 409, Abbruch, Fehlerformen).
  Agent-Orcs Proxy und das Dekodieren im Browser (Chrome, `decodeAudioData`) mit dem echten Dienst geprüft; abgespielt im Browser ist noch nichts gehört.
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
3. ~~Installationstest~~ erledigt (siehe Tabelle); TTS-Suite hat keinen Test in einem sauberen Container (Dienst `deploy/install.sh`, venv und Benutzerdienst nur auf dem Mini geprüft).
4. **Reddit-Beitrag:** erst ganz zum Schluss, Entwurf `.agent-orc/reddit-entwurf.txt` auf den neuen Stand bringen (Backends mit einem Befehl, Setup, ZIP, TTS-/STT-Suite).
5. Echo-Dot-Punkte zurückgestellt; Gespräche-Tab nach Bridge-Neustart nicht überprüfbar (Beobachter-Client gesperrt).
6. vllm-research darf weitermachen, sobald TTS-Suite-Test und Aufräumen fertig sind (Peuqui hat angeordnet, dass wir ihr das melden).

## Nachtrag 12.10.: Betrieb der TTS-Suite (Auftrag über AIfred) – für Peuqui

Vorbereitet und gepusht, nichts davon eingespielt (kein sudo):

- Repo MiniPCLinux (main, Commit „System-Unit, Polkit, nginx /tts-suite/, Landingpage-Karte und Dienst-Seite“):
  `systemd/system/tts-suite@.service`, `polkit-1/rules.d/60-tts-suite.rules`, `nginx/snippets/tts-suite.conf`
  (+ `include` und Icon-Zeile in `sites-available/narnia`), Karte in `landing.html`/`landing-order.json`
  (beide Kopien), `www-html/tts-suite-icon.svg`, Eintrag `ttssuite` in `ai-service-control.php/.html`
  (Start/Stop/Restart/Logs, je Engine und Rechner Zustand und VRAM aus `GET /engines`).
- Umstellung: `sudo ~/Projekte/TTS-Suite/deploy/switch-to-system-unit.sh` (stoppt zuerst die Benutzer-Unit,
  gleicher Port 5090), danach `nginx -t && sudo systemctl reload nginx` und
  `sudo ~/MiniPCLinux/system-config/ai-service-control/install.sh`. Das Skript überschreibt die
  nginx-Site-Datei NICHT, es zeigt den Unterschied zum Repo.
- Branch `tts-alte-sprachausgabe-entfernen` (MiniPCLinux): entfernt die alte Sprachausgabe-Liste (AIfreds
  `/tts/*`) – erst anwenden, wenn AIfred umgestellt ist.
- Geprüft mit einem eigenen nginx auf Port 18090: `/tts-suite`, `/tts-suite/`, `/tts-suite/ui` führen auf
  `/tts-suite/ui/`, Oberfläche, Skripte und `/tts-suite/engines` kommen unter dem Präfix an.
- Zugang: Die Site hat `auth_basic` auf Server-Ebene, `tts-suite.conf` schaltet es nicht ab – wie bei
  `/agent-orc/` verlangt jeder Zugriff die Anmeldung. Dahinter sieht der Dienst Loopback: Vorlesen und Lesen
  gehen ohne Token, Ändern (Start/Stopp, Konfiguration, Stimmen-Abgleich) verlangt das Token (einmal in der
  Seite eintragen). Wer die Anmeldung der Site hat, kann also vorlesen lassen (inkl. kostenpflichtigem
  DashScope, wenn ein Client es so anfragt) – das ist dieselbe Vertrauensgrenze wie bei Agent-Orc.

## Nachtrag 12.10. (nachts): TTS-Fenster, Feed, Stand

- TTS-Fenster (Einstellungen → Sprachausgabe → „Engines des TTS-Dienstes …“): zeigt immer den ganzen Katalog
  (Engine × Rechner), je Zeile Schalter, Einheit, Reihenfolge per Ziehen; Stimme je Engine. Nichts wird
  entfernt: was der Dienst nicht mehr anbietet, bleibt mit „vom Dienst nicht angeboten“ stehen und wird nie
  gesendet (`offered` wird bei jedem Lesen berechnet, nicht gespeichert); neue Zeilen kommen unten, AUS.
  Kein Rechner-Schalter (Peuqui: Zeilenschalter genügen). Dazu „Pause zwischen Absätzen (ms)“ (Standard 700,
  wird als `paragraph_pause_ms` gesendet, der Browser spielt `pause_ms`-Marker als Stille) und „Bereits
  geladene lokale Engine bevorzugen“ (Standard aus; läuft eine GPU-Engine der eigenen Liste schon, geht sie
  nach vorn). Gespeichert in `~/.local/state/agent-orc/tts-choices.json` (entries, voices,
  paragraph_pause_ms, prefer_loaded).
- Antworten-Feed: kommt eine neue Antwort und der Leser ist unten, scrollt der Feed, bis die älteste
  ungelesene Antwort oben anstößt (oder ans Ende, wenn alles darunter passt); nie zurück, nichts bei
  Lesern weiter oben, nichts beim „alles gelesen“-Haken; ist nichts Ungelesenes da (z. B. nach
  Ansichtswechsel), geht es ans Ende. Im Browser noch nicht mit echten Antworten gesehen.
- TTS-Suite-Oberfläche: Freigeben je Zeile und „Alle freigeben“ (`POST /release`), Pausenfeld im
  Probesprechen. Betrieb (System-Unit, nginx, Landingpage, Dienst-Seite): siehe Nachtrag oben.
- Offen: Aragon aus → Agent-Orc dort nicht eingespielt; Peuqui hört die TTS-Suite im Browser an;
  Umstellung auf die System-Unit (sudo, Skript liegt bereit); alten Sprachausgabe-Abschnitt der Dienst-Seite
  erst nach AIfreds Umstellung (Branch `tts-alte-sprachausgabe-entfernen`); Reddit-Entwurf zuletzt;
  STT-Suite-Oberfläche nach TTS-Muster.
