# gui/app.py — v0.2.9
# 2026-04-26 16:26
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
    # Save to local options.json
    # Sla op naar lokale options.json
    with open(OPTIONS_PATH, "w") as f:
        json.dump(data, f, indent=2)

    # Sync to supervisor so HA config tab stays in sync
    # Synchroniseer naar supervisor zodat HA configuratietab gesynchroniseerd blijft
    try:
        import requests as _req
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if token:
            _req.post(
                "http://supervisor/addons/self/options",
                json={"options": data},
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).debug(f"Supervisor sync failed (non-critical): {e}")


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


def _get_addon_version() -> str:
    """
    Read version from supervisor API or config.yaml.
    Lees versie uit supervisor API of config.yaml.
    """
    # Try supervisor API first
    try:
        import requests as _req
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if token:
            resp = _req.get(
                "http://supervisor/addons/self/info",
                headers={"Authorization": f"Bearer {token}"},
                timeout=3,
            )
            if resp.status_code == 200:
                return resp.json().get("data", {}).get("version", "?")
    except Exception:
        pass

    # Fallback: read from config.yaml
    try:
        for config_file in [
            Path(__file__).parent.parent.parent / "config.yaml",
            Path(__file__).parent.parent / "config.yaml",
        ]:
            if config_file.exists():
                for line in config_file.read_text().splitlines():
                    if line.startswith("version:"):
                        return line.split(":", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "?"

_ADDON_VERSION = _get_addon_version()


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
        "nav_url":       _url,
        "ingress_path":  ingress_path,
        "system_config": system_config,
        "addon_version": _ADDON_VERSION,
    }


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def root():
    return redirect(_url("dashboard"))


