# Plan: Modellkatalog zwischen Agent-Orc-Instanzen (14.11.2026)

**Status (14.11.2026):** umgesetzt in den Commits `3baf4c6` und `e579381`, eingespielt auf Mini und
Aragon am 14.11.2026.

## Ziel

Ein Agent-Orc soll Claude Code auf den lokalen Modellen eines **anderen** Rechners starten können,
mit der richtigen Auswahl und den richtigen Denkstufen, ohne dass jemand Modelle oder Stufen von
Hand pflegt. Allgemein für jeden Aufbau mit mehreren Rechnern, kein Sonderweg für Mini und Aragon.

## Ausgangslage

- Seit `c140be5`/`5c3cc38` liest ein Agent-Orc die Modelle und Stufen seines **eigenen** llama-swap
  selbst (`llama_swap_config`, `llama_swap.py`): Modelle aus `/v1/models`, Embedding-Server raus,
  Stufen aus dem Chat-Template.
- Das geht nur auf dem Rechner, auf dem die Modelldateien liegen. Aragon nutzt die Modelle des
  Mini (`base_urls: 10.0.0.1:11435`), kommt aber nicht an dessen Platte.
- Mehrere Rechner sind schon verbunden: der steuernde Agent-Orc hält zu jedem Rechner in `hosts`
  einen SSH-Tunnel zu dessen Socket. Darüber spiegelt er Einstellungen hin (`mirror_settings`) und
  holt Nachrichten ab (`relay_host_messages`). Das ist der Weg für den Katalog.

## Entwurf

**Katalog:** Was ein Agent-Orc über die Backends weiß, die er selbst liest (die mit
`llama_swap_config`): je Backend die angebotenen Modelle, je Modell die Stufen oder, wenn sie nicht
zu lesen sind, warum nicht.

**Rechnername:** der Hostname (`socket.gethostname()`), auf beiden Rechnern gleich `Mini` und
`Aragon` wie die Schlüssel unter `hosts`. Kein neues Config-Feld.

**Austausch über die vorhandenen Tunnel, in beide Richtungen,** durch den steuernden Agent-Orc,
für jeden erreichbaren Rechner in `hosts`:
- er **schickt** seinen Katalog hin (`PUT /api/catalogs/<sein Name>`), wie die Einstellungen;
- er **holt** dessen Katalog (`GET /api/catalog`) und legt ihn bei sich ab.

So geht es in beiden Aufbauten: Steuert der GPU-Rechner den Arbeitsplatz (Mini → Aragon), bekommt
der Arbeitsplatz den Katalog geschickt. Steuert der Arbeitsplatz den GPU-Rechner, holt er ihn ab.
Neue SSH-Schlüssel, Rückwärts-Tunnel oder ein zweiter Listener sind nicht nötig, und kein Rechner
bekommt mehr Zugriff auf den anderen als heute.

**Ablage:** `~/.local/state/agent-orc/catalogs/<Rechner>.json`, mit dem Zeitpunkt.

**Häufigkeit:** beim Erreichen eines Rechners und dann jede Minute, in beide Richtungen. Ein
leerer Katalog (der Rechner liest selbst kein Backend) wird nicht weitergegeben. Das Lesen der
Templates kostet wenig (Dateien, GGUF per mmap).

**Verbraucher:** Ein Backend bekommt `catalog_from: {machine: <Rechner>, backend: <Backend dort>}`
statt `llama_swap_config`. Das Backend dort wird ausdrücklich genannt, damit nichts still an
gleichen Namen hängt. Modelle und Stufen kommen dann aus dem abgelegten Katalog jenes Rechners:
- `models`: die Modelle, die der Server meldet und die im Katalog stehen;
- `levels`: die Stufen aus dem Katalog; stand dort ein Problem, ist das der Fehler, und die Karte
  des Agenten zeigt ihn (`4f26eac`);
- noch kein Katalog da: klarer Fehler „kein Katalog von Mini, dessen Agent-Orc hat diesen Rechner
  noch nicht erreicht“.

Die Config prüft: höchstens eins von `llama_swap_config` und `catalog_from`, und mit einem von
beiden keine `levels` in `models`.

**Was nicht dazugehört:** GPU-Orc bleibt, wie er ist. DashScope und andere Clouds behalten
`models` mit `levels` und `free_until`.

## Arbeitsschritte

1. `catalog.py`: Katalog dieses Rechners bauen, fremde Kataloge ablegen und lesen.
2. API: `GET /api/catalog` (eigener), `PUT /api/catalogs/{rechner}` (von einem steuernden Rechner).
3. `HostLink.get_json`, Austauschschleife `exchange_catalogs` neben `mirror_settings`.
4. `BackendConfig.catalog_from`, Prüfung, Verbraucher in `backends.py`.
5. Tests: Katalog, Endpunkte, Austausch mit zwei echten Apps (`other_machine`), Verbraucher.
6. README und Vorgabe-Config.
7. Einspielen auf Mini und Aragon, dann Aragons Config: `models` raus, `catalog_from: Mini`
   (Sicherung, Kopie vorher mit dem installierten Code prüfen).
