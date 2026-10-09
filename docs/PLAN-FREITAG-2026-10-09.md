# Plan für Freitag 9.10.2026 (nach dem Kontingent-Reset um 16:00)

Gesammelt am 8.10.2026 aus `docs/UEBERGABE-2026-10-07-abend.md`, `docs/TODO.md`, den Notizen der Sitzungen und den
Absprachen vom 8.10. Der Code ist die Wahrheit, bei Zweifeln dort nachsehen.

## Stand am 9.10., 18:25 (Sitzung mit Opus, Kontext gut 50 %)

Erledigt, gepusht und installiert:
- 1a Eingabe und Layout: Absenden über `POST /api/sessions/{id}/message` (Server tippt, dann Enter), Höhe der
  Vollbild-Seiten aus dem festen Body (`h-full`), Eingabefeld `field-sizing: content` mit Obergrenze `40cqh`,
  Umbruch langer Pfade in den Antworten, „App neu laden“ im ☰-Menü. **Am Handy noch nicht von Peuqui getestet.**
- Diktat sofort senden: ⚡ links neben dem Mikrofon (pro Gerät).
- Punkt 7 (mehrere Agenten im Ordner) ganz, inklusive eigener Startwerte je Agent (`--settings {settings}`).
- Punkt 2 Cache-Marker und Übergabe: `cache.py`, `CacheAge.vue`, `handover.lead_minutes` (Benutzer-Konfiguration
  umgestellt, Sicherung `config.yaml.bak-20261009-handover-lead`); Automatik bei Peuqui aus.
- `max-num-seqs` war schon 3.

In Arbeit / als Nächstes (Reihenfolge laut Peuqui):
1. Mitlesen (und später Mitdiskutieren) als eigener Tab „Gespräche“ rechts neben „Arbeitsfläche“. Anfrage an
   `Mini:AI-Connect` (18:21): Prozessgrenze statt Import, Befehle `observe-jsonl` und `send-json` im
   `observer_client.cli`; Antwort steht aus. User-Name kommt in die Agent-Orc-Konfiguration, das User-Token gibt
   Peuqui im Browser ein (pro Gerät), der Server reicht es nur durch.
2. `WorkspaceView.vue` aufspalten (Abschnitt 3).
3. Abschnitt 4: Schriftgröße der Antworten, Gelesen-Stand auf dem Server mit „Alle als gelesen“, Kontingent je
   Anbieter, Autoscan-Check.

Stolperfalle des Tages: Das DevTools-Werkzeug hängt fest an Port 9222; andere Agenten (AIfred) nutzen ihn auch.
Vor dem Start eines eigenen Chrome prüfen, ob 9222 frei ist, und nur die eigene Seite anfassen.

## 0. Vor dem Start

1. `peer_read`, dann `MEMORY.md` lesen.
2. Prüfen, dass es Freitag nach 16:00 ist. Danach den befristeten Abschnitt „BEFRISTET: Kontingent sparen“ in
   `~/.claude/CLAUDE.md` löschen.
3. Arbeitsbaum prüfen. `deploy/install.sh` bricht bei nicht committeten Änderungen ab. Zum Testen ohne Commit geht
   der Weg aus den früheren Sitzungen: `cd frontend && npm run build`, dann
   `~/.local/share/agent-orc/venv/bin/pip install .` im Projektordner und
   `systemctl restart agent-orc@mp.service` (Agenten laufen weiter, `KillMode=process`).

## 1. Offen aus dem 8.10.: Textfeld und Aktualisierung

- **Textfeld-Höhe** (`MessageInput.vue`, Funktion `fitHeight`, beim Aufbau und bei Textänderung): geändert, gebaut,
  am 8.10. installiert, **noch nicht committet**. Peuqui testet selbst (langer Text, Arbeitsfläche wechseln und
  zurück, abschicken) und sagt Bescheid, dann committen.
