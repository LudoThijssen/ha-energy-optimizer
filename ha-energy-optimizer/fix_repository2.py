#!/usr/bin/env python3
# fix_repository2.py — fixes single-quote multiline SQL in get_latest
from pathlib import Path

repo_path = Path(__file__).parent / "database" / "repository.py"
content = repo_path.read_text(encoding="utf-8")

old = '''    def get_latest(self) -> BatteryStatus | None:
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT id, measured_at, soc_pct, power_kw, voltage_v,
                       temperature_c, energy_charged_kwh,
                       energy_discharged_kwh, cycle_count
                FROM battery_status
                ORDER BY measured_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            return BatteryStatus(**row) if row else None'''

new = '''    def get_latest(self) -> BatteryStatus | None:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT id, measured_at, soc_pct, power_kw, voltage_v,
                       temperature_c, energy_charged_kwh,
                       energy_discharged_kwh, cycle_count
                FROM battery_status
                ORDER BY measured_at DESC LIMIT 1
            """)
            row = cur.fetchone()
            return BatteryStatus(**row) if row else None'''

if old in content:
    content = content.replace(old, new)
    repo_path.write_text(content, encoding="utf-8")
    print("[OK] Fixed — battery query now uses triple quotes")
else:
    print("[WARN] Pattern not found — checking current state:")
    lines = content.split('\n')
    for i, line in enumerate(lines[76:88], start=77):
        print(f"  {i}: {repr(line)}")
