# Plan: Aragon als Reserve, wenn der Mini ausfällt

Stand 05.11.2026, Entwurf zur Abstimmung mit Peuqui. Baut auf dem Umbau „Zentrale“ auf
(docs/PLAN-ZENTRALE.md, Paket 7). Noch nichts davon ist gebaut.

## Heute

- Die App gibt es nur unter `https://narnia.spdns.de/agent-orc/`. Die Fritzbox reicht Port 443
  an den Mini weiter, dort laufen nginx (Zertifikat von Let's Encrypt für `narnia.spdns.de`) und
  Agent-Orc mit dem einzigen Login.
- Agent-Orc auf Aragon lauscht nur auf einem Socket ohne Login. Erreichbar ist es nur durch den
  SSH-Tunnel des Mini (Kabel `10.0.0.2`, sonst Heimnetz `192.168.0.1`).
- Fällt der Mini aus, ist alles weg: die Seite, der Login, Aragons Agenten von außen.

## Ziel

Fällt der Mini aus, schaltet Peuqui **von Hand** auf Aragon um. Danach arbeitet er unter
**derselben Adresse** weiter: Die installierte PWA am Handy, der Login und die Push-Anmeldungen
bleiben gültig. Ein automatisches Umschalten gibt es nicht (zwei Zentralen gleichzeitig hießen
Abgleich in beide Richtungen und Konflikte).

## Bausteine

### 1. Aragon kann jederzeit Zentrale sein (Agent-Orc)

- `server` darf Socket **und** Port zugleich haben: den Socket für den Tunnel des Mini, den Port
  (nur `127.0.0.1` in WSL, hinter dem eigenen Proxy, Baustein 3) für den Notfall. Heute schließen
  sich beide aus (`ServerConfig.one_way_to_listen`). Der Login gilt nur am Port; der Socket bleibt
  ohne Login (SSH ist dort der Login).
- So ist im Notfall auf Aragon an Agent-Orc nichts umzustellen.

### 2. Die Nutzerdaten liegen als Kopie auf Aragon (Agent-Orc)

Der Mini spiegelt bei jeder Änderung (wie heute schon die Einstellungen, `mirror_settings`) auf
Aragon:

- geteilte Einstellungen, Übergabe-Schalter (schon gebaut), TTS-Auswahl, Prompt-Vorlagen,
  Zusatztasten, Notizbücher samt Dateien,
- **Login** (Passwort-Hash und Schlüssel der Anmelde-Cookies): dasselbe Passwort, und ein
  angemeldetes Handy bleibt angemeldet,
- **Push**: VAPID-Schlüssel und Anmeldungen der Geräte. Damit kann Aragon an dieselben Geräte
  senden, und das Handy muss sich nicht neu anmelden.

Die Kopie liegt in Aragons eigenen Dateien. Aragon benutzt sie im Normalbetrieb nicht, weil
niemand seine Seite öffnet. Nicht gespiegelt wird, was dem Mini als Rechner gehört (seine
Arbeitsflächen, Agenten, Kartenreihenfolge): Ist der Mini aus, gibt es seine Agenten nicht.

Weil Schlüssel über den Tunnel gehen: nur über die bestehende SSH-Verbindung, nie über das Netz
ohne SSH.

### 3. Aragon von außen erreichbar (Netz, Peuquis Seite)

Gleiche Adresse heißt: Im Notfall zeigt die Weiterleitung von Port 443 in der Fritzbox auf
Aragon statt auf den Mini, und Aragon beantwortet HTTPS für `narnia.spdns.de`.

- Auf Aragon ein Reverse Proxy mit TLS vor Agent-Orc (`/agent-orc/` wie im nginx-Snippet
  `deploy/nginx-location.conf`). In WSL: nginx oder Caddy (muss installiert werden, nur nach
  Freigabe). Dazu in Windows eine Portweiterleitung 443 → WSL, wie heute schon für 2222.
- Zertifikat: Der Mini kopiert nach jeder Erneuerung von Let's Encrypt das Zertifikat für
  `narnia.spdns.de` auf Aragon (Hook von certbot). Ist der Mini länger als die Laufzeit des
  Zertifikats (90 Tage) aus, muss Aragon selbst erneuern; das ist dann ein eigener Schritt.
- Im Normalbetrieb bleibt der Proxy auf Aragon aus (oder ohne Weiterleitung), damit niemand
  versehentlich auf der Reserve arbeitet.

Alternative ohne Portwechsel in der Fritzbox: über das VPN der Fritzbox ins Heimnetz und
Aragon direkt ansprechen. Nachteil: Eine andere Adresse heißt eine andere PWA, neuer Login,
neue Push-Anmeldung; ohne HTTPS gehen Diktat, Service Worker und Push gar nicht.

### 4. Ablauf im Notfall (Anleitung, `docs/RESERVE.md`)

1. Proxy auf Aragon einschalten (ein Befehl).
2. In der Fritzbox die Weiterleitung von 443 auf Aragon stellen.
3. App am Handy neu laden. Sie zeigt jetzt Aragon als Zentrale (der Rechner-Wechsler zeigt den
   Mini als „aus“, wenn Aragon ihn als Rechner kennt).

### 5. Rückweg, wenn der Mini wieder da ist

1. Was auf Aragon in der Zwischenzeit geändert wurde (Einstellungen, Notizen, Vorlagen), geht
   einmal zum Mini zurück: ein Befehl, der die Spiegelung in Gegenrichtung laufen lässt.
2. Fritzbox zurück auf den Mini, Proxy auf Aragon aus.
3. Danach spiegelt wieder der Mini auf Aragon.

### 6. Probe

Einmal den Mini-Dienst stoppen und den Ablauf durchspielen, mit Diktat, Terminal und
Push-Meldung, dann zurück. Erst danach gilt die Reserve als fertig.

## Antworten von Peuqui (05.11.2026)

- Kein VPN: Alles läuft über die Portweiterleitung der Fritzbox. Die VPN-Alternative entfällt.
- Vor allem sitzt **Authelia** (Zwei-Faktor) als Login des Proxys. Die Reserve braucht deshalb
  ebenfalls Authelia, sonst wäre Aragon im Notfall nur mit dem Login von Agent-Orc geschützt.
  Auf dem Mini läuft Authelia als Docker-Container mit nginx `auth_request`; auf Aragon genauso
  in WSL (Docker ist dort vorhanden). Gespiegelt werden Authelias Konfiguration, Nutzer und die
  Zwei-Faktor-Geheimnisse, damit die Authenticator-App am Handy weiter gilt.
- Reverse Proxy: in WSL, mit einer Windows-Portweiterleitung wie für 2222.
- Fritzbox von Hand umstellen reicht. Ist Aragon aus, weckt Peuqui ihn aus der Fritzbox per
  Wake-on-LAN. Offen: ob nach dem Aufwecken Windows ohne Anmeldung hochkommt und WSL samt
  Agent-Orc von selbst startet.
- Ports: Peuqui kommt über 8443 (meist) und 443 (aus der Klinik, oft abgeschaltet) herein; der
  Mini-nginx lauscht auf beiden. Aragons nginx lauscht genauso auf beiden. Im Notfall stellt
  Peuqui in der Fritzbox die Weiterleitungen, die er gerade offen hat, auf Aragon. Jeder Port ist
  für den Browser ein eigener Ursprung (eigene PWA, eigene Cookies, eigene Push-Anmeldung); das
  ist heute schon so und bleibt beim Umschalten gültig, weil Aragon dieselben Daten hat.
