# name:          validators.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/config/validators.py
# part version:  p_v0.3
# altered:       2026-06-21

def validate_time(value: str, field_name: str) -> None:
    try:
        parts = value.split(":")
        assert len(parts) == 2
        h, m = int(parts[0]), int(parts[1])
        assert 0 <= h <= 23 and 0 <= m <= 59
    except (ValueError, AssertionError):
        raise ValueError(
            f"Ongeldige tijd in '{field_name}': '{value}' "
            f"— verwacht formaat is HH:MM, bijvoorbeeld '14:15'"
        )


def validate_positive_int(value: int, field_name: str) -> None:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(
            f"'{field_name}' moet een positief geheel getal zijn, niet '{value}'"
        )
