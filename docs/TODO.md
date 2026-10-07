# Offene Ideen und Aufgaben

Nur was noch aussteht. Erledigtes steht in der Git-Historie.

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
