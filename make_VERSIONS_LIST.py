#!/usr/bin/env python3
# name:           make_VERSIONS_LIST.py
# part of:        ha-energy-optimizer
# location:       /
# part version:   p_v0.1
# altered:        2026-06-10
#

import os
import re
from datetime import datetime

SCAN_DIR = "."
# We kijken naar de live lijst in de repository om de huidige versie te bepalen
CURRENT_MD_PATH = "/home/ludo/Documenten/ha-energy-optimizer/ha-energy-optimizer/VERSION_LIST.md"
OUTPUT_MD = os.path.expanduser("~/Documenten/ha-energy-optimizer/ha-energy-optimizer/VERSION_LIST.md")

# 1. Bepaal automatisch het nieuwe versienummer
huidige_versie = "1.1" # Fallback als er nog geen bestand is
if os.path.exists(CURRENT_MD_PATH):
    try:
        with open(CURRENT_MD_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if "part version:" in line:
                    match = re.search(r"p_v(\d+\.\d+)", line)
                    if match:
                        huidige_versie = match.group(1)
                        break
    except Exception:
        pass

# Bereken nieuwe versie (bijv. 1.7 -> 1.8)
nieuwe_versie_num = round(float(huidige_versie) + 0.1, 1)
nieuwe_versie = f"p_v{nieuwe_versie_num}"
vandaag = datetime.now().strftime("%Y-%m-%d")

# Bouw de dynamische header op
markdown_lines = [
    "# HA Energy Optimizer — Version list",
    f"# name:          VERSION_LIST.md",
    "# part of:       ha-energy-optimizer",
    "# location:      /ha-energy-optimizer/VERSION_LIST.md",
    f"# part version:  {nieuwe_versie}",
    f"# altered:       {vandaag}",
    "",
    "| Bestand | Pad in repository | Versie | Datum |",
    "| :--- | :--- | :--- | :--- |"
]

# De ASCII-vriendelijke regex-patronen voor het scannen van bestanden
c_lt, c_ex, c_da = chr(60), chr(33), chr(45)
html_tag = c_lt + c_ex + c_da + c_da
p1 = "(?:#|--|" + html_tag + ")?\\s*(?:part\\s+)?version:\\s*[\"\\s]*([^\\s>\"]+)"
p2 = "(?:#|--|" + html_tag + ")?\\s*altered:\\s*[\"\\s]*([\\d-]+)"
versie_pattern = re.compile(p1, re.IGNORECASE)
datum_pattern = re.compile(p2, re.IGNORECASE)

all_dirs = []
root_files = []

# 2. Scannen en ALFABETISCH sorteren van mappen en bestanden
for root, dirs, files in os.walk(SCAN_DIR):
    if ".git" in root.split(os.sep):
        continue
    
    # Sorteer de bestanden en mappen direct alfabetisch
    dirs.sort(key=str.lower)
    files.sort(key=str.lower)
    
    if root == SCAN_DIR:
        root_files = files
    else:
        all_dirs.append((root, files))

# Sorteer ook de hoofdmappenlijst alfabetisch
all_dirs.sort(key=lambda x: x[0].lower())

def verwerk_bestand(root_path, filename):
    # Als het script zichzelf tegenkomt, krijgt het direct de NIEUWE versie en datum!
    if filename == "make_VERSIONS_LIST.py":
        return [filename, "/ha-energy-optimizer/make_VERSIONS_LIST.py", nieuwe_versie, vandaag]
        
    if filename in ["maak_csv.sh", "maak_markdown_tabel.py"]:
        return None
        
    full_path = os.path.join(root_path, filename)
    rel_path = os.path.relpath(full_path, SCAN_DIR)
    
    if rel_path in [".gitignore", ".gitattributes", "README.md", "repository.yaml"]:
        locatie = f"/{rel_path}"
    else:
        clean_rel = rel_path.lstrip("./")
        if not clean_rel.startswith("ha-energy-optimizer"):
            locatie = f"/ha-energy-optimizer/{clean_rel}"
        else:
            locatie = f"/{clean_rel}"
            
    # Specifieke uitzondering voor VERSION_LIST.md in de tabel zelf
    if filename == "VERSION_LIST.md":
        return [filename, locatie, nieuwe_versie, vandaag]

    versie = ""
    datum = ""
    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            head = [f.readline() for _ in range(10)]
    except Exception:
        return [filename, locatie, "", ""]
        
    for line in head:
        line = line.strip()
        if not versie:
            match_ver = versie_pattern.search(line)
            if match_ver:
                versie = match_ver.group(1).replace("-->", "").strip()
        if not datum:
            match_dat = datum_pattern.search(line)
            if match_dat:
                datum = match_dat.group(1).replace("-->", "").strip()
                
    return [filename, locatie, versie, datum]

# Voeg de bestanden uit de hoofdir toe
for file in root_files:
    rij = verwerk_bestand(SCAN_DIR, file)
    if rij:
        markdown_lines.append(f"| {rij[0]} | {rij[1]} | {rij[2]} | {rij[3]} |")

# Voeg de submappen en hun bestanden toe (alles is nu alfabetisch)
for folder_path, files in all_dirs:
    if not files:
        continue
    clean_folder = os.path.relpath(folder_path, SCAN_DIR).lstrip("./")
    if not clean_folder.startswith("ha-energy-optimizer"):
        group_name = f"# ha-energy-optimizer/{clean_folder}"
    else:
        group_name = f"# {clean_folder}"
        
    markdown_lines.append(group_name)
    for file in files:
        rij = verwerk_bestand(folder_path, file)
        if rij:
            markdown_lines.append(f"| {rij[0]} | {rij[1]} | {rij[2]} | {rij[3]} |")

# Schrijf alles weg naar de Downloads map
with open(OUTPUT_MD, "w", encoding="utf-8") as f:
    for line in markdown_lines:
        f.write(line + "\n")

print(f"Succes! Versie verhoogd naar {nieuwe_versie}. Alles staat alfabetisch gesorteerd in {OUTPUT_MD}")
