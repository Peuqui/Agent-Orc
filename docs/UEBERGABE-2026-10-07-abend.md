# Übergabe an die nächste Sitzung (Stand 7.10.2026, ca. 20:30 Uhr, Abendteil)

Ergänzt `docs/UEBERGABE-2026-10-07.md` (Mittagsstand, Testrezept, Stolperfallen); dort nachlesen, was hier nicht
wiederholt wird. Der Code ist die Wahrheit, bei Zweifeln dort nachsehen.

## Ziel

Agent-Orc ist die Weboberfläche, mit der Peuqui mehrere Claude-Code-Agenten (und andere, auch lokale Modelle)
auf dem Mini orchestriert: Karten, Arbeitsflächen mit mehreren Spalten (Iframes), Antworten-Ansicht, Sprache,
Notizen, Dateien, Verbrauch. Heute Nachmittag und Abend kamen dazu: Freigaben überall sichtbar, Anhänge,
Gespräche aufräumen, Agent- und Modellwechsel, lokale Bildmodelle für PDFs.

## Aktueller Stand

- Branch `main`, letzter Commit `ca88654`, gepusht, installiert (`bash deploy/install.sh`), Arbeitsbaum sauber.
- Prüfungen zuletzt grün: Python `venv/bin/python -m pytest` (276), `ruff check`, `ruff format --check`, `mypy`;
  Frontend in `frontend`: `node_modules/.bin/vue-tsc --noEmit`, `npm test` (42).
- **Kontingent von Peuqui ist bei ~95 %, Reset Freitag 9.10.2026 um 16:00.** In `~/.claude/CLAUDE.md` steht dazu
  ein befristeter Abschnitt „BEFRISTET: Kontingent sparen“ (Sparsam arbeiten, nichts Großes beginnen). **Nach
  Freitag 16 Uhr diesen Abschnitt löschen.** Bis dahin nur Kleinigkeiten und Antworten auf Fragen.

### Heute gebaut (alles installiert; Commits seit dem Mittag)

1. **Freigabe-Anfragen** (`components/ApprovalRequests.vue`, gemeinsam für alle Orte): auf der Agentenseite und in
   jeder Arbeitsflächen-Spalte als Überlager über dem Eingabefeld (so breit wie die Blasen, `JOG_TRACK_WIDTH_PX`
   in `device.ts`). Zusätzlich **Ankündigung oben auf jeder Seite** (`ApprovalBanner.vue`, nur im äußersten Fenster)
   für Agenten, die nicht im Blick sind (`composables/useShownAgents.ts`, von `WorkspaceView.vue` gesetzt). Knopf
   „Zum Agenten“ führt in die Arbeitsfläche des Agenten (`agentRoute` in `composables/useWorkspaceTab.ts`, wie der
   Terminal-Knopf der Karte). Fehler „Anfrage nicht mehr offen“ hat einen Text (`errors.ApprovalNotFoundError`).
2. **Anhänge** (`AttachMenu.vue`, `MessageInput.vue`, `attachInOrder.ts`): mehrere Dateien auf einmal, Drag and
   Drop auf die Seite (jede Spalte nimmt für ihren Agenten, Hinweis verschwindet von selbst nach 0,4 s ohne
   `dragover`), nicht abgeschickte Anhänge überleben das Neuladen (`sessionStorage`, Vorschau vom Server).
3. **Gespräche aufräumen** (Dateienkarte, `ConversationCleanup.vue`; Backend `history.py`:
   `list_all_claude_conversations`, `delete_claude_conversation`; `GET /api/conversations/all`,
   `POST /api/conversations/delete`): alle Projekte unter `~/Projekte` (mit „Außerhalb freischalten“ das Home),
   endgültig löschen, laufende und eben beschriebene Gespräche gesperrt. `cleanupPeriodDays` in
   `~/.claude/settings.json` auf 7 gesetzt.
