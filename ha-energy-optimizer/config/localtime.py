#
# name:          localtime.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/config/localtime.py
# part version:  p_v0.1
# altered:       2026-07-28
#
# now_local() — de enige juiste manier om "nu" op te vragen in deze add-on.
#
# WAAROM DIT BESTAAT:
# HA-add-on containers kunnen niet worden vertrouwd om de systeemklok op de
# juiste tijdzone te hebben staan. Dit is een bekend, actueel Supervisor-
# probleem (home-assistant/supervisor#5811): sommige add-on images blijven
# op UTC vastzitten ondanks een correct doorgegeven TZ-omgevingsvariabele,
# omdat Python's datetime.now() de tijdzone leest via /etc/localtime in de
# container — en die kan nog op UTC staan zelfs als TZ correct gezet is.
# Andere add-ons op hetzelfde systeem laten wél de juiste lokale tijd zien,
# dus dit is per image/basis-image inconsistent en dus niet te vertrouwen.
#
# Deze functie omzeilt dat probleem volledig: onafhankelijk van wat de
# container's systeemklok zegt, dwingt zoneinfo Europe/Amsterdam af.
#
# WHY THIS EXISTS:
# HA add-on containers cannot be trusted to have the system clock set to
# the correct timezone. This is a known, current Supervisor issue
# (home-assistant/supervisor#5811): some add-on images stay stuck on UTC
# despite a correctly-passed TZ environment variable, because Python's
# datetime.now() reads the timezone via /etc/localtime inside the
# container — which can still be UTC even when TZ is set correctly. Other
# add-ons on the same system DO show the correct local time, so this is
# inconsistent per image/base-image and therefore not to be trusted.
#
# This function sidesteps that entirely: regardless of what the
# container's system clock says, zoneinfo forces Europe/Amsterdam.
#
# BELANGRIJK — waarom dit een NAÏEVE datetime teruggeeft (geen tzinfo):
# De rest van de codebase (database, dict-sleutels zoals `prices{}`,
# vergelijkingen als `wh.forecast.slot_start.date()`) werkt overal met
# naïeve datetimes. Een tijdzone-bewuste datetime teruggeven zou daar
# overal `TypeError: can't compare offset-naive and offset-aware
# datetimes` opleveren. now_local() geeft daarom de juiste kloktijd terug,
# maar zonder tzinfo — een "correcte naïeve datetime", geen "tijdzone-
# bewuste datetime".
#
# IMPORTANT — why this returns a NAIVE datetime (no tzinfo):
# The rest of the codebase (database, dict keys like `prices{}`,
# comparisons like `wh.forecast.slot_start.date()`) works with naive
# datetimes throughout. Returning a timezone-aware datetime would cause
# `TypeError: can't compare offset-naive and offset-aware datetimes`
# everywhere. now_local() therefore returns the correct wall-clock time,
# but without tzinfo — a "correct naive datetime", not a "timezone-aware
# datetime".
#
# Toekomstig instelbaar via config.location.timezone (nu nog hardcoded —
# deze installatie draait op precies één locatie).
# Future-configurable via config.location.timezone (currently hardcoded —
# this installation runs at exactly one location).
#
# p_v0.1 addendum: price_collector.py had dit probleem al eerder correct
# opgelost, met exact dit patroon (config.location.timezone via ZoneInfo,
# terugval op "Europe/Amsterdam"). now_local() accepteert daarom optioneel
# een tz_name-parameter, zodat aanroepers mét toegang tot AppConfig die
# kunnen doorgeven, en die ene, al bestaande, correcte aanpak centraliseert
# i.p.v. ernaast een tweede implementatie te laten bestaan.
#
# p_v0.1 addendum: price_collector.py had already correctly solved this
# problem before, with exactly this pattern (config.location.timezone via
# ZoneInfo, falling back to "Europe/Amsterdam"). now_local() therefore
# optionally accepts a tz_name parameter, so callers WITH access to
# AppConfig can pass it through, centralizing that one, already-correct
# approach instead of letting a second implementation exist alongside it.

from datetime import datetime
from zoneinfo import ZoneInfo

_DEFAULT_TZ_NAME = "Europe/Amsterdam"


def now_local(tz_name: str | None = None) -> datetime:
    """
    Geef de huidige lokale kloktijd terug, als naïeve datetime — ongeacht
    de tijdzone-instelling van de container zelf.

    Return the current local wall-clock time, as a naive datetime —
    regardless of the container's own timezone setting.

    Args:
        tz_name: IANA-tijdzonenaam (bijv. "Europe/Amsterdam"). Geef
                 config.location.timezone door als die beschikbaar is;
                 anders wordt de hardcoded terugval gebruikt.
                 IANA timezone name (e.g. "Europe/Amsterdam"). Pass
                 config.location.timezone if available; otherwise the
                 hardcoded fallback is used.
    """
    tz = ZoneInfo(tz_name or _DEFAULT_TZ_NAME)
    return datetime.now(tz).replace(tzinfo=None)
