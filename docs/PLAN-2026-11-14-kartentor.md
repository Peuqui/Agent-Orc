# Plan: Kartentor für lokale Sitzungen (14.11.2026)

Abgestimmt mit Mini:AIfred-Intelligence (21:47), zur Freigabe bei Peuqui.

## Befund

Am 14.11. hielt vllm-research über GPU-Orc die Karten (Hold bis 15.11., 06:15). Die lokale Sitzung
AIfred-horarium (Profil `claude-local`, GLM) hat GLM trotzdem neu geladen; vllm-research musste es um
21:09 von Hand räumen. GPU-Orc-Log: Die Sitzung fragte GPU-Orc nur bei Peuquis Eingaben (18:00:17,
18:01:45, Hook `agent-free-cards`), während des Holds ab 20:55 nie.

Zwei Lücken:
1. **Das Wecken über AI-Connect** läuft am Hook `UserPromptSubmit` vorbei. Die Anfrage von Claude Code
   geht direkt an llama-swap, und llama-swap lädt auf Anfrage.
2. **Auch Start und Hook achten nicht auf einen Hold.** Sie rufen `/free`, das bei einem Hold Karten
   räumt statt abzulehnen. Das ist bei GPU-Orc gewollt, denn AIfred hat Vorrang. Danach geht die Eingabe
   weiter.

Ein Hold ist bei GPU-Orc eine Bitte an die Aufrufer (`hold.py`). Er gilt für den ganzen Rechner und
kennt keine einzelnen Karten (`Hold(since, reason)`). Abfragen lässt er sich über `GET /loading` →
`held`.

## Entwurf

**Ein Tor vor llama-swap, nur für die lokalen Sitzungen von Agent-Orc.** Agent-Orc setzt
`ANTHROPIC_BASE_URL` für diese Sitzungen ohnehin (`claude_environment`). Künftig zeigt die Adresse auf
das Tor statt direkt auf llama-swap. So läuft jede Anfrage einer solchen Sitzung durch das Tor, auch das
Wecken und das Warmhalten. GPU-Orc, llama-swap und AIfred bleiben unberührt.

- **Eigener Listener nur auf `127.0.0.1`.** Claude Code braucht eine HTTP-Adresse. Aragons Agent-Orc
  lauscht nur auf einem Socket, und beim Mini reicht nginx alles unter `/agent-orc/` nach außen weiter.
  Das Tor bekommt deshalb im selben Prozess einen eigenen kleinen Server, der nicht durch nginx geht.
  Den Port legt die Config fest.
- **Ein Zeichen je Sitzung als Schlüssel.** Agent-Orc gibt jeder lokalen Sitzung statt
  `sk-no-key-required` ein eigenes, zufälliges Zeichen als `ANTHROPIC_API_KEY`. Das Tor erkennt daran,
  welche Sitzung fragt. Für das Wecken nach dem Hold ist das nötig, und andere Benutzer des Rechners
  kommen so nicht hinein. llama-swap bekommt weiter einen beliebigen Schlüssel.
- **Prüfung je Anfrage:** Ist das Modell schon geladen (llama-swap `/running`), geht die Anfrage
  durch. Sonst fragt das Tor GPU-Orc (`/loading` → `held`; auf Aragon mit dem Token aus `gpu_orc`).
  Gibt es keinen Hold, reicht es die Anfrage an llama-swap durch, gestreamt wie die vorhandene
  Weiterleitung zu anderen Rechnern (`hosts.forward`). Gibt es einen, antwortet es mit einem Fehler im
  Anthropic-Format samt Grund: „Karten gehalten: <reason> seit <since>“.
- **Merken und wecken (AIfreds Punkt 1).** Das Tor merkt sich jede abgewiesene Sitzung. Ihre Karte
  zeigt „wartet auf Karten: <Grund>“. Solange eine Sitzung wartet, schaut Agent-Orc regelmäßig bei
  GPU-Orc nach. Endet der Hold, tippt es der Sitzung einen Text ein, der in der Config steht, etwa „Die
  Karten sind wieder frei. Mach dort weiter, wo die Anfrage abgewiesen wurde, und lies dabei auch
  liegengebliebene AI-Connect-Nachrichten (peer_read).“
- **Start:** `agent-orc backend run` prüft den Hold vor seinem `/free`. Gibt es einen, beginnt der Start
  nicht und nennt den Grund (Fehler wie andere `BackendError`).
- **Der Hook `agent-free-cards`** bleibt, wie er ist: Er räumt Sprachdienste und Hilfsmodelle für das
  eigene Modell. Den Hold prüft das Tor.

## Was vorher am echten Fall zu prüfen ist (AIfreds Punkt 1)

Was geschieht mit einer AI-Connect-Nachricht, wenn die geweckte Sitzung an einem Fehler der API
scheitert? Bleibt sie ungelesen auf der Bridge, und kommt nach dem eingetippten Text ein erneuter
Weckruf? Prüfen mit einer Wegwerf-Sitzung im Profil `claude-local`, einem kurzen Test-Hold (nur nach
Absprache, wie bei jeder Kartenaktion) und einer Nachricht an sie. Davon hängt der Wortlaut des
Wecktexts ab.

## Arbeitsschritte (je ein kleiner Auftrag, jeder einzeln geprüft)

1. Config: Port des Tors und Wecktext; Zeichen je Sitzung beim Start erzeugen und ablegen.
2. Tor: eigener Listener, Prüfung (geladen → durch; Hold → Fehler), gestreamte Weiterleitung, Tests mit
   einem gefälschten llama-swap und GPU-Orc.
3. Start: Hold vor `/free` prüfen; `claude_environment` zeigt auf das Tor und gibt das Zeichen weiter.
4. Merken, Karte („wartet auf Karten“), Wecken nach dem Hold; Texte de/en.
5. Doku, Einspielen auf Mini und Aragon, Configs mit Sicherung.
6. Live-Test am echten Fall wie oben, mit Absprache mit AIfred und vllm-research.
