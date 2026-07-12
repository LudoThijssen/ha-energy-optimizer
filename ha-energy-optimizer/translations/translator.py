#
# name:          translator.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/translations/translator.py
# part version:  p_v0.4
# altered:       2026-07-01
#
# Twee vertaallagen:
# 1. UI-teksten — uit JSON bestanden (bestaande functionaliteit)
# 2. Operationele teksten — uit database translation_strings tabel
#
# Two translation layers:
# 1. UI texts — from JSON files (existing functionality)
# 2. Operational texts — from database translation_strings table

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TRANSLATIONS_DIR = Path(__file__).parent
MASTER_FILE      = TRANSLATIONS_DIR / "en.json"
CONTEXT_FILE     = TRANSLATIONS_DIR / "_context.json"

_cache: dict[str, dict] = {}

# ── Laag 1: UI-teksten uit JSON ───────────────────────────────────────────────

def t(key: str, language: str = "en", **kwargs) -> str:
    """
    Vertaalfunctie voor UI-teksten uit JSON bestanden.
    Translation function for UI texts from JSON files.
    """
    translation = _get_cached(language)
    text = translation.get(key, key)
    for var, val in kwargs.items():
        text = text.replace(f"{{{var}}}", str(val))
    return text


def load_translation(language: str) -> dict:
    lang_file = TRANSLATIONS_DIR / f"{language}.json"

    if lang_file.exists():
        with open(lang_file, encoding="utf-8") as f:
            translation = json.load(f)
        return _merge_with_master(translation)

    logger.info(f"Geen vertaling gevonden voor '{language}' — AI-vertaling proberen")
    generated = _generate_with_ai(language)

    if generated:
        with open(lang_file, "w", encoding="utf-8") as f:
            json.dump(generated, f, ensure_ascii=False, indent=2)
        logger.info(f"AI-vertaling opgeslagen: {lang_file}")
        return _merge_with_master(generated)

    logger.warning(f"AI-vertaling mislukt voor '{language}' — terugvallen op Engels")
    return _load_master()


def _generate_with_ai(language: str) -> dict | None:
    try:
        import anthropic
        master  = _load_master()
        context = _load_context()

        lines = []
        for key, value in master.items():
            ctx = context.get(key, {}).get("context", "")
            line = f'"{key}": "{value}"'
            if ctx:
                line += f"  // Context: {ctx}"
            lines.append(line)

        prompt = f"""Translate the following UI strings from English to {language}.

IMPORTANT RULES:
- Return ONLY a valid JSON object, no explanation, no markdown backticks
- Keep all keys exactly as-is
- These strings are for a home energy management app controlling solar panels and a home battery
- "charge" in battery context means storing electricity in a battery — NOT a financial charge or fee
- "discharge" means releasing energy from a battery — NOT a financial term
- Use natural everyday language a homeowner would understand

Strings to translate:
{chr(10).join(lines)}"""

        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(message.content[0].text)

    except Exception as e:
        logger.error(f"AI-vertaling fout voor '{language}': {e}")
        return None


def _merge_with_master(translation: dict) -> dict:
    return {**_load_master(), **translation}


def _load_master() -> dict:
    with open(MASTER_FILE, encoding="utf-8") as f:
        return json.load(f)


