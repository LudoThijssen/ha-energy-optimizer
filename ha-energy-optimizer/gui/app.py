# gui/app.py — v0.2.9
# 2026-04-24 13:11
# Configuration GUI — Flask web server with HA ingress support.
# Configuratie-GUI — Flask webserver met HA ingress-ondersteuning.

from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
import threading
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import DatabaseConnection
from config.config import AppConfig

app = Flask(__name__, template_folder="templates", static_folder="static")

OPTIONS_PATH = Path("/data/options.json")
if not OPTIONS_PATH.exists():
    OPTIONS_PATH = Path(__file__).parent.parent / "options.json"


def _load_options() -> dict:
    if OPTIONS_PATH.exists():
        with open(OPTIONS_PATH) as f:
            return json.load(f)
    return {}


def _save_options(data: dict) -> None:
    with open(OPTIONS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _get_db():
    try:
        config = AppConfig.load()
        return DatabaseConnection(config.database)
    except Exception:
        return None


def _url(endpoint: str, **kwargs) -> str:
    ingress_path = request.headers.get("X-Ingress-Path", "").rstrip("/")
    base = url_for(endpoint, **kwargs)
    if ingress_path:
        return ingress_path + base
    return base


@app.context_processor
def inject_globals():
    ingress_path = request.headers.get("X-Ingress-Path", "").rstrip("/")
    system_config = None
    try:
        db = _get_db()
        if db:
            with db.cursor() as cur:
                cur.execute("SELECT * FROM system_config ORDER BY id DESC LIMIT 1")
                system_config = cur.fetchone()
    except Exception:
        pass
    return {
        "nav_url": _url,
        "ingress_path": ingress_path,
        "system_config": system_config,
    }


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    options = _load_options()
    db = _get_db()

    inverter_ok = False
    provider_ok = False
    config_ok   = False
    entity_count = 0
    last_schedule = []

    if db:
        try:
            with db.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM inverter_info")
                inverter_ok = cur.fetchone()["c"] > 0

                cur.execute("SELECT COUNT(*) AS c FROM provider_config WHERE is_active=1")
                provider_ok = cur.fetchone()["c"] > 0

                cur.execute("SELECT COUNT(*) AS c FROM system_config")
                config_ok = cur.fetchone()["c"] > 0

                cur.execute("SELECT COUNT(*) AS c FROM ha_entity_map")
                entity_count = cur.fetchone()["c"]

                cur.execute("""
                    SELECT schedule_for, action, target_power_kw,
                           expected_saving, reason
                    FROM optimizer_schedule
                    WHERE DATE(schedule_for) = (
                        SELECT DATE(schedule_for)
                        FROM optimizer_schedule
                        ORDER BY schedule_for DESC
                        LIMIT 1
                    )
                    GROUP BY schedule_for
                    ORDER BY schedule_for
                    LIMIT 24
                """)
                last_schedule = cur.fetchall()
        except Exception:
            pass

    return render_template("index.html",
        options=options,
        inverter_ok=inverter_ok,
        provider_ok=provider_ok,
        config_ok=config_ok,
        entity_count=entity_count,
        last_schedule=last_schedule,
    )


# ── Action routes / Actie-routes ─────────────────────────────────────────────

@app.route("/action/run-optimizer", methods=["POST"])
def action_run_optimizer():
    """Run the optimizer immediately / Voer de optimizer direct uit."""
    def _run():
        try:
            config = AppConfig.load()
            db = DatabaseConnection(config.database)
            from reporter.reporter import Reporter
            from optimizer.engine import OptimizerEngine
            reporter = Reporter(db, config)
            engine = OptimizerEngine(db, reporter, config)
            engine.run()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Manual optimizer run failed: {e}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout=30)

    return jsonify({
        "ok": True,
        "message": "Optimizer started — check logs and refresh in 30s / "
                   "Optimizer gestart — bekijk logs en ververs over 30s"
    })


