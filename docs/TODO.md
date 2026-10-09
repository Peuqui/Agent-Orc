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

- **Tab „Gespräche“ mit echtem User-Token testen:** Mitlesen, Senden mit falschem Token (403) und die Ansicht in
  Handybreite sind gegen die echte Bridge geprüft. Offen: eine echte Nachricht als User:Peuqui senden (Token eingeben)
  und sehen, dass sie live im Baum erscheint; Neuverbinden nach einem Neustart der Bridge.

## Sprache am Echo Dot

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
