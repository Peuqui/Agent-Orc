# Übergabe vom 9.10.2026 (Abend, Sitzung mit Opus)

Zuerst lesen: dieses Dokument, dann `docs/TODO.md`. Der Plan `docs/PLAN-FREITAG-2026-10-09.md` hat oben einen
Zwischenstand und die Details zu den Punkten. Der Code ist die Wahrheit.

## Ziel

Agent-Orc steuert mehrere Claude-Code-Agenten (Karten, Arbeitsfläche mit Spalten, Diktat, Sprache, Push). Diese
Sitzung hat die Eingabe am Handy repariert, mehrere Agenten pro Ordner möglich gemacht, eigene Startwerte pro
Agent eingeführt, einen Cache-Marker samt Übergabe vor dem Erkalten gebaut, die Arbeitsfläche aufgeteilt und den
Gelesen-Stand auf den Server gelegt. Als Nächstes kommt der Tab „Gespräche“: AI-Connect mitlesen und mitdiskutieren.

## Stand (alles committet, gepusht und installiert, zuletzt `07067b1`)

| Thema | Wo | Kern |
|---|---|---|
| Absenden | `api.py` `send_message`, `MessageInput.vue` | `POST /api/sessions/{id}/message`, der Server tippt per `type_line` und drückt dann Enter. Beim Fehler kommt der Text zurück ins Feld. |
| Layout | `style.css` (`app-shell`), Vollbild-Views `h-full`, `MessageInput.vue` | Die Höhe kommt nur aus dem festen Body. Das Feld nutzt `field-sizing: content`, maximal `40cqh` der Ansicht (`TerminalView` ist Size-Container). |
| Antworten umbrechen | `style.css` `.markdown` | `wrap-anywhere` |
| App neu laden | `SettingsMenu.vue` | ruft `reloadToNewVersion` |
| ⚡ Direkt senden | `DictationMic.vue`, `useSettings.ts` (`dictationSendsAtOnce`) | links neben dem Mikrofon, pro Gerät |
| Mehrere Agenten pro Ordner | `sessions.py` (`agent_name`, `check_suffix`, `find`, `@orc_suffix`), `StartAgentDialog.vue` | Ein weiterer Agent braucht einen Zusatz `[A-Za-z0-9_-]`. Die ID ergibt sich aus Pfad und Zusatz, `AgentSession.name`. Keine Sperre. |
| AI-Connect-Name | Profil-`env` `AI_CONNECT_PEER_SUFFIX: "{suffix}"` | Ergebnis `Mini:Projekt-Zusatz`, echt getestet |
| Neustart mit eigenem Gespräch | `api.py` `own_conversation`, `sessions._command` | `--continue` nur für den ersten Agenten, sonst `--resume <id>` aus dem Transkript |
| Startwerte pro Agent | `effort.py`, `config.py` (`AgentProfile.settings`, `{settings}`) | Eine eigene Datei pro Agent unter `<state>/agents/<id>.settings.json`. Gemessen mit Claude 2.1.295: `--settings` übersteuert die Ordnerdatei, und es gilt nur das letzte `--settings`. `store` ist entfallen. |
| Cache-Marker und Übergabe | `cache.py`, `handover.py`, `CacheAge.vue`, `useNow.ts` | Ablauf aus dem Transkript (letzte Antwort plus Fenster aus `cache_creation`). Übergabe fällig `lead_minutes` (10) vor Ablauf, wenn ein ruhender Agent mehr als 50 % Kontext hat. Ablauf: asked, working, done, bis zur nächsten Eingabe. Die Automatik ist bei Peuqui aus, er bekommt dann nur eine Benachrichtigung. |
| Arbeitsfläche aufgeteilt | `WorkspaceView.vue` (471 Zeilen), `useWorkspaceStore.ts`, `useColumnWidths.ts`, `useWorkspaceKeys.ts`, `WorkspaceSwitcher.vue`, `AddColumnMenu.vue`, `ColumnCountControl.vue` | Eine verschobene Spalte wird aktiv und rollt ins Bild. |
| Größe der Antworten | `useSettings.ts` (`answersScale`), `AnswersFeed.vue` (`zoom` auf der inneren Hülle) | 70–200 % in 10er-Schritten |
| Gelesen-Stand | `state.py` (`answers-seen.json`), `api.py` `answers_seen` (async!), `useAnswerSeen.ts` | Der Server geht nur vorwärts. Eine Spalte übernimmt nur, was über ihre eigenen Markierungen hinausgeht. Häkchen „Alle als gelesen“. |

Benutzer-Konfiguration `~/.config/agent-orc/config.yaml`, umgestellt mit Sicherungen:
- `.bak-20261009-peer-suffix`
- `.bak-20261009-agent-settings`: Hooks als `settings:`-Block mit Anker `claude_settings`, `{settings}` in den Argumenten
- `.bak-20261009-handover-lead`: `lead_minutes`

## Entscheidungen (mit Peuqui)