@app.route("/action/fetch-prices", methods=["POST"])
def action_fetch_prices():
    """Fetch energy prices immediately / Haal energieprijzen direct op."""
    try:
        config = AppConfig.load()
        db = DatabaseConnection(config.database)
        from reporter.reporter import Reporter
        from collectors.price_collector import PriceCollector
        reporter = Reporter(db, config)
        collector = PriceCollector(db, reporter, config)

        results = []
        # Try run_safe() which handles today + tomorrow internally
        # Probeer run_safe() die vandaag + morgen intern afhandelt
        ok = collector.run_safe()
        if ok:
            results.append("✓ prices fetched")
        else:
            # Fallback: try individual methods if they exist
            for method in ["fetch_today", "fetch_tomorrow", "run"]:
                fn = getattr(collector, method, None)
                if fn:
                    try:
                        r = fn()
                        results.append(f"{'✓' if r else '✗'} {method}")
                    except Exception as ex:
                        results.append(f"✗ {method}: {str(ex)[:30]}")

        # Count prices in DB
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM energy_prices")
            total = cur.fetchone()["c"]

        return jsonify({
            "ok": True,
            "message": f"Price fetch complete: {', '.join(results)}. "
                       f"Total in database: {total} rows / "
                       f"Prijzen opgehaald: {', '.join(results)}. "
                       f"Totaal in database: {total} rijen"
        })
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)})


@app.route("/action/test-entities", methods=["POST"])
def action_test_entities():
    """Read all mapped HA entities and return their current values."""
    try:
        config = AppConfig.load()
        db = _get_db()

        if not db:
            return jsonify({"ok": False, "message": "Database not connected / Database niet verbonden"})

        with db.cursor() as cur:
            cur.execute("SELECT internal_name, entity_id, unit FROM ha_entity_map ORDER BY internal_name")
            mappings = cur.fetchall()

        if not mappings:
            return jsonify({
                "ok": False,
                "message": "No entity mappings configured / Geen entiteitskoppelingen ingesteld",
                "entities": []
            })

        import requests as req
        ha_url = f"http://{config.ha.host}:{config.ha.port}"
        headers = {"Authorization": f"Bearer {config.ha.token}"}

        results = []
        for m in mappings:
            try:
                resp = req.get(
                    f"{ha_url}/api/states/{m['entity_id']}",
                    headers=headers,
                    timeout=5,
                )
                if resp.status_code == 200:
                    state = resp.json()
                    results.append({
                        "internal_name": m["internal_name"],
                        "entity_id":     m["entity_id"],
                        "value":         state.get("state", "unknown"),
                        "unit":          m.get("unit", ""),
                        "ok":            True,
                    })
                else:
                    results.append({
                        "internal_name": m["internal_name"],
                        "entity_id":     m["entity_id"],
                        "value":         f"HTTP {resp.status_code}",
                        "unit":          "",
                        "ok":            False,
                    })
            except Exception as e:
                results.append({
                    "internal_name": m["internal_name"],
                    "entity_id":     m["entity_id"],
                    "value":         str(e)[:40],
                    "unit":          "",
                    "ok":            False,
                })

        ok_count = sum(1 for r in results if r["ok"])
        return jsonify({
            "ok": ok_count > 0,
            "message": f"{ok_count}/{len(results)} entities reachable / entiteiten bereikbaar",
            "entities": results,
        })

    except Exception as e:
        return jsonify({"ok": False, "message": str(e), "entities": []})


# ── Configuration routes ──────────────────────────────────────────────────────

