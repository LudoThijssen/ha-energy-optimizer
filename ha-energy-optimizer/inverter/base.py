from abc import ABC, abstractmethod
from database.models import BatteryStatus


class BaseInverterDriver(ABC):
    """
    Abstracte interface voor alle inverter-drivers.
    Elke driver implementeert deze methoden voor zijn eigen protocol.
    """

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def read_status(self) -> BatteryStatus: ...

    @abstractmethod
    def set_charge_power(self, kw: float) -> None: ...

    @abstractmethod
    def set_discharge_power(self, kw: float) -> None: ...

    @abstractmethod
    def set_idle(self) -> None: ...

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()
