# Übergabe vom 11.10.2026 (Sitzung mit Sonnet)

Zuerst lesen: dieses Dokument, dann `docs/TODO.md` (nur das, was aussteht). Der Code ist die Wahrheit. Davor gelten
`docs/UEBERGABE-2026-10-10-abend.md` (Dateimanager, Vorlesen, Betrieb) und die Dokumente davor. Stand: `main` = `origin/main`,
alles auf Mini und Aragon eingespielt (Oberfläche `index-Bngmq87q.js` bis zum Nachmittag, danach die Menüs und der
Tastaturschalter; maßgeblich ist `git log`).

## Was heute dazukam (alles geprüft, eingespielt, gepusht)

| Thema | Wo | Kern |
|---|---|---|
| Handy-Kopfleiste der Arbeitsfläche | `WorkspaceSwitcher.vue`, `WorkspaceView.vue`, `HostSwitcher.vue`, `labelFit.ts` | Der Name der Arbeitsfläche ist ein Knopf mit Menü (Namensfeld zum Umbenennen, andere, neu, löschen). „+“, Lautsprecher (automatisch, neue), Vollbild bleiben in der Zeile, die Hilfe liegt hinter ⋮. Der Rechner ist ein Knopf, dessen Name nach Pixelbreite an ganzen Buchstaben auf die Breite von „Mini“ gekürzt wird (`fitLabel`); sein Menü hat die vollen Namen. `HostSwitcher` ist die eine Stelle für Arbeitsfläche und Hauptseite. |
| Einheitliche Auswahlen | `SelectMenu.vue`, `useModelChoice.ts` (`modelOptions`) | Alle elf `<select>` ersetzt: eine Liste am Knopf, in `<body>` mit fester Position (Dialoge und scrollende Menüs schneiden sie nicht ab), oben oder unten je nach Platz, Pfeiltasten, Escape. Das System-Auswahlfenster des Handys kommt nirgends mehr. |
| Dropdown-Menüs | `DropdownMenu.vue` | Messen beim Öffnen den Platz oben und unten (abzüglich `--app-header-height` und `--bottom-nav-height`), öffnen dort, wo es passt, und scrollen sonst (`max-height`). Löste das abgeschnittene Menü der untersten Agentenkarte; gilt für alle neun Menüs. |
| Schriftgrößen in Pixeln | `useSettings.ts`, `useViewZoom.ts`, `SettingsMenu.vue`, Ansichten | Zwei Einstellungen je Gerät, 8 bis 28 px: Terminal und Ansichten (Antworten, Notizen, Gespräche, Dateien, Verbrauch, Änderungen, Markdown-Vorschau; der Editor nimmt die Pixel direkt). Die Ansichten zoomen (`zoom` = Pixel / 14). `useViewZoom` hält den Text am oberen Rand fest: ein Faktor auf der Scroll-Position reichte nicht (größerer Text bricht in mehr Zeilen um, die Seite wuchs 1,93-fach bei 1,5-fachem Zoom), und ein Treffertest am Rand fand das offene Menü. Es sucht die oberste sichtbare Textstelle über die Geometrie der Textknoten. |
| Kopieren-Knopf an Codeblöcken | `markdown.ts`, `useCodeCopy.ts`, `style.css` | Jeder Codeblock (Antworten, Notizen, Vorschau) bekommt in `renderMarkdown` einen Knopf am rechten Rand; ein Klick-Hörer in `App.vue` kopiert ohne den Zeilenumbruch am Ende (ein Befehl liefe sonst beim Einfügen sofort). |
| Tastatur im Terminal | `TerminalView.vue`, `KeyBar.vue` | Der Tastaturknopf ist ein Schalter: bei einem normalen Terminal schreibt die Tastatur dann ins Terminal selbst (`inputmode` des xterm-Eingabefelds von `none` auf `text`), bei einem Agenten öffnet er das Nachrichtenfeld; der Zustand folgt dem Fokus (`syncKeyboardUp`). Bekannt: angetippte Gboard-Wortvorschläge verdoppeln Text (`docs/TODO.md`). |
| Kleinigkeiten | `MessageInput.vue`, `JogScroller.vue`, `AnswersFeed.vue`, `SettingsMenu.vue` | Das Nachrichtenfeld scrollt nach einem Diktat ans Ende. Jog doppelt so schnell (200 Zeilen/s am Ende). „Neue vorlesen (n)“ wird grau, wenn nichts Neues da ist. Das Einstellungsmenü scrollt (bis „App neu laden“ war es am Handy nicht erreichbar). |
| Sanftes Beenden | `sessions.py`, `config.py`, `default_config.yaml` | Beenden und Neustart schicken zuerst den `exit_command` des Profils (Claude: `/exit`) und warten bis zu `terminal.exit_wait_seconds` (5), erst dann `kill-session`; sonst blieb die Remote-Control-Sitzung als Offline-Eintrag in der Claude-App. Der Schlüssel steht in der Konfiguration beider Rechner (Sicherung `config.yaml.bak-20261011-exit-command`). Von Peuqui in der Praxis bestätigt: ein auf Aragon gestarteter Agent verschwand nach „Beenden“ aus der Claude-App. Ein Ende von außen (WSL aus) bleibt hart. |
| Aragon: User-Bus | `docs/aragon/Start-WSL.vbs`, `docs/TODO.md` | Nach einem Start der WSL ohne Windows-Anmeldung verdeckt WSLg `/run/user/1000` (doppeltes Mount), `systemctl --user` meldete „Failed to connect to bus“. `Start-WSL.vbs` (auf Aragon `D:\Archiv\VM\`, Autostart) startet danach `user@1000` neu, nur wenn der Bus verdeckt ist; im kalten Start geprüft (`/var/log/wsl-user-bus-fix.log`). In VBScript ist `Fix` ein Befehl: die Variable heißt `repairCommand`. |

README (Deutsch und Englisch) beschreibt jetzt alles davon, die Hilfe-Texte in `locales` (Abschnitt `help`) noch nicht im Einzelnen
(Schriftgrößen und Menüs sind dort schon, Kopieren-Knopf, Tastaturschalter und Handy-Kopfleiste nicht).

## Wichtige Erkenntnisse

- **Jeder Rechner liefert seine eigene Oberfläche.** Eine Seite „von Aragon“ läuft mit Aragons Version (`/hosts/Aragon/`); nach einer
  Frontend-Änderung auf beide Rechner einspielen (Mini: `npm run build`, `pip install .`, Dienst neu starten; Aragon:
  `deploy/deploy.sh -o BatchMode=yes -p 2222 mp@10.0.0.2`). Die Oberfläche ist komprimiert etwa 2,3 MB, einmal je Update.
- **Chrome-Port 9222 und der Mini.** Vor jedem Browsertest die anderen Agenten einzeln fragen (AIfred-Intelligence, FreeEchoDot2);
  läuft ein Messfenster von `Mini:vllm-research`, nur nach deren „jetzt“ bauen/testen und danach „fertig“ melden. Testrezept
  (eigene Instanz auf 18765 mit bekanntem Passwort, eigener tmux-Socket `orc-uitest`, `fetch('/api/login')`) in
  `docs/UEBERGABE-2026-10-10-abend.md`.
- **Lasttest der Terminal-Tests bestanden:** 40 von 40 Läufen unter 16 CPU-Prozessen (`stress`), Last bis 20,9 (früher scheiterte der Tunnel-Test
  in 23 von 40).
- **Windows-Skripte.** VBScript lässt sich hier nicht ausführen: vor jeder Änderung an `Start-WSL.vbs` einen Probelauf von Peuqui,
  und keine Variablennamen, die in VBScript Befehle sind (`Fix`, `Date`, …).

## Offen

Siehe `docs/TODO.md`; kurz: die Agentenseite wird von der Ansichten-Schriftgröße noch nicht skaliert; die Hilfe-Texte (Kopieren-Knopf,
Tastaturschalter, Handy-Kopfleiste); Gespräche-Tab nach einem Neustart der Bridge; Dateien-Reiter am Handy und ein Upload mit mehreren GB
über Aragon; Echo-Dot-Punkte (zurückgestellt). Ein Reddit-Beitrag ist in Vorbereitung (Entwurf nur lokal, nichts gepostet).
