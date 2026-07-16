# Migraties — leeswijzer

## Status: privé-repo, nog geen publieke bèta

# 
# name:          README.md
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/README.md
# part version:  p_v2.0
# altered:       2026-07-16
#
## 000_consolidated.sql — snelkoppeling, geen vervanging
`setup.py` gebruikt `000_consolidated.sql` **alleen** wanneer de tabel
`system_config` nog niet bestaat (dus een écht lege database). Dat is de
snelle route die het complete eindschema in één keer neerzet, in plaats
van 12 losse ALTER-stappen te doorlopen — dit voorkomt fouten zoals eerder
met de ontbrekende `hard_min_discharge_price_excl` kolom bij migratie 001.

Zodra `system_config` al bestaat, valt `setup.py` terug op de
stapsgewijze route (`_apply()` per bestand 001-014). Die route heeft de
losse migratiebestanden nog nodig.

## Waarom 002-014 nog niet verwijderen
Zolang dit een privé-repo is met Ludo als enige gebruiker, is het risico
klein: de live database staat al volledig op v14, dus `_apply()` doet
voor deze installatie nooit meer dan een `SELECT` die meteen terugkeert.

Zodra de repo publiek gaat (bij de bèta), kunnen anderen echter al eerder
geforkt/gekloond hebben en een installatie hebben die middenin de
migratieketen zit (bv. t/m versie 006). Die installaties hebben de losse
bestanden 008-014 nog nodig om te kunnen upgraden. Zonder die bestanden
crasht `_apply()` met een `FileNotFoundError`.

## Wanneer wel opschonen overwegen
Pas heroverwegen na de publieke bèta-release, en dan alleen als bevestigd
kan worden dat alle bekende installaties op v14 zitten. Tot die tijd:
laten staan — de kosten (een paar KB tekst, geen onderhoudslast) wegen
niet op tegen het risico van een kapotte upgrade-pad voor een vroege
gebruiker.

## Versiesysteem
Zie overdrachtsdocument voor het volledige versiesysteem (p_v0.x headers,
config.yaml add-on versie, VERSION_LIST.md).
