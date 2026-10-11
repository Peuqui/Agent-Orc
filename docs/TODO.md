# Offene Ideen und Aufgaben

Nur was noch aussteht. Erledigtes steht in der Git-Historie.

## Mehrere Rechner

- **Weitere Rechner und Feinschliff der Anbindung** (Stand 10.10.): Aragon ist angebunden. Jeder Rechner hat eine
  eigene Instanz auf einem Socket (kein Login, Ordner 0700), der Mini hält je Rechner einen SSH-Tunnel
  (`hosts` in der Konfiguration, baut sich nach Abbruch selbst neu auf) und reicht dessen App unter `/hosts/<Name>/`
  durch; Updates per `deploy/deploy.sh`. Geprüft über die Oberfläche: Rechner-Wahl in der Kopfzeile, Agentenliste je
  Rechner, Terminal und Agent auf Aragon starten und beenden; Verbrauch über alle Rechner zusammen, Startverzeichnis je
  Rechner in den Einstellungen, Entsperren ohne Passwortfrage auf Rechnern ohne Login. Offen:
  - **Aragons Agent in VS Code** steckt nicht in tmux und lässt sich nicht übernehmen; er muss einmal von Agent-Orc
    neu gestartet werden (Gespräch fortsetzen). Sichtbar bleibt er über „Gespräche“. Peuqui nutzt VS Code nur noch
    selten (Dateioperationen, Überblick am PC), der Rest läuft über Agent-Orc.
  - **Gemeinsame Agentenübersicht** (10.10.): Die Agentenseite des Minis listet jeden Rechner mit Überschrift,
    Zustandspunkt und amberfarbenem Trenner, die Karten sind überall die vollen (`HostSessions.vue`). Offen:
    Effort ändern und Neustart auf einem anderen Rechner sind nicht an einem echten Agenten gelaufen (nur Terminal
    starten und beenden); der Sprung der Rechner-Auswahl zum Abschnitt ist nur im Code, nicht an einer scrollenden
    Seite geprüft.
  - **Arbeitsflächen, Notizen und Gespräche-Tab** gehören je Rechner (jede Instanz hat ihren eigenen Zustand);
    Gespräche zeigt AI-Connect ohnehin für alle.
  - **Läuft der Dienst auf Aragon nur, solange WSL läuft:** ist Windows aus oder WSL beendet, steht Aragon als
    „nicht erreichbar“ da. `loginctl enable-linger mp` ist gesetzt (10.10.), der Dienst startet mit der WSL.
    **Behoben, Dauertest steht aus (11.10.):** Nach einem Start der WSL ohne Windows-Anmeldung war `systemctl --user` per SSH
    unerreichbar („Failed to connect to bus“): `/run/user/1000` ist doppelt eingehängt, unten das Runtime-Dir von systemd,
    darüber das von WSLg (nach dem Start von `user@1000`, `Aragon:Projekte` fand es über `/proc/301/mountinfo`), das es
    verdeckt. Ein einmaliges `wsl -d Ubuntu-24.04 -u root -- systemctl restart user@1000` (Administrator-Shell) legt die
    Sockets in die sichtbare Schicht, beide Verzeichnisse liegen dann nebeneinander (geprüft: `bus`, `systemd` neben
    `wayland-0`, `pulse`), WSLg bleibt. Dauerhaft: `D:\Archiv\VM\Start-WSL.vbs` (Sicherung `.bak`) ruft nach dem Start
    `D:\Archiv\VM\wsl-user-bus-fix.sh` als root auf (wartet auf die zweite Schicht, startet `user@1000` nur neu, wenn der
    Bus verdeckt ist, Protokoll `/var/log/wsl-user-bus-fix.log`). Offen: nach `wsl --shutdown` und Start über das VBS prüfen,
    dass `systemctl --user` ohne weiteres Zutun geht; erst danach gilt es als erledigt. Der Neustart kostet beim Start nichts
    (kein Agent läuft), später würde er laufende Agenten beenden (das Skript tut es nur bei verdecktem Bus).

## Dateien-Reiter und Oberfläche

- **Nicht geprüft:** der Dateien-Reiter mit Auswahl und zwei Ansichten auf dem Handy und ein Upload über
  `/hosts/Aragon/` mit mehreren GB (der Proxy reicht in Stücken durch). Geprüft (11.10.): Ordner aus dem
  Dateimanager des Betriebssystems ziehen, mehrere hundert MB in vielen Dateien.

- **Leere Unterordner:** Beim Ziehen eines Ordners werden sie jetzt mit übertragen. Über „Ordner hochladen“
  (Dateiauswahl des Browsers) nicht: der Browser liefert dort nur Dateien, keine leeren Ordner.
- **Tastatur im normalen Terminal am Handy** (11.10.): Der Tastaturknopf öffnet die Tastatur für das Terminal selbst; Schreiben,
  Verlauf (Pfeil hoch) und Gboard-Diktat gehen direkt. Bekannt: Tippt man einen **Wortvorschlag** der Gboard-Leiste an, entstehen
  doppelte Zeichen und Worte (die Tastatur ersetzt das eben geschriebene Wort, xterm.js sieht Löschen und Einfügen); ohne die
  Vorschläge anzutippen läuft alles. Von der Seite aus nicht abschaltbar (xterm setzt `autocorrect`, `autocapitalize` und
  `spellcheck` schon aus). Offen: ob ein Hinweis in der Hilfe reicht.

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