def _load_context() -> dict:
    if CONTEXT_FILE.exists():
        with open(CONTEXT_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _get_cached(language: str) -> dict:
    if language not in _cache:
        _cache[language] = load_translation(language)
    return _cache[language]


# ── Laag 2: Operationele teksten uit database ─────────────────────────────────

class OperationalTranslator:
    """
    Vertaler voor operationele teksten (reason strings, log berichten).
    Leest uit de translation_strings tabel in de database.
    Valt terug op Engels als de gevraagde taal niet beschikbaar is.

    Translator for operational texts (reason strings, log messages).
    Reads from the translation_strings table in the database.
    Falls back to English if the requested language is not available.
    """

    def __init__(self, db, language: str = "nl"):
        self._db       = db
        self._language = language
        self._cache: dict[str, str] = {}
        self._loaded   = False

    def _load(self) -> None:
        """Laad alle vertalingen voor de actieve taal in één query."""
        if self._loaded:
            return
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT string_key, text FROM translation_strings "
                    "WHERE language = %s",
                    (self._language,)
                )
                for row in cur.fetchall():
                    self._cache[row["string_key"]] = row["text"]

                # Vul ontbrekende keys aan vanuit Engels
                cur.execute(
                    "SELECT string_key, text FROM translation_strings "
                    "WHERE language = 'en' AND string_key NOT IN "
                    "(SELECT string_key FROM translation_strings WHERE language = %s)",
                    (self._language,)
                )
                for row in cur.fetchall():
                    self._cache[row["string_key"]] = row["text"]

            self._loaded = True
        except Exception as e:
            logger.warning(f"[translator] Vertalingen laden mislukt: {e}")

    def get(self, key: str, params: dict[str, Any] | None = None) -> str:
        """
        Haal vertaalde tekst op voor de gegeven key en vul parameters in.
        Get translated text for the given key and fill in parameters.

        Args:
            key:    Vertaalsleutel bijv. 'RS01' / Translation key e.g. 'RS01'
            params: Parameters voor variabelen bijv. {'price': 0.12}

        Returns:
            Vertaalde tekst met ingevulde parameters / Translated text with params filled in.
            Als key niet gevonden: geeft de key terug / If key not found: returns the key.
        """
        self._load()
        text = self._cache.get(key, key)
        if params:
            for var, val in params.items():
                # Ondersteun format-specs bijv. {price:.4f}
                # Support format specs e.g. {price:.4f}
                import re
                pattern = re.compile(r'\{' + var + r'(:[^}]*)?\}')
                def replacer(m):
                    spec = m.group(1) or ''
                    try:
                        return format(val, spec.lstrip(':'))
                    except (ValueError, TypeError):
                        return str(val)
                text = pattern.sub(replacer, text)
        return text

    def translate_new_language(self, target_language: str) -> int:
        """
        Vertaal alle Nederlandse teksten naar een nieuwe taal via AI.
        Slaat alleen keys op die nog niet bestaan voor die taal.

        Translate all Dutch texts to a new language via AI.
        Only saves keys that don't yet exist for that language.

        Returns: aantal vertaalde keys / number of translated keys
        """
        try:
            with self._db.cursor() as cur:
                # Haal alle nl teksten op die nog niet vertaald zijn
                cur.execute(
                    "SELECT string_key, text FROM translation_strings "
                    "WHERE language = 'nl' AND string_key NOT IN "
                    "(SELECT string_key FROM translation_strings WHERE language = %s)",
                    (target_language,)
                )
                to_translate = {row["string_key"]: row["text"] for row in cur.fetchall()}

            if not to_translate:
                logger.info(f"[translator] Alle keys al vertaald voor '{target_language}'")
                return 0

            # Vertaal via Anthropic API
            translated = self._ai_translate_operational(to_translate, target_language)
            if not translated:
                return 0

            # Sla op in database
            inserted = 0
            with self._db.cursor() as cur:
                for key, text in translated.items():
                    cur.execute(
                        "INSERT IGNORE INTO translation_strings "
                        "(string_key, language, text) VALUES (%s, %s, %s)",
                        (key, target_language, text)
                    )
                    inserted += cur.rowcount

            logger.info(f"[translator] {inserted} operationele vertalingen opgeslagen voor '{target_language}'")
            return inserted

        except Exception as e:
            logger.error(f"[translator] Vertaling naar '{target_language}' mislukt: {e}")
            return 0

    def _ai_translate_operational(
        self, texts: dict[str, str], target_language: str
    ) -> dict[str, str] | None:
        """Vertaal operationele teksten via de Anthropic API."""
        try:
            import anthropic
            import json as _json

            lines = [f'"{k}": "{v}"' for k, v in texts.items()]
            prompt = f"""Translate the following operational strings from Dutch to {target_language}.

IMPORTANT RULES:
- Return ONLY a valid JSON object, no explanation, no markdown backticks
- Keep all keys exactly as-is (e.g. RS01, LG03)
- Keep all variables in braces exactly as-is (e.g. {{price:.4f}}, {{sensor}}, {{error}})
- These strings are for a home energy management system
- "laden" = charging a battery (NOT loading)
- "ontladen" = discharging a battery
- "zon" = solar energy / sun
- "netafname" = grid import
- "teruglevering" = grid export (feeding back to grid)
- Use natural everyday language

Strings to translate:
{chr(10).join(lines)}"""

            client = anthropic.Anthropic()
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return _json.loads(message.content[0].text)

        except Exception as e:
            logger.error(f"[translator] AI-vertaling operationeel mislukt: {e}")
            return None

    def invalidate_cache(self) -> None:
        """Cache legen zodat vertalingen opnieuw worden geladen bij volgende aanroep."""
        self._cache.clear()
        self._loaded = False


def build_translator(db, language: str | None = None) -> OperationalTranslator:
    """
    Maak een OperationalTranslator aan met de taal uit de database.
    Create an OperationalTranslator with the language from the database.
    """
    if language is None:
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT language FROM system_config "
                    "ORDER BY id DESC LIMIT 1"
                )
                row = cur.fetchone()
                language = row["language"] if row and row.get("language") else "nl"
        except Exception:
            language = "nl"

    return OperationalTranslator(db, language)
