# HA Energy Optimizer — User Manual / Gebruikershandleiding
# name:          USER_MANUAL.md
# part of:       ha-energy-optimizer
# location:      /USER_MANUAL.md
# part version:  p_v0.1
# altered:       2026-09-16
#
# p_v0.1: NIEUW. Vult een gat in de documentatie — README.md verwijst hier
# al naar (sinds dezelfde wijziging), maar het bestand bestond nog niet.
# Inhoud gebaseerd op wat deze sessie met zekerheid is vastgesteld
# (schema.sql-kolomcommentaren, zelfgebouwde back-up/restore- en
# vertaalfunctionaliteit, log-berichten geïntroduceerd deze sessie,
# base.html voor de exacte navigatiestructuur). Instellingenpagina's
# waarvan de sjabloon-broncode niet is gezien, zijn expliciet als
# "nog aan te vullen" gemarkeerd i.p.v. dat er details verzonnen zijn.
#
# p_v0.1: NEW. Fills a documentation gap — README.md already points here
# (as of the same change), but the file didn't exist yet. Content based
# on what was established with certainty this session (schema.sql column
# comments, self-built backup/restore and translation functionality, log
# messages introduced this session, base.html for the exact navigation
# structure). Settings pages whose template source wasn't seen are
# explicitly marked "still to be completed" instead of inventing detail.
#

> ⚠️ **Alpha version / Alfa versie** — zie [README.md](README.md) voor de
> volledige alfa-kanttekening. Test grondig voordat u hierop vertrouwt.

---

## Inhoud / Contents

