from datetime import datetime
from decimal import Decimal
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from .base import BaseInverterDriver
from database.models import BatteryStatus
from collectors.base import CollectorTemporaryError, CollectorConfigError

# Register addresses — pas aan voor jouw inverter/batterij merk
# Deze adressen zijn voorbeeldwaarden; raadpleeg het Modbus-register document
# van jouw specifieke apparaat.
REG_SOC             = 0x0100   # State of charge in %
REG_POWER           = 0x0101   # Batterijvermogen in W (signed: + = laden)
REG_VOLTAGE         = 0x0102   # Spanning in 0.1V
REG_TEMPERATURE     = 0x0103   # Temperatuur in 0.1°C
REG_CHARGE_CONTROL  = 0x0200   # 0=idle, 1=laden, 2=ontladen
REG_CHARGE_POWER    = 0x0201   # Gewenst laadvermogen in W
REG_DISCHARGE_POWER = 0x0202   # Gewenst ontlaadvermogen in W


class ModbusDriver(BaseInverterDriver):
    """
    Modbus TCP driver voor inverter/batterij communicatie.

    driver_config verwacht (als JSON in inverter_info.driver_config):
        host:     str   — IP-adres of hostnaam van de inverter
        port:     int   — Modbus TCP poort (standaard 502)
        slave_id: int   — Modbus slave/unit ID (standaard 1)
    """

    def __init__(self, cfg: dict):
        self._host     = cfg.get("host", "")
        self._port     = int(cfg.get("port", 502))
        self._slave_id = int(cfg.get("slave_id", 1))
        self._client: ModbusTcpClient | None = None

        if not self._host:
            raise CollectorConfigError(
                "Modbus host ontbreekt in inverter_info.driver_config"
            )

    def connect(self) -> None:
        self._client = ModbusTcpClient(
            host=self._host,
            port=self._port,
            timeout=5,
        )
        if not self._client.connect():
            raise CollectorTemporaryError(
                f"Kan geen Modbus-verbinding maken met {self._host}:{self._port}"
            )

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def read_status(self) -> BatteryStatus:
        soc         = self._read_register(REG_SOC)
        power_w     = self._read_register_signed(REG_POWER)
        voltage_raw = self._read_register(REG_VOLTAGE)
        temp_raw    = self._read_register(REG_TEMPERATURE)

        return BatteryStatus(
            measured_at=datetime.now(),
            soc_pct=Decimal(str(soc)),
            power_kw=Decimal(str(power_w / 1000)),
            voltage_v=Decimal(str(voltage_raw / 10)) if voltage_raw else None,
            temperature_c=Decimal(str(temp_raw / 10)) if temp_raw else None,
        )

    def set_charge_power(self, kw: float) -> None:
        power_w = int(kw * 1000)
        self._write_register(REG_CHARGE_POWER, power_w)
        self._write_register(REG_CHARGE_CONTROL, 1)

    def set_discharge_power(self, kw: float) -> None:
        power_w = int(kw * 1000)
        self._write_register(REG_DISCHARGE_POWER, power_w)
        self._write_register(REG_CHARGE_CONTROL, 2)

    def set_idle(self) -> None:
        self._write_register(REG_CHARGE_CONTROL, 0)

    def _read_register(self, address: int) -> int:
        self._check_connected()
        result = self._client.read_holding_registers(
            address, count=1, slave=self._slave_id
        )
        if result.isError():
            raise CollectorTemporaryError(
                f"Modbus leesfout op register {hex(address)}"
            )
        return result.registers[0]

    def _read_register_signed(self, address: int) -> int:
        value = self._read_register(address)
        return value if value < 32768 else value - 65536

    def _write_register(self, address: int, value: int) -> None:
        self._check_connected()
        result = self._client.write_register(
            address, value, slave=self._slave_id
        )
        if result.isError():
            raise CollectorTemporaryError(
                f"Modbus schrijffout op register {hex(address)}"
            )

    def _check_connected(self) -> None:
        if not self._client or not self._client.is_socket_open():
            raise CollectorTemporaryError(
                "Modbus niet verbonden — roep connect() eerst aan"
            )
