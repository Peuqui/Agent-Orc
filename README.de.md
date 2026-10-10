<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="frontend/brand/logo.svg">
    <img src="frontend/brand/logo-light.svg" alt="Agent-Ørc — Agent Orchestrator" width="440">
  </picture>
</p>

[English](README.md)

> **Status: früh, aber im täglichen Einsatz.** Getestet unter Linux mit Claude Code; die
> Profile für Codex und Aider sind vorbereitet, aber ungetestet.

Agent-Orc startet, beobachtet und beendet Coding-Agenten (Claude Code, Codex, Aider, …) auf dem
eigenen Linux-Rechner, bedient über eine Web-App, die am Handy genauso funktioniert wie am
Rechner (PWA).

Jeder Agent läuft in einer eigenen `tmux`-Sitzung in einem Projektordner. Wer den Browser
schließt, trennt nur die Verbindung: Die Agenten arbeiten weiter und lassen sich von jedem Gerät
aus wieder aufnehmen. Weitere Rechner mit Agent-Orc lassen sich in derselben App zeigen, über
einen SSH-Tunnel ([Mehrere Rechner](#mehrere-rechner)).

<p align="center">
  <img src="docs/screenshots/overview-de.png" alt="Übersicht: Agentenkarten mit Kontext-Ring, Effort-Regler und Claude-Kontingent" width="860">
</p>

## Was es kann

**Agenten**
- Ordner wählen und mit einem Tipp einen Agenten starten; beenden, fortsetzen oder ein
  früheres Claude-Gespräch dieses Ordners wieder aufnehmen.
- Jede Karte zeigt das Modell des Agenten, wie voll sein Kontext ist (Ring: grün, gelb, rot ab
  70 %), ob er gerade arbeitet, und den Denkaufwand als Regler mit Ultracode-Schalter (Claude,
  pro Projektordner).
- Oben das 5-Stunden- und Wochen-Kontingent von Claude; die Karten lassen sich in die eigene
  Reihenfolge ziehen.
- Was ein Agent im Projekt geändert hat: geänderte, neue und gelöschte Dateien mit ihrem Diff
  (git).
- Token-Verbrauch aller Claude-Gespräche pro Tag, Projekt und Modell; Suche in früheren
  Gesprächen; eine Übergabe-Empfehlung, sobald der Kontext eines Agenten groß wird.
- Benachrichtigungen aufs Handy oder den Rechner, wenn ein Agent fertig ist oder auf eine
  Freigabe oder Antwort wartet (Web Push, pro Gerät einschaltbar); Antippen öffnet den Agenten.
- Der Freigabe-Modus, in dem ein Agent startet, pro Projekt (Fragen, Bearbeiten, Auto, Planen;
  Voreinstellung Auto). Fragt ein Agent um Erlaubnis, zeigt seine Karte den Befehl mit
  „Erlauben“ und „Ablehnen“; es gilt die Antwort, die zuerst kommt, auf der Karte oder im
  Terminal.
- Profile mit Modellwahl: Über ein kleines Startskript läuft Claude Code auch mit lokalen
  Modellen (z. B. vLLM oder llama-swap) oder bei anderen Anbietern. Der Startdialog bietet dann
  die Modelle und ihre Denkstufen an, mit einem Hinweis je Modell (etwa wie lange es frei
  nutzbar ist); ein Beispiel steht in den Kommentaren der Standard-Config.
- Ein Agent kann in einem eigenen Git-Worktree starten (zweite Arbeitskopie auf einem neuen
  Branch), damit zwei Agenten an einem Projekt arbeiten können; danach wird er wieder
  entfernt, ohne Arbeit zu verlieren.
- Neu starten (⟳) mit fortgesetztem Gespräch, Prompts für später planen, und nach dem
  Nutzungslimit automatisch weitermachen, sobald das Kontingent zurückgesetzt ist.
- Denselben Prompt an mehrere Agenten auf einmal schicken, abgeschickt oder nur ins Eingabefeld gelegt.
- Jede Karte hat ein Feld für die Arbeitsfläche: Ein Agent kommt in die beim Start gewählte
  Fläche und lässt sich später in eine andere verschieben; ohne Fläche steht er in „Unbenannt“.
  Hat ein Agent noch kein gespeichertes Modell, fragt Agent-Orc beim Neustart und Fortsetzen danach.
- Ein normales Terminal im Projektordner („>_“), auch neben dem laufenden Agenten.

**Arbeitsflächen**
- Mehrere Agenten als Spalten nebeneinander; Spaltenköpfe ziehen sortiert, die Trenner ziehen
  ändert die Breite.
- Arbeitsflächen liegen auf dem Server: Jedes Gerät zeigt dasselbe, und eine Änderung erscheint
  sofort überall. „Unbenannt“ steht da, solange es noch keine Fläche gibt, und das „+“ in der Leiste beginnt
  eine neue; mit einem Namen wird sie zu einer benannten, die in der Übersicht und in der Leiste jeder Arbeitsfläche erscheint. Ein Agent
  steht in genau einer Fläche: Fügt man ihn in einer anderen hinzu, wandert er. Ein Klick
  springt in den Tab, der eine Fläche zeigt – praktisch, um Arbeitsflächen auf mehrere Monitore
  zu verteilen. Am Handy wechselt die Leiste im selben Fenster.
- Einen Spaltenkopf auf den Namen einer anderen Fläche in der Leiste fallen lassen verschiebt den
  Agenten dorthin; ein Knopf neben der Spaltenzahl setzt alle verstellten Breiten zurück.
- Tastenkürzel am Rechner: Alt+Umschalt+1 … 9 für die Spalten, Alt+Umschalt+← / → für die
  Arbeitsflächen.
- Am Handy eine Spalte auf einmal: seitlich im Terminal wischen holt die nächste; ein Vollbild
  zeigt nur Terminal und Eingabefeld, die Sondertasten lassen sich einklappen, und die Aktionen
  eines Terminals liegen hinter ⋮.

<p align="center">
  <img src="docs/screenshots/workspace-de.png" alt="Arbeitsfläche mit einem Agenten und seinem Terminal nebeneinander" width="860">
</p>

**Antworten**
- Ein Umschalter in jedem Terminal zeigt nur das, was der Agent geantwortet hat (pro Anfrage
  der letzte Text, auf Wunsch jeder), statt des Terminals mit Gedanken und Diffs; was du
  während einer Antwort getippt hast, und seine Bilder erscheinen auch.
- Vorlesen mit den Stimmen des Browsers (eine Antwort, ab hier oder alle neuen; Code und
  Tabellen werden ausgelassen). Die Sprachausgabe ist eine Liste von Engines: mit einem Abschnitt
  `announce:` in der Konfiguration lässt sich der Hörabsatz auch über
  [AIfred](https://github.com/Peuqui/AIfred-Intelligence) auf einem Echo Dot ansagen, im Raum, den
  du in den Einstellungen wählst.

**Gespräche** (mit [AI-Connect](https://github.com/Peuqui/AI-Connect), der Brücke, über die Agenten-Sitzungen miteinander sprechen; optional)
- Live mitlesen: nach Gespräch (als Baum), als Verlauf oder als Spuren (Sequenzdiagramm mit einem
  Pfeil je Nachricht); dazu die Agenten, die online sind, mit ihrem Zustand (arbeitet, wartet,
  bereit).
- Eingeschaltet durch den Abschnitt `peers:` der Config; AI-Connect hält seine Tokens in eigenen
  Dateien.
- An einen, mehrere oder alle schreiben, als du selbst; Enter sendet, Shift+Enter macht eine neue
  Zeile. In einem aufgeklappten Gespräch antwortet das Feld darunter allen darin.

**Mehrere Rechner**
- Ein weiterer Rechner mit eigenem Agent-Orc (ein zweiter PC, ein WSL unter Windows, ein Server)
  erscheint in derselben App: eine Rechner-Auswahl in der Kopfzeile und seine Agenten unter
  deinen eigenen auf der Übersicht. Seine Terminals, Arbeitsflächen, Notizen und Dateien gehören
  dem Rechner und öffnen sich wie in jeder App.
- Ein Login, eine Adresse: Der andere Rechner hat weder einen Port noch ein Passwort, dein
  SSH-Schlüssel ist der Weg hinein.

**Notizen**
- Notizbücher als Reiter, je mit losen Notizen und Ordnern; sie liegen wie die Arbeitsflächen auf dem Server.
- Eine Notiz ist Markdown mit Formatierungsleiste (fett, kursiv, Überschrift, Liste, Code, Link),
  einer Suche über Titel und Text und Text und Ansicht nebeneinander am Rechner und Tablet.
- Fotos, Screenshots und Dateien an eine Notiz hängen; sie liegen auf dem Server und werden beim
  Senden an einen Agenten in dessen Ordner kopiert. Bilder erscheinen als Vorschau, PDFs mit der
  ersten Seite (auf Wunsch alle, gezeichnet von [pdf.js](https://mozilla.github.io/pdf.js/)).
- Per Diktat (Whisper) schreiben, eine Notiz kopieren oder ins Eingabefeld eines oder mehrerer Agenten legen (auf Wunsch abgeschickt).

**Terminal**
- Ein normales Eingabefeld unter dem Terminal, damit Handytastatur, Autokorrektur und Diktat
  funktionieren; Enter sendet, Shift+Enter macht eine neue Zeile.
- Diktat über einen lokalen Whisper-Dienst ([whisper-stt](https://github.com/Peuqui/whisper-stt),
  GPU oder CPU, Engine pro Gerät wählbar, z. B. Parakeet oder Whisper) oder die
  Spracherkennung des Browsers.
- Prompt-Vorlagen für häufige Anweisungen, mit einem Tipp im Eingabefeld.
- Foto, Screenshot (aus der Galerie, am Rechner direkt vom Bildschirm oder einfach mit Strg+V
  eingefügt) oder Datei anhängen: Sie landen im Projektordner, erscheinen als kleine Vorschau
  über dem Eingabefeld und gehen mit der nächsten Nachricht an den Agenten.
- Sondertasten-Leiste (Esc, Tab, Shift+Tab, Pfeile, einrastendes Strg/Alt, …) für die
  Bildschirmtastatur, frei anpassbar und mit Text-Tasten (Makros); ein Griff zum schnellen
  Scrollen, eine Schriftgröße pro Gerät, eine Textansicht zum Markieren und Kopieren,
  anklickbare Links.

**Dateien und mehr**
- Dateien in den Projektordnern durchsuchen, bearbeiten und in den Papierkorb legen (er steht
  neben der Liste: Datei darauf ziehen, dort wiederherstellen oder leeren);
  Markdown als Vorschau, Bilder als Bild, andere Dateien zum Herunterladen.
- Dateipfade in der Ausgabe eines Agenten sind anklickbar und öffnen die Datei (an der
  genannten Zeile) oder den Ordner.
- Einstellungen pro Gerät (Schrift, Größe, Zeilenabstand, Scrollgeschwindigkeit) und eine Hilfe
  (Glühbirne).
- Claude-Code-Sitzungen starten mit Remote Control und erscheinen dadurch auch in der Claude-App.

<p align="center">
  <img src="docs/screenshots/phone-overview-de.png" alt="Übersicht am Handy" width="280">
  &nbsp;&nbsp;
  <img src="docs/screenshots/phone-terminal-de.png" alt="Terminal am Handy mit Eingabefeld und Sondertasten" width="280">
</p>

## Voraussetzungen

- Linux mit `git` und `tmux`
- Python 3.12 oder neuer, mit dem Modul `venv` (Debian/Ubuntu: `apt install python3-venv`)
- Node.js 20.19+ oder 22.12+ mit npm (baut bei der Installation die Web-App; das `nodejs`-Paket
  von Ubuntu ist zu alt, siehe unten)
- die gewünschten Agenten-CLIs, z. B. [Claude Code](https://docs.claude.com/en/docs/claude-code)
- optional, fürs Diktat: [whisper-stt](https://github.com/Peuqui/whisper-stt) (lokale
  Spracherkennung)
- optional, für mehrere Rechner: `ssh` mit Schlüssel-Login auf jeden davon

Die Installation wurde auf frischen Systemen ausprobiert, jeweils wie ein Fremder sie macht:

- **Debian 13** geht mit den eigenen Paketen: `sudo apt-get install -y git tmux python3-venv nodejs npm`
  (Python 3.13, Node.js 20.19).
- **Fedora 43** geht mit den eigenen Paketen: `sudo dnf install -y git tmux python3 nodejs npm`
  (Python 3.14, Node.js 22).
- **Ubuntu 24.04** hat Python 3.12, aber sein Paket `nodejs` ist Node 18 und für den Bau zu alt. Ein
  aktuelles Node.js kommt von NodeSource:

  ```bash
  sudo apt-get install -y git tmux python3-venv curl ca-certificates
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
  ```

- **Debian 12 und Ubuntu 22.04** sind zu alt (Python 3.11 / 3.10, Node 18): Der Installer sagt es und
  bricht ab; ein neueres Python muss von anderswo kommen.

`deploy/install.sh` prüft zuerst die Versionen von Node.js und Python und nennt, was fehlt.

## Installation

```bash
git clone https://github.com/Peuqui/Agent-Orc.git && cd Agent-Orc
deploy/install.sh          # baut die Web-App, installiert nach ~/.local/share/agent-orc/venv
agent-orc setup            # stellt ein paar Fragen, schreibt Config und Passwort
agent-orc serve            # http://127.0.0.1:8770
```

`deploy/install.sh` verlinkt den Befehl `agent-orc` nach `~/.local/bin`; dieser Ordner muss im
`PATH` liegen.

`agent-orc setup` prüft, ob `tmux` und `git` da sind und welche Agenten-CLIs es findet, und
fragt dann nach:

- dem Ordner mit deinen Projekten (wird angelegt, falls es ihn nicht gibt),
- ob ein anderes Agent-Orc diesen Rechner über SSH steuert (dann lauscht er auf einem Socket und
  verlangt kein Passwort, siehe [Mehrere Rechner](#mehrere-rechner)); wenn nicht, ob er hinter
  HTTPS läuft oder für einen ersten lokalen Test über einfaches HTTP,
- einem Whisper-Dienst fürs Diktat, falls du einen betreibst (es prüft, ob er antwortet); ohne
  ihn nutzt das Mikrofon die Spracherkennung des Browsers (Chrome),
- deiner E-Mail-Adresse für die Push-Dienste, die Benachrichtigungen zustellen (optional),
- dem Passwort für die Web-App.

Es schreibt `~/.config/agent-orc/config.yaml`: die mitgelieferte Standard-Config mit deinen
Antworten; ihre Kommentare erklären alle übrigen Einstellungen. `agent-orc set-password` ändert
das Passwort später.

Danach `http://127.0.0.1:8770` öffnen und mit dem Passwort anmelden.

### Aktualisieren

```bash
git pull && deploy/install.sh
```

Das Skript installiert nur committeten Code und startet einen laufenden Dienst
`agent-orc@<user>` neu; dafür braucht der Benutzer das Recht, ihn neu zu starten (z. B. per
polkit-Regel), sonst den Dienst selbst neu starten. Laufende Agenten überstehen den Neustart.

### Als Dienst

`deploy/agent-orc@.service` betreibt Agent-Orc für einen Benutzer (`agent-orc` muss in dessen
`PATH` liegen):

```bash
sudo cp deploy/agent-orc@.service /etc/systemd/system/
sudo systemctl enable --now agent-orc@$USER
```

### Hinter nginx

`deploy/nginx-location.conf` stellt Agent-Orc unter `/agent-orc/` in einem HTTPS-Serverblock
bereit, samt Terminal-WebSocket. Hinter HTTPS lässt sich die App auf dem Handy-Startbildschirm
installieren.

### Mehrere Rechner

Jeder Rechner betreibt ein eigenes Agent-Orc; das, das du im Browser öffnest (der Hauptrechner),
zeigt die anderen. Auf den anderen wird nichts aus dem Quellcode installiert: Der Hauptrechner
baut die Web-App und liefert sie per SSH aus. Der andere Rechner braucht `python3` (3.12+, mit
`venv`), `tmux`, `git`, die dort gewünschten Agenten-CLIs und einen SSH-Login mit Schlüssel (kein
Passwort).

```bash
# 1. Auf dem Hauptrechner: das Programm zum anderen schicken (ssh-Optionen wie bei ssh).
deploy/deploy.sh -p 2222 ich@anderer-rechner
# 2. Einmal auf dem anderen Rechner: die Frage nach einem anderen Agent-Orc mit „ja“ beantworten.
ssh -t -p 2222 ich@anderer-rechner agent-orc setup
# 3. Nochmal: jetzt findet es eine Config und startet den Dienst (ein systemd-Benutzerdienst).
deploy/deploy.sh -p 2222 ich@anderer-rechner
```

Danach den Rechner in der `~/.config/agent-orc/config.yaml` des Hauptrechners benennen und diesen
neu starten (die Kommentare der Config enthalten dasselbe Beispiel):

```yaml
hosts:
  Anderer:
    ssh: ["-p", "2222", "ich@anderer-rechner"]
    socket: /home/ich/.local/state/agent-orc/run/agent-orc.sock   # server.socket des anderen Rechners
```

Der Rechner erscheint dann in der Rechner-Auswahl der Kopfzeile (sie bleibt auf der Seite, auf der
du bist) und unter deinen Agenten auf der Übersicht. Dahinter hält der Hauptrechner einen
SSH-Tunnel zum Socket des anderen offen, baut ihn nach einem Abbruch neu auf und reicht dessen App
unter `/hosts/<Name>/` durch; dein Login dort ist der einzige. Kontingent und Gespräche kommen
immer vom Hauptrechner (ein Konto, ein AI-Connect).

`deploy/deploy.sh` ist zugleich das Update: nach jeder Änderung erneut ausführen (es liefert nur
committeten Code aus, wie `deploy/install.sh`). Die Agenten dort laufen dabei weiter. Der Dienst
endet mit der Benutzersitzung des Rechners; `loginctl enable-linger` (einmal als root) hält ihn auch
ohne Anmeldung am Laufen. Ein Rechner, der aus ist oder dessen Tunnel steht, erscheint als nicht
erreichbar.

### Tipp: neue Agenten sofort loslegen lassen

Ein Claude-Code-Agent wartet auf die erste Nachricht. Sein Startbefehl in der Config nimmt am
Ende eine erste Anfrage an, etwa um die Schritte auszuführen, die deine Hooks verlangen:

```yaml
agents:
  claude:
    start: [claude, --settings, ..., --remote-control, "{name}",
      "Sitzungsbeginn: Führe die Pflichtschritte aus deinem Startkontext aus und melde dich dann in einem Satz bereit."]
```

Beim Fortsetzen wird sie nicht wiederholt.

## Tests

```bash
venv/bin/ruff check . && venv/bin/mypy && venv/bin/python -m pytest   # Backend, mit echtem tmux
cd frontend && npm test                                               # reine Frontend-Logik (Test-Runner von Node)
```

## Sicherheit

Agent-Orc gibt Zugriff auf den Rechner auf Shell-Ebene. Es bringt einen eigenen Login mit und
lauscht nur auf `127.0.0.1`. Ins Internet nur hinter HTTPS stellen, am besten hinter einem
Reverse Proxy mit zusätzlicher Authentifizierung.

Ein von einem anderen Rechner gesteuerter Rechner hat weder Login noch Port: Er lauscht auf einem
Unix-Socket in einem Ordner, den nur sein Benutzer betreten darf (bei jedem Start geprüft), und
hinein kommt, wer sich mit dem Schlüssel per SSH auf diesem Rechner anmelden darf. Den Schlüssel
genauso sorgfältig verwahren wie den Login.

## Lizenz

[MIT](LICENSE)