4. **Agent oder Modell wechseln** (⋮-Menü, `ModelDialog.vue`, `RestartButton.vue`; Backend `POST
   /api/sessions/{id}/profile`, `sessions.py: change_profile`, `api.py: prepare_start`): auch auf lokale Profile,
   Codex usw.; Gespräch geht weiter, wenn beide Profile dieselbe `conversations.source` haben, sonst neues
   Gespräch (Dialog sagt es vorher). **Denkaufwand wird im selben Aufruf mitgeschickt** (Regel `nearestLevel` in
   `effort.ts`: gespeicherte Stufe, sonst nächsthöhere, sonst höchste; Server prüft nur). ⋮-Menü schließt nach
   jeder Aktion (`done`-Ereignis).
5. **Arbeits-Markierung beim Komprimieren**: Hook-Befehle `agent-orc agent-compacting` (PreCompact) und
   `agent-compacted` (PostCompact), `context.py: begin_compaction/end_compaction`; ein antwortender Agent bleibt
   unberührt (automatisches Komprimieren beendet die Antwort nicht).
6. Kleineres: Inline-Code in Antworten blau (`--color-code`), Fehler „Nicht gefunden“ bei neuen Agenten
   (Transkript existiert erst mit der ersten Nachricht).

### Änderungen außerhalb des Repositorys (alle mit Sicherung `*.bak-20261007-*` daneben)

- `~/.config/agent-orc/config.yaml`: Startprompt als Anker `&start_prompt` auch für `claude-local` und
  `claude-dashscope`; Hooks `PreCompact`, `PostCompact` und beim Hook `UserPromptSubmit` zusätzlich
  `lclaude-free-gpus` (Timeout 900 s). Wirkt nur für Agenten, die **danach** gestartet werden.
- `~/MiniPCLinux/scripts/lclaude` (Symlink in `~/bin`) und neues `lclaude-free-gpus` (Symlink in `~/bin`):
  vor jedem Laden eines lokalen Modells (beim Start und als Hook bei jeder Eingabe) Whisper-GPU-Worker beenden
  (CPU-Modell bleibt, `WHISPER_RELEASE_WAIT_MAX_S` Standard 600) und llama-swap-Hilfsmodelle (`-visiond`,
  `-embed`) entladen, die eine Karte mit dem Zielmodell teilen. Ohne `LCLAUDE_BASE_URL`/`LCLAUDE_MODEL` (Cloud-
  Agent) tut es nichts. Gleicher Ablauf wie AIfreds `_free_gpus_for_load`, aber dupliziert.
- `~/.config/llama-swap/config.yaml`: **neun vLLM-Einträge** (Qwen3.8-27B-NVFP4 und alle acht Flash-Next-
  Varianten) haben `--limit-mm-per-prompt '{"image":12,"video":0}' --mm-processor-kwargs '{"max_pixels":2097152}'`.
  Ursache: der vLLM-Fork setzt auf den V100-Karten standardmäßig **1 Bild pro Anfrage** („At most 1 image(s) may be
  provided“); ein PDF mit zwei Scanseiten scheiterte. Mit der Option las ein lokaler Agent Rams handgeschriebenen
  Brief und übersetzte ihn. llama-swap läuft mit `--watch-config`: **jede Änderung der Datei entlädt das geladene
  Modell sofort.** `Qwen3.6-27B-FP8-Dense-GDN-MTP` ist ein Testmodell für vllm-research und blieb unberührt.
  Der Sicherungslauf (`scripts/backup-system-configs.sh`) hat die Datei in MiniPCLinux committet und gepusht.
- `~/.claude/settings.json`: `cleanupPeriodDays: 7`.
- Grafana (MiniPCLinux, `docker/monitoring`): ein früherer Schalter für Handy/Tablet machte das Dashboard am
  Desktop riesig; zurückgenommen (`92b997d`). Das Handy-Anliegen von damals ist wieder offen.

## Getroffene Entscheidungen (Peuqui)

- Iframes der Arbeitsfläche **bleiben** (kein spürbares Leistungsproblem); `WorkspaceView.vue` (860 Zeilen) wird
  nur aufgespalten, nicht umgebaut.
