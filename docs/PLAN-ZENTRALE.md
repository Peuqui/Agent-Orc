# Umbau: eine Zentrale statt einer App je Rechner

Stand 05.11.2026, Branch `zentrale`. Mit Peuqui abgestimmt: Modell B (eine Wahrheit für alles,
was dem Nutzer gehört), Ausfall des Mini per Hand-Umschaltung auf Aragon (späteres Paket).

## Ziel

Der Rechner, bei dem man sich anmeldet (normal der Mini), ist die **Zentrale**: Er liefert die
einzige Oberfläche und hält alles, was dem Nutzer und seinen Geräten gehört. Die anderen Rechner
liefern nur, was an der Maschine hängt. Eine eigene Rollen-Einstellung braucht es nicht: Zentrale
ist, wer die Seite ausliefert. Derselbe Code läuft überall, deshalb kann im Notfall auch Aragon
Zentrale werden.

## Wem was gehört

**Dem Nutzer (immer an der Zentrale, `fromRoot`):** Login, geteilte Einstellungen, Diktat,
Vorlesen (TTS-Suite, Echo), Push-Anmeldungen, Notizbücher und ihre Dateien, Kartenreihenfolge,
Zusatztasten und Terminal-Darstellung, Prompt-Vorlagen, Übergabe-Schalter, Quota, AI-Connect,
Rechnerliste, Arbeitsflächen (siehe Paket 5).

**Dem Rechner (relativ zur Seite, unter `/hosts/<name>/`):** Agenten-Profile, Sitzungen und alles
an ihnen (Antworten, Bilder, Änderungen, Effort, Modell, Warmhalten an/aus, Zeitplan), Terminals,
Dateien und Papierkorb, Gespräche (Claude-Verläufe), Freigaben, Bereich (scope), Verbrauch,
Rundruf an die Agenten des Rechners.

## Pakete

Erledigt auf dem Branch: 1 und 2 (955b372), 3 und 4 (0fea151), 6 (28af9d6). Offen: 5, 7.

1. **Eine Oberfläche:** Die Zentrale liefert unter `/hosts/<name>/` ihre eigene Oberfläche aus und
   reicht nur `api/…` und Websockets an den Rechner weiter. Die Seite eines Rechners ist damit
   der Build der Zentrale; die relative Adressierung (`document.baseURI`) bleibt, wie sie ist.
   Die Versionsprüfung (`checkBuild`) vergleicht nur noch mit der Zentrale.
2. **Nutzer-Aufrufe an die Zentrale:** alle Aufrufe der ersten Liste mit `fromRoot`, ebenso ihre
   Live-Streams (Einstellungen, Rechnerliste schon erledigt in 34162ae; Notizbücher).
3. **Push über die Zentrale:** Jeder Server stellt seine Agenten-Meldungen (Übergabe, fertig,
   nicht zugestellt …) als Live-Stream bereit; die Zentrale liest die Streams der Rechner über
   den Tunnel und schickt sie mit ihren Schlüsseln an die Geräte. Ein Rechner ohne Anmeldungen
   schickt selbst nichts.
4. **Einstellungen, die ein Rechner anwendet** (Warmhalten-Anzahl, Übergabe-Schalter): Die
   Zentrale hält sie und spiegelt sie bei jeder Änderung und wenn ein Rechner online kommt auf
   ihn; der Rechner liest sie wie bisher aus seiner Datei.
5. **Arbeitsflächen rechnerübergreifend:** Eine Spalte trägt neben der Sitzung ihren Rechner;
   Arbeitsflächen liegen nur an der Zentrale. Die vorhandenen Arbeitsflächen von Aragon werden
   von Hand übernommen.
6. **Mehrere Wege zu einem Rechner:** `hosts.<name>.ssh` wird eine Liste von Zielen (Kabel
   `10.0.0.2`, Heimnetz), der Tunnel nimmt das erste, das antwortet, und versucht beim Abbruch
   die anderen.
7. **Später: Reserve.** Die Zentrale spiegelt die Nutzerdaten auf die Rechner; Anleitung
   „Aragon zur Zentrale machen“. Zugang von außen zu Aragon klärt Peuqui.

## Offen

- Paket 5 ist eine neue Fähigkeit (Agenten verschiedener Rechner nebeneinander); Peuqui fragen,
  ob er das so will oder Arbeitsflächen je Rechner bleiben sollen (dann an der Zentrale, aber je
  Rechner getrennt).
- Meldungen eines Rechners, während die Zentrale ihn nicht erreicht, gehen verloren (kein
  Nachholen) — reicht das?