1. [Belangrijkste functies / Key features](#belangrijkste-functies--key-features)
2. [Navigatie & instellingenpagina's / Navigation & settings pages](#navigatie--instellingenpaginas--navigation--settings-pages)
3. [Back-up & herstel / Backup & restore](#back-up--herstel--backup--restore)
4. [Vertalingen / Translations](#vertalingen--translations)
5. [Probleemoplossing / Troubleshooting](#probleemoplossing--troubleshooting)
6. [Known limitations / Bekende beperkingen](#known-limitations--bekende-beperkingen)
7. [Roadmap](#roadmap)

---

## Belangrijkste functies / Key features

- **Dagbalansplanning / Day balance planning** — berekent elke avond
  (standaard 21:00, instelbaar) hoeveel er ontladen moet worden om ruimte
  te maken voor de verwachte zonopbrengst van de volgende dag.
  Calculates each evening (default 21:00, configurable) how much to
  discharge to make room for the next day's expected solar production.

- **Slimme laadregels / Smart charging rules** — laadt alleen vanaf het
  net als de prijsspreiding het round-trip-rendementsverlies
  rechtvaardigt (drempel instelbaar via `min_spread_ratio_for_discharge`).
  Only charges from the grid when the price spread justifies the
  round-trip efficiency loss.

- **Negatieve-prijsbescherming / Negative price protection** — detecteert
  negatieve terugleverprijzen (`negative_export_threshold_excl`) en meldt
  dit, zodat apparaten (boiler, wasmachine) ingeschakeld kunnen worden.
  Detects negative export prices and notifies you to switch on appliances.

- **Temperatuurbeveiliging / Temperature derating** — vermindert
  automatisch het batterijvermogen boven `temp_derating_threshold_c`
  (standaard 35°C), met een instelbare reductiefactor
  (`temp_derating_factor`).
  Automatically reduces battery power above a configurable temperature
  threshold, protecting battery lifetime.

- **A/B-strategie batterijruimte voor zon / Solar reserve strategy** —
  kiest hoe de optimizer omgaat met batterijruimte reserveren vóór een
  verwacht négatief exportprijsvenster (Systeempagina,
  `solar_reserve_strategy`):
  - **A — "block"**: laadt helemaal niet van het net zolang de verwachte
    zon vóór dat venster genoeg is om de batterij te vullen.
  - **B — "throttle"** (standaard): laadt wel van het net, maar begrenst
    het vermogen zodat er ruimte overblijft voor de verwachte zon.
  Chooses how the optimizer handles reserving battery capacity ahead of a
  forecasted negative export price window. Default is B ("throttle").

- **Off-grid uitvaldetectie / Off-grid outage detection** — optioneel
  (`has_offgrid_switch`), koppelt aan een HA-entiteit die aangeeft of het
  systeem off-grid draait; pauzeert optimizer-beslissingen zolang dat zo
  is, en gebruikt een dynamische SoC-ondergrens tussen dag- en
  nachtwaarde.
  Optional off-grid detection tied to an HA entity; pauses optimizer
  decisions while off-grid.

- **Meertalig / Multilingual** — ingebouwd NL, EN, DE, FR, ES. Twee
  aparte lagen: statische UI-teksten (JSON per taal) en operationele
  teksten (reason-strings, database-gebaseerd, met AI-vertaalknop).
  Built-in NL, EN, DE, FR, ES, with two separate text layers.

- **Back-up & herstel / Backup & restore** — zie de aparte sectie
  hieronder.

---

## Navigatie & instellingenpagina's / Navigation & settings pages

De GUI is ingedeeld in vier groepen in het navigatiemenu:
The GUI is organized into four groups in the navigation menu:

**Installatie / Installation:** Overzicht, Systeem, Database, Home
Assistant, Inverter & batterij *(alleen als `has_battery` aan staat)*,
Provider, Entiteiten.

**Optimizer:** Tijden, Drempelwaarden, Prijzen.

**Rapporten / Reports:** Rapportagelog, Geschiedenis, Energiekosten.

**Persoonlijk / Personal:** Kleuren, Vertalingen.

Hieronder de pagina's waarvan de instellingen in deze handleiding al in
detail beschreven zijn. Voor de overige pagina's, zie
["Nog aan te vullen"](#nog-aan-te-vullen--still-to-be-completed) onderaan
— daar is bewust geen detail verzonnen.

The sections below cover the pages whose settings are already documented
in detail. For the remaining pages, see ["Still to be completed"](#nog-aan-te-vullen--still-to-be-completed)
at the end — detail was deliberately not invented there.

### Systeem / System

| Veld / Field | Betekenis / Meaning | Standaard / Default |
|---|---|---|
| `language` | UI-taal / UI language | nl |
| `battery_efficiency_pct` | Rendement batterij (laad+ontlaad rondje) / Round-trip battery efficiency | 75,00% |
| `hard_min_discharge_price_excl` | Onder deze prijs (excl. BTW) wordt nooit ontladen / Never discharge below this price (excl. VAT) | €0,05000 |
| `temp_derating_threshold_c` | Batterijtemperatuur waarboven vermogen wordt verlaagd / Battery temp above which power is derated | 35,00°C |
| `temp_derating_factor` | Vermogensfactor bij te hoge temperatuur / Power reduction factor when exceeded | 0,70 |
| `min_spread_ratio_for_discharge` | Minimale prijsspreiding om ontladen te triggeren / Min price spread ratio to trigger discharge | 2,00× |
| `discharge_near_peak_fraction` | Prijs moet binnen deze fractie van de piek liggen / Price must be within this fraction of peak | 0,85 |
| `extreme_price_multiplier` | Veelvoud van gemiddelde prijs dat als extreem geldt / Multiple of avg price considered extreme | 2,50× |
| `negative_export_threshold_excl` | Terugleverprijs waaronder export beperkt wordt / Export price below which export is limited | €0,00000 |
| `notify_export_threshold_excl` | Gebruiker melden bij lage terugleverprijs / Notify user below this export price | €0,02000 |
| `charge_near_cheapest_fraction` | Prijs moet binnen deze fractie van het minimum liggen / Price must be within this fraction of cheapest | 1,05 |
| `min_sunshine_pct_for_refill` | Min. zonpercentage morgen om vandaag te mogen ontladen / Min sunshine % tomorrow to allow discharge | 40,00% |
| `sunrise_buffer_pct` | SoC-buffer bij zonsopgang / SoC buffer to keep at sunrise | 10,00% |
| `evening_planning_time` | Tijdstip avond-dagbalansplanning / Time for evening day balance planning | 21:00 |
| `solar_charge_threshold` | Blokkeer nettoladen bij verwachte zon ≥ deze fractie van bruikbare capaciteit / Block grid charging above this expected-solar fraction | 0,80 |
| `solar_reserve_strategy` | A ("block") of B ("throttle") — zie Belangrijkste functies | throttle (B) |
| `schedule_interval_minutes` | Tijdstap van het schema, informatief / Schedule time step, informational | 15 |

**Off-grid (alleen relevant als `has_offgrid_switch` aan staat):**

| Veld / Field | Betekenis / Meaning | Standaard / Default |
|---|---|---|
| `offgrid_reserve_high_pct` | SoC-ondergrens overdag / SoC floor during the day | 10,00% |
| `offgrid_reserve_low_pct` | SoC-ondergrens 's nachts / SoC floor during the night | 5,00% |
| `offgrid_night_threshold_pct` | Drempel "nacht"-verbruik, als % van het daggemiddelde / Night-consumption threshold, % of daily average | 50,00% |
| `offgrid_night_confirm_slots` | Opeenvolgende kwartier-slots onder drempel om "nacht" te bevestigen / Consecutive quarter-slots to confirm night | 8 |
| `offgrid_primary_entity_id` | Primaire detectie-entiteit / Primary detection entity | — |
| `offgrid_fallback_entity_id` | Terugval-entiteit (bv. P1-meter) / Fallback entity | — |
| `offgrid_alarm_entity_id` | Entiteit teruggeschreven naar HA / Entity written back to HA | `binary_sensor.ha_energy_optimizer_offgrid` |

**Energiekosten (gas/stadsverwarming):**

| Veld / Field | Betekenis / Meaning |
|---|---|
| `gas_price_eur_m3` / `gas_price_entity_id` | Vaste gasprijs óf HA-entiteit voor dynamische prijs / Fixed price or an HA entity for dynamic pricing |
| `heating_price_eur_gj` / `heating_price_entity_id` | Zelfde patroon voor stadsverwarming / Same pattern for district heating |

### Database

Verbindingsinstellingen (host, poort, naam, gebruiker, wachtwoord) plus
een testknop. Zie de aparte sectie [Back-up & herstel](#back-up--herstel--backup--restore)
voor de rest van deze pagina.

### Kleuren / Colors

Aanpasbare kleuren voor de dashboardgrafiek: zon, eigen verbruik,
netimport, netexport, laadtoestand (SoC), laden, ontladen, zon-laden.
Customizable dashboard chart colors: solar, own consumption, grid
import/export, state of charge, charge, discharge, solar-charge.

### Vertalingen / Translations

Zie de aparte sectie [Vertalingen](#vertalingen--translations) hieronder.

---

## Back-up & herstel / Backup & restore

Op de Database-pagina:

- **Back-up downloaden** — genereert een `.sql`-bestand met de volledige
  inhoud van de database. Dit bestand is **altijd veilig om te draaien**,
  hoe vaak ook: het voegt alleen rijen toe die nog niet bestaan, en
  overschrijft nooit bestaande data. Kan ook los in phpMyAdmin gedraaid
  worden, buiten de app om.
  Generates a `.sql` file with the database's full contents. Always safe
  to run, any number of times: only adds missing rows, never overwrites
  existing data. Can also be run standalone in phpMyAdmin.

- **Terugzetten** — upload een back-upbestand, met een keuze:
  - **Aanvullen** (standaard) — voegt alleen ontbrekende data toe.
  - **Vervangen** — maakt eerst ALLE tabellen leeg, en laadt dan het
    bestand. **Niet ongedaan te maken** — vraagt om bevestiging.
  Upload a backup file, choosing **append** (default) or **replace**
  (empties everything first — cannot be undone, asks for confirmation).

- Na het terugzetten wordt per tabel gerapporteerd: gelukt, mislukt, of
  overgeslagen (leeg, of niet in het bestand).
  After restoring, each table reports success, failure, or skipped.

**Gebruik om data te delen** — een back-up bevat ook persoonlijke
configuratie (locatie, HA entity-ID's, apparaatinstellingen). Wie een
back-up van iemand anders importeert (bijvoorbeeld om een nieuwe
installatie een vliegende start te geven met al geleerde zon-/
verbruikspatronen) moet de Systeem-, Inverter- en overige
configuratiepagina's daarna zelf nalopen en aanpassen.
Sharing data — a backup also contains personal configuration. Anyone
importing someone else's backup should review and adjust the System,
Inverter, and other configuration pages afterward.

---

## Vertalingen / Translations

De Vertalingenpagina beheert de operationele teksten (reason-strings
zoals "RS07", log-categorieën, notificaties) — een apart systeem van de
vaste UI-teksten.

- Teksten kunnen placeholders bevatten, zoals `{price:.4f}` of
  `{target_soc:.0f}`. Deze worden getoond als **niet-bewerkbare
  blokjes**: typen kan overal in de tekst, maar niet in een blokje zelf.
  Texts can contain placeholders like `{price:.4f}`, shown as
  **non-editable chips** — you can type anywhere except inside a chip.
- Een blokje verplaatsen: klik erop om 'm op te pakken, klik dan op de
  gewenste plek (of op een ander blokje) om 'm daar neer te zetten.
  To move a chip: click it to pick it up, then click the target spot (or
  another chip) to drop it there.
- Bij opslaan wordt gecontroleerd of de placeholders nog exact
  overeenkomen met het origineel — bij een mismatch wordt niet
  opgeslagen en verschijnt een foutmelding.
  On save, placeholders are checked against the original — a mismatch
  blocks the save and shows an error.
- **AI vertalen** — vult ontbrekende vertalingen voor een taal in één
  keer in (niet beschikbaar voor nl/en, de basistalen).
  Fills in missing translations for a language in one go (not available
  for nl/en).

---

## Probleemoplossing / Troubleshooting

### Wat betekenen deze log-berichten? / What do these log messages mean?

**Normaal, zelfherstellend gedrag — geen reden tot zorg:**
**Normal, self-healing behavior — not cause for concern:**

| Bericht (begin) / Message (start) | Betekenis / Meaning |
|---|---|
| `database.setup: Schema wordt toegepast` / `Schema succesvol toegepast` | Het databaseschema wordt bij elke opstart gecontroleerd en zo nodig aangevuld. / The database schema is checked and filled in as needed on every startup. |
| `database.connection: Pool opgewarmd` | Databaseverbindingen worden bij het opstarten alvast eenmalig gebruikt, om een eenmalige driver-eigenaardigheid voor te zijn. / Database connections are used once at startup to pre-empt a one-time driver quirk. |
| `database.connection: Connectie niet bruikbaar (poging 1/2) ... probeer een verse` | Een databaseverbinding bleek onverwacht niet bruikbaar; de app probeert automatisch een verse verbinding en gaat door. Zonder vervolgmelding van een collector: geen gevolgen gehad. / A connection turned out unexpectedly unusable; the app automatically tries a fresh one and continues. No consequences if no follow-up error appears. |

**Kunnen op een echt probleem wijzen / May indicate a real problem:**

| Bericht (begin) / Message (start) | Wat te doen / What to do |
|---|---|
| `database.setup: ... is MISLUKT / FAILED` | De add-on start dan niet op. Controleer de volledige foutmelding — meestal een databaseverbindingsprobleem of conflicterende bestaande tabelstructuur. / The add-on won't start. Check the full error — usually a connectivity problem or a conflicting table structure. |
| `collectors.*: Onverwachte fout` / `Voorspelling mislukt`, **herhaaldelijk** | Eén geïsoleerde melding vlak na opstarten kan onschadelijk zijn. Komt dit **herhaaldelijk** terug, controleer de databaseverbinding. / A single message right after startup can be harmless. If it **keeps recurring**, check the database connection. |
| `[translations] AI-vertaling mislukt` | Controleer de internetverbinding van de add-on. / Check the add-on's internet connection. |

### Add-on herstarten vs. herinstalleren / Restarting vs. reinstalling

- **Herstarten** stopt en start alleen de draaiende container opnieuw —
  pakt GEEN wijzigingen op die je alleen op GitHub hebt gepusht.
  Restarting only stops and starts the running container — does NOT pick
  up changes only pushed to GitHub.
- Om code-wijzigingen daadwerkelijk toegepast te krijgen: verwijder de
  add-on-link in Home Assistant en voeg 'm opnieuw toe — dat forceert een
  verse build vanaf GitHub.
  To actually apply code changes: remove the add-on link in Home
  Assistant and add it again — forces a fresh build from GitHub.
- Controleer na zo'n herbouw de versie-header van het gewijzigde bestand
  op GitHub, om zeker te weten dat de nieuwe versie is meegekomen.
  After such a rebuild, check the changed file's version header on
  GitHub to confirm the new version made it through.

---

## Known limitations / Bekende beperkingen

- Modbus register addresses in `inverter/modbus.py` must be manually
  adjusted to match your specific inverter model.
- Export price feed is not yet separated from import price for all
  providers.
- The optimizer has not yet been extensively tested against a live
  inverter.
- Er zijn op dit moment 2 bekende installaties (alfa-stadium) — het
  gewogen samenvoegen van geleerde data bij een back-up-import op een
  bestaande installatie is bewust nog niet gebouwd (back-up/restore
  ondersteunt nu: aanvullen op een lege/nieuwe installatie, of volledig
  vervangen).
  There are currently 2 known installations (alpha stage) — weighted
  merging of learned data on backup import into an existing installation
  hasn't been built yet (backup/restore currently supports: append into
  an empty/new installation, or full replace).

---

## Roadmap

- [ ] Live inverter testing with Modbus
- [ ] Separate export price feed for all providers
- [ ] SolarEdge / Growatt / MQTT inverter drivers
- [ ] Frank Energie provider
- [ ] Unit tests
- [ ] Beta release
- [ ] Notificatieniveaus (info/waarschuwing/kritiek), per-niveau
      instelbaar / Notification levels, configurable per level
- [ ] OperationalTranslator-laag koppelen aan decision_engine.py's
      reason-strings (nu nog losse Nederlandse tekst) / Connect the
      OperationalTranslator layer to decision_engine.py's reason strings
- [ ] Databasegrootte inzichtelijk maken in de GUI / Show database size
      in the GUI
- [ ] `optimizer_schedule` mist een echte unieke sleutel op
      `schedule_for` — de `ON DUPLICATE KEY UPDATE` in
      `repository.py::save_slot()` triggert vermoedelijk nooit (nog niet
      onderzocht hoeveel dubbele rijen dit al veroorzaakt heeft) /
      `optimizer_schedule` lacks a real unique key on `schedule_for` —
      the `ON DUPLICATE KEY UPDATE` in `repository.py::save_slot()`
      presumably never triggers (not yet investigated how many duplicate
      rows this has already caused)

---

## Nog aan te vullen / Still to be completed

Onderstaande pagina's/onderdelen zijn nog niet in detail beschreven omdat
hun sjabloon-broncode niet is meegenomen bij het opstellen van dit
document. De structuur (groepering, paginanamen) komt wel al exact uit
`base.html`; alleen de veld-voor-veld-inhoud ontbreekt nog:

The pages/parts below aren't yet described in detail because their
template source wasn't reviewed while drafting this document. The
structure (grouping, page names) is already exact, taken from
`base.html`; only the field-by-field content is still missing:

**Installatie / Installation:** Overzicht (`index.html`), Home Assistant
(`homeassistant.html`), Inverter & batterij (`inverter.html`), Provider
(`provider.html`), Entiteiten (`entities.html`)

**Optimizer:** Tijden (`schedule.html`), Drempelwaarden — volledig
(`optimizer.html`, gedeeltelijk hierboven via schema.sql-kolommen),
Prijzen (`prices.html`)

**Rapporten / Reports:** Rapportagelog (`reportlog.html`), Geschiedenis
(`history.html`), Energiekosten (`energy_costs.html`)
