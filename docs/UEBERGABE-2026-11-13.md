# Übergabe 13.11.2026

Was heute an Diktier- und Lautsprecher-Knopf, an den Symbolen von Mundwerk, an AI-ATC und am Einspielen geschah, was gilt und was
offen ist. Der Code ist die Wahrheit.

## Die zwei gemeinsamen Quellen der Oberfläche

Peuquis Regel (globale `~/.claude/CLAUDE.md`, Abschnitt Code): Wo ein Programm Sprache aufnimmt, kommt der Diktier-Knopf der
STT-Suite hinein, wo es Sprache ausgibt, der Lautsprecher-Knopf der TTS-Suite. Eine eigene Fassung oder eine von Hand
geänderte Kopie gibt es nicht; eine Änderung gehört in die Quelle.

| Stück | Quelle (einzige) | Was drin ist |
| --- | --- | --- |
| Diktier-Knopf | `STT-Suite/ui/badge/` (`badge.svg`, `badge.css`) | Rundes Abzeichen (Logo, Rand), drei Zustände `ready`, `listening`, `transcribing`, GPU-Zeichen, Spinner; Farben als `--badge-*`-Variablen mit Vorgaben in `:where(:root)` |
| Lautsprecher-Knopf | `TTS-Suite/src/tts_suite/service/ui/speaker/` (`speaker.svg`, `speaker-from.svg`, `speaker.css`) | Symbol, Pfeil „ab hier“, Bewegung beim Vorlesen (`playing`); Farben und Größe als `--speaker-*` (Größe in `em`) |
| Verteiler und Liste | `STT-Suite/scripts/sync_ui.py`, `STT-Suite/scripts/ui-consumers.json` | Ein Skript für beide Stücke, ein Eintrag je Programm mit „badge“- und/oder „speaker“-Block; `--check` zeigt veraltete Kopien (Ausgang 1) |
| Symbole als Dateien | `STT-Suite/scripts/render_badge_icons.py` | Rendert das Abzeichen mit Chrome (headless) und Pillow zu PNG, ICO, ICNS und einer Übersicht; Marke (Hash der Quelle) neben den Symbolen, die `sync_ui.py --check` prüft |

Das gemeinsame Skript liegt in der STT-Suite (nicht je Suite ein eigenes, das wäre dieselbe Doppelung gewesen); die TTS-Suite
verweist in ihren READMEs darauf. Alle Repos liegen nebeneinander in `~/Projekte`, die Liste nennt Pfade relativ dazu.

Verbraucher (Stand der Liste): STT-Suite (Probe-Seite), TTS-Suite (Probesprechen), AIfred (`DictationBadge.vue`, `TtsIcon.vue`),
Agent-Orc (`DictationBadge.vue`, `SpeakerIcon.vue`), Mundwerk (Badge-Seite und alle Symbole), AI-ATC (`DictationBadge.vue`,
`SpeakerIcon.vue`). Ohne Knopf, nur Nutzer des Dienstes: GPU-Orc, WakeWordResearch.

Ablauf einer Änderung am Knopf: Quelle ändern, `python3 STT-Suite/scripts/sync_ui.py` (schreibt die Kopien in alle Verbraucher),
bei Änderung am Abzeichen auch `python3 STT-Suite/scripts/render_badge_icons.py` (Symbole von Mundwerk), `--check` muss
„All copies are up to date.“ melden, dann je Verbraucher prüfen, committen, einspielen. Die Programme setzen nur Farben und
Größen über die Variablen (Agent-Orc in `theme.css`, AIfred in `ChatInput.vue` aus `theme.py`).

## Agent-Orc

| Was | Wo | Hinweis |
| --- | --- | --- |
| Diktier-Knopf aus der Quelle | `frontend/src/components/DictationBadge.vue` (erzeugt), `assets/dictation-badge/badge.css`, `DictationMic.vue`, `DictationPointer.vue`, `theme.css` | GPU-Zeichen ist die geteilte Klasse `dictation-gpu`; der Zeiger an der Maus trägt den Schatten auf einem Umschlag, weil das Grau der Quelle ein Filter für sich ist |
| Lautsprecher aus der Quelle | `SpeakerIcon.vue` (erzeugt), `assets/speaker/speaker.css`, `theme.css` | `--speaker-size: 1.5rem`; `frontend/brand/tts-icon.svg` entfällt |
| Test für mypy | `tests/test_context.py` | Zusicherung als lokale Namen; war ein alter mypy-Fehler |

Eingespielt am 13.11. auf Mini und Aragon (21a5b51); die späteren Commits (nur Kommentare der erzeugten Dateien, diese Übergabe)
sind nicht neu eingespielt, es ändert sich nichts am Verhalten. Beim nächsten Deploy mitnehmen.