@app.route("/system", methods=["GET", "POST"])
def system():
    options = _load_options()
    if request.method == "POST":
        options["location"] = {
            "latitude":  float(request.form["latitude"]),
            "longitude": float(request.form["longitude"]),
            "timezone":  request.form["timezone"],
        }
        options["language"] = request.form["language"]
        has_grid    = 1 if "has_grid"    in request.form else 0
        has_solar   = 1 if "has_solar"   in request.form else 0
        has_gas     = 1 if "has_gas"     in request.form else 0
        has_battery = 1 if "has_battery" in request.form else 0
        has_heating = 1 if "has_heating" in request.form else 0

        options.setdefault("system", {}).update({
            "has_grid_connection":  bool(has_grid),
            "has_solar_panels":     bool(has_solar),
            "has_gas":              bool(has_gas),
            "has_battery":          bool(has_battery),
            "has_district_heating": bool(has_heating),
        })
        _save_options(options)

        # Also save to database / Sla ook op in database
        db = _get_db()
        if db:
            lat = float(request.form["latitude"])
            lng = float(request.form["longitude"])
            tz  = request.form["timezone"]
            lang = request.form["language"]
            with db.cursor() as cur:
                cur.execute("SELECT id FROM system_config ORDER BY id DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    cur.execute("""
                        UPDATE system_config SET
                            latitude=%(lat)s, longitude=%(lng)s,
                            has_grid_connection=%(grid)s,
                            has_solar_panels=%(solar)s,
                            has_gas=%(gas)s,
                            has_battery=%(battery)s,
                            has_district_heating=%(heating)s,
                            language=%(lang)s
                        WHERE id=%(id)s
                    """, {
                        "lat": lat, "lng": lng,
                        "grid": has_grid, "solar": has_solar,
                        "gas": has_gas, "battery": has_battery,
                        "heating": has_heating,
                        "lang": lang, "id": row["id"]
                    })
                else:
                    cur.execute("""
                        INSERT INTO system_config
                            (latitude, longitude, has_grid_connection,
                             has_solar_panels, has_gas, has_battery,
                             has_district_heating, language)
                        VALUES (%(lat)s, %(lng)s, %(grid)s, %(solar)s,
                                %(gas)s, %(battery)s, %(heating)s, %(lang)s)
                    """, {
                        "lat": lat, "lng": lng,
                        "grid": has_grid, "solar": has_solar,
                        "gas": has_gas, "battery": has_battery,
                        "heating": has_heating, "lang": lang
                    })

        return redirect(_url("system") + "?saved=1")
    return render_template("system.html", options=options,
                           saved=request.args.get("saved"))


@app.route("/database", methods=["GET", "POST"])
def database():
    options = _load_options()
    if request.method == "POST":
        options["database"] = {
            "host":     request.form["host"],
            "port":     int(request.form["port"]),
            "name":     request.form["name"],
            "user":     request.form["user"],
            "password": request.form["password"],
        }
        _save_options(options)
        return redirect(_url("database") + "?saved=1")
    return render_template("database.html", options=options,
                           saved=request.args.get("saved"), error=None)


@app.route("/database/test", methods=["POST"])
def test_database():
    data = request.json
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=data["host"], port=int(data["port"]),
            database=data["name"], user=data["user"],
            password=data["password"], connection_timeout=5,
        )
        conn.close()
        return jsonify({"ok": True, "message": "Verbinding geslaagd / Connection successful"})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)})


@app.route("/homeassistant", methods=["GET", "POST"])
def homeassistant():
    options = _load_options()
    if request.method == "POST":
        options["homeassistant"] = {
            "host":  request.form["host"],
            "port":  int(request.form["port"]),
            "token": request.form["token"],
        }
        _save_options(options)
        return redirect(_url("homeassistant") + "?saved=1")
    return render_template("homeassistant.html", options=options,
                           saved=request.args.get("saved"))


@app.route("/homeassistant/test", methods=["POST"])
def test_ha():
    data = request.json
    import requests as req
    try:
        resp = req.get(
            f"http://{data['host']}:{data['port']}/api/",
            headers={"Authorization": f"Bearer {data['token']}"},
            timeout=5,
        )
        if resp.status_code == 200:
            return jsonify({"ok": True, "message": "Verbinding geslaagd / Connection successful"})
        return jsonify({"ok": False, "message": f"HTTP {resp.status_code}"})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)})


@app.route("/inverter", methods=["GET", "POST"])
def inverter():
    options = _load_options()
    db = _get_db()
    inverter_row = None
    battery_row  = None

    if db:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM inverter_info ORDER BY id DESC LIMIT 1")
            inverter_row = cur.fetchone()
            cur.execute("SELECT * FROM battery_info ORDER BY id DESC LIMIT 1")
            battery_row = cur.fetchone()

    if request.method == "POST" and db:
        driver = request.form.get("driver", "simulate")
        if driver == "simulate":
            driver_cfg = {
                "initial_soc_pct": float(request.form.get("initial_soc", 65.0)),
                "capacity_kwh":    float(request.form.get("capacity_kwh", 10.0)),
                "temperature_c":   float(request.form.get("temperature_c", 22.0)),
            }
        else:
            driver_cfg = {
                "host":     request.form.get("modbus_host", ""),
                "port":     request.form.get("modbus_port", "502"),
                "slave_id": request.form.get("modbus_slave_id", "1"),
            }

        inv = {
            "brand":        request.form.get("brand"),
            "model":        request.form.get("model"),
            "driver":       driver,
            "cfg":          json.dumps(driver_cfg),
            "max_charge":   request.form.get("max_charge_kw"),
            "max_discharge":request.form.get("max_discharge_kw"),
        }
        bat = {
            "brand":         request.form.get("bat_brand"),
            "model":         request.form.get("bat_model"),
            "capacity_kwh":  request.form.get("capacity_kwh"),
            "usable_kwh":    request.form.get("usable_kwh"),
            "max_charge":    request.form.get("max_charge_kw"),
            "max_discharge": request.form.get("max_discharge_kw"),
            "min_soc":       request.form.get("min_soc", 10),
            "max_soc":       request.form.get("max_soc", 95),
        }

        with db.cursor() as cur:
            if inverter_row:
                cur.execute("""UPDATE inverter_info SET brand=%(brand)s, model=%(model)s,
                    driver=%(driver)s, driver_config=%(cfg)s,
                    max_charge_kw=%(max_charge)s, max_discharge_kw=%(max_discharge)s
                    WHERE id=%(id)s""", {**inv, "id": inverter_row["id"]})
            else:
                cur.execute("""INSERT INTO inverter_info
                    (brand, model, driver, driver_config, max_charge_kw, max_discharge_kw)
                    VALUES (%(brand)s, %(model)s, %(driver)s, %(cfg)s,
                    %(max_charge)s, %(max_discharge)s)""", inv)

            if battery_row:
                cur.execute("""UPDATE battery_info SET brand=%(brand)s, model=%(model)s,
                    capacity_kwh=%(capacity_kwh)s, usable_capacity_kwh=%(usable_kwh)s,
                    max_charge_kw=%(max_charge)s, max_discharge_kw=%(max_discharge)s,
                    working_charge_kw=%(max_charge)s, working_discharge_kw=%(max_discharge)s,
                    min_soc_pct=%(min_soc)s, max_soc_pct=%(max_soc)s
                    WHERE id=%(id)s""", {**bat, "id": battery_row["id"]})
            else:
                cur.execute("""INSERT INTO battery_info
                    (brand, model, capacity_kwh, usable_capacity_kwh,
                     max_charge_kw, max_discharge_kw,
                     working_charge_kw, working_discharge_kw,
                     min_soc_pct, max_soc_pct)
                    VALUES (%(brand)s, %(model)s, %(capacity_kwh)s, %(usable_kwh)s,
                    %(max_charge)s, %(max_discharge)s, %(max_charge)s, %(max_discharge)s,
                    %(min_soc)s, %(max_soc)s)""", bat)

        return redirect(_url("inverter") + "?saved=1")

    return render_template("inverter.html", options=options,
                           inverter=inverter_row, battery=battery_row,
                           saved=request.args.get("saved"))


@app.route("/provider", methods=["GET", "POST"])
def provider():
    db = _get_db()
    provider_row = None
    if db:
        with db.cursor() as cur:
            cur.execute("""SELECT * FROM provider_config
                WHERE energy_type='electricity' AND is_active=1
                ORDER BY id DESC LIMIT 1""")
            provider_row = cur.fetchone()

    if request.method == "POST" and db:
        driver = request.form.get("provider_driver")
        driver_cfg = {}
        if driver in ("anwb", "energyzero"):
            driver_cfg = {"vat_pct": float(request.form.get("vat_pct", 21.0)),
                          "incl_tax": "incl_tax" in request.form}
        elif driver == "tibber":
            driver_cfg = {"token": request.form.get("tibber_token", "")}
        elif driver == "entsoe":
            driver_cfg = {"token": request.form.get("entsoe_token", ""),
                          "area_code": request.form.get("area_code", "10YNL----------L"),
                          "vat_pct": float(request.form.get("vat_pct", 21.0))}

        with db.cursor() as cur:
            cur.execute("UPDATE provider_config SET is_active=0")
            if provider_row:
                cur.execute("""UPDATE provider_config SET provider_driver=%(driver)s,
                    driver_config=%(cfg)s, is_active=1 WHERE id=%(id)s""",
                    {"driver": driver, "cfg": json.dumps(driver_cfg),
                     "id": provider_row["id"]})
            else:
                cur.execute("""INSERT INTO provider_config
                    (energy_type, provider_driver, driver_config, is_active)
                    VALUES ('electricity', %(driver)s, %(cfg)s, 1)""",
                    {"driver": driver, "cfg": json.dumps(driver_cfg)})

        return redirect(_url("provider") + "?saved=1")

    import json as _j
    if provider_row and isinstance(provider_row.get("driver_config"), str):
        try:
            provider_row["driver_config"] = _j.loads(provider_row["driver_config"])
        except Exception:
            provider_row["driver_config"] = {}
    return render_template("provider.html", provider=provider_row,
                           saved=request.args.get("saved"))


@app.route("/entities", methods=["GET", "POST"])
def entities():
    db = _get_db()
    entity_rows = []
    if db:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM ha_entity_map ORDER BY internal_name")
            entity_rows = cur.fetchall()

    if request.method == "POST" and db:
        with db.cursor() as cur:
            cur.execute("""INSERT INTO ha_entity_map
                (internal_name, entity_id, unit, description)
                VALUES (%(n)s, %(e)s, %(u)s, %(d)s)
                ON DUPLICATE KEY UPDATE entity_id=VALUES(entity_id),
                unit=VALUES(unit), description=VALUES(description)""",
                {"n": request.form.get("internal_name"),
                 "e": request.form.get("entity_id"),
                 "u": request.form.get("unit", ""),
                 "d": request.form.get("description", "")})
        return redirect(_url("entities") + "?saved=1")

    return render_template("entities.html", entities=entity_rows,
                           saved=request.args.get("saved"))


@app.route("/entities/delete/<int:entity_id>", methods=["POST"])
def delete_entity(entity_id: int):
    db = _get_db()
    if db:
        with db.cursor() as cur:
            cur.execute("DELETE FROM ha_entity_map WHERE id=%(id)s", {"id": entity_id})
    return redirect(_url("entities"))


@app.route("/schedule", methods=["GET", "POST"])
def schedule():
    options = _load_options()
    if request.method == "POST":
        options["collectors"] = {
            "ha_interval_seconds":       int(request.form["ha_interval"]),
            "weather_interval_seconds":  int(request.form["weather_interval"]),
            "price_fetch_time_today":    request.form["price_time_today"],
            "price_fetch_time_tomorrow": request.form["price_time_tomorrow"],
            "price_fetch_max_retries":   int(request.form["price_retries"]),
            "price_fetch_retry_minutes": int(request.form["price_retry_minutes"]),
        }
        options["optimizer"] = {
            "run_time":              request.form["optimizer_time"],
            "rerun_on_price_update": "rerun" in request.form,
        }
        options["reporting"] = {
            "daily_report_time":  request.form["report_time"],
            "notify_on_warning":  "notify_warning" in request.form,
            "notify_on_error":    "notify_error" in request.form,
        }
        _save_options(options)
        return redirect(_url("schedule") + "?saved=1")
    return render_template("schedule.html", options=options,
                           saved=request.args.get("saved"))


@app.route("/optimizer", methods=["GET", "POST"])
def optimizer():
    db = _get_db()
    config_row  = None
    battery_row = None
    if db:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM system_config ORDER BY id DESC LIMIT 1")
            config_row = cur.fetchone()
            cur.execute("SELECT * FROM battery_info ORDER BY id DESC LIMIT 1")
            battery_row = cur.fetchone()

    if request.method == "POST" and db:
        with db.cursor() as cur:
            if config_row:
                cur.execute("""UPDATE system_config SET
                    min_price_to_discharge=%(min_dis)s,
                    max_price_to_charge=%(max_chg)s,
                    hard_min_discharge_price_excl=%(hard_min)s,
                    battery_efficiency_pct=%(eff)s, price_incl_tax=%(incl)s
                    WHERE id=%(id)s""",
                    {"min_dis":  request.form.get("min_discharge_price"),
                     "max_chg":  request.form.get("max_charge_price"),
                     "hard_min": request.form.get("hard_min_discharge_price"),
                     "eff":      request.form.get("battery_efficiency"),
                     "incl":     1 if "price_incl_tax" in request.form else 0,
                     "id":      config_row["id"]})
            if battery_row:
                cur.execute("""UPDATE battery_info SET
                    min_soc_pct=%(min_soc)s, max_soc_pct=%(max_soc)s
                    WHERE id=%(id)s""",
                    {"min_soc": request.form.get("min_soc"),
                     "max_soc": request.form.get("max_soc"),
                     "id":      battery_row["id"]})
        return redirect(_url("optimizer") + "?saved=1")

    return render_template("optimizer.html", config=config_row,
                           battery=battery_row,
                           saved=request.args.get("saved"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099, debug=False)

