# HA Energy Optimizer

<!--
name:          README.md
part of:       ha-energy-optimizer
location:      /README.md
version:       v0.2.13-alpha
altered:       2026-09-23

p_v0.2.13-alpha (deze wijziging): nieuwe sectie "Database aanmaken"
toegevoegd met daadwerkelijke SQL-stappen (CREATE DATABASE/USER/GRANT)
— geldt voor zowel de automatische als de handmatige installatiemethode,
dus hoort in README.md zelf, niet pas in het nog niet bestaande
MANUAL_INSTALL.md. Bevat de verwijzing naar het verwijderen van de
database op precies het moment dat je 'm aanmaakt.

p_v0.2.13-alpha (this change): added a "Create the database" section
with actual SQL steps (CREATE DATABASE/USER/GRANT) — applies to both the
automatic and manual installation methods, so belongs in README.md
itself, not in the not-yet-existing MANUAL_INSTALL.md. Includes the
pointer to removing the database at exactly the moment you create it.

p_v0.2.13-alpha (vorige wijziging): ingekort tot wat nodig is vóór/tijdens
installatie (wat de app doet, vereisten, installatie-instructies).
Alles over instellingen, mogelijkheden en probleemoplossing verhuisd
naar USER_MANUAL.md — dat bestaat nu ook, was eerder een lege plek in
de documentatie.

p_v0.2.13-alpha (previous change): trimmed down to what's needed before/
during installation (what the app does, requirements, installation
instructions). Everything about settings, features and troubleshooting
moved to USER_MANUAL.md — which now exists, previously a gap in the
documentation.
-->

> ⚠️ **Alpha version / Alfa versie — v0.2.13-alpha** 
>
> This add-on is in early development and not yet ready for production use.
> Test thoroughly before relying on this for your home energy system.
> Breaking changes may occur between versions.
>
> Deze add-on is in vroege ontwikkeling en nog niet klaar voor productiegebruik.
> Test grondig voordat u hierop vertrouwt voor uw thuisenergiesysteem.
> Wijzigingen tussen versies kunnen achterwaartse compatibiliteit breken.

