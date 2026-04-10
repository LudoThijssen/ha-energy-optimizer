# gui/app.py — v0.2.2
#
# Configuration GUI — Flask web server with HA ingress support.
# Configuratie-GUI — Flask webserver met HA ingress-ondersteuning.

from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import DatabaseConnection
from config.config import AppConfig

app = Flask(__name__, template_folder="templates", static_folder="static")

# Detect HA ingress prefix from environment or headers
# Detecteer HA ingress-prefix uit omgevingsvariabele of headers
INGRESS_ENTRY = os.environ.get("INGRESS_ENTRY", "")

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
    """
    Generate URL that works both with and without HA ingress prefix.
    Genereer URL die werkt met en zonder HA ingress-prefix.
    """
    # Get the X-Ingress-Path header if present
    ingress_path = request.headers.get("X-Ingress-Path", "")
    base = url_for(endpoint, **kwargs)
    if ingress_path:
        return ingress_path.rstrip("/") + base
    return base


@app.context_processor
def inject_url_helper():
    """Make _url available in all templates / Maak _url beschikbaar in alle templates."""
    return {"nav_url": _url}


@app.route("/")
def index():
    return render_template("index.html", options=_load_options())


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
        options.setdefault("system", {}).update({
            "has_grid_connection": "has_grid" in request.form,
            "has_solar_panels":    "has_solar" in request.form,
            "has_gas":             "has_gas" in request.form,
            "has_battery":         "has_battery" in request.form,
            "has_district_heating":"has_heating" in request.form,
        })
        _save_options(options)
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
            return jsonify({"ok": True, "message": "Verbinding geslaagd"})
        return jsonify({"ok": False, "message": f"HTTP {resp.status_code}"})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)})


@app.route("/inverter", methods=["GET", "POST"])
def inverter():
    options = _load_options()
    db = _get_db()
    inverter_row = None
    battery_row = None

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
            "brand": request.form.get("brand"),
            "model": request.form.get("model"),
            "driver": driver,
            "cfg": json.dumps(driver_cfg),
            "max_charge": request.form.get("max_charge_kw"),
            "max_discharge": request.form.get("max_discharge_kw"),
        }
        bat = {
            "brand": request.form.get("bat_brand"),
            "model": request.form.get("bat_model"),
            "capacity_kwh": request.form.get("capacity_kwh"),
            "usable_kwh": request.form.get("usable_kwh"),
            "max_charge": request.form.get("max_charge_kw"),
            "max_discharge": request.form.get("max_discharge_kw"),
            "min_soc": request.form.get("min_soc", 10),
            "max_soc": request.form.get("max_soc", 95),
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
                     max_charge_kw, max_discharge_kw, working_charge_kw, working_discharge_kw,
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
                    {"driver": driver, "cfg": json.dumps(driver_cfg), "id": provider_row["id"]})
            else:
                cur.execute("""INSERT INTO provider_config
                    (energy_type, provider_driver, driver_config, is_active)
                    VALUES ('electricity', %(driver)s, %(cfg)s, 1)""",
                    {"driver": driver, "cfg": json.dumps(driver_cfg)})

        return redirect(_url("provider") + "?saved=1")

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
    config_row = None
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
                    hard_min_discharge_price_excl=%(min_dis)s,
                    battery_efficiency_pct=%(eff)s, price_incl_tax=%(incl)s
                    WHERE id=%(id)s""",
                    {"min_dis": request.form.get("min_discharge_price"),
                     "eff": request.form.get("battery_efficiency"),
                     "incl": 1 if "price_incl_tax" in request.form else 0,
                     "id": config_row["id"]})
            if battery_row:
                cur.execute("""UPDATE battery_info SET
                    min_soc_pct=%(min_soc)s, max_soc_pct=%(max_soc)s
                    WHERE id=%(id)s""",
                    {"min_soc": request.form.get("min_soc"),
                     "max_soc": request.form.get("max_soc"),
                     "id": battery_row["id"]})
        return redirect(_url("optimizer") + "?saved=1")

    return render_template("optimizer.html", config=config_row, battery=battery_row,
                           saved=request.args.get("saved"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099, debug=False)