- **PWA ohne Aktualisieren:** Peuqui meldet, dass die installierte App keinen Aktualisieren-Knopf mehr hat und sich
  nicht mehr herunterziehen lässt (eine frühere Designänderung). Neue Versionen kommen nur über die automatische
  Aktualisierung (`frontend/src/update.ts`: Service-Worker, Neuladen beim Wechsel). Klären: Was genau wurde
  entfernt, und braucht es einen Weg zum erzwungenen Neuladen (zum Beispiel Eintrag im ☰-Menü)?

## 1a. Zuerst: Schritt zurück bei Vollbild-Layout und Texteingabe (Peuqui, 8.10.)

Peuqui vermutet, dass die einzelnen Flicken der letzten Tage zusammen eher schaden („baufälliger Holzschuppen“),
und will vor dem Weiterbauen ganz sorgfältig analysieren, ob es einen einfacheren Grund für alle aufgelaufenen
Probleme gibt. Möglicherweise reicht eine grundsätzliche Lösung statt vieler Ausnahmen. **Nicht weiter flicken, bis
das geklärt ist.** Der Text-Fix von `fitHeight` bleibt uncommittet, bis klar ist, ob er in die neue Lösung gehört.

Zu klärende Symptome (Details in `docs/TODO.md`, Abschnitt „Eingabefeld und Oberfläche“):
- Eingabefeld ragt mit langem Text über den unteren Bildschirmrand und wird abgeschnitten.
- Langer Text wird eingetippt, das Enter aber als Zeilenumbruch genommen (drei Nachrichten wurden zu einer).
- Seit dem Festsetzen des Bodys geht das Herunterziehen zum Neuladen nicht mehr.
- Eingabefeld schrumpft nach Arbeitsflächenwechsel (`fitHeight`).

Vorgehen:
1. Den Zustand **vor** `9e5d071` (7.10., 12:40, Body `position: fixed`, `overflow: clip`) ansehen und die Ursache
   für das damalige Verrutschen (Fokus im Eingabefeld, Bildschirmtastatur, Höhe `dvh`/Iframe) wirklich messen,
   statt weitere Ausnahmen zu setzen. Ob die Klammer um den Body nur ein Symptom abdeckte.
2. Die Kette der Änderungen am Eingabebereich lesen, die miteinander wirken: Fokus gehört dem Nachrichtenfeld
   (`3310d64`), Klick in die Antworten fokussiert das Feld (`8f7926f`), Tippen ins Terminal öffnet keine Tastatur
   (`d54da3e`), kein Fokus nach dem Diktat (`3a6e27c`, `caac2cb`), Überlager über dem Feld (`785e6f1`), Feld
   wächst mit dem Inhalt, Enter getrennt vom Text (`submitText`, `pump_input`, `type_line`).
3. Daraus eine Lösung für alle Symptome ableiten (zum Beispiel eine einzige Stelle für Höhe und Fokus, Absenden
   serverseitig als eine Nachricht, Seitenhöhe aus der sichtbaren Fläche), erst dann bauen und mit echten Daten auf
   dem Handy testen. Danach Abschnitt 1 (Aktualisieren) neu bewerten.

## 2. Cache-Marker und automatischer Handover (Absprache vom 8.10.)

**Marker (eine gemeinsame Komponente, zum Beispiel `CacheAge.vue`)**
- Neben dem Agentennamen in der Kopfzeile von Agentenkarte (`SessionsView.vue`) und Terminal-Ansicht
  (`TerminalView.vue`); dazu die rote Warnung in Terminal-, schöner Ansicht und Karte.
- Zeigt das Alter des Caches („42 min“), die Restzeit im Tooltip, bei laufender Arbeit „aktiv“.
- Farben: warm neutral oder grün; unter dem Vorlauf gelb; kalt rot, mit Zusatz „Handover liegt vor“, wenn einer
  geschrieben wurde.
