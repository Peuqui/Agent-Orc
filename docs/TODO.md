# Offene Ideen und Aufgaben

Nur was noch aussteht. Erledigtes steht in der Git-Historie.

## Eingabefeld und Oberfläche

- **Am Handy prüfen (Umbau vom 9.10.):** Höhe der Vollbild-Seiten aus dem festen Body statt `h-dvh`, Eingabefeld mit
  `field-sizing: content` und Obergrenze 40 % der Ansicht (`cqh`), Absenden über `POST /api/sessions/{id}/message`,
  Umbruch langer Pfade in den Antworten, „App neu laden“ und „Diktat sofort senden“ im ☰-Menü. In der Emulation
  gemessen, auf dem echten Android nicht: langes Diktat in einer Arbeitsflächen-Spalte (Tastenleiste bleibt sichtbar),
  Arbeitsfläche wechseln und zurück (Feld behält die Höhe), langer Text wird abgeschickt.
- **Wackelnder Test:** `test_restart_resumes_a_busy_agent_with_its_waiting_effort` schlug am 9.10. in einem von neun
  vollen Läufen fehl (einzeln 25-mal grün). Fehlermeldung beim nächsten Auftreten festhalten.

## AI-Connect

- **Mitlesen und Mitdiskutieren (Tab „Gespräche“ rechts neben „Arbeitsfläche“):** Bridge-Seite ist fertig
  (`observer_client/` mit `ObserverConnection`, `UserConnection`, `TokenRefused`; Bridge am 9.10. neu gestartet,
  Beobachter-Token angenommen). Agent-Orc soll den Client über eine Prozessgrenze nutzen (Befehl in der Konfiguration,
  JSON-Zeilen), nicht per Import: Anfrage an `Mini:AI-Connect` am 9.10., 18:21, nach `observe-jsonl` und `send-json`
  im `observer_client.cli`; Antwort steht aus. User-Name in die Agent-Orc-Konfiguration, User-Token gibt Peuqui im
  Browser ein (pro Gerät), der Server reicht es nur durch.
- **Kontingent je Anbieter:** heute nur Claude (`QUOTA_SOURCES` in `context.py`). Für Codex, DashScope usw. erst
  klären, woher sie ihre Grenzen melden; lokale Modelle zeigen nichts.

## Sprache am Echo Dot

- **Antwort zurück an den Echo:** Hat ein Auftrag per Sprache einen Agenten angestoßen, soll sein
  Hörabsatz nach der Antwort in denselben Raum angesagt werden. Ansatz: der Stop-Hook
  (`agent-idle` in `cli.py`) ist ein eigener Prozess, der Raum muss also über eine Markierungsdatei
  vom Server zum Hook kommen.
- **Aufzeichnen, was verstanden wurde:** Erkannter Text, gewählter Agent und Ähnlichkeitswert ins
  Log, damit die Namenserkennung an echten Fällen gemessen werden kann (zum Beispiel „Vispa“ statt
  „Whisper“).
- **Double Metaphone** (englische Phonetik) als Ergänzung oder Ersatz der Kölner Phonetik in
  `phonetics.py`, falls englische Agentennamen oft falsch erkannt werden. Braucht ein Paket (nur
  nach Rückfrage) oder viel eigenen Code, deshalb erst nach den gemessenen Fällen.
- **Folgeaufnahme ohne Wake-Word (Weg B2):** Der Puck hört nach der Rückfrage kurz zu, ein
  Flag `expect_reply` in der Ansage. Braucht Firmware und AIfred, nur falls „Sag Hey Orc, ja oder
  nein“ im Alltag nervt.
- **Automatische Ansage auch ohne Sprach-Auftrag:** Heute meldet sich ein Agent am Echo nur, wenn
  der Auftrag per Sprache kam (Peuqui will es ausdrücklich nur so, der Kanal bleibt derselbe).
- **Aufnahmen alter Äußerungen:** Rotation nach Anzahl (`keep_entries`) und Löschen mit dem
  gestoppten Agenten gibt es; eine Aufbewahrung nach Alter wäre eine Ergänzung.
