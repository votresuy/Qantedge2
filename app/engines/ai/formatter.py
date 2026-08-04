"""AI Analysis Engine — Formatter step. Parses the model's structured text reply."""

import re


def parse_ai_response(raw_text: str) -> dict:
    fields = ["PROFESSIONAL_ANALYSIS", "TRADE_SUMMARY", "RISK_SUMMARY", "WHY_BUY", "WHY_SELL"]
    result = {f.lower(): None for f in fields}

    for field in fields:
        pattern = rf"{field}:\s*(.+?)(?=\n[A-Z_]+:|$)"
        match = re.search(pattern, raw_text, re.DOTALL)
        if match:
            value = match.group(1).strip()
            if value.upper() == "N/A":
                value = None
            result[field.lower()] = value

    return result
