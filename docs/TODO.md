# Offene Ideen und Aufgaben

Nur was noch aussteht. Erledigtes steht in der Git-Historie.

## Eingabefeld und Oberfläche

- **Am Handy prüfen (Umbau vom 9.10.):** Höhe der Vollbild-Seiten aus dem festen Body statt `h-dvh`, Eingabefeld mit
  `field-sizing: content` und Obergrenze 40 % der Ansicht (`cqh`), Absenden über `POST /api/sessions/{id}/message`,
  Umbruch langer Pfade in den Antworten, „App neu laden“ und „Diktat sofort senden“ im ☰-Menü. In der Emulation
  gemessen, auf dem echten Android nicht: langes Diktat in einer Arbeitsflächen-Spalte (Tastenleiste bleibt sichtbar),
  Arbeitsfläche wechseln und zurück (Feld behält die Höhe), langer Text wird abgeschickt.
- **Wackelnder Test:** `test_restart_resumes_a_busy_agent_with_its_waiting_effort` schlägt etwa in jedem zehnten vollen
  Lauf fehl (am 9.10. abends in Lauf 2 gefangen). Meldung: `concurrent.futures.CancelledError` beim Verlassen von
  `client.websocket_connect(...)` (`tests/test_api.py:779`, Starlette `TestClient.__exit__`), also beim Aufräumen der
  Test-Websocket nach dem Neustart, nicht in Agent-Orc selbst. Niedrige Priorität; eine Lösung wäre, die Websocket vor
  dem Neustart zu schließen oder den Neustart-Fall ohne Test-Websocket zu prüfen.

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
