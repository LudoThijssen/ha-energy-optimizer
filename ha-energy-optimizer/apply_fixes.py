#!/usr/bin/env python3
# apply_fixes.py
#
# Applies two fixes to the project:
# Paste twee fixes toe op het project:
#
# Fix 1: strategy.py — parse driver_config JSON string from database
# Fix 2: reporter.py — suppress HA notifications when HA is unreachable
#
# Run from the ha-energy-optimizer subfolder:
# Uitvoeren vanuit de ha-energy-optimizer submap:
#   python apply_fixes.py

import re
from pathlib import Path

BASE = Path(__file__).parent

# ── Fix 1: strategy.py — parse driver_config as JSON ─────────────────────────
print("Applying Fix 1: strategy.py — JSON parsing for driver_config...")

strategy_path = BASE / "optimizer" / "strategy.py"
content = strategy_path.read_text(encoding="utf-8")

old = '''    if prov and prov.get("driver_config"):
        vat_pct = Decimal(str(prov["driver_config"].get("vat_pct", 21.0)))'''

new = '''    if prov and prov.get("driver_config"):
        import json as _json
        drv_cfg = prov["driver_config"]
        if isinstance(drv_cfg, str):
            try:
                drv_cfg = _json.loads(drv_cfg)
            except Exception:
                drv_cfg = {}
        vat_pct = Decimal(str(drv_cfg.get("vat_pct", 21.0)))'''

if old in content:
    content = content.replace(old, new)
    strategy_path.write_text(content, encoding="utf-8")
    print("  [OK] strategy.py patched")
elif new in content:
    print("  [OK] strategy.py already patched — skipping")
else:
    print("  [WARN] Could not find target text in strategy.py")
    print("         Please check the file manually")

# ── Fix 2: reporter.py — catch HA notification errors gracefully ──────────────
print("Applying Fix 2: reporter.py — graceful HA notification failure...")

reporter_path = BASE / "reporter" / "reporter.py"
content = reporter_path.read_text(encoding="utf-8")

old_notify = '''    def _notify(self, message: str, title: str = "HA Energy Optimizer") -> None:
        try:
            requests.post(
                f"{self._ha_url}/api/services/notify/notify",
                json={"title": title, "message": message},
                headers=self._headers,
                timeout=5,
            )
        except Exception as e:
            logger.warning(f"HA-notificatie mislukt: {e}")'''

new_notify = '''    def _notify(self, message: str, title: str = "HA Energy Optimizer") -> None:
        """
        Send notification to Home Assistant.
        Verstuur melding naar Home Assistant.
        Fails silently when HA is unreachable (e.g. during local testing).
        Faalt stil als HA niet bereikbaar is (bijv. tijdens lokaal testen).
        """
        try:
            resp = requests.post(
                f"{self._ha_url}/api/services/notify/notify",
                json={"title": title, "message": message},
                headers=self._headers,
                timeout=5,
            )
            if resp.status_code not in (200, 201):
                logger.debug(f"HA notification returned {resp.status_code}")
        except requests.exceptions.ConnectionError:
            logger.debug("HA not reachable — notification skipped (local test?)")
        except requests.exceptions.Timeout:
            logger.debug("HA notification timeout — skipped")
        except Exception as e:
            logger.warning(f"HA notification failed / HA-notificatie mislukt: {e}")'''

if old_notify in content:
    content = content.replace(old_notify, new_notify)
    reporter_path.write_text(content, encoding="utf-8")
    print("  [OK] reporter.py patched")
elif new_notify in content:
    print("  [OK] reporter.py already patched — skipping")
else:
    print("  [WARN] Could not find target text in reporter.py")
    print("         The reporter will still work, but may show HA warnings")

print("\nAll fixes applied. Run python test_local.py to verify.")
print("Alle fixes toegepast. Voer python test_local.py uit om te controleren.")
