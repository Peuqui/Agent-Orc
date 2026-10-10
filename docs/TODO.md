# Offene Ideen und Aufgaben

Nur was noch aussteht. Erledigtes steht in der Git-Historie.

## Eingabefeld und Oberfläche

- **Wackelnder Test:** `test_restart_resumes_a_busy_agent_with_its_waiting_effort` schlägt etwa in jedem zehnten vollen
  Lauf fehl (am 9.10. abends in Lauf 2 gefangen). Meldung: `concurrent.futures.CancelledError` beim Verlassen von
  `client.websocket_connect(...)` (`tests/test_api.py:779`, Starlette `TestClient.__exit__`), also beim Aufräumen der
  Test-Websocket nach dem Neustart, nicht in Agent-Orc selbst. Niedrige Priorität; eine Lösung wäre, die Websocket vor
  dem Neustart zu schließen oder den Neustart-Fall ohne Test-Websocket zu prüfen.

## Mehrere Rechner

- **Weitere Rechner und Feinschliff der Anbindung** (Stand 10.10.): Aragon ist angebunden. Jeder Rechner hat eine
  eigene Instanz auf einem Socket (kein Login, Ordner 0700), der Mini hält je Rechner einen SSH-Tunnel
  (`hosts` in der Konfiguration, baut sich nach Abbruch selbst neu auf) und reicht dessen App unter `/hosts/<Name>/`
  durch; Updates per `deploy/deploy.sh`. Geprüft über die Oberfläche: Rechner-Wahl in der Kopfzeile, Agentenliste je
  Rechner, Terminal und Agent auf Aragon starten und beenden. Offen:
  - **Aragons Agent in VS Code** steckt nicht in tmux und lässt sich nicht übernehmen; er muss einmal von Agent-Orc
    neu gestartet werden (Gespräch fortsetzen). Sichtbar bleibt er über „Gespräche“.
  - **Datei-Entsperrung** fragt auf einem Rechner ohne Login trotzdem nach einem Passwort (jede Eingabe gilt, der
    SSH-Schlüssel ist die Anmeldung). Die Oberfläche sollte die Frage dort weglassen.
  - **Agentenliste anderer Rechner** ist schreibgeschützt (Name, Zustand, Modell, Kontext); gesteuert wird in der App
    des Rechners („Öffnen“ oder die Wahl in der Kopfzeile). Volle Karten mit allen Knöpfen in einer Liste hieße, jeden
    Aufruf der Oberfläche um den Rechner zu erweitern.
  - **Arbeitsflächen, Notizen und Gespräche-Tab** gehören je Rechner (jede Instanz hat ihren eigenen Zustand);
    Gespräche zeigt AI-Connect ohnehin für alle.
  - **Läuft der Dienst auf Aragon nur, solange WSL läuft** (User-Dienst ohne Linger): ist Windows aus oder WSL
    beendet, steht Aragon als „nicht erreichbar“ da.

## AI-Connect

- **Tab „Gespräche“ nach einem Neustart der Bridge:** Mitlesen, Senden als User:Peuqui (Enter) und die Ansicht sind
  im echten Betrieb geprüft (9.10. abends). Offen: ob sich eine offene Seite nach einem Neustart der Bridge von selbst
  neu verbindet und den Verlauf wieder zeigt.

## Sprache am Echo Dot

- **Double Metaphone** (englische Phonetik) als Ergänzung oder Ersatz der Kölner Phonetik in
  `phonetics.py`, falls englische Agentennamen oft falsch erkannt werden. Zurückgestellt (Peuqui, 9.10.): erst die
  deutsche Erkennung im Alltag testen, die Fälle sammelt das Sprachprotokoll. Braucht ein Paket (nur nach Rückfrage)
  oder viel eigenen Code.
- **Automatische Ansage auch ohne Sprach-Auftrag:** Heute meldet sich ein Agent am Echo nur, wenn
  der Auftrag per Sprache kam (Peuqui will es ausdrücklich nur so, der Kanal bleibt derselbe).