---

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.2.13--alpha-orange.svg)]()
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Add--on-41BDF5.svg)](https://www.home-assistant.io/)
[![Status](https://img.shields.io/badge/status-alpha-red.svg)]()

---

## What it does / Wat het doet

HA Energy Optimizer controls your home battery based on:

- Dynamic electricity prices (ANWB, EnergyZero, Tibber, ENTSO-E)
- Solar panel production forecasts / Zonpaneelproductieverwachtingen
- Weather forecasts via Open-Meteo (free, no API key needed)
- Household consumption patterns / Huishoudelijke verbruikspatronen
- Battery state of charge and temperature / Laadtoestand en temperatuur batterij

It calculates an optimal 24-hour charge/discharge schedule and executes it
automatically, saving money while protecting battery lifetime.

Het berekent een optimaal 24-uurs laad-/ontlaadschema en voert dit automatisch
uit, wat geld bespaart terwijl de levensduur van de batterij wordt beschermd.

📖 **For all settings, features, and troubleshooting, see [USER_MANUAL.md](USER_MANUAL.md).**
📖 **Voor alle instellingen, mogelijkheden en probleemoplossing, zie [USER_MANUAL.md](USER_MANUAL.md).**

---

## Installation / Installatie

### Method 1 — Automatic via HA Add-on Store (recommended)
### Methode 1 — Automatisch via de HA Add-on Store (aanbevolen)

1. Open Home Assistant → **Settings → Add-ons → Add-on store**
2. Click **⋮** (top right) → **Repositories**
3. Add this URL / Voeg deze URL toe:
   ```
   https://github.com/LudoThijssen/ha-energy-optimizer
   ```
4. Find **HA Energy Optimizer** in the store → **Install**
5. Configure via the **Configuration** tab → **Start**
6. Open the web UI via **Open Web UI** for the full configuration wizard

### Method 2 — Manual installation
### Methode 2 — Handmatige installatie

See [MANUAL_INSTALL.md](MANUAL_INSTALL.md) for step-by-step instructions.
Zie [MANUAL_INSTALL.md](MANUAL_INSTALL.md) voor stapsgewijze instructies.

---

## Requirements / Vereisten

- Home Assistant OS or Supervised (not Core or Container)
- MySQL database — local or on NAS / lokaal of op NAS
- A long-lived access token from Home Assistant
- Inverter/battery with Modbus TCP support (other protocols planned)

---

## Database aanmaken (verplicht, vóór installatie) / Create the database (required, before installing)

Zowel bij de automatische als de handmatige installatiemethode moet er
vooraf een **lege** database met een eigen gebruiker en wachtwoord
bestaan — de add-on maakt zelf alle tabellen aan bij de eerste opstart,
maar kan geen database of gebruiker aanmaken.

For both the automatic and manual installation methods, an **empty**
database with its own user and password must exist beforehand — the
add-on creates all tables itself on first startup, but cannot create the
database or user.

Via phpMyAdmin (of een andere MariaDB-beheertool):
Via phpMyAdmin (or another MariaDB management tool):

```sql
CREATE DATABASE `energy` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'energy'@'%' IDENTIFIED BY 'kies-een-sterk-wachtwoord';
GRANT ALL PRIVILEGES ON `energy`.* TO 'energy'@'%';
FLUSH PRIVILEGES;
```

(Namen `energy`/`energy` zijn de standaardwaarden op de Database-pagina
van de add-on — andere namen mogen ook, zolang je ze straks consistent
invult.)
(The names `energy`/`energy` are the defaults on the add-on's Database
page — other names are fine too, as long as you fill them in
consistently afterward.)

Deze gegevens (host, poort, databasenaam, gebruikersnaam, wachtwoord)
vul je na installatie in op de **Database**-pagina van de
webinterface — zie [USER_MANUAL.md](USER_MANUAL.md#database) voor die
pagina.
You enter these details (host, port, database name, username, password)
on the add-on's **Database** page after installation — see
[USER_MANUAL.md](USER_MANUAL.md#database) for that page.

📖 **Bewaar dit moment goed: de database later verwijderen is een
handmatige stap, niet automatisch via Home Assistant's verwijderfunctie
— zie [USER_MANUAL.md](USER_MANUAL.md#add-on-verwijderen--de-database-gaat-niet-automatisch-mee--uninstalling--the-database-is-not-removed-automatically)
zodat je alvast weet waar je straks moet zijn.**
📖 **Keep this moment in mind: removing the database later is a manual
step, not automatic via Home Assistant's uninstall — see
[USER_MANUAL.md](USER_MANUAL.md#add-on-verwijderen--de-database-gaat-niet-automatisch-mee--uninstalling--the-database-is-not-removed-automatically)
so you already know where to look when the time comes.**

---

## Supported energy providers / Ondersteunde energieproviders

| Provider | Status | Notes |
|---|---|---|
| ANWB Energie | ✅ Built-in | Via EnergyZero platform |
| EnergyZero | ✅ Built-in | No API key needed / Geen API-sleutel nodig |
| ENTSO-E | ✅ Built-in | Free, European day-ahead prices |
| Tibber | ✅ Built-in | Token required / Token vereist |
| Frank Energie | 🔜 Planned / Gepland | Contributions welcome |

## Supported inverter protocols / Ondersteunde inverterprotocollen

| Protocol | Status | Notes |
|---|---|---|
| Modbus TCP/RTU | ✅ Built-in | Register map must match your inverter |
| SolarEdge cloud | 🔜 Planned / Gepland | |
| Growatt cloud | 🔜 Planned / Gepland | |
| MQTT | 🔜 Planned / Gepland | |

---

## Key features / Belangrijkste functies

See [USER_MANUAL.md](USER_MANUAL.md) for the full feature list and how each one works.
Zie [USER_MANUAL.md](USER_MANUAL.md) voor de volledige functielijst en hoe elke functie werkt.

---

## Configuration GUI / Configuratie-interface

The add-on includes a full web-based configuration interface accessible via
**Open Web UI** in the add-on panel. No manual editing of config files needed.
See [USER_MANUAL.md](USER_MANUAL.md) for every settings page explained.

De add-on bevat een volledige webgebaseerde configuratie-interface toegankelijk
via **Open Web UI** in het add-on paneel. Geen handmatige bewerking van
configuratiebestanden nodig. Zie [USER_MANUAL.md](USER_MANUAL.md) voor elke
instellingenpagina uitgelegd.

---

## Known limitations in alpha / Bekende beperkingen in alfa

See [USER_MANUAL.md](USER_MANUAL.md#known-limitations--bekende-beperkingen).
Zie [USER_MANUAL.md](USER_MANUAL.md#known-limitations--bekende-beperkingen).

---

## Roadmap

See [USER_MANUAL.md](USER_MANUAL.md#roadmap).
Zie [USER_MANUAL.md](USER_MANUAL.md#roadmap).

---

## Contributing / Bijdragen

Contributions are very welcome — especially:
- New inverter drivers / Nieuwe inverterdrivers
- Energy provider integrations / Energieprovider-integraties
- Translations / Vertalingen
- Bug reports / Bugrapporten

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License / Licentie

MIT — see [LICENSE](LICENSE) for details.

---

## Author / Auteur

Ludo Thijssen