- Freigabe-Ankündigung nur für Agenten außerhalb des geöffneten Arbeitsbereichs, mit „Zum Agenten“-Knopf, die
  Entscheidung (Erlauben/Ablehnen) bleibt in der Ankündigung.
- Denkaufwand beim Modellwechsel wird im Dialog **mit angeboten** (nicht nachgefragt, nicht serverseitig
  umgebogen); der Fehler darf nicht auftreten.
- Option für mehrere Bilder **direkt in die bestehenden** llama-swap-Einträge (nicht als Zusatzprofile), 12 Bilder.
- Gespräche werden endgültig gelöscht (kein Archiv, kein Papierkorb).
- Antworten-Ansicht bekommt später eine **eigene** Schriftgröße („Größer/Kleiner“, feste Stufen, Verhältnis bleibt);
  die Terminal-Schrift bleibt unverändert und wirkt dort nicht (gemessen, Terminal funktioniert).
- Lokale Modelle: kein Kontingent anzeigen; kein Gesamtwert über Anbieter.

## Offene Aufgaben (nach dem Reset, Freitag 9.10. ab ca. 16:00)

1. **`WorkspaceView.vue` aufspalten** (Kopfzeile, Spaltenraster, Sortieren/Ziehen, Speicher/Synchronisation als
   Composables, Tests für die reinen Teile); Verhalten gleich, Layout in elf Auflösungen prüfen
   (Testrezept in der Mittags-Übergabe). `TerminalView.vue` (596) und `SessionsView.vue` (527) erst danach.
2. **Schriftgröße der Antworten-Ansicht** (siehe Entscheidungen), pro Gerät, Spalten per `storage`-Ereignis wie
   `setting()` in `composables/useSettings.ts`.
3. **Kontingentanzeige je Anbieter**: heute nur Claude (`QUOTA_SOURCES` in `context.py`, `AgentProfile.quota` in
   `config.py`; `/api/quota` und `QuotaPanel.vue` sind schon eine Liste pro Profil). Für Codex, DashScope usw. je
   eine Quelle; erst klären, woher sie ihre Grenzen melden (unbekannt, DashScope evtl. nur Guthaben).
4. **Beobachter-Seite für AI-Connect** (Teilnehmer + Verkehr): Teilnehmer per WebSocket `list_peers` an die Bridge
   (Port 9999, Token aus `~/.config/ai-connect/config.yaml`, nicht hartkodieren), Verkehr aus der SQLite-Datei
   `~/.config/ai-connect/messages.db` lesend (Tabelle `messages`: Absender, Empfänger, Text, Zeit; ~800 Nachrichten
   seit April); Live durch Nachfragen alle 1–2 s. Abhängigkeit `websockets` ist im Entwicklungs-venv, nicht in
   `pyproject.toml`: nur nach Rückfrage eintragen/installieren.
5. **Prüfen**, ob AIfreds `llama-swap-autoscan.py` (läuft vor jedem Dienststart von llama-swap, schreibt
   `groups.main.members`) die `--limit-mm-per-prompt`-Option stehen lässt. Falls nicht: AIfred (Peer
   `Mini:AIfred-Intelligence`) fragen.
6. Ungeklärt: ob „Arbeitsmarkierung fehlt bei lokalem Agenten“ wirklich das Komprimieren war (normale Prompts sind
   gemessen korrekt markiert); die neuen Hooks wirken erst bei neu gestarteten Agenten. Beim nächsten echten
   `/compact` prüfen, ob die Karte „arbeitet“ zeigt.
7. Nicht getestet: Agentenwechsel mit Gesprächsübernahme auf einem echten Modell (nur tmux-Befehle in den Tests);
   Wirkung auf dem alten Lenovo-Pad (Android 10), alles nur im Desktop-Chrome geprüft; der 27B-Eintrag mit 12 Bildern
   (nur Flash-Next lief mit Bildern); Hook `lclaude-free-gpus` in einem echten Agenten über ein TTL-Entladen.
