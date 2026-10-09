# Offene Ideen und Aufgaben

Nur was noch aussteht. Erledigtes steht in der Git-Historie.

## Eingabefeld und Oberfläche

- **Feld unten abgeschnitten (Handy, Arbeitsfläche):** Mit langem Text (nach dem Wiederherstellen des Entwurfs oder
  beim Diktieren) ragt das Eingabefeld über den unteren Bildschirmrand, der Überstand wird abgeschnitten (Screenshot
  vom 8.10., 08:35). Der Body der Vollbild-Seiten ist fest und clippt (`9e5d071`), deshalb ist nichts scrollbar.
  Welches Element zu hoch ist (Iframe der Spalte, Terminalbereich oder Feld mit `max-h-[40dvh]`), ist nicht
  gemessen: in einer Testinstanz mit Handygröße Höhen auslesen.
- **Langer Text wird eingetippt, aber nicht abgeschickt (Verdacht, aus dem Code gelesen, nicht reproduziert):**
  `submitText` in `TerminalView.vue` schickt den Text und danach nach `submit_delay_ms` (80 ms, im Browser) ein
  `\r`. Der Server tippt den Text in Stücken zu 200 Zeichen mit 30 ms Pause (`terminal.py`, `pump_input`) und
  verarbeitet die Nachrichten nacheinander. Bei langem Text dauert das Tippen länger als die 80 ms, das `\r`
  kommt dann ohne Pause direkt hinter dem letzten Stück an, und Claude Code nimmt es als Teil der Eingabe (neue
  Zeile statt Absenden). Auf dem Screenshot vom 8.10., 09:05, steht der Text unabgeschickt im Eingabefeld von
  Claude Code, der Cursor in einer neuen Zeile. Lösungsrichtung: eine Nachrichtenart „submit“ im Terminal-Kanal,
  bei der der Server den Text tippt, `submit_delay_ms` wartet und dann das `\r` schickt (wie `type_line` in
  `sessions.py`, gemeinsame Tipp-Funktion statt zweiter Kopie).
- **Neu laden in der App:** Seit `9e5d071` geht das Herunterziehen auf Vollbild-Seiten nicht mehr. Ein Eintrag
  „Neu laden“ im ☰-Menü, der `reloadToNewVersion()` aus `update.ts` aufruft.

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

- **Diktat sofort senden (Peuqui, 9.10.):** Schalter pro Gerät, die Aufnahme geht nach der Transkription direkt an den Agenten
  (wie „Direkt senden“ in AIfred). Details im Plan für Freitag, Abschnitt 4, Punkt 8. Erst nach der Reparatur des Absendens.

- **Antworten-Ansicht am Handy scrollt seitlich (Peuqui, 9.10., Screenshot 13:20):** In der einspaltigen Handy-Arbeitsfläche lassen
  sich die Sprechblasen innerhalb der Spalte horizontal hin- und herschieben und rutschen am linken Rand heraus (Texte
  beginnen mitten im Wort, rechts bleibt Platz bis zum Griff). Kopfzeile und Umschalter bleiben stehen, es verschiebt sich
  nur der Inhalt der Liste. Vermutete Ursache (aus dem Code, nicht gemessen): Der Container in `AnswersFeed.vue`
  (Zeile 204, `ref="box"`) hat nur `overflow-y-auto`; dann wird `overflow-x` automatisch ebenfalls `auto`, und jedes
  zu breite Element in irgendeiner Blase macht die ganze Liste seitlich scrollbar. Zu klären: welches Element zu
  breit ist (lange Pfade oder Adressen im Text, Tabelle, Code), und ob es mit dem seitlichen Wischen zwischen den
  Spalten zusammenhängt. Lösungsrichtung: `overflow-x-hidden` auf dem Container und das zu breite Element umbrechen oder
  in seiner Blase scrollen lassen. Gehört zum Schritt zurück beim Vollbild-Layout (Plan Punkt 1a).

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
