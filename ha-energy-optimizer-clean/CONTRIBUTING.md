# Contributing / Bijdragen

Contributions are very welcome — especially translations, inverter drivers and energy providers.

## Adding a translation
1. Copy `ha-energy-optimizer/translations/en.json` to `ha-energy-optimizer/translations/xx.json`
2. Translate all values (keep keys exactly as-is)
3. Check context hints in `_context.json` — "charge" means battery charging, never a fee
4. Submit a pull request

## Adding an inverter driver
1. Create `ha-energy-optimizer/inverter/yourbrand.py`
2. Extend `BaseInverterDriver` from `inverter/base.py`
3. Implement: `connect()`, `disconnect()`, `read_status()`, `set_charge_power()`, `set_discharge_power()`, `set_idle()`
4. Register in `inverter/__init__.py`
5. Submit a pull request

## Adding an energy provider
1. Create `ha-energy-optimizer/providers/yourprovider.py`
2. Extend `BaseEnergyProvider` from `providers/base.py`
3. Implement `get_hourly_prices(target_date) → list[EnergyPrice]`
4. Register in `providers/__init__.py`
5. Submit a pull request

## Code style
- Python 3.11+
- Bilingual comments: English first, Dutch second
- Use `Decimal` for all financial and energy values (never `float`)
