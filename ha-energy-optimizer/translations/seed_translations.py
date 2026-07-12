#
# name:          seed_translations.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/translations/seed_translations.py
# part version:  p_v0.4
# altered:       2026-07-01
#
# Vult de translation_strings tabel met alle operationele teksten in
# Nederlands (nl) en Engels (en). Wordt aangeroepen bij eerste installatie
# en bij updates als er nieuwe keys zijn toegevoegd.
# Bestaande aanpassingen worden NIET overschreven (INSERT IGNORE).
#
# Fills the translation_strings table with all operational texts in
# Dutch (nl) and English (en). Called on first install and on updates
# when new keys have been added.
# Existing customisations are NOT overwritten (INSERT IGNORE).

import logging
from database.connection import DatabaseConnection

logger = logging.getLogger(__name__)

# ── Seed data ────────────────────────────────────────────────────────────────
# Formaat: (key, taal, tekst)
# Variabelen tussen accolades worden vervangen door reason_params
# Format: (key, language, text)
# Variables in braces are replaced by reason_params

SEED: list[tuple[str, str, str]] = [

    # ── RS: Reason strings — optimizer beslissingen ──────────────────────────

    ("RS01", "nl", "Zon-overschot {surplus_kw:.2f} kW — batterij laden"),
    ("RS01", "en", "Solar surplus {surplus_kw:.2f} kW — charging battery"),

    ("RS02", "nl", "Batterij vol — zon-overschot terugleveren"),
    ("RS02", "en", "Battery full — exporting solar surplus"),

    ("RS03", "nl", "Batterij vol, terugleverprijs {export_price:.4f} €/kWh — export beperken"),
    ("RS03", "en", "Battery full, export price {export_price:.4f} €/kWh — limiting export"),

    ("RS04", "nl", "Batterij vol, overschot {surplus_kw:.2f} kW teruggeleverd"),
    ("RS04", "en", "Battery full, surplus {surplus_kw:.2f} kW exported"),

    ("RS05", "nl", "Hoge prijs {price:.4f} €/kWh — ontladen"),
    ("RS05", "en", "High price {price:.4f} €/kWh — discharging"),

    ("RS06", "nl", "Onvoldoende beschikbare laadtoestand voor ontladen (beschikbaar: {available:.1f}%, reserve: {reserve:.1f}%)"),
    ("RS06", "en", "Insufficient available SoC for discharge (available: {available:.1f}%, reserve: {reserve:.1f}%)"),

    ("RS07", "nl", "Laden bij lage prijs {price:.4f} €/kWh"),
    ("RS07", "en", "Charging at low price {price:.4f} €/kWh"),

    ("RS08", "nl", "Laden bij lage prijs {price:.4f} €/kWh ({reason})"),
    ("RS08", "en", "Charging at low price {price:.4f} €/kWh ({reason})"),

    ("RS09", "nl", "Anti-cycling: prijs {price:.4f} te dicht bij laadprijs {charge_price:.4f} (break-even {break_even:.4f}) — rust"),
    ("RS09", "en", "Anti-cycling: price {price:.4f} too close to charge price {charge_price:.4f} (break-even {break_even:.4f}) — idle"),

    ("RS10", "nl", "Geen voordelige actie dit uur"),
    ("RS10", "en", "No profitable action this hour"),

    ("RS11", "nl", "Off-grid actief — nettoladen geblokkeerd"),
    ("RS11", "en", "Off-grid active — grid charging blocked"),

    ("RS12", "nl", "Dagbalans: ruimte maken voor zonopbrengst morgen — doel {target_soc:.0f}%"),
    ("RS12", "en", "Day balance: making room for tomorrow's solar — target SoC {target_soc:.0f}%"),

    ("RS13", "nl", "Zon morgen: {solar:.1f} kWh, verbruik: {consumption:.1f} kWh — doel-laadtoestand bij zonsopgang: {target_soc:.0f}%"),
    ("RS13", "en", "Solar tomorrow: {solar:.1f} kWh, consumption: {consumption:.1f} kWh — target SoC at sunrise: {target_soc:.0f}%"),

    ("RS14", "nl", "Goedkope prijs {price:.4f} €/kWh excl. — laden vanaf net"),
    ("RS14", "en", "Cheap price {price:.4f} €/kWh excl. — charging from grid"),

    ("RS15", "nl", "Temperatuurverlaging actief: {temp:.1f}°C — vermogen begrensd"),
    ("RS15", "en", "Temperature derating active: {temp:.1f}°C — power limited"),

    ("RS16", "nl", "Negatieve prijs {price:.4f} €/kWh — altijd laden"),
    ("RS16", "en", "Negative price {price:.4f} €/kWh — always charging"),

    ("RS17", "nl", "Spread {spread:.2f}× ≥ drempel — ontladen"),
    ("RS17", "en", "Spread {spread:.2f}× ≥ threshold — discharging"),

    ("RS18", "nl", "Laadtoestand te laag voor nacht ({soc:.0f}% < {min_soc:.0f}%) — laden"),
    ("RS18", "en", "SoC too low for night ({soc:.0f}% < {min_soc:.0f}%) — charging"),

    ("RS19", "nl", "Laadtoestand te laag voor volgende dag ({soc:.0f}% < {min_soc:.0f}%) — laden"),
    ("RS19", "en", "SoC too low for next day ({soc:.0f}% < {min_soc:.0f}%) — charging"),

    ("RS20", "nl", "Opportunistisch laden bij lage prijs {price:.4f} €/kWh"),
    ("RS20", "en", "Opportunistic charging at low price {price:.4f} €/kWh"),

    # ── LG: Log berichten — collectors ──────────────────────────────────────

    ("LG01", "nl", "Sensor {sensor} niet beschikbaar — laatste bekende waarde {value} gebruikt"),
    ("LG01", "en", "Sensor {sensor} unavailable — using last known value {value}"),

    ("LG02", "nl", "Geen instraling beschikbaar voor zon-leermodel"),
    ("LG02", "en", "No irradiance available for solar learning model"),

    ("LG03", "nl", "Zon-leermodel update mislukt: {error}"),
    ("LG03", "en", "Solar learning model update failed: {error}"),

    ("LG04", "nl", "Verbruik-leermodel update mislukt: {error}"),
    ("LG04", "en", "Consumption learning model update failed: {error}"),

    ("LG05", "nl", "Batterijvermogen berekend: laden {charge:.2f} - ontladen {discharge:.2f} = {result:.2f} kW"),
    ("LG05", "en", "Battery power derived: charge {charge:.2f} - discharge {discharge:.2f} = {result:.2f} kW"),

    ("LG06", "nl", "Prijzen ophalen mislukt (poging {attempt}/{max}): {error}"),
    ("LG06", "en", "Price fetch failed (attempt {attempt}/{max}): {error}"),

    ("LG07", "nl", "Weerdata ophalen mislukt: {error}"),
    ("LG07", "en", "Weather data fetch failed: {error}"),

    ("LG08", "nl", "Optimizer gestart"),
    ("LG08", "en", "Optimizer started"),

    ("LG09", "nl", "Optimizer voltooid — {slots} uren gepland"),
    ("LG09", "en", "Optimizer completed — {slots} hours scheduled"),

    ("LG10", "nl", "Optimizer mislukt: {error}"),
    ("LG10", "en", "Optimizer failed: {error}"),

    ("LG11", "nl", "DecisionEngine fase 3 gebruikt"),
    ("LG11", "en", "DecisionEngine phase 3 used"),

    ("LG12", "nl", "DecisionEngine mislukt — terugval op strategie: {error}"),
    ("LG12", "en", "DecisionEngine failed — falling back to strategy: {error}"),

    # ── NT: Notificaties — HA push berichten ────────────────────────────────

    ("NT01", "nl", "Waarschuwing: {message}"),
    ("NT01", "en", "Warning: {message}"),

    ("NT02", "nl", "Fout: {message}"),
    ("NT02", "en", "Error: {message}"),

    ("NT03", "nl", "HA Energy Optimizer — Fout"),
    ("NT03", "en", "HA Energy Optimizer — Error"),

    ("NT04", "nl", "Dagrapport energie"),
    ("NT04", "en", "Daily energy report"),

    # ── SY: Systeem berichten — dagrapport ───────────────────────────────────

    ("SY01", "nl", "Dagrapport energie-optimizer"),
    ("SY01", "en", "Daily energy optimizer report"),

    ("SY02", "nl", "Zonopbrengst:     {solar:.2f} kWh"),
    ("SY02", "en", "Solar yield:      {solar:.2f} kWh"),

    ("SY03", "nl", "Zonopbrengst:     {solar:.2f} kWh ⚠ (geen data)"),
    ("SY03", "en", "Solar yield:      {solar:.2f} kWh ⚠ (no data)"),

    ("SY04", "nl", "Netafname:        {import_kwh:.2f} kWh"),
    ("SY04", "en", "Grid import:      {import_kwh:.2f} kWh"),

    ("SY05", "nl", "Teruglevering:    {export_kwh:.2f} kWh"),
    ("SY05", "en", "Grid export:      {export_kwh:.2f} kWh"),

    ("SY06", "nl", "Totaal verbruik:  {consumption:.2f} kWh"),
    ("SY06", "en", "Total consumption:{consumption:.2f} kWh"),

    ("SY07", "nl", "Netdata:          ⚠ geen data beschikbaar"),
    ("SY07", "en", "Grid data:        ⚠ no data available"),

    ("SY08", "nl", "Batterij SoC:     {min_soc:.0f}% — {max_soc:.0f}%"),
    ("SY08", "en", "Battery SoC:      {min_soc:.0f}% — {max_soc:.0f}%"),

    ("SY09", "nl", "Opgeladen:        {charged:.2f} kWh"),
    ("SY09", "en", "Charged:          {charged:.2f} kWh"),

    ("SY10", "nl", "Ontladen:         {discharged:.2f} kWh"),
    ("SY10", "en", "Discharged:       {discharged:.2f} kWh"),

    # ── ER: Foutmeldingen ────────────────────────────────────────────────────

    ("ER01", "nl", "Geen uurprognoses beschikbaar — optimizer overgeslagen"),
    ("ER01", "en", "No hourly forecasts available — optimizer skipped"),

    ("ER02", "nl", "Database verbinding mislukt: {error}"),
    ("ER02", "en", "Database connection failed: {error}"),

    ("ER03", "nl", "HA verbinding mislukt: {error}"),
    ("ER03", "en", "HA connection failed: {error}"),

    ("ER04", "nl", "Kon rapport niet opslaan: {error}"),
    ("ER04", "en", "Could not save report: {error}"),

    ("ER05", "nl", "HA-notificatie mislukt: {error}"),
    ("ER05", "en", "HA notification failed: {error}"),
]


def run_seed(db: DatabaseConnection, overwrite: bool = False) -> int:
    """
    Voer de seed in — sla over als key+taal al bestaat (tenzij overwrite=True).
    Run the seed — skip if key+language already exists (unless overwrite=True).

    Returns het aantal ingevoegde rijen / Returns number of inserted rows.
    """
    inserted = 0
    with db.cursor() as cur:
        for key, lang, text in SEED:
            if overwrite:
                cur.execute(
                    "REPLACE INTO translation_strings (string_key, language, text) "
                    "VALUES (%s, %s, %s)",
                    (key, lang, text)
                )
                inserted += 1
            else:
                cur.execute(
                    "INSERT IGNORE INTO translation_strings (string_key, language, text) "
                    "VALUES (%s, %s, %s)",
                    (key, lang, text)
                )
                inserted += cur.rowcount

    logger.info(f"[seed_translations] {inserted} vertalingen ingevoegd / translations inserted")
    return inserted
