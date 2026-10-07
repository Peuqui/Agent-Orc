# Übergabe an die nächste Sitzung (Stand 7.10.2026, gegen Mittag)

Dieses Dokument ersetzt kein Gedächtnis. Es hält fest, was in der Sitzung vom 7.10.2026 passiert ist,
was Peuqui entschieden hat und was offen ist. Der Code ist die Wahrheit; bei Zweifeln dort nachsehen.

## Ziel

Agent-Orc ist die Weboberfläche, mit der Peuqui mehrere Claude-Code-Agenten (und andere Agenten)
auf dem Mini orchestriert: Karten pro Agent, Arbeitsflächen mit mehreren Spalten, Antworten-Ansicht,
Sprache (Diktat, Vorlesen, Echo Dot über AIfred), Notizen, Dateien, Verbrauch. Gearbeitet wird fast
nur auf Handy und Tablet (Querformat, Arbeitsfläche) sowie am Desktop.

Ziel der Sitzung war eine Reihe von Alltagsverbesserungen, die Peuqui laufend aus dem Gebrauch gemeldet
hat: Modell und Kontext eines laufenden Agenten ändern, bessere Menüs, saubere Layouts auf allen Geräten,
Markierung neuer Antworten, lokalisierte Zahlen, aktuelle Hilfetexte.

## Aktueller Stand

- Branch `main`, letzter Commit `22f13c8`, gepusht, Arbeitsbaum sauber.
- Installiert ist derselbe Stand (`bash deploy/install.sh` baut das Frontend, installiert das Paket in
  `~/.local/share/agent-orc/venv` und startet den Dienst `agent-orc@mp.service` neu; Agenten laufen
  weiter). Das Skript verlangt einen sauberen Arbeitsbaum, es installiert nur Committetes.
- Tests: Python `venv/bin/python -m pytest` (262 grün), `ruff check`, `mypy`; Frontend im Ordner
  `frontend`: `node_modules/.bin/vue-tsc --noEmit` und `npm test` (38 grün).

### Was in der Sitzung gebaut wurde (alles installiert)

1. **Modell eines laufenden Agenten wechseln** (`POST /api/sessions/{id}/model`). Profile mit
   `model_live` (Claude: `/model {model}`) wechseln im laufenden Betrieb ohne Neustart; Claude fragt bei
   gefülltem Gespräch „Switch model?“, dafür gibt es `model_live.confirm` (Text der Rückfrage, dann Enter).
   Arbeitet der Agent gerade, wird der Wechsel vorgemerkt (`pending_model`, gelbe Zeile auf der Karte)
   und nach der Antwort eingetippt. Profile ohne `model_live` werden mit dem Modell neu gestartet
   (`--continue`). `/model` schreibt das Modell als Standard in `~/.claude/settings.json`; Agent-Orc stellt
   die Datei wieder her (`keep_file_while` in `effort.py`, gemeinsam mit dem Denkaufwand-Wechsel).
2. **Kontext leeren und komprimieren** ohne Neustart (`POST /api/sessions/{id}/context/{clear|compact}`),
   Profilschlüssel `clear_command` und `compact_command` (Claude: `/clear`, `/compact`). Nur im Leerlauf
   (409 sonst), beides mit Rückfrage.
3. **Gemeinsames ⋮-Menü** (`AgentActions.vue`) auf der Agentenkarte und der Agentenseite: Prompt planen,
   Modell wechseln, Kontext komprimieren, Kontext leeren, Neu starten, abgesetzt rot Beenden. Sichtbar
   bleiben Terminal, Änderungen und `>_` (Karte) beziehungsweise die Navigationssymbole (Agentenseite).
4. **Denkaufwand auf der Karte als Dropdown** statt Schieber (kein Verstellen mehr beim Wischen, spart
   Platz). Im Startdialog bleibt der Schieber.
5. **Lange Eingaben in Stücken tippen** (`type_chunk_chars` 200, `type_chunk_delay_ms` 30 in
   `terminal:`; `SessionManager.type_line` und der WebSocket in `terminal.py`). Ab etwa 800 Zeichen in
   einem Stück macht Claude Code ein `<pasted_content>` daraus, und Haiku weigerte sich dann, den Text als
   Anweisung zu befolgen. Gemessen mit echten Haiku-Sitzungen.