- Das Backend liefert pro Sitzung Ablaufzeitpunkt und Fensterlänge, das Frontend zählt lokal.
- Fensterlänge: aus dem Transcript, `usage.cache_creation.ephemeral_1h_input_tokens` oder `…5m…` (1 Stunde heute
  üblich, bei Kontingent-Überschreitung 5 Minuten). Zeitstempel des letzten Requests: erst prüfen, ob die
  Statuszeile ihn liefert, sonst aus dem Transcript.
- Kontextgröße kommt schon: `agent-orc statusline` meldet `context_tokens` und `context_window`
  (`cli.py`, `context.py`), die Oberfläche zeigt sie im Ring.

**Automatischer Handover vor dem Erkalten**
- Vorhanden ist `src/agent_orc/handover.py` (Hinweis ab `threshold_percent`, Schalter `auto`, tippt den Prompt in
  den ruhenden Agenten). Neu ist nur der Auslöser: Restzeit unter dem Vorlauf statt Leerlauf über
  `cold_after_minutes` (die Absicht des alten Werts war der Fall „schon kalt“).
- Vorlauf **10 Minuten** (Handover nach 50 Minuten), konfigurierbar. Schwelle **50 Prozent** des Fensters
  (Fenster pro Agent aus `context_window`, bei einer Million Token also 500.000, bei Haiku automatisch richtig).
- **Sperre:** nur ein Handover pro Leerlaufphase. Der Handover wärmt den Cache selbst auf, sonst käme er jede Stunde
  wieder. Danach kalt bleiben lassen; erst eine neue Eingabe setzt zurück.
- „Restzeit unter Vorlauf“ gilt auch bei negativer Restzeit (schon kalt), kein zweiter Pfad. Nur im Leerlauf.
- Kein Pop-up (würde nach einer Stunde Stille ungesehen verfallen). Meldung danach auf der Karte und per Push.
- Kein Warmhalten per Ping, kein Aufwärmen bei kleinem Kontext (höchstens später als abschaltbarer Schalter).
- Schwellen in die Konfiguration (`HandoverConfig`), nichts hartkodieren. Neue Schlüssel erst in die Benutzer-
  Konfiguration eintragen, wenn die Version installiert ist, die sie kennt.

## 3. `WorkspaceView.vue` aufspalten (Entscheidung vom 7.10.)

- Iframes **bleiben**. Die Datei (860 Zeilen) wird nur aufgespalten: Kopfzeile mit den Arbeitsflächen, Spaltenraster
  (Köpfe, Trenner), Sortieren und Ziehen, Speicher und Synchronisation als Composables, Tests für die reinen Teile.
- Verhalten bleibt gleich. Layout in den elf Auflösungen prüfen (Testrezept in `docs/UEBERGABE-2026-10-07.md`).
- `TerminalView.vue` (596) und `SessionsView.vue` (527) erst danach.
- Mit einbauen (Verhaltensänderung, `docs/TODO.md`): Eine per Tab verschobene Spalte zieht das horizontale Scrollen
  mit und bleibt sichtbar, auch wenn sie ans andere Ende wandert.

## 4. Weitere Aufgaben (Reihenfolge nach Peuqui)

1. **Schriftgröße der Antworten-Ansicht:** eigene Einstellung im ☰-Menü neben der Terminal-Schrift, „Größer/Kleiner“
   in festen Stufen (Prozentzahl daneben), alle Schriftgrößen um denselben Faktor, damit das Verhältnis bleibt.
   Pro Gerät, Spalten per `storage`-Ereignis wie `setting()` in `composables/useSettings.ts`. Die Terminal-Schrift
   bleibt unverändert.
2. **Kontingentanzeige je Anbieter:** heute nur Claude (`QUOTA_SOURCES` in `context.py`, `AgentProfile.quota` in
   `config.py`). Für Codex, DashScope usw. je eine Quelle; erst klären, woher sie ihre Grenzen melden (unbekannt,
   DashScope evtl. nur Restguthaben). Lokale Modelle: nichts anzeigen, kein Gesamtwert über Anbieter.
