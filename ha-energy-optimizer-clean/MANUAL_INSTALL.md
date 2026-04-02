# Manual Installation / Handmatige Installatie

Use this method when the HA add-on store is not available.

## Steps / Stappen

1. Download the latest zip from the [Releases](https://github.com/YOUR_USERNAME/ha-energy-optimizer/releases) page
2. Transfer the zip to your HA machine via Samba or SCP
3. Open SSH or the Terminal add-on and run:
   ```bash
   cd /addons
   mkdir -p ha-energy-optimizer
   unzip /path/to/ha-energy-optimizer.zip -d ha-energy-optimizer/
   ```
4. In HA go to **Settings → Add-ons** and click the refresh icon
5. Find **HA Energy Optimizer** under **Local add-ons** → **Install**
6. Configure via the **Configuration** tab → **Start**
7. Open the web UI at `http://homeassistant.local:8099`

## Updating / Bijwerken

1. Stop the add-on
2. Extract the new zip over the existing folder (`unzip -o`)
3. Restart the add-on — your database and config are preserved

## Uninstalling / Verwijderen

```bash
cd /addons/ha-energy-optimizer
python3 uninstall.py
rm -rf /addons/ha-energy-optimizer
```
