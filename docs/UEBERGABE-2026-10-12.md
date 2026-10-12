# Übergabe 12.10.2026

Was heute an Agent-Orc und der TTS-Suite geschah, was gilt und was offen ist. Der Code ist die Wahrheit.

## Agent-Orc

| Was | Wo | Hinweis |
| --- | --- | --- |
| Einstellungen für Diktat und Vorlesen auf dem Server | `shared_settings.py`, `GET/PATCH /api/settings`, `/api/settings/events`, `SettingsSync.vue` | Auf jedem Gerät gleich, Änderung kommt auf allen offenen an. Am Gerät bleiben Schrift, Scrollen, Browser-Stimme, automatisch vorlesen, Ansicht je Agent, Spalten. Diktat-Vorgabe CPU. |
| Einstellungsmenü als kurze Liste | `SettingsMenu.vue`, `BaseDialog.vue` (`near`) | Jeder Eintrag ein eigenes Fenster direkt unter dem Hamburger-Knopf; gespeichert wird sofort. |
| Tempo und Tonhöhe als Dezimalfelder | `FactorInput.vue`, `speech_pitch`, `TtsSpeakRequest.pitch` | Komma oder Punkt; leer gilt die Einstellung der Suite, ein Wert überschreibt sie. |
| Hörabsatz-Lautsprecher als Knopf | `markdown.ts` (`LISTEN_REPLAY_CLASS`), `AnswersFeed.vue`, `speech.ts`, `replayCache.ts` | Klick liest die Antwort noch einmal. Die TTS-Engine merkt sich bis zum Ende gespielte Lesungen im Arbeitsspeicher des Browsers (Schlüssel: Text, Sprache, Tempo, Tonhöhe; letzte 8). Browser-Stimme und Echo sprechen neu. Vom Nutzer ausprobiert, vom Code nur durch Typprüfung und Tests des Zwischenspeichers gedeckt. |

Einspielen: Mini `cd frontend && npm run build`, `~/.local/share/agent-orc/venv/bin/pip install -q .`, `systemctl restart agent-orc@mp.service`; Aragon `deploy/deploy.sh -o BatchMode=yes -p 2222 mp@10.0.0.2`. Beide Rechner stehen auf `1614e9e` (Build-ID 2026-10-12T18:10:41Z).

## TTS-Suite (Repo `~/Projekte/TTS-Suite`)

- **Stimmen im Repo:** `voices/` (sechs Stimmen) und `voice-sources/` gehören zum Repository (Peuqui: dürfen auf GitHub). Standard von `voices_dir` ist `<Suite>/voices`; `tts-suite serve` braucht kein `--voices-dir` mehr. Die Config des Minis zeigt auf `/home/mp/Projekte/TTS-Suite/voices`.
- **Host-Skript** `scripts/tts-host-ctl.sh`: löst `voices/` relativ zu sich selbst auf und setzt `TTS_VOICES_DIR` für jeden Befehl; neue Aktion `receive-voices` (tar über stdin, ergänzt und überschreibt, löscht nichts, `..` wird abgewiesen). Muss auf jedem Host liegen (Aragon: identisch mit `main`, Prüfsumme).
- **`POST /voices/push`** (Token) gibt die Stimmen an alle Hosts, Knopf im Stimmen-Reiter. Am 12.10. gegen Aragon geprüft, Prüfsumme über alle Stimmendateien gleich.
- **Geändertes `voices_dir`** gibt laufende Container frei (einer, den eine Lesung hält, wird ins Log geschrieben); die nächste Anfrage startet sie mit dem neuen Mount.
- **Zehn Sprachen** (de en fr it es pt ru zh ja ko), von AIfred ergänzt.
- **Nicht gebaut, bewusst:** `peak_vram_mib` im Lesungs-Ergebnis (der Katalogwert nach der Lesung ist die Spitze; Peuqui und AIfred einverstanden).

## STT-Suite (Repo `~/Projekte/STT-Suite`)