8. Kleinigkeiten, optional: Aufräumliste erst beim Aufklappen laden (0,05 s, Peuqui: nicht nötig); Warnung beim
   Anhängen von Bildern/PDFs an ein reines Textmodell (DeepSeek kann keine Bilder); Handy/Tablet-Layout von Grafana.
9. Von früher offen: Trust-Einträge für Test-Ordner im Scratchpad in `~/.claude.json` (mehrere Sitzungen schreiben
   die Datei, daher nicht angefasst); Hilfetexte „Einstellungen (☰)“ und Startdialog nur knapp; Docs/TODO.md Ideen
   zur Sprache am Echo Dot.

## Nächste Schritte (Vorschlag)

1. Zuerst `peer_read`, dann `MEMORY.md` lesen (neu: `state-2026-10-07-evening.md`, `plan-refactor-workspaceview.md`).
2. Vor jeder Arbeit prüfen, ob es Freitag 16 Uhr ist; vorher kein großes Paket beginnen und danach den befristeten
   Sparabschnitt aus `~/.claude/CLAUDE.md` entfernen.
3. Aufgaben 1 und 2 (Aufspalten, Schriftgröße) zuerst, dann 3 bis 5 nach Peuqui Reihenfolge.
4. Bei jeder Änderung an `llama-swap/config.yaml` vorher fragen, ob ein Modell geladen ist (entlädt sofort).

## Wichtige Dateien

Backend (`src/agent_orc/`): `api.py` (alle Endpunkte: Profilwechsel, Modell, Neustart, Gespräche aufräumen,
Freigaben), `sessions.py` (`change_profile`, `_respawn`), `history.py` (Gespräche, Aufräumen), `context.py`
(Arbeits-/Komprimierzustand, Kontingentquellen), `cli.py` (Hook-Befehle), `default_config.yaml`.

Frontend (`frontend/src/`): `components/ApprovalRequests.vue`, `ApprovalBanner.vue`, `ModelDialog.vue`,
`RestartButton.vue`, `AgentActions.vue`, `ConversationCleanup.vue`, `AttachMenu.vue`, `MessageInput.vue`,
`views/WorkspaceView.vue`, `TerminalView.vue`, `SessionsView.vue`, `FilesView.vue`, `effort.ts`,
`composables/useShownAgents.ts`, `useWorkspaceTab.ts` (`agentRoute`), `useSettings.ts`, `attachInOrder.ts`.
Tests: `tests/test_api.py`, `test_history.py`, `test_context.py`; `frontend/tests/effort.test.ts`.

Außerhalb: `~/MiniPCLinux/scripts/lclaude`, `lclaude-free-gpus`, `backup-system-configs.sh`;
`~/.config/agent-orc/config.yaml`, `~/.config/llama-swap/config.yaml`, `~/.config/lclaude/models.conf`.

## Stolperfallen

- Neue Konfigurationsschlüssel erst eintragen, wenn die Version installiert ist, die sie kennt; Hook-Befehle laden
  die Konfiguration. Hooks wirken nur für Agenten, die nach der Änderung gestartet wurden.
- Eine Änderung an der llama-swap-Datei entlädt das Modell (`--watch-config`); eigene Einträge dort immer als
  kompakter JSON schreiben (`{"image":12,"video":0}`, kein „: “ in der einfachen Zeichenkette von `cmd:`).
- Das gelöschte Modell `…-mm8-vllm` kann noch in einem Agenten gespeichert sein (Fehler „issue with the selected
  model“): im Wechseldialog auf das normale Modell stellen.
- Test mit Haiku oder lokalem Modell, Aufräumschritte aus der Mittags-Übergabe (Testinstanz über PID beenden,
  `tmux -L orc-uitest kill-server`, eigene Verlaufsordner unter `~/.claude/projects` mit `readlink -f` prüfen).
- Texte mit echten Umlauten, auch in Commits (Conventional Commits, Zeilen `Co-Authored-By` und `Claude-Session`);
  gezielt `git add`; Konfiguration und Sicherungen gehören nicht ins Repository.
