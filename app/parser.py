import re
from typing import List, Dict, Any, Optional
from app.database import search_brand_in_db, get_all_brands

# Standard Indian Clinical Frequency Dictionary
FREQUENCY_PATTERNS = [
    # Numeric patterns (Indian convention e.g., 1-0-1, 1-1-1)
    (r"\b1-1-1-1\b", 4.0, "QID (Four times daily: Morning, Afternoon, Evening, Night)"),
    (r"\b1-1-1\b", 3.0, "TDS (Thrice daily: Morning, Afternoon, Night)"),
    (r"\b1-0-1\b", 2.0, "BD (Twice daily: Morning & Night)"),
    (r"\b0-1-1\b", 2.0, "BD (Twice daily: Afternoon & Night)"),
    (r"\b1-1-0\b", 2.0, "BD (Twice daily: Morning & Afternoon)"),
    (r"\b1-0-0\b", 1.0, "OD (Once daily: Morning)"),
    (r"\b0-0-1\b", 1.0, "OD / HS (Once daily: Night)"),
    (r"\b0-1-0\b", 1.0, "OD (Once daily: Afternoon)"),

    # Latin & standard abbreviations
    (r"\b(QID|4\s*times\s*a\s*day)\b", 4.0, "QID (Four times daily)"),
    (r"\b(TDS|TID|thrice\s*a\s*day|3\s*times\s*a\s*day)\b", 3.0, "TDS / TID (Thrice daily)"),
    (r"\b(BD|BID|twice\s*a\s*day|2\s*times\s*a\s*day)\b", 2.0, "BD / BID (Twice daily)"),
    (r"\b(OD|once\s*a\s*day|1\s*time\s*a\s*day)\b", 1.0, "OD (Once daily)"),
    (r"\b(HS|bedtime|at\s*night)\b", 1.0, "HS (At bedtime)"),
    (r"\b(SOS|PRN|as\s*needed|when\s*required)\b", 1.5, "SOS / PRN (As needed / Max evaluated at 2x)"),
    (r"\b(STAT|immediately)\b", 1.0, "STAT (Immediately once)"),
    (r"\b(QOD|alternate\s*day|every\s*other\s*day)\b", 0.5, "QOD (Every other day)"),
    (r"\bQ4H\b", 6.0, "Every 4 hours (6x daily)"),
    (r"\bQ6H\b", 4.0, "Every 6 hours (4x daily)"),
    (r"\bQ8H\b", 3.0, "Every 8 hours (3x daily)"),
    (r"\bQ12H\b", 2.0, "Every 12 hours (2x daily)")
]

TIMING_INSTRUCTIONS = [
    (r"\b(BBF|before\s*breakfast|empty\s*stomach|AC|before\s*food|before\s*meals)\b", "Before food / Empty stomach"),
    (r"\b(PC|after\s*food|after\s*meals)\b", "After food / With meals"),
    (r"\b(morning)\b", "Morning"),
    (r"\b(night)\b", "Night"),
    (r"\b(SL|sublingual)\b", "Sublingual (under tongue)")
]

def clean_line(line: str) -> str:
    """Removes bullet numbers, Rx tags, tab/cap prefixes."""
    line = re.sub(r"^(?:Rx:?|\d+[\.\)]|\-|\*)\s*", "", line, flags=re.IGNORECASE).strip()
    return line

def extract_units_per_dose(line: str) -> float:
    """Extracts quantity taken per dose (e.g. 1 tab, 2 tabs, 1/2 tab)."""
    if re.search(r"\b(?:half|1/2|0\.5)\s*(?:tab|cap|tablet|capsule)?\b", line, re.IGNORECASE):
        return 0.5
    match_qty = re.search(r"\b([1-4])\s*(?:tab|cap|tablet|capsule|pill|sachet)\b", line, re.IGNORECASE)
    if match_qty:
        return float(match_qty.group(1))
    return 1.0

def extract_frequency(line: str) -> tuple[float, str]:
    """Finds the frequency multiplier and readable frequency text."""
    for pattern, multiplier, desc in FREQUENCY_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return multiplier, desc
    # Default fallback
    return 1.0, "OD (Assumed once daily - unstated)"

def extract_timing(line: str) -> str:
    """Extracts food timing instructions."""
    timings = []
    for pattern, text in TIMING_INSTRUCTIONS:
        if re.search(pattern, line, re.IGNORECASE):
            timings.append(text)
    return ", ".join(timings) if timings else "Not specified (Routine)"