3. **AI-Connect mitlesen (Peuqui, 8.10.):** Der User will den Datenverkehr der Bridge mitlesen, live und rückwirkend,
   sortiert nach „wer redet mit wem“, zum Beispiel als Baum (Teilnehmer, darunter die Gesprächspartner, darunter die
   Nachrichten). Aufrufbar als eigenes Programm im Terminal **und** per Knopf in Agent-Orc als eigene Ansicht (wie
   Dateien, Agentenkarten, Arbeitsflächen). Die Bridge hat dafür heute keine Funktion: Wächter und Verlauf
   gelten pro Teilnehmername (`server/websocket_server.py`). Entwurf: neue, nur lesende Nachrichtenart „observe“
   (alle Nachrichten live) und ein Verlauf über alle Paare in der Bridge selbst, ein gemeinsamer Client für das
   Programm und für Agent-Orc (SSOT statt eigenem SQLite-Zugriff). Zugang mit dem vorhandenen Token (Bridge-
   Konfiguration, nicht hartkodieren). Die Anfrage dazu ging am 8.10. an den Peer `Mini:AI-Connect`; Antwort und
   Entwurf dort abwarten. Das Paket `websockets` steht nur im Entwicklungs-venv von Agent-Orc: eintragen oder
   installieren nur nach Rückfrage.
   Einschätzung von `Mini:AI-Connect` (8.10., aus dem Kopf, beim Bau gegen den Code prüfen):
   - „observe“ als eigene Verbindungsart ohne `register`: Der Server führt sie in einer getrennten Beobachter-Menge und
     lehnt alles außer `observe`, `history_all` und `ping` ab. Es entsteht kein Eintrag in der Teilnehmertabelle,
     also kann ein Mitleser weder senden noch einen Namen belegen.
   - Ein einziger Hook an der Stelle, an der der Server die Nachricht ohnehin speichert (`message_store`), statt einer
     zweiten Kopie im Routing: eine Wahrheit, kein vergessbarer zweiter Pfad.
   - Token: ein eigener, nur lesender Token wäre sauberer als der vorhandene (sonst liest jeder Besitzer des
     Peer-Tokens alles mit). **Entscheidung für Peuqui:** Läuft alles auf einem Rechner mit einem Benutzer, reicht der
     vorhandene.
   - Gemeinsames Modul im Repository AI-Connect (observe-Verbindung, `history_all`, Baum-Aufbau) plus ein dünnes
     Terminalprogramm; Agent-Orc importiert das Modul oder spricht dieselbe Schnittstelle an, kein SQLite-Zugriff.
     Agent-Orc reicht per SSE oder WebSocket durch, das Token bleibt im Server.
   - Größe: Nachrichten enthalten oft Code und Dateiinhalte. `history_all` mit Pflicht-Limit und Zeitraum (Standard zum
     Beispiel 24 h beziehungsweise 200 Nachrichten), Seiten über Zeitstempel oder ID. Im Baum nur eine gekürzte erste
     Zeile, den vollen Text erst beim Aufklappen.
   - Darstellung: Baum Teilnehmer, Gesprächspartner, Nachrichten (mit Anzahl und Zeit der letzten Nachricht, neueste
     oben) und zusätzlich eine chronologische Live-Ansicht „A -> B: Vorschau“ als Umschalter. Ein Paar A/B nur einmal
     (sortiertes Paar als Wurzel „Gespräch“), sonst doppelt sich der Baum.
   - AI-Connect baut ab Freitag mit, Agent-Orc meldet sich dort dann.
   **Erweiterung, noch zu besprechen (Peuqui, 8.10.):** Der Mitleser soll auch eingreifen können, als „User“ angemeldet, mit
   einer Nachricht an beide oder mehrere Teilnehmer einer Diskussion. Das ändert die Sicherheitsfrage: Nur lesen
   (Beobachter, kein `register`) und Senden als User sind getrennte Rollen. Offene Punkte:
   - Der Absendername darf nicht fälschbar sein. Heute prüft die Bridge nur das gemeinsame Token, jeder Teilnehmer
     könnte sich „User“ nennen. Vorschlag: eigenes Token für die Rolle User, die Bridge vergibt den Absendernamen aus
     dem Token (Name reserviert), das Lese-Token kann nicht senden.
   - Autorität: Agenten behandeln Peer-Nachrichten als Information, nicht als Anweisung des Users. Soll eine
     Nachricht des reservierten Absenders als Anweisung von Peuqui gelten, braucht es eine Regel dafür in der
     globalen `CLAUDE.md` (`integrations/claude-code/CLAUDE.md`), sonst bleibt sie nur ein Hinweis.
   - Mehrere Empfänger: einfachste Lösung ohne neue Protokollart ist ein Versand an jeden Empfänger einzeln mit
     Hinweis im Text („von Peuqui an A, B“). Im Baum erschiene das als zwei Gespräche (User-A, User-B); ein echtes
     Gruppengespräch bräuchte eine Gesprächs-Kennung in der Bridge.
   - Der Handshake (`[LGTM]`/`[CONTINUE]`) und die Antworten der Agenten müssen mit einem menschlichen Teilnehmer
     umgehen können (keine Ausstiegsschleife an den User).

   **Antwort von `Mini:AI-Connect` auf die Erweiterung (8.10., 15:08):**
   - Rollenmodell schon in Schritt 1 (kein Vorratsbau, der Mitleser braucht den Mechanismus ohnehin): Konfiguration
     bildet Token auf Rolle ab (`peer`, `observer`, `user`), `_check_token` hängt die Rolle an die Verbindung, eine
     Tabelle Rolle zu erlaubten Nachrichtenarten ist die einzige Wahrheit. „user“ ist später ein dritter Eintrag.
     Der Absendername der Rolle `user` kommt vom Server (reserviert, zum Beispiel `User:Peuqui`), `register` mit
     diesem Namen wird für `peer` abgelehnt.
   - **Folge, die Peuqui wissen und entscheiden muss:** Das alte Einzel-Token entfällt (kein Fallback). Alle Teilnehmer
     (Plugin-Konfiguration jeder Claude-Code-Sitzung und jeder andere Client) bekommen ihr Peer-Token und müssen
     einmal umgestellt werden. Agent-Orc braucht für die Ansicht das Beobachter-Token.
   - Keine Gesprächs-Kennung jetzt (SQLite-Änderung ohne Nutzer; später eine nullable Spalte per `ALTER TABLE`).
     Einzelversand an jeden Empfänger genügt; der Baum kann gleichlautende User-Nachrichten später gruppieren.
   - Handshake-Ausnahme und Autorität nur als Regel in `integrations/claude-code/CLAUDE.md`, **gebunden an den vom
     Server gesetzten Absender**, nie an Text im Inhalt („Peuqui sagt …“). Die Autoritätsregel entscheidet Peuqui.
   - Schnitt (ein Paket, jede Datei eine Aufgabe): `server/roles.py` (Token zu Rolle, Rolle zu erlaubten Arten),
     `server/observers.py` (Beobachter-Menge, Verteilung aus dem Hook im `message_store`), `message_store` bekommt
     nur `history_all` (Zeitraum, Limit), `websocket_server` nur Verdrahtung. Client als eigenes Paket
     (`observer_client/`: `connection.py`, `tree.py` als reiner Datenaufbau mit Gespräch gleich sortiertes Paar,
     `cli.py`); Agent-Orc benutzt `connection` und `tree`, nicht `cli`. Schritt 2 später: `server/user_send.py`
     (Handler für Rolle `user`, setzt den Absender, Mehrfachversand) plus ein `send`-Befehl im Client.

   **Entscheidungen von Peuqui (8.10.):** Anweisungen von `User:Peuqui` gelten als Befehle (Regel in
   `integrations/claude-code/CLAUDE.md`, gebunden an den Server-Absender). Eigene Tokens pro Rolle sind in Ordnung.
   **Klarstellung zu den Tokens:** Es gibt drei Tokens, nicht eines pro Sitzung: `peer` (alle Agenten gemeinsam, wie
   heute das eine Token), `observer` (Agent-Orc und Terminalprogramm), `user` (später). Alle Sitzungen lesen die
   Datei `~/.config/ai-connect/config.yaml` desselben Benutzers (`load_config`), ein neuer Agent in einem anderen
   Ordner braucht deshalb nichts Neues. Zu klären: Bleibt der Wert des heutigen Tokens als `peer`-Token erhalten,
   muss an den Sitzungen nichts umgestellt werden, nur die Konfiguration der Bridge bekommt eine Tabelle; andere
   Rechner (zum Beispiel Aragon mit `FreeEchoDot2`) haben dieselbe Datei mit demselben Token.
   **Offene Sicherheitsgrenze:** Die Agenten laufen unter demselben Betriebssystem-Benutzer und können die
   Konfigurationsdatei lesen, also auch die Tokens für `observer` und `user`. Die Trennung schützt dann vor
   Versehen und falschen Namen, nicht vor einem Agenten, der die Datei absichtlich liest. Abhilfen zu besprechen:
   eigene Datei für `observer`/`user` nur für die Werkzeuge des Users und in den Claude-Einstellungen das Lesen dieser
   Datei verbieten (weicher Schutz), oder ein eigener Benutzer (hart, aufwendig).