6. **Antworten gelten als gesehen**, sobald sie 2 s überwiegend auf dem Bildschirm waren
   (`useSeenOnScreen.ts`, IntersectionObserver), nach dem Vorlesen und wenn ein anderes Fenster dieses
   Geräts sie gesehen hat (storage-Ereignis). Die Arbeitsfläche hält Spalten tagelang offen, dort ging
   die rote Markierung nie weg.
7. **KeyBar auch in der Antworten-Ansicht**; die Arbeitsfläche scrollt beim Laden zur aktiven Spalte.
8. **Verbrauchszahlen und Kontextanzeige lokalisiert** (`useTokenFormat.ts`, Einheiten in den
   Sprachdateien): Deutsch Tsd., Mio., Mrd., Bio., Brd. mit Komma, Englisch k, M, B, T, Q.
9. **Layout ohne Überlappungen** gemessen in elf Auflösungen (360 bis 1920 px, hoch und quer): Karten
   brechen Kontext und Denkaufwand um, Reiter in der Kopfzeile erst ab 1024 px (`lg`), darunter die untere
   Leiste.
10. **Vollbild-Seiten verschieben sich nicht mehr** (`html.app-shell`, Body fest und `overflow: clip`,
    in `App.vue` und `style.css`). Peuqui sah auf dem Handy eine nach oben verschobene Seite; der Fehler
    ließ sich im Browser nicht auslösen, die Absicherung wirkt in der Simulation. **Ob sie seinen Fall
    behebt, ist offen.**
11. **Hilfetexte** (Glühbirne) neu geschrieben und ergänzt, Deutsch und Englisch gleich aufgebaut: neue
    Abschnitte „Kopfzeile und Seiten“ und „Dateien“, ⋮-Menü, Modell, Kontext, Beenden, Markierungen.
12. **Hilfe-Dialog war kaputt**: ein `@` im Notizen-Hilfetext (seit dem 6.10.) ist in vue-i18n die Syntax
    für verlinkte Texte und ließ das Anzeigen mit `SyntaxError: 10` scheitern. Jetzt `{'@'}`, und
    `frontend/tests/locales.test.ts` kompiliert alle Texte beider Sprachen und prüft gleiche Schlüssel.
13. AIfred (Peer `Mini:AIfred-Intelligence`) verlangt in seiner API jetzt `speaker` (Ansage) und `sender`
    (Chat-Inject, Agent-Trigger). Agent-Orc sendet `speaker` immer (Randfall im Frontend behoben:
    `Speakable.label` ist Pflicht), ruft die beiden anderen Routen nicht auf. Austausch mit `[LGTM]` beendet.

## Getroffene Entscheidungen (Peuqui, wo nicht anders vermerkt)

- **Generisch statt claude-spezifisch:** Live-Wechsel und Kontextbefehle stehen pro Profil in der
  Konfiguration. Wo ein Profil sie nicht kennt, wird neu gestartet (Modell) beziehungsweise der Punkt fehlt
  (Kontext). Kein stiller Ersatzweg.
- **Modellwechsel wartet auf das Antwortende** und wird vorgemerkt, statt zu sperren („das haben wir
  doch schon gebaut“). Kontext leeren und komprimieren dagegen nur im Leerlauf (zerstörerisch, deshalb
  kein automatisches Nachholen). Auf Wunsch könnte man es vormerken.
- **Menü:** häufige Dinge sichtbar, seltene und folgenreiche im ⋮; Beenden abgesetzt und rot. Denkaufwand
  und Modus (Auto) bleiben auf der Karte. „Kontext komprimieren“ und „Prompt planen“ ins Menü (Peuqui:
  „baue es mit ein, ich muss gucken, wie ich es einsetze“).
- **Neu-Markierung:** Peuqui liest selbst, statt vorlesen zu lassen; Markierung verschwindet automatisch,
  kein Knopf, kein Timer.
- **Tests mit echten Agenten nur mit Haiku oder Sonnet** (Wochenkontingent war bei 92 %). Siehe Memory
  `test-models-cheap`.
- **Neue Konfigurationsschlüssel haben Standardwerte im Code** (`type_chunk_*`), damit eine ältere
  Konfiguration nicht bricht; sie stehen in `default_config.yaml` nur als Kommentar. Kleine Dopplung zur
  SSOT-Regel, Peuqui hat nicht widersprochen.
- Commit und Push dürfen selbst entschieden werden; nach jedem Paket installieren.

## Konfiguration von Peuqui (`~/.config/agent-orc/config.yaml`)