**Anzeige-Einstellungen sind je Gerät im Browser** (`composables/useSettings.ts`, `localStorage`): Schriftgrößen von Terminal und
Ansichten, Zeilenabstand, Scroll-Zeilen, Größe der Bedienelemente, „Frage oben festhalten“, Terminalschrift, Diktier-Engine und
-Töne, Spaltenbreiten und letzter Reiter je Arbeitsbereich, Dateisortierung, Sprache. Zentral auf dem Server liegen nur die
`SharedSettings` (Diktier-Gerät, „Diktat sofort senden“, Tempo, Tonhöhe, Namen ansagen, Stimmen, Zeichenlimit, Warmhalten).
Peuqui will es so (Anzeige je Gerät, beim Gerätewechsel unverändert). Der Speicher gilt je Adresse des Browsers: Mini und Aragon unter ihren
eigenen Adressen haben getrennte Werte.

## Mundwerk (Windows-Programm, Repo `~/Projekte/Mundwerk`)

- **Alle Symbole sind das Abzeichen mit Kreis, aus der Quelle:** vier Tray-Zustände (gelber Rand bereit, roter Rand hört zu, grau
  transkribiert, dunkelroter Rand mit grauen Balken Fehler, der nur in `render_badge_icons.py` definiert ist), Programm-Icon
  (`src-tauri/icons/icon.ico`, `icon.icns`, PNGs) und Fenster-Icon (`ui/icon.png`). Die Tray-Bilder nutzen das Profil „small“
  (Ring 48 statt 24, Wellen 1,15-fach), sonst wirkte das Symbol bei 16 Pixeln klein. `docs/icons.png` ist die erzeugte Übersicht.
  Die handgemachten `assets/icon.svg` und `assets/tray/*.svg` entfielen.
- **`src-tauri/build.rs`:** `cargo:rerun-if-changed=icons`. Ohne das blieb das Programm-Icon der Exe das alte Mikrofon, weil
  Cargo das Build-Skript für ein geändertes Icon nicht neu ausführt (belegt: alle Bilder der alten `icon.ico` steckten in der Exe).
- **Fehlerzustand** zeigt das Tray-Symbol bei jedem gemeldeten Fehler (STT-Suite nicht erreichbar, Mikrofon, Ton, Einfügen, Autostart).
- **Eine Instanz:** das Plugin `tauri_plugin_single_instance` gab es schon; ein zweiter Start öffnet nur die Einstellungen der ersten.
  Beim Update die alte Version vorher im Tray beenden, sonst läuft die neue nie an.
- **Bauen auf dem Mini** (Windows-Exe, rund 30 s, vorher vllm-research fragen):
  `cd Mundwerk/src-tauri && CARGO_BUILD_JOBS=3 PATH="/usr/lib/llvm-17/bin:$HOME/.cargo/bin:$PATH" nice -n 10 cargo tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc --no-bundle`,
  Ergebnis `target/x86_64-pc-windows-msvc/release/mundwerk.exe`.
- **Einspielen auf Aragon geht nicht von hier:** Aragons WSL erreicht per SSH `C:` nicht (Eingabe-/Ausgabefehler), und eine laufende Exe
  lässt sich unter Windows nicht überschreiben. Weg: Exe mit Commit-Kennung im Namen (`mundwerk-<hash>.exe`) nach
  `Agent-Orc/.agent-orc/previews/` legen, den Pfad in Backticks nennen, Peuqui lädt sie im Browser; alte Datei dort entfernen.
  Stand: `mundwerk-486cbe4.exe`.
- **Windows merkt Icons je Dateiname** (Explorer-Zwischenspeicher): Unter einem neuen Namen zeigt sich das richtige Icon, unter dem alten das
  alte. Abhilfe in der Administrator-PowerShell (`;` statt `&`):
  `taskkill /f /im explorer.exe; Remove-Item "$env:LOCALAPPDATA\Microsoft\Windows\Explorer\iconcache*" -Force -ErrorAction SilentlyContinue; Start-Process explorer.exe`
  (der Explorer-Neustart hat bei Peuqui gewirkt; `ie4uinit.exe -show` reichte nicht).

## STT-Suite, TTS-Suite

- **STT-Suite:** Probe-Seite (`ui/test.js`, `ui/dictation-mic.js`) zeigt das Badge statt des Textknopfs „Aufnehmen“; GPU-Zeichen aus
  `/status` (`gpu_loaded`, nicht bei Gerät CPU), grau und mit Spinner beim Transkribieren, Nachfrage nach Ablauf der Leerlaufzeit.
  Die Oberfläche liegt im Docker-Image: neu gebaut und Container neu erstellt am 13.11. (Diktat nach rund 15 s wieder bereit);
  seitdem nur ein Kommentar in `badge.css` geändert, nicht neu gebaut. Verwerfen-X und Escape gibt es nur in AIfred und Agent-Orc, in
  der Probe nicht (Peuqui: nicht nötig, kurze Tests).
- **TTS-Suite:** Probesprechen zeigt das Symbol im Knopf „Sprechen“ (`speaker-icon.js`, `speak.js`). Sie läuft editierbar aus dem Klon
  (`~/.local/share/tts-suite/venv`), neue UI-Dateien sind sofort live, ein Neustart war nicht nötig.
- Die Skripte brauchen nichts Neues zum Installieren: `sync_ui.py` nur Python; `render_badge_icons.py` Chrome und Pillow (beides da).

## AI-ATC (Repo `~/Projekte/AI-ATC`)