4. **Autoscan-Check:** Ob `llama-swap-autoscan.py` von AIfred (läuft vor jedem Start von llama-swap) die Option
   `--limit-mm-per-prompt` stehen lässt. Falls nicht: Peer `Mini:AIfred-Intelligence` fragen. Vor jeder Änderung an
   `~/.config/llama-swap/config.yaml` fragen, ob ein Modell geladen ist (die Datei entlädt es sofort).

5. **Gelesen-Stand der Antworten auf dem Server** statt im Browser (Details in `docs/TODO.md`), damit der Wechsel
   zwischen Desktop, Handy und Tablet nicht alles wieder rot macht.
6. ~~llama-swap: `--max-num-seqs` von 4 auf 3~~ erledigt (geprüft 9.10.: 27B und alle Flash-Next-Einträge stehen auf 3).

7. **Mehrere Agenten im selben Projektordner (Peuqui, 9.10., neu gefasst am Nachmittag)**

   *Ziel.* Im selben Ordner laufen mehrere Agenten gleichzeitig, zum Beispiel einer zum Reviewen oder für eine andere
   Aufgabe; sie können sich über AI-Connect absprechen. **Keine Sperre, kein Umschalten:** Die eigene Sitzungs-ID trennt
   alles in Agent-Orc; gleichzeitiges Schreiben in dieselbe Datei erkennt Claude Code selbst (geändert seit dem Lesen),
   beim Committen gilt „gezielt `git add`“.

   *Name.* Der erste Agent heißt wie der Ordner (wie heute). Jeder weitere braucht einen **Pflicht-Zusatz**: Der Start-
   dialog zeigt den Ordnernamen fest vorne und ein Feld für den Zusatz („Agent-Orc-“ + „Review“); Starten geht erst,
   wenn der Zusatz nicht leer, erlaubt (Buchstaben, Ziffern, `.`, `_`, `-`) und im Ordner frei ist. Der Server prüft
   dasselbe (409). Keine Rollen-Konfiguration: Der Zusatz ist die Rolle; Profil, Modell und Denkstufe wählt der
   Startdialog wie heute.

   *AI-Connect.* Eigener Peer-Name je Agent über eine optionale Variable `AI_CONNECT_PEER_SUFFIX` (Anfrage an
   `Mini:AI-Connect` am 9.10., 17:15): AI-Connect hängt den Zusatz mit Bindestrich an seinen selbst gebildeten Namen
   (`Mini:Agent-Orc-Review`), die Regel „Host:Projekt“ bleibt dort. Agent-Orc setzt die Variable nur bei einem Zusatz;
   ihr Name steht in der Profil-Konfiguration, nicht im Code.

   *Bausteine, jeder für sich, mit Tests:*
   1. Sitzungs-ID aus Pfad plus Zusatz (`sessions.py`: `session_id_for`, `find_by_path`, 409 je Name); Zustandsdateien
      je ID tragen die neue ID.
   2. Start mit Zusatz (API und Startdialog, Pflichtfeld wenn der Ordner schon einen Agenten hat), Zusatz als
      Umgebungsvariable an den Agenten.
   3. Einstellungen je Sitzung beim Start (`--settings` und Optionen) statt `<Ordner>/.claude/settings.local.json`;
      `effort.py` darauf umstellen. Vorher klein mit Haiku testen, ob Startangaben die Ordner-Datei übersteuern.
   4. „Letztes Gespräch fortsetzen“ je Agent (ausdrückliche Gesprächs-ID statt „neuestes im Ordner“).
   5. Anzeige: voller Name auf Karte, Spaltenkopf und in der Fernsteuerung.

   *Stand 9.10., 17:35:* Bausteine 1, 2, 4 und 5 erledigt und installiert (Zusatz, Startdialog mit Pflichtfeld, Neustart
   mit eigenem Gespräch, Namen auf Karten). `AI_CONNECT_PEER_SUFFIX: "{suffix}"` steht in den drei Claude-Profilen der
   Benutzer-Konfiguration; echt getestet mit zwei Haiku-Agenten: `Mini:peertest` und `Mini:peertest-Test` gleichzeitig
   online. Baustein 3 erledigt am Abend (`19a37aa`): eigene Einstellungsdatei je Agent
   (`--settings {settings}`), Profil-Eintrag `settings`, `store` entfallen; echt getestet mit zwei Haiku-Agenten im
   selben Ordner (gemeldet `high` und `low`). Benutzer-Konfiguration migriert, Sicherung
   `config.yaml.bak-20261009-agent-settings`.

   *Verworfen.* Sperre mit vorgemerkter Umschaltung und Eingabe-Tor (unnötig ohne Ausschluss), feste Rollen-
   Konfiguration, Worktree je Agent, Unteragent als einziger Weg.