Eingetragen in dieser Sitzung (Sicherungen daneben: `config.yaml.bak-20261007-modellive`, `-clear`,
`-compact`):

- Profil `claude`: `model_live: {command: "/model {model}", confirm: "Switch model?", protected_file:
  ~/.claude/settings.json}`, `clear_command: /clear`, `compact_command: /compact`.
- Profile `claude-local` und `claude-dashscope`: `clear_command` und `compact_command`, aber **noch kein
  `model_live`** (nicht getestet).

**Regel:** neue Schlüssel erst eintragen, nachdem die Version installiert ist, die sie kennt (`Config` ist
ein StrictModel, die Hook-Befehle laden die Konfiguration). Ich habe das einmal verletzt (`confirm` vor der
Installation eingetragen); Hooks wie `agent-idle` konnten für kurze Zeit scheitern. Folgen wurden nicht
gemeldet.

## Offene Aufgaben

1. **Lokale Modelle über llama-swap testen** (`claude-local`, `claude-dashscope`): geht `/model` im
   laufenden Prozess, und passen die Denkstufen des neuen Modells (`levels_command`)? Peuqui: „Vermutlich
   geht es nicht … man ruft es einfach auf, und über llama-swap läuft das, wie AIfred den GPU-Wechsel
   macht.“ Voraussetzung: **Freigabe und ein kleines Modell von Peuqui**, vorher GPU-Belegung prüfen; bei
   Bedarf `curl -X POST 'http://localhost:5080/unload?device=cuda'` (Whisper entlädt nur den GPU-Worker,
   Container nicht stoppen). Danach entscheiden, ob `model_live` für diese Profile eingetragen wird.
2. **Peuqui probiert die Neuerungen auf Handy und Tablet** und meldet: ⋮-Menü auf der Karte, Dropdown,
   Modellwechsel, Kontext komprimieren und leeren, Kopfzeile ab 1024 px, sauberes Diktat ohne
   `pasted_content`, Markierungen. Besonders: **verschobene Seite** (Absicherung wirkt nur, falls die
   Ursache ein scrollbares Dokument war; falls es wieder auftritt, fragen, was kurz davor war: Tastatur
   gerade geschlossen, nach dem Diktat, Gerät gedreht, Hoch- oder Querformat).
3. **Unklare Randfälle:**
   - Während `/compact` läuft, ist der Agent nicht sicher als „arbeitet“ markiert (kein normaler Hook),
     „Kontext leeren“ bliebe dann kurz anklickbar. Nicht geprüft.
   - Das ⋮-Menü bleibt unter einem Dialog offen und schließt erst bei einem Klick daneben.
   - `speech.ts`: `echo.speak` sendet noch den leeren Sprecher `''` (toter Pfad, weil `speakAll` immer
     benutzt wird). Entweder entfernen oder durchreichen.
4. **Hilfetexte:** Abschnitt „Einstellungen (☰)“ ist unverändert (2 Punkte), der Startdialog (Modell,
   Fortsetzen früherer Gespräche) nur knapp. „Außerhalb freischalten“ nennt „wenige Minuten“ statt der
   Konfigurationszahl `files.unlock_minutes` (Standard 10).
5. **`docs/TODO.md`** enthält weiter die Ideen zur Sprache am Echo Dot (Aufzeichnen, was verstanden wurde,
   Double Metaphone, Folgeaufnahme ohne Wake-Word, Aufbewahrung nach Alter); nichts davon wurde angefasst.
6. Nur angeboten, nicht bestellt: „Ab hier alle“ als Beschriftung für „Ab hier“ im Antworten-Fenster.

## Nächste Schritte (Vorschlag)

1. Zuerst `peer_read`, dann die Memory-Einträge lesen (`MEMORY.md`), besonders `test-models-cheap`,
   `config-after-install`, `coordinate-heavy-work`.
2. Auf Peuqui warten beziehungsweise nach seinen Handy-Erfahrungen fragen (Punkt 2 oben).
3. Mit seinem Okay und einem kleinen Modell den llama-swap-Test machen (Punkt 1), dann `model_live` für
   die Wrapper-Profile entscheiden und, falls ja, nach dem Muster „Code installieren, dann Konfiguration“
   eintragen.
4. Danach Randfälle (Punkt 3) und die Hilfe-Lücken (Punkt 4) abarbeiten.

## Wichtige Dateien

