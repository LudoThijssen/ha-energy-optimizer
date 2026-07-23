#
# name:          timeslot.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/config/timeslot.py
# part version:  p_v0.1
# altered:       2026-07-22
#
# Centrale definitie van de schema-tijdstap (kwartier). Alle modulen die
# per-slot leren of plannen gebruiken deze constanten/functies i.p.v. eigen
# uur-aannames, zodat de tijdstap op één plek staat gedefinieerd en niet
# opnieuw door alle bestanden gezocht hoeft te worden als dit ooit weer
# verandert.
#
# Central definition of the schedule time step (quarter hour). All modules
# that learn or plan per slot use these constants/functions instead of their
# own hour assumptions, so the time step lives in a single place and doesn't
# need to be hunted down across every file if it ever changes again.
#
# Ludo's formule / Ludo's formula:
#   rekenfactor = schema_tijdstap / meetinterval
#   conversion_factor = schedule_step / measurement_interval
# Bij 1 uur-loop: 4 waarden optellen, /4. Bij 2 uur-loop: 8 optellen, /8.
# Generiek: SLOT_TO_MEASUREMENT_FACTOR hieronder dekt elke combinatie af.

from datetime import datetime
from decimal import Decimal

# Lengte van één schema-slot in minuten. Dit is de ENIGE plek die moet
# veranderen om de granulariteit van het hele systeem aan te passen.
# Length of one schedule slot in minutes. This is the ONLY place that needs
# to change to adjust the granularity of the entire system.
SLOT_MINUTES = 15

# Meetinterval van ha_collector — blijft altijd 5 minuten, los van de
# schema-tijdstap (zie config.collectors.ha_interval_seconds in options.json).
# Measurement interval of ha_collector — always stays 5 minutes, independent
# of the schedule time step (see config.collectors.ha_interval_seconds).
MEASUREMENT_MINUTES = 5

# Aantal slots per uur / per dag.
# Number of slots per hour / per day.
SLOTS_PER_HOUR = 60 // SLOT_MINUTES        # 4 bij 15 min
SLOTS_PER_DAY = 24 * SLOTS_PER_HOUR        # 96 bij 15 min

# Rekenfactor: hoeveel meetintervallen (5 min) passen er in één schema-slot.
# Gebruikt om een "per meetinterval"-waarde (zoals SolarLearner/
# ConsumptionLearner die opslaan) om te rekenen naar "per schema-slot".
# Conversion factor: how many measurement intervals (5 min) fit in one
# schedule slot. Used to convert a "per measurement interval" value (as
# stored by SolarLearner/ConsumptionLearner) into a "per schedule slot" value.
SLOT_TO_MEASUREMENT_FACTOR = SLOT_MINUTES / MEASUREMENT_MINUTES  # 3 bij 15 min

# Aantal meetintervallen per uur (bij 5 min: 12). Dit is de factor die
# SolarLearner/ConsumptionLearner gebruiken om een "per meetinterval"-
# waarde om te rekenen naar een gemiddeld vermogen (kW). Deze factor hangt
# af van het MEETinterval, niet van de schema-tijdstap, en verandert dus
# NIET mee als SLOT_MINUTES wijzigt.
# Number of measurement intervals per hour (at 5 min: 12). This is the
# factor SolarLearner/ConsumptionLearner use to convert a "per measurement
# interval" value into an average power (kW). This factor depends on the
# MEASUREMENT interval, not the schedule step, so it does NOT change when
# SLOT_MINUTES changes.
MEASUREMENTS_PER_HOUR = 60 // MEASUREMENT_MINUTES  # 12 bij 5 min

# Rekenfactor voor kWh <-> kW-vermogen over precies één schema-slot.
# Bijv. bij 15 min: 1 kW gedurende 1 slot = 0,25 kWh.
# Conversion factor for kWh <-> kW power over exactly one schedule slot.
# E.g. at 15 min: 1 kW for 1 slot = 0.25 kWh.
# Decimal, niet float — decision_engine.py/engine.py rekenen overal met
# Decimal, en Decimal * float geeft een TypeError in Python.
# Decimal, not float — decision_engine.py/engine.py compute everywhere
# with Decimal, and Decimal * float raises a TypeError in Python.
SLOT_HOURS = Decimal(SLOT_MINUTES) / Decimal(60)


def slot_of_day(dt: datetime) -> int:
    """
    Bereken het slot-nummer binnen de dag (0..SLOTS_PER_DAY-1).
    Calculate the slot number within the day (0..SLOTS_PER_DAY-1).
    """
    return dt.hour * SLOTS_PER_HOUR + (dt.minute // SLOT_MINUTES)


def slot_start(dt: datetime) -> datetime:
    """
    Rond een tijdstip af naar het begin van zijn schema-slot.
    Round a timestamp down to the start of its schedule slot.
    """
    minute = (dt.minute // SLOT_MINUTES) * SLOT_MINUTES
    return dt.replace(minute=minute, second=0, microsecond=0)


def slots_for_duration(minutes: int) -> int:
    """
    Aantal schema-slots dat in de gegeven duur past (naar boven afgerond).
    Number of schedule slots that fit in the given duration (rounded up).
    """
    return -(-minutes // SLOT_MINUTES)  # ceiling division