8. **Diktat sofort an den Agenten senden (Peuqui, 9.10., heute ab 16 Uhr):** Ein Schalter, damit eine Aufnahme nach der
   Transkription **direkt** an den Agenten geht, ohne Druck auf „Senden“. So ist es in AIfred umgesetzt (Text
   „⚡ Direkt senden“ in `aifred/lib/i18n/de.json`, dort die Umsetzung nachlesen). Der Text muss dabei nicht noch einmal im
   Eingabefeld erscheinen (Peuqui: kann, muss nicht), er steht danach im Terminal und in der Antworten-Ansicht.
   - Einstellung pro Gerät, Standard aus, im ☰-Menü bei den Sprach-Einstellungen; Speicherung wie die übrigen Geräte-
     einstellungen (`setting()` in `composables/useSettings.ts`, zum Beispiel wie `speechEngine`).
   - Umsetzung an der einen Stelle, an der die Transkription ankommt (`useDictation(...)` in `MessageInput.vue`): bei
     eingeschaltetem Schalter ruft sie dieselbe `submit()` auf wie der Sendeknopf (also dasselbe Absenden mit Anhängen),
     statt den Text ins Feld zu setzen. Kein zweiter Sendeweg.
   - Zu entscheiden: Steht schon ein Entwurf im Feld, geht er mit hinaus (Vorschlag: ja, Diktat wird angehängt, wie heute)
     oder bleibt er stehen. Fehlgeschlagene Aufnahmen („Erneut“) bleiben unverändert und senden nach gelungenem
     Erneut-Versuch ebenfalls sofort.
   - Abhängigkeit: Es nutzt das Absenden, in dem das Enter-Problem steckt (siehe Punkt 1a und `docs/TODO.md`, langer Text
     wird nicht abgeschickt). Erst das Absenden reparieren, dann diesen Schalter einbauen, sonst bleiben diktierte
     Texte unabgeschickt im Eingabefeld von Claude Code stehen, ohne dass man es merkt.

