#!/usr/bin/env python3
# uninstall.py
#
# HA Energy Optimizer — Uninstaller
# HA Energy Optimizer — Verwijderaar
#
# Run this script before removing the add-on from Home Assistant.
# Voer dit script uit voordat u de add-on uit Home Assistant verwijdert.
#
# Usage / Gebruik:
#   python3 uninstall.py [--keep-database] [--keep-translations] [--silent]

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "HA Energy Optimizer uninstaller. / HA Energy Optimizer verwijderaar.\n"
            "Removes add-on data and optionally the database."
        )
    )
    parser.add_argument(
        "--keep-database",
        action="store_true",
        help=(
            "Keep the MySQL database and all collected data. / "
            "Behoud de MySQL database en alle verzamelde gegevens."
        ),
    )
    parser.add_argument(
        "--keep-translations",
        action="store_true",
        help=(
            "Keep AI-generated translation files. / "
            "Behoud AI-gegenereerde vertaalbestanden."
        ),
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Skip confirmation prompts. / Sla bevestigingsvragen over.",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  HA Energy Optimizer — Uninstaller")
    print("=" * 60)
    print()

    # Load config to know database credentials
    # Configuratie laden voor databasetoegang
    config = _load_config()

    if not args.silent:
        print("This will remove the following:")
        print("Dit verwijdert het volgende:")
        print()
        print("  [✓] Add-on configuration / Add-on configuratie")
        print("  [✓] Log files / Logbestanden")
        if not args.keep_translations:
            print("  [✓] AI-generated translations / AI-gegenereerde vertalingen")
        if not args.keep_database:
            print("  [✓] MySQL database and all data / MySQL database en alle gegevens")
        else:
            print("  [–] MySQL database (kept / behouden)")
        print()

        answer = input("Continue? / Doorgaan? (yes/ja to confirm): ").strip().lower()
        if answer not in ("yes", "ja", "y", "j"):
            print("\nUninstall cancelled. / Verwijderen geannuleerd.")
            sys.exit(0)

    print()

    # Step 1: Remove AI-generated translation files
    # Stap 1: AI-gegenereerde vertaalbestanden verwijderen
    if not args.keep_translations:
        _remove_generated_translations()

    # Step 2: Drop database
    # Stap 2: Database verwijderen
    if not args.keep_database and config:
        _drop_database(config, args.silent)

    # Step 3: Remove local data files
    # Stap 3: Lokale databestanden verwijderen
    _remove_data_files()

    print()
    print("=" * 60)
    print("  Uninstall complete. / Verwijdering voltooid.")
    print()
    print("  You can now remove the add-on from Home Assistant.")
    print("  U kunt de add-on nu verwijderen uit Home Assistant.")
    if args.keep_database:
        print()
        print("  Your database has been kept.")
        print("  Uw database is behouden.")
        if config:
            print(f"  Host: {config.get('database', {}).get('host', '?')}")
            print(f"  Database: {config.get('database', {}).get('name', '?')}")
    print("=" * 60)
    print()


def _load_config() -> dict | None:
    """
    Load options.json to retrieve database credentials.
    Laad options.json om databasegegevens op te halen.
    """
    options_paths = [
        Path("/data/options.json"),          # Home Assistant add-on path
        Path("options.json"),                # Local development / Lokale ontwikkeling
        Path("config/options.json"),
    ]
    for path in options_paths:
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
    print("  [!] Could not load options.json — database will not be dropped automatically.")
    print("  [!] Kon options.json niet laden — database wordt niet automatisch verwijderd.")
    return None


def _remove_generated_translations() -> None:
    """
    Remove AI-generated translation files (not the built-in ones).
    Verwijder AI-gegenereerde vertaalbestanden (niet de ingebouwde).
    """
    built_in = {"en.json", "nl.json", "de.json", "fr.json", "es.json", "_context.json"}
    translations_dir = Path(__file__).parent / "translations"

    removed = []
    if translations_dir.exists():
        for f in translations_dir.glob("*.json"):
            if f.name not in built_in:
                f.unlink()
                removed.append(f.name)

    if removed:
        print(f"  [✓] Removed AI translations / Verwijderde AI-vertalingen: {', '.join(removed)}")
    else:
        print("  [–] No AI-generated translations found / Geen AI-vertalingen gevonden")


def _drop_database(config: dict, silent: bool) -> None:
    """
    Drop the MySQL database after a final confirmation.
    Verwijder de MySQL database na een laatste bevestiging.
    """
    db_cfg = config.get("database", {})
    host   = db_cfg.get("host", "localhost")
    port   = db_cfg.get("port", 3306)
    name   = db_cfg.get("name", "energy")
    user   = db_cfg.get("user", "energy")
    pwd    = db_cfg.get("password", "")

    if not silent:
        print()
        print(f"  [!] About to DROP database '{name}' on {host}:{port}")
        print(f"  [!] Database '{name}' op {host}:{port} wordt VERWIJDERD")
        print("      This cannot be undone! / Dit kan niet ongedaan worden gemaakt!")
        answer = input("      Type 'DELETE' to confirm / Typ 'VERWIJDER' om te bevestigen: ").strip()
        if answer not in ("DELETE", "VERWIJDER"):
            print("  [–] Database removal cancelled. / Databaseverwijdering geannuleerd.")
            return

    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=host, port=port,
            user=user, password=pwd,
            connection_timeout=10,
        )
        cur = conn.cursor()

        # Remove database user / Databasegebruiker verwijderen
        try:
            cur.execute(f"DROP USER IF EXISTS '{user}'@'%'")
            print(f"  [✓] Removed database user / Databasegebruiker verwijderd: {user}")
        except Exception as e:
            print(f"  [!] Could not remove user / Kon gebruiker niet verwijderen: {e}")

        # Drop database / Database verwijderen
        cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
        print(f"  [✓] Dropped database / Database verwijderd: {name}")

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print(f"  [!] Database removal failed / Databaseverwijdering mislukt: {e}")
        print(f"      You can remove it manually with:")
        print(f"      U kunt het handmatig verwijderen met:")
        print(f"      DROP DATABASE `{name}`;")
        print(f"      DROP USER '{user}'@'%';")


def _remove_data_files() -> None:
    """
    Remove runtime data files (logs, cache).
    Verwijder runtime databestanden (logs, cache).
    """
    targets = [
        Path("/data/options.json"),
        Path("logs/"),
        Path("*.log"),
    ]
    removed = []

    for target in targets:
        if target.is_file():
            target.unlink()
            removed.append(str(target))
        elif target.is_dir():
            import shutil
            shutil.rmtree(target, ignore_errors=True)
            removed.append(str(target))

    if removed:
        print(f"  [✓] Removed data files / Verwijderde bestanden: {', '.join(removed)}")
    else:
        print("  [–] No runtime data files found / Geen runtime bestanden gevonden")


if __name__ == "__main__":
    main()
