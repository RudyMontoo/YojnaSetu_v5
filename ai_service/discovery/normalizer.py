"""
normalizer.py — Gemini-based structured eligibility extraction.

Per CLAUDE.md's pipeline/normalizer.py spec: turns a scheme's free-text
`eligibility` string into a structured dict:
    {maxIncome, minAge, maxAge, category: [], occupation: [], state,
     isRural, isBpl, hasLand}

This replaces the `eligibilityRules: {}` placeholder that
scripts/migrate_schemes.py left in place — that script's docstring said
explicitly this was a stopgap, not silently assumed away. Used by both the
migration backfill and Agent 2 Discovery (agent2.py) so newly-discovered
schemes get the same structured shape as migrated ones.

Fields are all Optional — if the source text doesn't mention an income
cap, maxIncome should be null, not a guessed number. The prompt says so
explicitly because LLMs like to fill in plausible-looking values otherwise.
"""
import json
import logging

from ai_service.graph.llm import ainvoke_with_fallback

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = """Extract structured eligibility rules from this Indian government welfare scheme's eligibility text.

Scheme name: {name}
Eligibility text: "{eligibility_text}"
Benefit text: "{benefit_text}"

Return ONLY a JSON object with these fields. Use null for any field not mentioned or not inferable — do NOT guess a plausible-sounding value if the text doesn't support it:
{{
  "maxIncome": <annual income cap in INR, number or null>,
  "minAge": <number or null>,
  "maxAge": <number or null>,
  "category": [<subset of "general","obc","sc","st" mentioned, or empty list>],
  "occupation": [<subset of "farmer","student","daily_wage","self_employed","unemployed","salaried" mentioned, or empty list>],
  "isRural": <true, false, or null if not specified>,
  "isBpl": <true if BPL/below-poverty-line required, else false>,
  "hasLand": <true if land ownership required, false if explicitly not required, null if not mentioned>
}}"""


async def extract_eligibility_rules(name: str, eligibility_text: str, benefit_text: str = "") -> dict:
    if not eligibility_text.strip():
        return {}

    prompt = _EXTRACT_PROMPT.format(name=name, eligibility_text=eligibility_text, benefit_text=benefit_text)
    try:
        # prefer="groq": this runs at bulk-migration/discovery volume (hundreds of calls),
        # which blows through Gemini's 5rpm free-tier quota immediately — see llm.py docstring.
        response = await ainvoke_with_fallback(prompt, temperature=0.0, prefer="groq")
        raw = response.content.strip().strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
        parsed = json.loads(raw)
        return {k: v for k, v in parsed.items() if v not in (None, [], "")}
    except (json.JSONDecodeError, AttributeError, Exception) as e:
        logger.warning("Eligibility extraction failed for %r: %s", name, e)
        return {}