## 5. Zu prüfen und nicht getestet

- Ob „Arbeitsmarkierung fehlt bei lokalem Agenten“ wirklich das Komprimieren war. Die Hooks `PreCompact` und
  `PostCompact` wirken nur bei neu gestarteten Agenten; beim nächsten echten `/compact` prüfen, ob die Karte
  „arbeitet“ zeigt.
- Agentenwechsel mit Gesprächsübernahme auf einem echten Modell (bisher nur tmux-Befehle in den Tests).
- Wirkung auf dem alten Lenovo-Pad (Android 10); bisher alles nur im Desktop-Chrome geprüft.
- Der 27B-Eintrag mit 12 Bildern (nur Flash-Next lief mit Bildern).
- Hook `lclaude-free-gpus` in einem echten Agenten über ein TTL-Entladen.

## 6. Kleinigkeiten, optional

- Aufräumliste für Gespräche erst beim Aufklappen laden (0,05 s, Peuqui: nicht nötig).
- Warnung beim Anhängen von Bildern oder PDFs an ein reines Textmodell (DeepSeek kann keine Bilder).
- Handy- und Tablet-Layout von Grafana (MiniPCLinux, `docker/monitoring`).
- Trust-Einträge für Test-Ordner im Scratchpad in `~/.claude.json` (mehrere Sitzungen schreiben die Datei, daher
  nicht angefasst).
