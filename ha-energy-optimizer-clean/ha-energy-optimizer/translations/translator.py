import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TRANSLATIONS_DIR = Path(__file__).parent
MASTER_FILE      = TRANSLATIONS_DIR / "en.json"
CONTEXT_FILE     = TRANSLATIONS_DIR / "_context.json"

_cache: dict[str, dict] = {}


def t(key: str, language: str = "en", **kwargs) -> str:
    """
    Vertaalfunctie voor gebruik door de rest van de app.

    Gebruik:
        t("battery.action.charge", "nl")
        → "Opladen"

        t("report.notify.battery_low", "nl", soc=12)
        → "Batterij bijna leeg (12%)"
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
    """Vul ontbrekende sleutels aan vanuit de Engelse master."""
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
