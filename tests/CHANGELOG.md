# Changelog

Vse pomembne spremembe te integracije so naštete tukaj. Skladno z [Keep a Changelog](https://keepachangelog.com/sl/1.0.0/).

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