- Hilfetexte „Einstellungen (☰)“ und Startdialog sind nur knapp.

## 7. Sprache am Echo Dot (`docs/TODO.md`, ohne Termin)

- Antwort zurück an den Echo: Hörabsatz nach der Antwort in denselben Raum ansagen, Raum per Markierungsdatei vom
  Server zum Stop-Hook (`agent-idle` in `cli.py`).
- Verstandenes aufzeichnen (Text, gewählter Agent, Ähnlichkeitswert) und die Namenserkennung daran messen.
- Double Metaphone als Ergänzung der Kölner Phonetik (`phonetics.py`), nur nach gemessenen Fällen und nach Rückfrage
  wegen des Pakets.
- Folgeaufnahme ohne Wake-Word (Weg B2): braucht Firmware und AIfred.
- Automatische Ansage auch ohne Sprach-Auftrag: bewusst nicht gewollt.
- Aufbewahrung alter Aufnahmen nach Alter (Rotation nach Anzahl gibt es).

## Stolperfallen

- Neue Konfigurationsschlüssel erst eintragen, wenn die Version installiert ist, die sie kennt. Hooks wirken nur für
  Agenten, die nach der Änderung gestartet wurden.
- Tests mit echten Agenten nur mit Haiku oder lokalem Modell. Aufräumschritte (Testinstanz über PID beenden,
  `tmux -L orc-uitest kill-server`, Verlaufsordner mit `readlink -f` prüfen) stehen in der Mittags-Übergabe.
- Commits: Conventional Commits mit echten Umlauten, gezielt `git add`, Konfiguration und Sicherungen nicht ins
  Repository.