- **Weboberfläche** unter `/ui/` (`/` leitet relativ auf `ui/`, damit der Proxy-Pfad `/whisper/` funktioniert): Zustand (CPU/GPU, Karte, Worker, Restzeit, Freigeben), Konfiguration, Probe (Datei oder Mikrofon). Reine HTML/CSS/JS-Dateien in `ui/`, die `Dockerfile` kopiert sie mit. Im Browser an einem Testcontainer geprüft, Produktion neu gebaut (Commit `1e8a71c`, danach `db17b47`).
- **Aufräumen:** Docker-Label des Containers zeigt jetzt auf `STT-Suite`; `.env.bak-vor-quality` und der leere Ordner `AIfred-Intelligence/docker/tts` (ignoriert, nur `.env` mit zwei Zeilen und `__pycache__`) sind gelöscht. Offen: Compose-Warnung, das Volume `whisper_models` sei für das Projekt `whisper` angelegt (nur kosmetisch; Beheben hieße Volume mit den Modellen umziehen).
- **GPU-Wahl:** Der GPU-Worker nimmt die Karte mit dem meisten freien Speicher (`_find_best_gpu`), bevorzugt leere Karten; Parakeet braucht 4500 MiB frei. Kein stiller Rückfall auf die CPU: ohne Platz antwortet `/transcribe` mit 503; AIfred fällt bei kleinen Dateien selbst auf die CPU zurück (eigene Entscheidung, im Log).
- **Engine je Gerät, Automatik, Burn-in** (STT-Suite `2bad01d`, `c629cac`): `cpu_engine`/`gpu_engine` ersetzen `engine` (harter Schnitt; unbekannte Felder und ungültige Werte antworten 400), `device=cpu|cuda` laden genau die eingestellte Kombination oder antworten 503, die Degradierungskette und `GPU_MIN_MODEL` sind weg. `device=auto` geht die Liste `auto_chain` durch (Einträge aus Gerät, Engine, Modell, Schalter; Vorgabe GPU- dann CPU-Modell; bei Peuqui: GPU Parakeet fp32, GPU Whisper medium, CPU Parakeet fp32); die Antwort nennt Verwendetes und `fallback` mit Gründen. Tabelle des Grafikspeicher-Bedarfs `vram_mib.json` (Schätzwerte) mit Messwerten aus einem Burn-in auf der Webseite (Reiter Grafikspeicher, `POST/GET /burn-in`, gemessene Werte in `/state/vram_measured.json`) und einem einstellbaren Puffer `vram_margin_mib` (256). Ein geladenes Modell wird nur entladen, wenn das neue danach sicher passt. Gemessen (MiB, Quadro RTX 8000): tiny 370, base 530, small 978, medium 2418, large-v3 4594, Parakeet int8 1030, fp32 3708 (60-s-Aufnahme; bei 3 min Parakeet fp32 6332: der Bedarf hängt bei Parakeet an der Aufnahmelänge, die Tabelle gilt für Diktate bis etwa eine Minute).
- **AIfred** (`2ef3b05d`): nur noch „Bevorzugtes Gerät“ (Automatik | Nur CPU | Nur GPU), schickt nur `device`; lange Aufnahmen (>10 MB) bei Automatik immer `device=cpu`; keine eigenen Modellfelder. Agent-Orc zeigt „GPU <engine modell> · CPU <engine modell>“ aus `/status`.
- **Fremden-Test** (Incus, Ubuntu 24.04, Docker über get.docker.com): CPU-Datei startet ohne GPU, `/health` 200, `/ui/` 200, `device=cuda` 503. Die Basisdatei scheitert ohne NVIDIA-Treiber (steht in der README).
- **Landingpage und Service Control:** Karte „STT-Suite“ (`/whisper/ui/`), Eintrag in Service Control umbenannt (`STT-Suite :5080 Docker`); der Pfad der Start-/Stopp-Knöpfe in `ai-service-control.php` zeigte noch auf den gelöschten Ordner `whisper-stt` und ist korrigiert; die Symbole (Farbverlauf an senkrechten Linien unsichtbar) sind repariert, auch das der TTS-Suite. Eingespielt von Peuqui per `sudo` (Sicherungen `*.bak-vor-stt-suite` in `/var/www/html`).

## Offen / Ideen

- **Parakeet lang und kurz:** Eine Aufnahme von mehreren Minuten braucht auf der GPU bis ~6,3 GB statt ~3,7 GB; falls es auf knapper Karte zu Speicherfehlern kommt, zwei Werte je Modell (kurz/lang) in die Tabelle oder `PARAKEET_CHUNK_S` verkleinern.
- **Agent-Orc-Diktat mit `device=auto`:** schickt heute immer das gewählte Gerät, nie die Automatik; auf Wunsch einbaubar.
- **Wiederholen mit Speicher auf dem Server (Variante B):** übersteht ein Neuladen und gilt für alle Geräte; die Suite bleibt außen vor (Peuqui: Zwischenspeichern ist Sache von Agent-Orc, der Papierkorb leert es). Zurückgestellt.
- Die Sicherungsdateien `~/.config/tts-suite/config.json.bak-*` kann Peuqui löschen.
- Neuinstallation in sauberem System am 12.10. geprüft (Incus, Debian 13): Agent-Orc (install.sh, setup, serve, Anmeldung) und TTS-Suite (install.sh, token, serve, Stimmen aus dem Klon) laufen durch; nicht geprüft: Systemeinheit mit PolKit-Regel, Engine-Container, GPU.