def extract_duration(line: str) -> Optional[str]:
    """Extracts prescription duration like 'x 5 days' or 'for 1 week'."""
    match = re.search(r"(?:x|for)\s*(\d+\s*(?:days?|weeks?|months?))", line, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def parse_prescription_text(text: str) -> List[Dict[str, Any]]:
    """
    Parses a typed prescription into structured medications with their active ingredients,
    strengths, intake quantities, frequency multipliers, and daily doses.
    """
    lines = [clean_line(l) for l in text.splitlines() if clean_line(l)]
    all_brands = get_all_brands()
    # Sort brands by name length descending so multi-word brands match first (e.g. 'Augmentin 625 Duo' before 'Augmentin')
    all_brands_sorted = sorted(all_brands, key=lambda b: len(b["brand_name"]), reverse=True)

    parsed_items = []
    matched_lines = set()

    for idx, line in enumerate(lines):
        line_clean = re.sub(r"^(?:Tab\.?|Cap\.?|Syp\.?|Inj\.?|Oint\.?)\s+", "", line, flags=re.IGNORECASE)
        found_brand = None

        # 1. Try finding known brands from DB in the line
        for b in all_brands_sorted:
            # Match brand name as a distinct sequence, ignoring punctuation differences
            brand_escaped = re.escape(b["brand_name"]).replace(r"\-", r"[\s\-]?")
            pattern = rf"\b{brand_escaped}\b"
            if re.search(pattern, line_clean, re.IGNORECASE):
                found_brand = b
                break

        # 2. If not matched with full name, try searching database with first 2 tokens
        if not found_brand:
            words = line_clean.split()
            if words:
                search_term = words[0]
                if len(words) > 1 and not any(f[0] in words[1].upper() for f in ["OD", "BD", "TDS", "QID", "TAB"]):
                    search_term += " " + words[1]
                found_brand = search_brand_in_db(search_term)

        if found_brand:
            matched_lines.add(idx)
            units_per_dose = extract_units_per_dose(line)
            freq_mult, freq_desc = extract_frequency(line)
            timing_info = extract_timing(line)
            duration_info = extract_duration(line)

            # Calculate active ingredient breakdown per dose and per day
            active_molecules = []
            for ing in found_brand.get("ingredients", []):
                strength_per_unit = float(ing["strength_mg"])
                single_dose_mg = strength_per_unit * units_per_dose
                daily_dose_mg = single_dose_mg * freq_mult
                active_molecules.append({
                    "name": ing["ingredient_name"],
                    "strength_per_unit_mg": strength_per_unit,
                    "single_dose_mg": single_dose_mg,
                    "daily_dose_mg": daily_dose_mg,
                    "drug_class": ing.get("drug_class", "General"),
                    "adult_max_daily_mg": ing.get("adult_max_daily_mg", 0),
                    "geriatric_max_daily_mg": ing.get("geriatric_max_daily_mg", 0),
                    "pediatric_dose_mg_per_kg_dose": ing.get("pediatric_dose_mg_per_kg_dose", 0),
                    "pediatric_max_daily_mg_per_kg": ing.get("pediatric_max_daily_mg_per_kg", 0),
                    "renal_notes": ing.get("renal_notes", ""),
                    "pregnancy_category": ing.get("pregnancy_category", "C"),
                    "notes": ing.get("notes", "")
                })

            parsed_items.append({
                "original_line": line,
                "brand_id": found_brand["id"],
                "brand_name": found_brand["brand_name"],
                "manufacturer": found_brand.get("manufacturer", ""),
                "form": found_brand.get("form", "Tablet"),
                "schedule": found_brand.get("schedule", "Schedule H"),
                "units_per_dose": units_per_dose,
                "frequency_multiplier": freq_mult,
                "frequency_description": freq_desc,
                "timing": timing_info,
                "duration": duration_info,
                "active_ingredients": active_molecules
            })
        else:
            # Unrecognized line/medicine
            if len(line.strip()) > 3 and not line.strip().lower().startswith("rx"):
                parsed_items.append({
                    "original_line": line,
                    "brand_name": line.split()[0] if line.split() else line,
                    "unrecognized": True,
                    "active_ingredients": []
                })

    return parsed_items