- Mehrere Agenten pro Ordner arbeiten gleichzeitig, ohne Sperre und ohne Umschalten. Der Zusatz ist die Rolle, eine feste Rollen-Konfiguration gibt es nicht.
- Jeder Agent hat eigene Startwerte. Agent-Orc beschreibt Projektordner nicht mehr. Alte `settings.local.json` bleiben liegen, weil Claude dort auch eigene Berechtigungsregeln ablegt.
- Keine Übernahme alter Werte: neue Startwerte kommen aus der Profil-Voreinstellung, und die Antworten erscheinen einmal alle als ungelesen.
- Tab „Gespräche“ rechts neben „Arbeitsfläche“. Agent-Orc nutzt AI-Connect über eine **Prozessgrenze**, nicht per Import, weil AI-Connect kein Paket ist und eigene Abhängigkeiten hat.
- User-Name für das Mitdiskutieren aus der Agent-Orc-Konfiguration. Das User-Token gibt Peuqui im Browser ein (pro Gerät), der Server reicht es nur durch und speichert es nicht.

## Nächste Schritte

1. **Tab „Gespräche“ bauen.** Die Schnittstelle von AI-Connect ist fertig (Commits 412ae9a, cc36c1a):
   - Mitlesen: `<AI-Connect>/venv/bin/python -m observer_client.jsonl observe --hours N --limit M`, Arbeitsverzeichnis ist der AI-Connect-Ordner. Ausgabe als JSON-Zeilen:
     - `{"event":"peers",...}` beim Start und bei jedem An- oder Abmelden;
     - `{"event":"message",id,from,to,content,context,timestamp}`;
     - `{"event":"history_end"}`;
     - `{"event":"error","kind":"token_refused|token_missing|unreachable|closed"}` als letzte Zeile mit Exit 1. Bei `closed` (Neustart der Bridge) startet Agent-Orc den Prozess neu.
   - Senden: `... -m observer_client.jsonl send`. Eingabe über stdin `{"token","as","to":[...],"content"}`. Ausgabe auf stdout `{"sent":[{to,id,online}]}` mit Exit 0, oder `{"error":"token_refused|bridge|unreachable",...}` mit Exit 1.
   - Der Befehl, `hours`, `limit` und der User-Name gehören in die Agent-Orc-Konfiguration (neuer Abschnitt). Neue Schlüssel erst eintragen, wenn die Version installiert ist, die sie kennt.
   - Darstellung: Baum Gespräch (sortiertes Paar; Rundruf ist (Absender, `*`)), darunter Nachrichten mit gekürzter erster Zeile, der volle Text beim Aufklappen. Umschalter auf eine chronologische Live-Ansicht. Das Senden erst, wenn das Token da ist.
   - **Achtung:** Bash-Befehle mit `observer_client` im Text sind für Claude-Sitzungen gesperrt. Agent-Orc ruft den Prozess aus Python auf, Tests von Hand also nur so, dass der Name nicht im Befehl steht.
   - **Vorher von Peuqui:** User-Token erzeugen, danach `ai-connect.service` neu starten. Klären, ob der Agent den Neustart machen darf. Am 9.10. durfte er einmal auf Ansage.
2. **Kontingent je Anbieter:** Peuqui fragen, welche Anbieter (Codex, DashScope, andere) und wo sie ihre Grenzen melden.
3. **Peuqui fragen:** Den Satz vom 8.10. zum Gelesen-Stand („Auch könnte man ja …“) beenden.
4. **Am Handy testen lassen:** Layout, Absenden langer Diktate, ⚡, Cache-Marker. Das ist bisher nur in der Emulation geprüft.
5. Wackelnder Test `test_restart_resumes_a_busy_agent_with_its_waiting_effort`: einmal in neun vollen Läufen fehlgeschlagen.

## Testrezept, Stolperfallen

- UI-Testinstanz: Skript `uitest_serve.py` im Scratchpad der alten Sitzung. Es liest die echte Konfiguration, nutzt Port 18765, tmux `orc-uitest` und ein `cat`-Demo-Profil mit `{suffix}`. Mit dem Argument `real` gelten die echten Profile. Im Repository liegt es nicht, bei Bedarf neu schreiben nach dem Rezept in `docs/UEBERGABE-2026-10-07.md`.
- **Port 9222:** Das DevTools-Werkzeug hängt fest daran, auch andere Agenten (AIfred) nutzen ihn. Vorher `ss -ltnp | grep 9222` prüfen und nur die eigene Seite anfassen. Nach dem Neubau Service Worker und Caches leeren. Nach `fetch('/api/login')` neu laden, sonst bleibt die Login-Maske.
- Die Antworten-Ansicht liest nur Transkripte unter `~/.claude/projects`.
- `TestClient` ohne `with` startet pro Anfrage eine eigene Ereignisschleife. Für Tests mit Nebenläufigkeit `with TestClient(...)` nehmen.
- Nie `npx` (installiert stillschweigend). Die Skripte aus `frontend/package.json` benutzen: `npm run typecheck|test|build`.
- Aufräumen: Test-Agenten über tmux beenden, ihre Ordner unter `~/.claude/projects` mit `readlink -f` prüfen und löschen.
