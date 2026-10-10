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
    neu gestartet werden (Gespräch fortsetzen). Sichtbar bleibt er über „Gespräche“.
  - **Gemeinsame Agentenübersicht** (10.10.): Die Agentenseite des Minis listet jeden Rechner mit Überschrift,
    Zustandspunkt und amberfarbenem Trenner, die Karten sind überall die vollen (`HostSessions.vue`). Offen:
    Effort ändern und Neustart auf einem anderen Rechner sind nicht an einem echten Agenten gelaufen (nur Terminal
    starten und beenden); der Sprung der Rechner-Auswahl zum Abschnitt ist nur im Code, nicht an einer scrollenden
    Seite geprüft.
  - **Arbeitsflächen, Notizen und Gespräche-Tab** gehören je Rechner (jede Instanz hat ihren eigenen Zustand);
    Gespräche zeigt AI-Connect ohnehin für alle.
  - **Läuft der Dienst auf Aragon nur, solange WSL läuft:** ist Windows aus oder WSL beendet, steht Aragon als
    „nicht erreichbar“ da. `loginctl enable-linger mp` ist gesetzt (10.10.), der Dienst startet mit der WSL. Ob das
    nach einem Windows-Start ohne SSH-Anmeldung wirklich klappt, ist ungeprüft.

## Dateien-Reiter und Oberfläche

- **Nicht geprüft (10.10.):** das Ziehen eines echten Ordners aus dem Dateimanager des Betriebssystems (Logik nur
  mit künstlichen Einträgen getestet), der Dateien-Reiter mit Auswahl und zwei Ansichten auf dem Handy, ein Upload
  über `/hosts/Aragon/` mit mehreren GB (der Proxy reicht in Stücken durch, nur mit kleinen Mengen getestet).
- **Leere Unterordner** werden beim Ordner-Upload nicht mit übertragen (nur Dateien mit ihrem Pfad).
- **Dienst-Stopp hängt:** `systemctl restart agent-orc@mp.service` wartete 90 s auf offene Browser-Verbindungen und
  endete mit SIGKILL (Unit hat `KillMode=process`); der Aufräumer für verwaiste Tunnel fängt die Folgen ab, die
  Ursache ist offen.
- **„Neue vorlesen (0)“** bleibt bei null als abgedunkeltes Rot stehen (gesperrter roter Knopf); das Häkchen daneben
  wird grau. Ob auch dieser Knopf grau werden soll, ist nicht entschieden.

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
