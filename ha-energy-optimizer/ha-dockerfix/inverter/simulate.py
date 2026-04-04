# inverter/simulate.py
#
# Simulation inverter driver — safe for testing without real hardware.
# Simulatie-inverterdiver — veilig voor testen zonder echte hardware.
#
# This driver does NOT send any commands to a real inverter.
# It logs what it would do and returns realistic simulated values.
# Deze driver stuurt GEEN commando's naar een echte inverter.
# Hij logt wat hij zou doen en geeft realistische gesimuleerde waarden terug.
#
# Enable by setting driver = 'simulate' in inverter_info.driver_config.
# Activeer door driver = 'simulate' in te stellen in inverter_info.driver_config.

import logging
from datetime import datetime
from decimal import Decimal

from .base import BaseInverterDriver
from database.models import BatteryStatus

logger = logging.getLogger(__name__)


class SimulateDriver(BaseInverterDriver):
    """
    Simulated inverter driver for local and HA testing.
    Gesimuleerde inverterdiver voor lokaal en HA-testen.

    Simulates a battery that responds to charge/discharge commands
    by updating an internal state — no real hardware required.
    Simuleert een batterij die reageert op laad-/ontlaadcommando's
    door een interne status bij te houden — geen echte hardware nodig.

    driver_config options / driver_config opties:
        initial_soc_pct:  float  — starting state of charge (default 65.0)
        capacity_kwh:     float  — simulated capacity in kWh (default 10.0)
        temperature_c:    float  — simulated temperature (default 22.0)
    """

    def __init__(self, cfg: dict):
        self._soc_pct      = Decimal(str(cfg.get("initial_soc_pct", 65.0)))
        self._capacity_kwh = Decimal(str(cfg.get("capacity_kwh", 10.0)))
        self._temperature  = Decimal(str(cfg.get("temperature_c", 22.0)))
        self._power_kw     = Decimal("0")
        self._connected    = False
        self._cycle_count  = 0
        logger.info(
            f"[simulate] Driver initialized — "
            f"SoC: {self._soc_pct}%, capacity: {self._capacity_kwh} kWh / "
            f"Driver geïnitialiseerd — laadtoestand: {self._soc_pct}%"
        )

    def connect(self) -> None:
        self._connected = True
        logger.info("[simulate] Connected to simulated inverter / Verbonden met gesimuleerde inverter")

    def disconnect(self) -> None:
        self._connected = False
        logger.info("[simulate] Disconnected / Verbinding verbroken")

    def read_status(self) -> BatteryStatus:
        """
        Return simulated battery status.
        Geef gesimuleerde batterijstatus terug.
        """
        status = BatteryStatus(
            measured_at=datetime.now(),
            soc_pct=self._soc_pct,
            power_kw=self._power_kw,
            temperature_c=self._temperature,
            voltage_v=Decimal("48.0") + (self._soc_pct / 100 * Decimal("6.0")),
            cycle_count=self._cycle_count,
        )
        logger.debug(
            f"[simulate] Status: SoC {self._soc_pct:.1f}%, "
            f"power {self._power_kw:.2f} kW, temp {self._temperature:.1f}°C"
        )
        return status

    def set_charge_power(self, kw: float) -> None:
        """
        Simulate charging at the given power.
        Simuleer laden op het opgegeven vermogen.
        Updates SoC based on 1-hour equivalent energy.
        Werkt laadtoestand bij op basis van 1-uur equivalent energie.
        """
        self._power_kw = Decimal(str(kw))
        # Simulate 5-minute interval update / Simuleer 5-minuten interval update
        energy_kwh    = self._power_kw * Decimal("5") / Decimal("60")
        efficiency    = Decimal("0.75")
        delta_pct     = energy_kwh * efficiency / self._capacity_kwh * 100
        self._soc_pct = min(Decimal("95"), self._soc_pct + delta_pct)
        logger.info(
            f"[simulate] CHARGE {kw:.2f} kW → SoC now {self._soc_pct:.1f}% / "
            f"OPLADEN {kw:.2f} kW → laadtoestand nu {self._soc_pct:.1f}%"
        )

    def set_discharge_power(self, kw: float) -> None:
        """
        Simulate discharging at the given power.
        Simuleer ontladen op het opgegeven vermogen.
        """
        self._power_kw = Decimal(str(-kw))
        energy_kwh    = Decimal(str(kw)) * Decimal("5") / Decimal("60")
        efficiency    = Decimal("0.75")
        delta_pct     = energy_kwh / efficiency / self._capacity_kwh * 100
        self._soc_pct = max(Decimal("10"), self._soc_pct - delta_pct)
        self._cycle_count += 1
        logger.info(
            f"[simulate] DISCHARGE {kw:.2f} kW → SoC now {self._soc_pct:.1f}% / "
            f"ONTLADEN {kw:.2f} kW → laadtoestand nu {self._soc_pct:.1f}%"
        )

    def set_idle(self) -> None:
        """Stop all battery activity. / Stop alle batterijactiviteit."""
        self._power_kw = Decimal("0")
        logger.info("[simulate] IDLE — battery resting / batterij rust")
