#
# name:          offgrid_monitor.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/collectors/offgrid_monitor.py
# part version:  p_v0.1
# altered:       2026-07-30
#
# Bewaakt of de installatie off-grid is (netuitval) en:
#   1. Slaat het resultaat op in system_config.offgrid_active, zodat
#      decision_engine.py de optimizer-beslissingen kan pauzeren.
#   2. Schrijft een alarm-entiteit terug naar Home Assistant (via
#      POST /api/states/<entity_id> — dit creëert de entiteit vanzelf als
#      die nog niet bestaat), zodat eigen HA-automations (deurbel,
#      geluidspatroon, wat dan ook) daarop kunnen reageren.
#
# Draait op hetzelfde ritme als ha_collector.py (config.collectors.
# ha_interval_seconds, standaard 5 min) — los van de 15-minuten optimizer-
# cyclus, want een stroomstoring moet je snel weten, niet pas bij de
# volgende herberekening.
#
# Monitors whether the installation is off-grid (grid outage) and:
#   1. Stores the result in system_config.offgrid_active, so
#      decision_engine.py can pause optimizer decisions.
#   2. Writes an alarm entity back to Home Assistant (via
#      POST /api/states/<entity_id> — this creates the entity automatically
#      if it doesn't exist yet), so the user's own HA automations
#      (doorbell, sound pattern, whatever) can react to it.
#
# Runs on the same cadence as ha_collector.py (config.collectors.
# ha_interval_seconds, default 5 min) — separate from the 15-minute
# optimizer cycle, since a power outage needs to be known quickly, not
# only at the next recalculation.
#
# Detectie / Detection:
#   - Primair: een geconfigureerde entiteit (bijv. de status van de
#     off-grid schakelaar zelf) — heeft voorrang als beschikbaar.
#   - Terugval: als primair niet geconfigureerd of niet leesbaar is, wordt
#     gekeken of de terugval-entiteit (bijv. de P1-meter sensor)
#     "unavailable"/"unknown" is — een zwakker signaal, want dat kan ook
#     door andere oorzaken (wifi, HA-herstart) komen.
#   - Geen van beide beschikbaar: veiligheidshalve NIET als off-grid
#     aanmerken (geen vals alarm), wel loggen.
#
#   - Primary: a configured entity (e.g. the off-grid switch's own status)
#     — takes precedence if available.
#   - Fallback: if primary isn't configured or unreadable, checks whether
#     the fallback entity (e.g. the P1 meter sensor) is
#     "unavailable"/"unknown" — a weaker signal, since that can also
#     happen for other reasons (wifi, HA restart).
#   - Neither available: for safety, do NOT flag as off-grid (avoid false
#     alarm), but do log it.
#
# Alleen actief als system_config.has_offgrid_switch aan staat (vinkje op
# de Systeem-pagina) — anders doet deze collector niets.
# Only active if system_config.has_offgrid_switch is on (checkbox on the
# System page) — otherwise this collector does nothing.

import logging
import requests
from database.connection import DatabaseConnection
from config.config import AppConfig
from config.localtime import now_local
from .base import BaseCollector

logger = logging.getLogger(__name__)

_DEFAULT_ALARM_ENTITY = "binary_sensor.ha_energy_optimizer_offgrid"


