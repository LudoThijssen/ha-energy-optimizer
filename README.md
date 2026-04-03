# HA Energy Optimizer

> ⚠️ **Alpha version / Alfa versie — v0.1.0-alpha**
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
[![Version](https://img.shields.io/badge/version-0.1.0--alpha-orange.svg)]()
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

- **Day balance planning** — calculates how much to discharge each evening to make
  room for the next day's solar production
  **Dagbalansplanning** — berekent hoeveel elke avond ontladen moet worden om
  ruimte te maken voor de zonopbrengst van de volgende dag

- **Smart charging rules** — only charges from the grid when the price spread
  justifies the round-trip efficiency loss
  **Slimme laadregels** — laadt alleen vanaf het net als de prijsspreiding het
  round-trip rendementsverlies rechtvaardigt

- **Negative price protection** — detects negative export prices and notifies
  you to switch on appliances (boiler, washing machine, dishwasher)
  **Negatieve prijsbescherming** — detecteert negatieve terugleverprijzen en
  meldt dit zodat u apparaten kunt inschakelen

- **Temperature derating** — automatically reduces battery power when the
  battery temperature is too high, protecting battery lifetime
  **Temperatuurbeveiliging** — vermindert automatisch het batterijvermogen bij
  te hoge temperatuur om de levensduur te beschermen

- **Multilingual** — built-in NL, EN, DE, FR, ES with AI-powered translation
  for any other language on first use
  **Meertalig** — ingebouwd NL, EN, DE, FR, ES met AI-vertaling voor elke
  andere taal bij eerste gebruik

---

## Configuration GUI / Configuratie-interface

The add-on includes a full web-based configuration interface accessible via
**Open Web UI** in the add-on panel. No manual editing of config files needed.

De add-on bevat een volledige webgebaseerde configuratie-interface toegankelijk
via **Open Web UI** in het add-on paneel. Geen handmatige bewerking van
configuratiebestanden nodig.

Configuration sections / Configuratiesecties:
- System & location / Systeem & locatie
- Database connection / Databaseverbinding
- Home Assistant connection / Home Assistant verbinding
- Inverter & battery / Inverter & batterij
- Energy provider / Energieprovider
- HA entity mapping / HA entiteit-koppeling
- Timing & intervals / Tijden & intervallen
- Optimizer thresholds / Optimizer-drempelwaarden

---

## Known limitations in alpha / Bekende beperkingen in alfa

- Modbus register addresses in `inverter/modbus.py` must be manually adjusted
  to match your specific inverter model
  Modbus-registernummers in `inverter/modbus.py` moeten handmatig worden
  aangepast aan uw specifieke invertermodel

- Historical consumption data is not yet used for forecasting — a fixed
  default value is used instead
  Historische verbruiksgegevens worden nog niet gebruikt voor prognoses —
  er wordt een vaste standaardwaarde gebruikt

- Export price feed is not yet separated from import price — both use the
  same dynamic price source
  Terugleverprijs is nog niet gescheiden van importprijs — beide gebruiken
  dezelfde dynamische prijsbron

- The optimizer has not yet been tested against a live inverter
  De optimizer is nog niet getest tegen een echte inverter

---

## Roadmap

- [ ] Live inverter testing with Modbus
- [ ] Historical consumption averaging for better forecasts
- [ ] Separate export price feed
- [ ] SolarEdge / Growatt / MQTT inverter drivers
- [ ] Frank Energie provider
- [ ] Unit tests
- [ ] Beta release

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
