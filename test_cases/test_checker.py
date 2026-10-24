import sys
import os

# Add root directory to python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, get_all_brands, get_all_interactions, get_db_connection
from app.parser import parse_prescription_text
from app.safety_engine import SafetyEngine

def run_tests():
    print("=== [1/4] INITIALIZING AND VERIFYING DATABASE ===")
    init_db()
    brands = get_all_brands()
    interactions = get_all_interactions()
    print(f" Loaded {len(brands)} Indian Brands from SQLite.")
    print(f" Loaded {len(interactions)} Clinical Interaction Pairs.")
    assert len(brands) >= 30, f"Expected at least 30 brands, got {len(brands)}"
    assert len(interactions) >= 15, f"Expected at least 15 interactions, got {len(interactions)}"

    print("\n=== [2/4] TESTING CLINICAL TRAP 1: HIDDEN COMBINATIONS & DUPLICATION ===")
    rx1 = """
    Rx:
    1. Tab Dolo 650 1 tab TDS
    2. Tab Combiflam 1 tab BD
    3. Tab Zerodol-P 1 tab BD SOS
    4. Tab Pan 40 1 tab OD (BBF)
    """
    parsed1 = parse_prescription_text(rx1)
    engine1 = SafetyEngine(parsed1, {"age": 34, "gender": "Male", "weight_kg": 68, "egfr": 95, "pregnant": False})
    report1 = engine1.analyze()
    print(f"Trap 1 Brands parsed: {[p['brand_name'] for p in parsed1 if 'brand_name' in p]}")
    print(f"Trap 1 Critical Alerts: {report1['summary']['critical_count']}")
    
    # Verify Paracetamol duplication
    pcm_found = any("Paracetamol" in a.get("title", "") for a in report1["alerts"]["critical"] + report1["alerts"]["moderate"])
    # Verify Dual NSAID alert (Ibuprofen + Aceclofenac)
    nsaid_found = any("Dual NSAID" in a.get("title", "") for a in report1["alerts"]["critical"])
    
    print(f"  -> Duplicate Paracetamol Flagged: {pcm_found}")
    print(f"  -> Dual NSAID Danger Flagged: {nsaid_found}")
    assert pcm_found, "Failed to detect duplicate paracetamol in combinations!"
    assert nsaid_found, "Failed to detect dual NSAID dangerous co-prescription!"

    print("\n=== [3/4] TESTING CLINICAL TRAP 2: 'TRIPLE WHAMMY' AKI & SEVERE CKD ===")
    rx2 = """
    Rx:
    1. Tab Glycomet-GP 2 1 tab BD
    2. Tab Telma-H 1 tab OD
    3. Tab Combiflam 1 tab BD
    4. Tab Pantocid 40 1 tab OD
    """
    parsed2 = parse_prescription_text(rx2)
    # Severe CKD eGFR = 26 in elderly 72yo
    engine2 = SafetyEngine(parsed2, {"age": 72, "gender": "Female", "weight_kg": 54, "egfr": 26, "pregnant": False})
    report2 = engine2.analyze()
    
    triple_whammy = any("Triple Whammy" in a.get("title", "") for a in report2["alerts"]["critical"])
    metformin_contra = any("Metformin in Severe CKD" in a.get("title", "") for a in report2["alerts"]["critical"])
    
    print(f"  -> 'Triple Whammy' Acute Renal Failure Triad: {triple_whammy}")
    print(f"  -> Metformin Absolute Contraindication (MALA): {metformin_contra}")
    assert triple_whammy, "Failed to detect Triple Whammy AKI triad!"
    assert metformin_contra, "Failed to flag Metformin contraindication in eGFR < 30!"

    print("\n=== [4/4] TESTING CLINICAL TRAP 3: CARDIO CYP2C19 & TRAP 4: PEDIATRIC CHELATION ===")
    rx3 = "Tab Clopilet 75 1 tab OD\nTab Omez 20 1 tab OD\nTab Ecosprin 75 1 tab OD"
    parsed3 = parse_prescription_text(rx3)
    engine3 = SafetyEngine(parsed3, {"age": 58, "gender": "Male", "weight_kg": 75, "egfr": 80, "pregnant": False})
    report3 = engine3.analyze()
    cyp2c19 = any("Clopidogrel + Omeprazole" in a.get("title", "") for a in report3["alerts"]["critical"])
    print(f"  -> Clopidogrel + Omeprazole CYP2C19 Blunting Flagged: {cyp2c19}")
    assert cyp2c19, "Failed to detect Clopidogrel + Omeprazole interaction!"

    rx4 = "Tab Cifran 500 1 tab BD\nTab Shelcal 500 1 tab OD"
    parsed4 = parse_prescription_text(rx4)
    engine4 = SafetyEngine(parsed4, {"age": 8, "gender": "Female", "weight_kg": 24, "egfr": 110, "pregnant": False})
    report4 = engine4.analyze()
    chelation = any("Ciprofloxacin + Calcium Carbonate" in a.get("title", "") for a in report4["alerts"]["moderate"])
    ped_warning = any("Fluoroquinolone" in a.get("title", "") for a in report4["alerts"]["moderate"])
    print(f"  -> Cipro + Calcium Insoluble Chelation Flagged: {chelation}")
    print(f"  -> Pediatric Fluoroquinolone Precaution Flagged: {ped_warning}")
    assert chelation, "Failed to detect antibiotic chelation!"

    print("\nALL CLINICAL INTEGRITY & DATABASE TESTS PASSED SUCCESSFULLY! ")

if __name__ == "__main__":
    run_tests()