@app.route("/overview")
def index():
    options = _load_options()
    db = _get_db()

    inverter_ok  = False
    provider_ok  = False
    config_ok    = False
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
        options = _load_options()
        ha_cfg  = options.get("homeassistant", {})
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
        ha_url  = f"http://{ha_cfg.get('host', 'homeassistant')}:{ha_cfg.get('port', 8123)}"
        headers = {"Authorization": f"Bearer {ha_cfg.get('token', '')}"}

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

    # On GET: sync options from database if system section is missing/empty
    # Bij GET: synchroniseer opties vanuit database als systeemsectie ontbreekt
    if request.method == "GET":
        db = _get_db()
        sys_opts = options.get("system", {})
        # Sync from DB if all components are default false (= fresh install)
        # Synchroniseer vanuit DB als alle componenten standaard false zijn (= nieuwe installatie)
        all_default = not any([
            sys_opts.get("has_solar_panels"),
            sys_opts.get("has_battery"),
            sys_opts.get("has_gas"),
            sys_opts.get("has_district_heating"),
        ])
        if db and all_default:
            try:
                with db.cursor() as cur:
                    cur.execute("SELECT * FROM system_config ORDER BY id DESC LIMIT 1")
                    row = cur.fetchone()
                    if row:
                        options["system"] = {
                            "has_grid_connection":  bool(row.get("has_grid_connection", 1)),
                            "has_solar_panels":     bool(row.get("has_solar_panels", 0)),
                            "has_battery":          bool(row.get("has_battery", 0)),
                            "has_gas":              bool(row.get("has_gas", 0)),
                            "has_district_heating": bool(row.get("has_district_heating", 0)),
                        }
                        options["location"] = {
                            "latitude":  float(row.get("latitude", 52.1551)),
                            "longitude": float(row.get("longitude", 5.3872)),
                            "timezone":  options.get("location", {}).get("timezone", "Europe/Amsterdam"),
                        }
                        _save_options(options)
            except Exception:
                pass

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

    # Parse driver_config JSON string
    # Parseer driver_config JSON-string
    driver_cfg_parsed = {}
    if inverter_row and inverter_row.get("driver_config"):
        import json as _j
        cfg = inverter_row["driver_config"]
        if isinstance(cfg, str):
            try:
                driver_cfg_parsed = _j.loads(cfg)
            except Exception:
                driver_cfg_parsed = {}
        elif isinstance(cfg, dict):
            driver_cfg_parsed = cfg
   
    if request.method == "POST" and db:
        driver = request.form.get("driver", "simulate")
        if driver == "simulate":
            driver_cfg = {
                "initial_soc_pct": float(request.form.get("initial_soc", 65.0)),
                "capacity_kwh":    float(request.form.get("sim_capacity_kwh", 17.281)),
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
                           driver_cfg=driver_cfg_parsed,
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
        elif driver == "ha_energyzero":
            driver_cfg = {
                "entity_id": request.form.get("ha_entity_id", "sensor.energy_prices_today"),
                "ha_host":   request.form.get("ha_energyzero_host", "homeassistant"),
                "ha_port":   int(request.form.get("ha_energyzero_port", 8123)),
                "ha_token":  request.form.get("ha_energyzero_token", ""),
            }
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
    # gui/app.py — entities route — v0.2.10
    # Sensor definitions loaded from config/internal_sensors.json
    # Sensordefinities geladen uit config/internal_sensors.json
    db = _get_db()
    entity_rows = []
    if db:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM ha_entity_map ORDER BY internal_name")
            entity_rows = cur.fetchall()

    if request.method == "POST":
        if not db:
            return render_template("entities.html",
                                   entities=entity_rows,
                                   error="Database niet beschikbaar / Database unavailable",
                                   saved=None)
        try:
            action = request.form.get("action", "add")

            if action == "update":
                # Update existing entity mapping / Bestaande koppeling bijwerken
                internal_name = request.form.get("internal_name_custom", "").strip()
                entity_id     = request.form.get("entity_id", "").strip()
                unit          = request.form.get("unit", "")
                description   = request.form.get("description", "")
                if internal_name and entity_id:
                    with db.cursor() as cur:
                        cur.execute("""INSERT INTO ha_entity_map
                            (internal_name, entity_id, unit, description)
                            VALUES (%(n)s, %(e)s, %(u)s, %(d)s)
                            ON DUPLICATE KEY UPDATE entity_id=VALUES(entity_id),
                            unit=VALUES(unit), description=VALUES(description)""",
                            {"n": internal_name, "e": entity_id,
                             "u": unit, "d": description})
            else:
                # Add new entity mapping / Nieuwe koppeling toevoegen
                internal_name = (request.form.get("internal_name_custom") or
                                request.form.get("internal_name", "")).strip()
                if internal_name:
                    with db.cursor() as cur:
                        cur.execute("""INSERT INTO ha_entity_map
                            (internal_name, entity_id, unit, description)
                            VALUES (%(n)s, %(e)s, %(u)s, %(d)s)
                            ON DUPLICATE KEY UPDATE entity_id=VALUES(entity_id),
                            unit=VALUES(unit), description=VALUES(description)""",
                            {"n": internal_name,
                             "e": request.form.get("entity_id"),
                             "u": request.form.get("unit", ""),
                             "d": request.form.get("description", "")})

            return redirect(_url("entities") + "?saved=1")

        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).exception("[entities] Save failed")
            return render_template("entities.html",
                                   entities=entity_rows,
                                   error=f"Opslaan mislukt / Save failed: {str(e)[:120]}",
                                   saved=None)

    # Load known sensors from JSON
    # Laad bekende sensoren uit JSON
    import json as _json
    sensors_file = Path(__file__).parent.parent / "config" / "internal_sensors.json"
    try:
        with open(sensors_file) as f:
            all_sensors = _json.load(f)
    except Exception:
        all_sensors = []

    # Load installed components from system_config
    # Laad geïnstalleerde componenten uit system_config
    installed = {
        "has_grid_connection": True,
        "has_solar_panels":    False,
        "has_battery":         False,
        "has_gas":             False,
        "has_district_heating":False,
    }
    db2 = _get_db()
    if db2:
        try:
            with db2.cursor() as cur:
                cur.execute("SELECT * FROM system_config ORDER BY id DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    for key in installed:
                        installed[key] = bool(row.get(key, 0))
        except Exception:
            pass

    # Filter sensors based on installed components
    # Filter sensoren op basis van geïnstalleerde componenten
    def component_active(sensor: dict) -> bool:
        comp = sensor.get("requires_component")
        if comp is None:
            return True
        return installed.get(comp, False)

    visible_sensors = [s for s in all_sensors if component_active(s)]

    # Build lookup maps / Bouw opzoektabellen
    entity_map = {e["internal_name"]: e for e in entity_rows}
    sensor_map = {s["internal_name"]: s for s in all_sensors}

    # Find unmapped visible sensors for dropdown
    # Vind niet-gekoppelde zichtbare sensoren voor dropdown
    unmapped_names = [
        s for s in visible_sensors
        if s["internal_name"] not in entity_map
    ]

    return render_template("entities.html",
                           entities=entity_rows,
                           all_sensors=visible_sensors,
                           entity_map=entity_map,
                           sensor_map=sensor_map,
                           unmapped_names=unmapped_names,
                           installed=installed,
                           saved=request.args.get("saved"))


@app.route("/entities/validate", methods=["POST"])
def validate_entity():
    """
    Check if an entity ID exists in HA.
    Controleer of een entiteit-ID bestaat in HA.
    """
    import requests as req
    data = request.json or {}
    entity_id = data.get("entity_id", "").strip()
    if not entity_id:
        return jsonify({"ok": False, "message": "No entity ID provided"})
    try:
        options = _load_options()
        ha_cfg  = options.get("homeassistant", {})
        resp = req.get(
            f"http://{ha_cfg.get('host', 'homeassistant')}:{ha_cfg.get('port', 8123)}/api/states/{entity_id}",
            headers={"Authorization": f"Bearer {ha_cfg.get('token', '')}"},
            timeout=5,
        )
        if resp.status_code == 200:
            state = resp.json()
            value = state.get("state", "unknown")
            unit  = state.get("attributes", {}).get("unit_of_measurement", "")
            return jsonify({
                "ok": True,
                "message": f"✓ Found: {value} {unit}",
                "value": value,
                "unit": unit,
            })
        elif resp.status_code == 404:
            return jsonify({"ok": False, "message": f"✗ Entity not found in HA"})
        else:
            return jsonify({"ok": False, "message": f"✗ HTTP {resp.status_code}"})
    except Exception as e:
        return jsonify({"ok": False, "message": f"✗ Error: {str(e)[:60]}"})



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
            "evening_planning_time": request.form.get("evening_planning_time", "21:00"),
            "profile_update_time":   request.form.get("profile_update_time", "03:00"),
            "rerun_on_price_update": "rerun" in request.form,
        }
        options["reporting"] = {
            "daily_report_time":           request.form["report_time"],
            "notify_on_warning":           "notify_warning" in request.form,
            "notify_on_error":             "notify_error" in request.form,
            "dashboard_refresh_seconds":   int(request.form.get("dashboard_refresh_seconds", 300)),
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
                    battery_efficiency_pct=%(eff)s,
                    price_incl_tax=%(incl)s,
                    solar_charge_threshold=%(solar_thr)s
                    WHERE id=%(id)s""",
                    {"min_dis":   request.form.get("min_discharge_price"),
                     "max_chg":   request.form.get("max_charge_price"),
                     "hard_min":  request.form.get("hard_min_discharge_price"),
                     "eff":       request.form.get("battery_efficiency"),
                     "incl":      1 if "price_incl_tax" in request.form else 0,
                     "solar_thr": request.form.get("solar_charge_threshold", "0.80"),
                     "id":        config_row["id"]})
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


@app.route("/reportlog")
def reportlog():
    # gui/app.py — reportlog route — v0.2.10
    # Shows paginated report log with filters
    # Toont gepagineerd rapport-log met filters
    db = _get_db()
    entries = []
    type_counts = {}
    cat_counts  = {}
    total_count = 0
    per_page    = 50
    page        = int(request.args.get("page", 1))
    active_type = request.args.get("type", "")
    active_cat  = request.args.get("category", "")

    if db:
        with db.cursor() as cur:
            # Count per type / Aantal per type
            cur.execute("""
                SELECT report_type, COUNT(*) AS c
                FROM report_log
                GROUP BY report_type
                ORDER BY FIELD(report_type,'error','warning','daily','info')
            """)
            type_counts = {row["report_type"]: row["c"] for row in cur.fetchall()}

            # Count per category / Aantal per categorie
            cur.execute("""
                SELECT category, COUNT(*) AS c
                FROM report_log
                WHERE category IS NOT NULL
                GROUP BY category
                ORDER BY c DESC
                LIMIT 10
            """)
            cat_counts = {row["category"]: row["c"] for row in cur.fetchall()}

            # Build WHERE clause / Bouw WHERE clausule
            where = "WHERE 1=1"
            params: dict = {}
            if active_type:
                where += " AND report_type = %(type)s"
                params["type"] = active_type
            if active_cat:
                where += " AND category = %(cat)s"
                params["cat"] = active_cat

            # Total count for pagination
            cur.execute(f"SELECT COUNT(*) AS c FROM report_log {where}", params)
            total_count = cur.fetchone()["c"]

            # Fetch page
            offset = (page - 1) * per_page
            cur.execute(f"""
                SELECT id, created_at, report_type, category, message
                FROM report_log
                {where}
                ORDER BY created_at DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """, {**params, "limit": per_page, "offset": offset})
            entries = cur.fetchall()

    total_pages = max(1, (total_count + per_page - 1) // per_page)

    return render_template("reportlog.html",
                           entries=entries,
                           type_counts=type_counts,
                           cat_counts=cat_counts,
                           total_count=total_count,
                           total_pages=total_pages,
                           page=page,
                           active_type=active_type,
                           active_cat=active_cat)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/dashboard")
def dashboard():
    # gui/app.py — dashboard route — v0.2.11
    options = _load_options()
    refresh = options.get("reporting", {}).get("dashboard_refresh_seconds", 300)
    return render_template("dashboard.html",
                           refresh_seconds=refresh,
                           options=options)


@app.route("/api/dashboard-data")
def api_dashboard_data():
    """
    JSON endpoint for live dashboard data.
    JSON-endpoint voor live dashboardgegevens.
    """
    db = _get_db()
    data = {
        "live":     {},
        "today":    {},
        "schedule": [],
        "prices":   [],
    }

    if not db:
        return jsonify(data)

    try:
        options    = _load_options()
        ha_cfg     = options.get("homeassistant", {})
        import requests as _req

        ha_url     = f"http://{ha_cfg.get('host', 'homeassistant')}:{ha_cfg.get('port', 8123)}"
        ha_headers = {"Authorization": f"Bearer {ha_cfg.get('token', '')}"}

        # ── Live sensor readings / Live sensorwaarden ─────────────────────
        with db.cursor() as cur:
            cur.execute("SELECT internal_name, entity_id FROM ha_entity_map")
            entity_map = {r["internal_name"]: r["entity_id"] for r in cur.fetchall()}

        live = {}
        for name, entity_id in entity_map.items():
            try:
                resp = _req.get(
                    f"{ha_url}/api/states/{entity_id}",
                    headers=ha_headers, timeout=4
                )
                if resp.status_code == 200:
                    state = resp.json().get("state", "unavailable")
                    try:
                        live[name] = float(state)
                    except (ValueError, TypeError):
                        live[name] = None
                else:
                    live[name] = None
            except Exception:
                live[name] = None

        data["live"] = live

        # ── Current price / Huidige prijs ─────────────────────────────────
        with db.cursor() as cur:
            cur.execute("""
                SELECT price_per_kwh, price_incl_tax
                FROM energy_prices
                WHERE price_hour <= NOW()
                  AND energy_type = 'electricity'
                ORDER BY price_hour DESC LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                data["live"]["current_price"] = float(row["price_per_kwh"])
                data["live"]["price_incl_tax"] = bool(row["price_incl_tax"])

        # ── Today summary / Samenvatting vandaag ──────────────────────────
        with db.cursor() as cur:
            # Solar today / Zon vandaag
            cur.execute("""
                SELECT COALESCE(SUM(power_kw) / 12.0, 0) AS solar_kwh
                FROM solar_production
                WHERE DATE(measured_at) = CURDATE()
            """)
            row = cur.fetchone()
            data["today"]["solar_kwh"] = round(float(row["solar_kwh"] or 0), 2)

            # Grid today / Net vandaag
            cur.execute("""
                SELECT
                    ROUND(SUM(GREATEST(grid_import_kw, 0)) / 12.0, 2) AS import_kwh,
                    ROUND(SUM(GREATEST(grid_export_kw, 0)) / 12.0, 2) AS export_kwh
                FROM home_consumption
                WHERE DATE(measured_at) = CURDATE()
            """)
            row = cur.fetchone()
            data["today"]["import_kwh"] = float(row["import_kwh"] or 0)
            data["today"]["export_kwh"] = float(row["export_kwh"] or 0)

            # Battery today / Batterij vandaag
            cur.execute("""
                SELECT MIN(soc_pct) AS min_soc, MAX(soc_pct) AS max_soc
                FROM battery_status
                WHERE DATE(measured_at) = CURDATE()
            """)
            row = cur.fetchone()
            if row and row["min_soc"] is not None:
                data["today"]["battery_min_soc"] = float(row["min_soc"])
                data["today"]["battery_max_soc"] = float(row["max_soc"])

            # Expected saving / Verwachte besparing
            cur.execute("""
                SELECT COALESCE(SUM(expected_saving), 0) AS total_saving
                FROM optimizer_schedule
                WHERE DATE(schedule_for) = CURDATE()
            """)
            row = cur.fetchone()
            data["today"]["expected_saving"] = round(float(row["total_saving"] or 0), 4)

        # ── Optimizer schedule 48h / Optimizer schema 48 uur ─────────────────
        with db.cursor() as cur:
            cur.execute("""
                SELECT schedule_for, action, target_power_kw,
                       expected_price, expected_saving, executed,
                       expected_solar_kw, expected_consumption_kw,
                       target_soc_pct
                FROM optimizer_schedule
                WHERE schedule_for >= DATE_FORMAT(NOW(), '%Y-%m-%d 00:00:00')
                  AND schedule_for < DATE_FORMAT(NOW() + INTERVAL 2 DAY, '%Y-%m-%d 00:00:00')
                ORDER BY schedule_for
            """)
            data["schedule"] = [
                {
                    "hour":           row["schedule_for"].strftime("%d-%m %H:%M"),
                    "hour_only":      row["schedule_for"].strftime("%H:%M"),
                    "day":            row["schedule_for"].strftime("%Y-%m-%d"),
                    "action":         row["action"],
                    "power_kw":       float(row["target_power_kw"] or 0),
                    "price":          float(row["expected_price"] or 0),
                    "saving":         float(row["expected_saving"] or 0),
                    "executed":       bool(row["executed"]),
                    "solar_kw":       float(row["expected_solar_kw"] or 0),
                    "consumption_kw": float(row["expected_consumption_kw"] or 0),
                    "soc_pct":        float(row["target_soc_pct"] or 0),
                }
                for row in cur.fetchall()
            ]

        # ── Measured hourly values / Gemeten uurwaarden ───────────────────
        with db.cursor() as cur:
            cur.execute("""
                SELECT
                    DATE_FORMAT(measured_at, '%H:00') AS hour,
                    ROUND(AVG(power_kw), 3)           AS solar_kw
                FROM solar_production
                WHERE DATE(measured_at) = CURDATE()
                GROUP BY DATE_FORMAT(measured_at, '%H:00')
                ORDER BY hour
            """)
            solar_measured = {r["hour"]: float(r["solar_kw"]) for r in cur.fetchall()}

            cur.execute("""
                SELECT
                    DATE_FORMAT(measured_at, '%H:00')               AS hour,
                    ROUND(AVG(GREATEST(grid_import_kw, 0)), 3)     AS import_kw,
                    ROUND(AVG(GREATEST(grid_export_kw, 0)), 3)     AS export_kw,
                    ROUND(AVG(GREATEST(total_consumption_kw,0)),3)  AS consumption_kw
                FROM home_consumption
                WHERE DATE(measured_at) = CURDATE()
                GROUP BY DATE_FORMAT(measured_at, '%H:00')
                ORDER BY hour
            """)
            consumption_measured = {
                r["hour"]: {
                    "import_kw":      float(r["import_kw"]),
                    "export_kw":      float(r["export_kw"]),
                    "consumption_kw": float(r["consumption_kw"]),
                }
                for r in cur.fetchall()
            }

        all_hours = sorted(set(list(solar_measured.keys()) +
                               list(consumption_measured.keys())))
        data["measured"] = [
            {
                "hour":           h,
                "solar_kw":       solar_measured.get(h, 0),
                "import_kw":      consumption_measured.get(h, {}).get("import_kw", 0),
                "export_kw":      consumption_measured.get(h, {}).get("export_kw", 0),
                "consumption_kw": consumption_measured.get(h, {}).get("consumption_kw", 0),
            }
            for h in all_hours
        ]

        # ── Prices 48h / Prijzen 48 uur ──────────────────────────────────
        with db.cursor() as cur:
            cur.execute("""
                SELECT price_hour, price_per_kwh, price_incl_tax
                FROM energy_prices
                WHERE price_hour >= DATE_FORMAT(NOW(), '%Y-%m-%d 00:00:00')
                  AND price_hour < DATE_FORMAT(NOW() + INTERVAL 2 DAY, '%Y-%m-%d 00:00:00')
                  AND energy_type = 'electricity'
                ORDER BY price_hour
            """)
            data["prices"] = [
                {
                    "hour":      row["price_hour"].strftime("%d-%m %H:%M"),
                    "hour_only": row["price_hour"].strftime("%H:%M"),
                    "day":       row["price_hour"].strftime("%Y-%m-%d"),
                    "price":     float(row["price_per_kwh"]),
                    "incl_tax":  bool(row["price_incl_tax"]),
                }
                for row in cur.fetchall()
            ]



    except Exception as e:
        data["error"] = str(e)

    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099, debug=False, threaded=True)


