"""
benefit_parser.py — turns a scheme's free-text `benefitAmount` (e.g. "Rs
6000/year direct income support", "Rs 300/month for disabled BPL persons")
into a structured, annualized rupee figure Agent 7 (Financial Planning) can
sum across schemes.

Real failure found while testing this against actual scheme data, fixed
here rather than shipped: a naive "extract the rupee amount" prompt
happily extracted "Rs 5 lakh" out of "No tax up to Rs 5 lakh income" (a tax
EXEMPTION THRESHOLD, not a cash payment) and out of "8.2% interest... up to
Rs 30 lakh deposit" (a savings scheme's deposit ceiling — the citizen's own
money, not a government giveaway) — inflating one test citizen's reported
annual benefit by ~Rs 8 lakh out of a Rs 13.36 lakh total. For something
meant to inform a citizen's real financial planning, that's not an
acceptable error margin.

Fix: classify the benefit_type first, and only `direct_transfer` amounts
count toward the guaranteed total. `conditional_payout` (compensation/
insurance, paid only if a triggering event occurs) is extracted but kept
separate — it's not routine annual income. `savings_investment` and
`tax_relief` never produce a cash amount at all, by construction — see the
examples below.
"""
import json
import logging

from ai_service.graph.llm import ainvoke_with_fallback

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = """Extract the monetary benefit from this Indian government scheme benefit description.

Benefit text: "{text}"

First classify benefit_type, then extract amount_inr ONLY if benefit_type is direct_transfer or conditional_payout:
- direct_transfer: guaranteed cash/pension paid BY the government TO the citizen on a schedule (e.g. "Rs 6000/year income support", "Rs 300/month pension")
- conditional_payout: cash paid ONLY if a specific triggering event occurs (death, disability, accident, calamity) — NOT routine annual income
- savings_investment: an interest-bearing deposit/savings scheme — the citizen deposits THEIR OWN money and earns interest; the government is not giving them anything. amount_inr MUST be null for this type, even if a deposit ceiling or interest rate is mentioned.
- tax_relief: a tax exemption, deduction, or "no tax up to X" threshold — this is not a cash amount, it's a threshold below which tax isn't owed. amount_inr MUST be null for this type.
- subsidy_or_loan: a loan, credit line, or subsidized loan — must be repaid, not free money. amount_inr MUST be null.
- in_kind: a free good/service (electricity units, food, healthcare access) with no rupee figure attached. amount_inr MUST be null.
- unclear: text doesn't give enough information.

Return ONLY a JSON object:
{{"benefit_type": "<one of the types above>", "amount_inr": <number or null>, "frequency": "<monthly, annual, one_time, or unknown>"}}

Examples:
"Rs 6000/year direct income support" -> {{"benefit_type": "direct_transfer", "amount_inr": 6000, "frequency": "annual"}}
"Rs 300/month for disabled BPL persons" -> {{"benefit_type": "direct_transfer", "amount_inr": 300, "frequency": "monthly"}}
"Rs 5 lakh compensation for accidental death/disability" -> {{"benefit_type": "conditional_payout", "amount_inr": 500000, "frequency": "one_time"}}
"No tax up to Rs 5 lakh income" -> {{"benefit_type": "tax_relief", "amount_inr": null, "frequency": "unknown"}}
"8.2% interest quarterly deposit for 5 years, up to Rs 30 lakh" -> {{"benefit_type": "savings_investment", "amount_inr": null, "frequency": "unknown"}}
"300 units free electricity per month" -> {{"benefit_type": "in_kind", "amount_inr": null, "frequency": "monthly"}}
"Crop loan up to Rs 3 lakh at subsidized interest" -> {{"benefit_type": "subsidy_or_loan", "amount_inr": null, "frequency": "unknown"}}"""


async def extract_benefit_amount(benefit_text: str) -> dict:
    """Returns {"benefit_type": str, "amount_inr": float|None, "frequency": str, "annualized_inr": float|None}.
    annualized_inr is populated ONLY for benefit_type == "direct_transfer" — conditional_payout amounts are
    returned but never annualized, since folding a one-off compensation payout into a routine "annual benefit"
    figure would overstate what a citizen can actually expect to receive every year."""
    if not benefit_text.strip():
        return {"benefit_type": "unclear", "amount_inr": None, "frequency": "unknown", "annualized_inr": None}

    try:
        response = await ainvoke_with_fallback(_EXTRACT_PROMPT.format(text=benefit_text[:500]), temperature=0.0)
        raw = response.content.strip().strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
        parsed = json.loads(raw)
        benefit_type = parsed.get("benefit_type", "unclear")
        amount = parsed.get("amount_inr")
        frequency = parsed.get("frequency", "unknown")

        annualized = None
        if amount is not None and benefit_type == "direct_transfer":
            if frequency == "monthly":
                annualized = amount * 12
            elif frequency in ("annual", "one_time"):
                annualized = amount

        return {"benefit_type": benefit_type, "amount_inr": amount, "frequency": frequency, "annualized_inr": annualized}
    except Exception as e:
        logger.warning("Benefit amount extraction failed for %r: %s", benefit_text[:80], e)
        return {"benefit_type": "unclear", "amount_inr": None, "frequency": "unknown", "annualized_inr": None}