Backend (`src/agent_orc/`):
- `api.py`: alle Endpunkte; Modell (`change_model`, `apply_model`, `apply_pending_models`), Kontext
  (`change_context`, `context_commands`), `/api/agents` liefert `model_live`, `context_actions`.
- `config.py`: `AgentProfile` mit `model_live` (`LiveModelConfig`), `clear_command`, `compact_command`;
  `TerminalConfig` mit `type_chunk_chars`, `type_chunk_delay_ms`.
- `effort.py`: `keep_file_while`, `confirm_when_asked`, Denkaufwand live.
- `sessions.py`: `type_line` (in Stücken), `press_enter`, `set_model`, `text_pieces`.
- `terminal.py`: WebSocket-Brücke, stückelt Eingaben.
- `default_config.yaml`: Beispiele und Kommentare für `model_live`, `clear_command`, `compact_command`.

Frontend (`frontend/src/`):
- `components/AgentActions.vue`, `ContextButton.vue`, `RestartButton.vue` (auch Modellwahl über
  `change-model`), `ModelDialog.vue`, `ScheduleButton.vue`, `ReasoningControl.vue`, `AnswersFeed.vue`.
- `composables/useSeenOnScreen.ts`, `useTokenFormat.ts`, `useSpeech.ts`, `useAnswerSeen.ts`.
- `views/SessionsView.vue` (Karten), `TerminalView.vue` (Agentenseite), `WorkspaceView.vue`,
  `App.vue` (`app-shell`), `style.css`, `format.ts`, `answers.ts`.
- `locales/de.json`, `locales/en.json` (Hilfetexte unter `help.sections`; Sonderzeichen `@ | { }` mit
  `{'@'}` schreiben), `components/HelpButton.vue`.
- Tests: `frontend/tests/format.test.ts`, `answers.test.ts`, `locales.test.ts`; Python `tests/test_api.py`
  (Profile `swapper`, `chooser`), `test_sessions.py`, `test_effort.py`.

## Testrezept für Oberflächenänderungen (hat sich bewährt)

1. Frontend bauen: `cd frontend && npm run build` (schreibt nach `src/agent_orc/static`, nicht
   versioniert).
2. Eigene Testinstanz **im Prozess** mit `create_app` und einer Kopie der echten Konfiguration, geändert:
   eigener tmux-Socket (`orc-uitest`), Port 18765, `cookie_secure: False`, eigener `XDG_STATE_HOME` im
   Scratchpad, ein Demo-Profil mit `cat` als Agent (kein Token-Verbrauch) und gefälschtem Status über
   `agent_orc.context.store_status`. Dev-venv des Projekts benutzen (dort ist `httpx2` für den Test-Client);
   die Produktions-venv hat es nicht und braucht es nicht.
3. Chrome headless starten: `google-chrome --headless=new --remote-debugging-port=9222
   --user-data-dir=<Scratchpad>/chrome-profile about:blank`, dann die DevTools-Werkzeuge
   (`mcp__chrome-devtools__*` per ToolSearch laden). Anmelden per `fetch('/api/login')`, danach neu laden.
   Nach einem Neubau Service Worker und Caches löschen, sonst bleibt die App leer (404 auf alte Assets).
4. Überlappungen automatisch messen (Rechtecke von Knöpfen und Texten schneiden sich) in 360, 412, 768,
   800, 860, 915, 1024, 1100, 1280, 1366, 1920 px, mobil und quer (`emulate`).
5. **Aufräumen:** Testinstanz und Chrome über PID beenden (`ss -ltnp | grep 18765`, nie `pkill -f`),
   `tmux -L orc-uitest kill-server`, Verlaufsordner der Test-Agenten unter `~/.claude/projects/` löschen
   (vorher `readlink -f ./<Ordner>`, der Name beginnt mit `-`, also mit `./` voran).
6. Echte Agenten nur mit Haiku oder Sonnet starten und danach genauso aufräumen.

## Stolperfallen

- Zeitangaben und Aufwandsschätzungen nicht raten; messen.
- Texte mit echten Umlauten, auch in Commits (Conventional Commits, mit den Zeilen `Co-Authored-By` und
  `Claude-Session`).
- `git add` gezielt; die Konfiguration und ihre Sicherungen gehören nicht ins Repository.
- Das Plugin AI-Connect weckt die Sitzung bei Nachrichten; nicht in Schleifen auf Antworten warten.
- Peer: `Mini:AIfred-Intelligence` (Ansage-API, Pflichtfelder `speaker` und `sender`).
