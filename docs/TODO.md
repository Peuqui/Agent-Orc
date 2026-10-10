# Offene Ideen und Aufgaben

Nur was noch aussteht. Erledigtes steht in der Git-Historie.

## Eingabefeld und Oberfläche

- **Wackelnder Test:** `test_restart_resumes_a_busy_agent_with_its_waiting_effort` schlägt etwa in jedem zehnten vollen
  Lauf fehl (am 9.10. abends in Lauf 2 gefangen). Meldung: `concurrent.futures.CancelledError` beim Verlassen von
  `client.websocket_connect(...)` (`tests/test_api.py:779`, Starlette `TestClient.__exit__`), also beim Aufräumen der
  Test-Websocket nach dem Neustart, nicht in Agent-Orc selbst. Niedrige Priorität; eine Lösung wäre, die Websocket vor
  dem Neustart zu schließen oder den Neustart-Fall ohne Test-Websocket zu prüfen.

## Mehrere Rechner

- **Aragon (und beliebige weitere Rechner) anbinden:** Jeder Rechner bekommt eine eigene Agent-Orc-Instanz, der Mini
  bündelt sie in einer Oberfläche (Peuqui, 10.10.). Jede Instanz bedient ihre eigene Maschine mit dem vorhandenen Code
  (tmux, Transkripte, Dateien, Änderungen bleiben lokal); der Mini leitet Anfragen per SSH-Tunnel weiter. Aragon ist
  vom Mini über `10.0.0.2:2222` (WSL) per Schlüssel erreichbar. Stand: Wheel liegt in einem venv auf Aragon
  (`~/.local/share/agent-orc/venv`, `agent-orc` in `~/.local/bin`); noch keine Konfiguration, kein Dienst, kein Tunnel.
  Offen: Konfiguration und Passwort auf Aragon, Dienst (systemd-User-Dienst im WSL), Tunnel (z. B. `autossh`-artig als
  Dienst auf dem Mini), Rechner-Ebene in Backend und Oberfläche (Sitzungs-Kennungen mit Rechnername, Auswahl),
  Anmeldung der Instanzen untereinander. Der Agent auf Aragon läuft in VS Code und nicht in tmux; er muss einmal von
  Agent-Orc neu gestartet werden (Gespräch fortsetzen), um verwaltbar zu sein.

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