- **Narnia ist der Mini selbst** (Hostname `Mini`, 192.168.0.249): Entwicklung und Produktion sind derselbe Ordner. nginx liefert `/ai-atc/` aus
  `frontend/dist/` (Authelia davor), die API läuft als `ai-atc.service` auf Port 8100 (`disabled`, wird bei Bedarf gestartet; Polkit erlaubt
  `systemctl restart ai-atc`). Einspielen heißt `cd frontend && npm run build` (vorher `dist` sichern; Sicherung vom 13.11. unter
  `~/.local/share/ai-atc-backup/dist-20261113`). Die Projekt-`CLAUDE.md` sagt es jetzt (e08f383).
- **Backend meldet das Gerät:** `loaded_device` (`cuda`, `cpu` oder nichts) in `/api/stt/settings`; die Einstellung „cuda“ kann auf der CPU enden.
  Geprüft mit dem echten `medium`-Modell auf der CPU, keine Karte angefasst.
- **Oberfläche:** Push-to-Talk ist das Abzeichen mit Spinner und GPU-Zeichen (nach `loaded_device`, Nachfrage nach der Leerlaufzeit),
  der Schalter für das Vorlesen zeigt das TTS-Symbol (gedimmt aus, in Bewegung beim Sprechen).
- **Das neue `dist` enthält auch die Änderungen vom 3. Oktober** (eSpeak NG als dritte TTS-Engine, Piste-Hinweis, STT-GPU-Wahl), die vorher
  nie gebaut waren (das alte `dist` war vom 29. Juli).
- **Nicht gesehen:** die Seite im Browser (hinter Authelia), und das GPU-Zeichen, weil der Dienst nicht läuft (der Start nimmt llama-swap mit,
  und die Karten gehörten an dem Tag vllm-research).

## Gelernte Wege (stehen auch in der globalen `CLAUDE.md` und im Gedächtnis)

- **Dateien für Peuqui:** nur als Pfad in Backticks, im Projektordner unter `.agent-orc/previews/` (git-ignoriert); Agent-Orc macht daraus
  einen Link, ein Klick öffnet das Bild im Editor (Binärdateien mit „Herunterladen“). Nicht sichtbar für ihn: Pfade mit `@` im Text (gilt nur für
  seine Nachrichten) und `SendUserFile`.
- **Vor „Produktion Narnia“ zuerst `hostname` prüfen**, nicht SSH: Der Mini hatte nie eine SSH-Verbindung dorthin, weil es der gleiche Rechner ist.
- **Schwere Arbeit auf dem Mini:** vllm-research vorher per `peer_send` fragen („jetzt“ oder „später“); Bau mit 3 Jobs und `nice 10`.

## Offen

- **Terminalrand am Tablet** (Freitagsliste): Die linke Terminal-Spalte war am Rand abgeschnitten; bei Peuqui passt es gerade wieder, er
  beobachtet es. Ursache unbekannt; kommt es wieder: Drahtloses Debugging am Tablet (`adb`, Port 9222 vorher mit den Peers absprechen) oder ein
  kleiner Mess-Aufruf in der Oberfläche; Kandidaten stehen in `LISTE-FREITAG-2026-11-13.md` im AIfred-Ordner `data/handover`.
- **AI-ATC:** Dienst starten und das GPU-Zeichen sowie die Seite im Browser ansehen; ein Transkript prüfen.
- **Nicht gesehen im Betrieb:** Bewegung des Lautsprechers beim Vorlesen, die Probe-Seiten der Suiten im Browser, das Tray-Symbol und
  das Programm-Icon im echten Windows nach einem Neubau (bei Peuqui kam das Programm-Icon nach dem Explorer-Neustart richtig).
- **Dokumentation der anderen:** AIfred, PharmaLens und die Agenten von vllm-research ziehen ihre Doku selbst nach (Peuqui); AIfred hat
  die Kopf-Kommentare seiner vier erzeugten Dateien noch nicht committet (nur Kommentare).
- Nicht meine Baustellen der Freitagsliste: PharmaLens-Reste, AIfred (Ansagen in Räumen, Dateikopie zwischen Arbeitsbereich und Nextcloud).

## Commits dieses Tages

| Repo | Commits |
| --- | --- |
| STT-Suite | `dd1f203` Knopf-Quelle und Probe, `4ed37bb` Symbole rendern, `1243aff` Übersicht, `e867e60` Profil „small“, `766517f` ein Sync-Skript |
| TTS-Suite | `0772645` Lautsprecher-Quelle, `1731031` Skript wandert in die STT-Suite |
| Mundwerk | `819ba88`, `5ddbb17`, `0343706`, `5d943f2`, `486cbe4`, `9ad5b1d` |
| AI-ATC | `701dc0f` Backend, `50e074d` Oberfläche, `e08f383` Doku, `79c092f` Kommentare |
| Agent-Orc | `6920048` Knöpfe, `21a5b51` mypy-Test, `9e2274d` Kommentare, diese Übergabe |
| AIfred | `47ee5b42`, `8b15315e`, `3c5ea091` (von AIfred selbst) |
