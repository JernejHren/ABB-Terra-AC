# Changelog

Vse pomembne spremembe te integracije so naštete tukaj. Skladno z [Keep a Changelog](https://keepachangelog.com/sl/1.0.0/).

## [0.4.0]

### Release notes (EN)

- **Requires Home Assistant 2026.9 or newer.** The integration now uses Home Assistant's shared Modbus connection (`modbus.async_get_unit`) instead of opening its own `pymodbus` client.
- Charger communication moved into a Home Assistant-independent device library (`abb_terra_ac.api`) built on `modbus-connection`.
- Added a **Modbus unit ID** field to setup and reconfigure (default `1`). Existing config entries are migrated automatically (entry version 3).
- Removed the integration's own reconnect, retry and Modbus lock: the shared connection serializes requests and reopens itself after a dropped link.
- The `pymodbus` requirement was removed from `manifest.json`; the `modbus` integration is now a dependency.
- Diagnostics: the `client` section is now `device` and includes the unit ID.
- Tests rewritten for the new Modbus layer; duplicated `tests/tests` copy removed.
- Fixed the current limit being written 1 mA too low for some values (float truncation); out-of-range values are now rejected instead of wrapped.
- Charging state is now masked with bits 6..0 as in the manual; clarified the register 400Dh comment.
- New repair warning when the poll interval is not shorter than the charger's communication timeout (EN/SL). README corrected: poll interval is configurable, and the charging state byte layout matches the ABB document.
- Added direct tests of the device library against the examples in the ABB Modbus manual v1.11.
- Error code sensor: several simultaneous errors are now decoded (lowest bit is the state; `active_errors`, `raw_code` and `unknown_bits` attributes added). README has a table of all error codes from the Terra AC installation manual.
- Session state: state 5 ("Paused") with a commanded limit of 6 A or more is now treated as the short transition while a session starts, no longer as "paused by current". Anything below 6 A (not only 0 A) is "paused by current". Seen on a real charger: stop leaves the Modbus limit at 0 A.
- Session state: a drop to B1 after charging, with a commanded limit below 6 A (what setting the limit to 0 A during charging does on a real charger), is now `paused_by_current` instead of `idle`. B1 right after plugging in stays `idle`. This relies on the state seen since the vehicle was last idle, so after a Home Assistant restart it reads `idle` until charging is seen again.
- The "charging at reduced current" diagnostic binary sensor is now disabled by default for new installs: on a real charger bit 7 was set in every state, including while charging at the commanded current. Existing entities are not changed.
- One missed poll (timeout or lost link) no longer makes the entities unavailable: the previous data is kept for that poll and the entities become unavailable only on the second failed poll in a row. This hides the single missed poll seen when an idle charger resets itself about every 14 minutes.
- Diagnostics now include the raw status block as hex (serial number registers omitted). With debug logging for `custom_components.abb_terra_ac`, registers 400Ch-400Fh, 4022h-4023h and the phase currents are logged whenever the state or limits change.

### Spremenjeno

- Integracija zahteva **Home Assistant 2026.9 ali novejši** in uporablja skupno Modbus povezavo prek vgrajene integracije `modbus` (`async_get_unit`) namesto lastnega odjemalca `pymodbus`.
- Komunikacija s polnilnico je v ločeni knjižnici brez odvisnosti od Home Assistanta (`abb_terra_ac.api`) na osnovi `modbus-connection`.
- Nastavitev in ponovna nastavitev imata novo polje **Modbus unit ID** (privzeto `1`). Obstoječi vnosi se samodejno migrirajo.
- Odstranjeni so lasten reconnect, ponovni poskus in Modbus zaklep; skupna povezava sama serializira zahteve in se po izpadu ponovno odpre.
- V `manifest.json` ni več `pymodbus`; odvisnost je integracija `modbus`.
- Stanje seje: stanje 5 (pavza) z omejitvijo 6 A ali več je zdaj kratek prehod ob začetku seje, ne več »pavza zaradi toka«. Vse pod 6 A (ne samo 0 A) je »pavza zaradi toka«. Na pravi polnilnici ukaz stop pusti Modbus omejitev na 0 A.
- Stanje seje: prehod v B1 po polnjenju z omejitvijo pod 6 A (to naredi nastavitev limita na 0 A med polnjenjem) je zdaj `paused_by_current`, ne več `idle`. B1 takoj po priklopu ostane `idle`. Odločitev temelji na stanju od zadnjega mirovanja vozila, zato po ponovnem zagonu HA kaže `idle`, dokler se polnjenje ne zazna znova.
- Diagnostični binarni senzor »polnjenje z zmanjšanim tokom« je pri novih namestitvah privzeto onemogočen: na pravi polnilnici je bil bit 7 nastavljen v vseh stanjih, tudi med polnjenjem s predpisanim tokom. Obstoječe entitete se ne spremenijo.
- Ena zgrešena meritev (časovna omejitev ali prekinjena povezava) ne naredi več entitet nedosegljivih: za to meritev se obdržijo prejšnji podatki, nedosegljive postanejo šele po drugi zaporedni neuspešni meritvi. S tem se skrije ena zgrešena meritev, ki jo povzroči ponastavitev polnilnice v mirovanju na ~14 minut.
- Diagnostika vsebuje surovi blok registrov (heksadecimalno, brez serijske številke). Z debug zapisom za `custom_components.abb_terra_ac` se ob spremembi stanja ali omejitev zapišejo registri 400Ch–400Fh, 4022h–4023h in tokovi po fazah.

## [0.3.3]

### Release notes (EN)

- Fixed intermittent `pymodbus` errors like `Request cancelled outside pymodbus` by avoiding external asyncio cancellations around Modbus requests.
- Serialized Modbus operations with a shared `asyncio.Lock` to prevent overlapping reads/writes on the same TCP client.
- Added automatic reconnect and a single retry for coordinator polling reads after transient I/O failures.
- Applied the same resilient Modbus call path to the config flow probe and to entity write helpers.
- Added tests covering `ModbusIOException` handling and reconnect+retry behavior.

### Popravljeno

- Odpravljena občasna napaka `Request cancelled outside pymodbus` pri branju registrov, ker integracija ne prekinja več `pymodbus` klicev z zunanjim `asyncio.wait_for`.

### Izboljšano

- Vsi Modbus klici (poll + zapisi) so serializirani prek skupnega `asyncio.Lock`, da se branja in zapisi ne prekrivajo na istem TCP odjemalcu.
- Coordinator ob prehodni I/O napaki naredi reconnect in enkrat ponovi branje (retry samo za read).
- Enako robustno obnašanje se uporabi tudi pri validaciji v config flowu.

## [0.3.0]

### Release notes (EN)

- Added a **Reconfigure flow** to change charger `host`/`port` from the UI without removing the integration.
- Added **Diagnostics** export for the config entry with sensitive fields redacted.
- Added **Repair issue** warnings when the charger reports invalid limits after a firmware reset and automatic recovery fails.
- Added **translations** for entities, icons, config flow strings, and exceptions for a better UI experience.
- Replaced the charging enable/disable **switch** with separate **Start** and **Stop** buttons.
- Improved type safety with **strict typing** and `mypy` configuration.
- Improved docs (supported devices, features, limitations, examples, troubleshooting).
- Improved test coverage around coordinator recovery logging, diagnostics, and reconfigure flow.
- Fixed UI setup and reconfiguration regressions:
  - `reconfigure` stays on the **reconfigure** step when validation fails (no step switching back to `user`).
  - Options flow uses suggested values consistently for the scan interval field.
- Improved runtime reliability by applying **consistent Modbus connect/read timeouts** in both config flow and coordinator polling to avoid hangs.

### Dodano

- **Reconfiguration flow** za posodobitev IP naslova ali vrat brez odstranjevanja integracije.
- **Diagnostics** izvoz za config entry z anonimizacijo občutljivih podatkov.
- **Repair issue** opozorila, ko polnilnica po firmware resetu vrne neveljavne limite in samodejna obnova ne uspe.
- **Entity translations**, **icon translations** in **exception translations** za boljši Home Assistant UI.
- **Strict typing** z `mypy` konfiguracijo in tipno čistim paketom integracije.

### Izboljšano

- Boljša dokumentacija: podprte naprave, funkcije, omejitve, primeri uporabe, troubleshooting in obnašanje osveževanja.
- Stabilnejši testi za coordinator recovery logiko, diagnostics in reconfiguration flow.
- Izboljšana kakovost integracije po Home Assistant Quality Scale smernicah.

### Spremenjeno

- Stikalo za vklop/izklop polnjenja je zamenjano z ločenima gumboma **Start** in **Stop**.

### Opombe

- Number sliderja za `charging current limit` in `fallback limit` namenoma ostajata vidna kot običajni kontroli v UI in nista premaknjena v config kategorijo, ker je to boljša uporabniška izkušnja za dejansko uporabo integracije.

## [0.2.0]

### Dodano

- Integracija **ABB Terra AC** prek **Modbus TCP** (`pymodbus` ≥ 3.9.2), razred `local_polling`.
- **Config flow**: nastavitev prek UI-ja (IP/naslov, vrata), preizkus povezave in branja holding registrov, `unique_id` v obliki `host:port`.
- **DataUpdateCoordinator** s periodičnim osveževanjem (privzeto 15 s), en sam blok branja 37 registrov od naslova 16384 (4000h).
- **Senzorji**: stanje polnjenja (IEC 61851-1), serijska številka, različica firmware, koda napake, stanje zaklepa vtičnice, aktivna moč, energija seje, tokovi L1–L3, napetosti L1–L3, dejanski limit toka. Serijska in firmware sta privzeto onemogočena v registru entitet.
- **Stikal**: start/stop polnjenja, zaklepanje/odklepanje kabla (ustrezni Modbus registri).
- **Številke (number)**: limit toka polnjenja in **fallback limit** z dinamičnim maksimumom glede na `user_settable_max_current`, način drsnika.
- **Naprava**: `device_info` (ABB, Terra AC, serijska, `sw_version` po podatkih s polnilnice).
- **Odstranitev naprave iz registra**: `async_remove_config_entry_device` dovoli odstranitev osamljenih naprav iz UI-ja.
- **Prevod**: `strings.json` in `translations/sl.json` za korak config flow in napake.

### Popravljeno / delo okoli firmware

- Stanje polnjenja se bere iz registra **400Dh** (visoki bajt), ker dokumentirani 400Ch v praksi vrača 0.
- Ob znanih težavah firmware po nenapovedanem rebootu (**fallback limit** npr. 256 A, **limit toka** npr. 32 A nad dovoljenim maksimumom) integracija poskuša **enkrat** povrniti zadnjo veljavno vrednost ali `user_settable_max_current`.

### Tehnično

- Varen `close()` Modbus odjemalca, če je `close()` awaitable.
- Odvisnost v `manifest.json`: `pymodbus>=3.9.2`.

### Config flow

- **`AbortFlow` (npr. `already_configured`)** se ne ujame več v splošni `except Exception`, tako da ponovna dodaja istega polnilnika v UI pravilno konča z abortom in ne z obrazcem »Unexpected error«.

### Razvoj / testi (v repozitoriju)

- **pytest** testi (`pytest-homeassistant-custom-component`): config flow, setup/unload, **register entitet / naprave**, stanja izbranih senzorjev iz Modbus blokov, **`switch.turn_on`** (zapis 4105h) ter **`number.set_value`** za limit toka in fallback; `tests/helpers/modbus.py` z gradnikom 37 registrov; `requirements_test.txt` vključuje tudi `pymodbus`.