class OffgridMonitor(BaseCollector):
    name = "offgrid_monitor"

    def __init__(self, db: DatabaseConnection, reporter, config: AppConfig):
        super().__init__(reporter)
        self._db = db
        self._config = config
        self._base_url = f"http://{config.ha.host}:{config.ha.port}"
        self._headers = {
            "Authorization": f"Bearer {config.ha.token}",
            "Content-Type": "application/json",
        }

    def _now(self):
        tz_name = getattr(self._config.location, "timezone", "Europe/Amsterdam")
        return now_local(tz_name)

    def collect(self) -> None:
        cfg = self._load_config()
        if not cfg or not cfg.get("has_offgrid_switch"):
            return  # feature uit — niets doen / feature off — do nothing

        is_offgrid, reason = self._detect(cfg)
        self._save_state(cfg["id"], is_offgrid)
        self._write_alarm_entity(cfg, is_offgrid, reason)

    def _load_config(self) -> "dict | None":
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT id, has_offgrid_switch, offgrid_primary_entity_id, "
                "offgrid_primary_off_value, offgrid_fallback_entity_id, "
                "offgrid_alarm_entity_id, offgrid_active "
                "FROM system_config ORDER BY id DESC LIMIT 1"
            )
            return cur.fetchone()

    def _detect(self, cfg: dict) -> tuple[bool, str]:
        """
        Returns (is_offgrid, reden/reason) — reden is voor logging/alarm-
        attributen, niet voor beslislogica.
        Returns (is_offgrid, reason) — reason is for logging/alarm
        attributes, not for decision logic.
        """
        primary_id = cfg.get("offgrid_primary_entity_id")
        if primary_id:
            state = self._fetch_state(primary_id)
            if state is not None:
                off_value = (cfg.get("offgrid_primary_off_value") or "off").strip().lower()
                is_offgrid = state.strip().lower() == off_value
                return is_offgrid, f"primair ({primary_id}={state})"
            logger.debug(
                f"[offgrid_monitor] Primaire entiteit {primary_id} niet "
                f"leesbaar, terugval op fallback-entiteit indien geconfigureerd"
            )

        fallback_id = cfg.get("offgrid_fallback_entity_id")
        if fallback_id:
            state = self._fetch_state(fallback_id)
            if state is None:
                return True, f"terugval ({fallback_id} onbereikbaar/unavailable)"
            return False, f"terugval ({fallback_id}={state})"

        logger.warning(
            "[offgrid_monitor] Geen bruikbare detectie-entiteit "
            "(primair niet leesbaar, geen terugval geconfigureerd) — "
            "off-grid status kan niet bepaald worden, blijft op 'nee' "
            "staan om vals alarm te voorkomen"
        )
        return False, "onbekend — geen entiteit beschikbaar"

    def _fetch_state(self, entity_id: str) -> "str | None":
        """
        Haal de RUWE tekst-status van een entiteit op (niet numeriek zoals
        ha_collector._fetch_entity — off-grid statussen zijn meestal
        on/off/unavailable, geen getallen).
        Fetch the RAW text state of an entity (not numeric like
        ha_collector._fetch_entity — off-grid statuses are usually
        on/off/unavailable, not numbers).
        """
        url = f"{self._base_url}/api/states/{entity_id}"
        try:
            response = requests.get(url, headers=self._headers, timeout=5)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            state = response.json().get("state")
            if state in (None, "unavailable", "unknown"):
                return None
            return str(state)
        except requests.RequestException as e:
            logger.debug(f"[offgrid_monitor] Kon {entity_id} niet lezen: {e}")
            return None

    def _save_state(self, config_id: int, is_offgrid: bool) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                "UPDATE system_config SET offgrid_active=%(v)s, "
                "offgrid_last_checked_at=%(now)s WHERE id=%(id)s",
                {"v": 1 if is_offgrid else 0, "now": self._now(), "id": config_id}
            )

    def _write_alarm_entity(self, cfg: dict, is_offgrid: bool, reason: str) -> None:
        """
        Zet (en creëert indien nodig) de alarm-entiteit in HA via de
        states-API. Dit werkt zonder aparte registratie — HA maakt de
        entiteit vanzelf aan bij de eerste POST.

        Sets (and creates if needed) the alarm entity in HA via the
        states API. This works without separate registration — HA creates
        the entity automatically on the first POST.
        """
        entity_id = cfg.get("offgrid_alarm_entity_id") or _DEFAULT_ALARM_ENTITY
        url = f"{self._base_url}/api/states/{entity_id}"
        payload = {
            "state": "on" if is_offgrid else "off",
            "attributes": {
                "friendly_name": "HA Energy Optimizer — Netuitval",
                "device_class": "problem",
                "icon": "mdi:transmission-tower-off" if is_offgrid else "mdi:transmission-tower",
                "reason": reason,
            },
        }
        try:
            response = requests.post(url, headers=self._headers, json=payload, timeout=5)
            response.raise_for_status()
            if is_offgrid:
                logger.warning(
                    f"[offgrid_monitor] OFF-GRID gedetecteerd — {reason}. "
                    f"Alarm-entiteit {entity_id} op 'on' gezet."
                )
        except requests.RequestException as e:
            # p_v0.1: als dit faalt (bijv. HA niet bereikbaar of token
            # ongeldig — zelfde token als ha_collector.py, dus meestal
            # geen apart rechtenprobleem), kan de entiteit niet automatisch
            # aangemaakt worden. Duidelijke instructie in de log zodat de
            # gebruiker het handmatig kan oplossen.
            # p_v0.1: if this fails (e.g. HA unreachable or invalid token
            # — same token as ha_collector.py, so usually not a separate
            # permissions issue), the entity can't be created
            # automatically. Clear instruction in the log so the user can
            # resolve it manually.
            logger.error(
                f"[offgrid_monitor] Kon alarm-entiteit {entity_id} niet "
                f"schrijven naar HA: {e}. Los dit op door in HA zelf een "
                f"input_boolean of template-entiteit met exact deze "
                f"entity_id aan te maken ('{entity_id}'), of controleer "
                f"of het HA-token en adres in de add-on instellingen "
                f"nog kloppen."
            )
