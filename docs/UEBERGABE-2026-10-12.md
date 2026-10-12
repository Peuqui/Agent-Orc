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

## Offen / Ideen

- **Wiederholen mit Speicher auf dem Server (Variante B):** übersteht ein Neuladen und gilt für alle Geräte; die Suite bleibt außen vor (Peuqui: Zwischenspeichern ist Sache von Agent-Orc, der Papierkorb leert es). Zurückgestellt.
- Die Sicherungsdateien `~/.config/tts-suite/config.json.bak-*` kann Peuqui löschen.
- Neuinstallation in sauberem System nach den heutigen Änderungen: siehe Ende dieses Abschnitts, sobald geprüft.
