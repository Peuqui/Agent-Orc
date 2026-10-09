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

- **Arbeitsfläche: verschobene Spalte bleibt im Blick (Peuqui, 8.10.):** Hat die Arbeitsfläche mehr Spalten als
  auf den Bildschirm passen (zum Beispiel drei Terminals, zwei sichtbar) und man zieht eine Spalte per Tab an eine
  andere Position (etwa von ganz rechts nach ganz links), verschwindet sie aus dem Sichtfeld, weil die Leiste
  horizontal nicht mitscrollt. Man muss von Hand zurückscrollen und sucht sie erst. Gewollt: Die verschobene
  (aktive) Spalte zieht das horizontale Scrollen mit, sodass sie sichtbar bleibt. Gehört zum Aufspalten von
  `WorkspaceView.vue` (Sortieren und Ziehen, Spaltenraster), dort mit bauen statt vorher flicken.

- **Gelesen-Stand der Antworten auf dem Server (Peuqui, 8.10.):** Heute liegt er pro Gerät im `localStorage`
  (`composables/useAnswerSeen.ts`, pro Agent die Zeit der neuesten gesehenen Antwort). Wer zwischen Desktop, Handy
  und Tablet wechselt, sieht überall alles wieder als ungelesen. Lösung im vorhandenen Muster (wie
  `card-order.json`, `prompt-templates.json` in `state.py`): Server speichert pro Agent „gesehen bis“, zwei
  Endpunkte, der Wert steigt nur (Maximum). Kein Rückfall auf `localStorage`, keine Übernahme alter Werte (einmalig
  alles ungelesen). Betrifft `AnswersFeed.vue`, `WorkspaceView.vue`. Peuqui hat den Satz nicht zu Ende gesprochen
  („Auch könnte man ja …“): nachfragen, was noch gemeint war.
  Dazu (Peuqui, 8.10.): Knopf „Alle als gelesen“ mit Häkchen neben „Neue vorlesen (n)“ in `AnswersFeed.vue`, nur
  sichtbar bei n > 0, setzt „gesehen bis“ des Agenten dieser Spalte auf die Zeit der neuesten Antwort (`markSeen`).
  Der Hilfetext (`locales/de.json`, „ein Knopf zum Markieren ist nicht nötig“) muss dann angepasst werden.

## AI-Connect

- **Mitlesen für den User (Peuqui, 8.10., ab Freitag):** Datenverkehr der Bridge live und rückwirkend ansehen, sortiert
  nach „wer redet mit wem“ (Baumdarstellung oder Ähnliches), als eigenes Programm im Terminal und per Knopf in
  Agent-Orc als eigene Ansicht. Die Bridge hat dafür noch keine Funktion (Wächter und Verlauf nur pro Name):
  nur lesende Nachrichtenart „observe“ und Verlauf über alle Paare in der Bridge, ein gemeinsamer Client für beide
  Oberflächen. Anfrage an `Mini:AI-Connect` am 8.10. Details im Plan für Freitag, Abschnitt 4, Punkt 3.

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
