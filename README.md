# HA Energy Optimizer
# name:          README.md
# part of:       ha-energy-optimizer
# location:      /README.md
# version:       v0.2.13-alpha
# altered:       2026-09-16
#
# p_v0.2.13-alpha (deze wijziging): ingekort tot wat nodig is vóór/tijdens
# installatie (wat de app doet, vereisten, installatie-instructies).
# Alles over instellingen, mogelijkheden en probleemoplossing verhuisd
# naar USER_MANUAL.md — dat bestaat nu ook, was eerder een lege plek in
# de documentatie.
#
# p_v0.2.13-alpha (this change): trimmed down to what's needed before/
# during installation (what the app does, requirements, installation
# instructions). Everything about settings, features and troubleshooting
# moved to USER_MANUAL.md — which now exists, previously a gap in the
# documentation.
#
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
