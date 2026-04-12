#!/usr/bin/env python3
# fix_repository.py
#
# Fixes the syntax error in repository.py caused by the previous fix script.
# Run from ha-energy-optimizer subfolder:
#   python fix_repository.py

from pathlib import Path

BASE = Path(__file__).parent
repo_path = BASE / "database" / "repository.py"

print("Reading repository.py...")
content = repo_path.read_text(encoding="utf-8")

# Show lines around line 80 for diagnosis
lines = content.split('\n')
print(f"Total lines: {len(lines)}")
print("Lines 75-90:")
for i, line in enumerate(lines[74:90], start=75):
    print(f"  {i}: {repr(line)}")

print()

# Fix the broken BatteryStatus query — the fallback left a broken string
# Look for the malformed query and replace it
broken_patterns = [
    # Pattern 1: triple quote mess
    ('""""', '"""'),
]

fixed = False
for old, new in broken_patterns:
    if old in content:
        content = content.replace(old, new)
        print(f"Fixed pattern: {repr(old)} → {repr(new)}")
        fixed = True

# Also fix the battery query which may have gotten mangled
old_battery_broken = '''                SELECT id, measured_at, soc_pct, power_kw, voltage_v,
                       temperature_c, energy_charged_kwh,
                       energy_discharged_kwh, cycle_count
                FROM battery_status
                ORDER BY measured_at DESC LIMIT 1""""'''

new_battery_clean = '''                SELECT id, measured_at, soc_pct, power_kw, voltage_v,
                       temperature_c, energy_charged_kwh,
                       energy_discharged_kwh, cycle_count
                FROM battery_status
                ORDER BY measured_at DESC LIMIT 1"""'''

if old_battery_broken in content:
    content = content.replace(old_battery_broken, new_battery_clean)
    print("Fixed battery query triple-quote")
    fixed = True

if fixed:
    repo_path.write_text(content, encoding="utf-8")
    print("\nFixed and saved!")
else:
    print("\nNo pattern found — showing full lines 70-95 for manual diagnosis:")
    for i, line in enumerate(lines[69:95], start=70):
        print(f"  {i}: {repr(line)}")
