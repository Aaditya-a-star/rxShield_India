import sqlite3
import json
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prescription_safety.db")
SEED_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "seed_data.json")

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL COLLATE NOCASE,
        aliases TEXT,
        drug_class TEXT NOT NULL,
        adult_max_daily_mg REAL NOT NULL,
        geriatric_max_daily_mg REAL NOT NULL,
        pediatric_dose_mg_per_kg_dose REAL DEFAULT 0,
        pediatric_max_daily_mg_per_kg REAL DEFAULT 0,
        renal_notes TEXT,
        pregnancy_category TEXT DEFAULT 'C',
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS brands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brand_name TEXT UNIQUE NOT NULL COLLATE NOCASE,
        manufacturer TEXT,
        form TEXT DEFAULT 'Tablet',
        schedule TEXT DEFAULT 'Schedule H'
    );

    CREATE TABLE IF NOT EXISTS brand_ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brand_id INTEGER NOT NULL,
        ingredient_id INTEGER NOT NULL,
        strength_mg REAL NOT NULL,
        FOREIGN KEY (brand_id) REFERENCES brands (id) ON DELETE CASCADE,
        FOREIGN KEY (ingredient_id) REFERENCES ingredients (id) ON DELETE CASCADE,
        UNIQUE(brand_id, ingredient_id)
    );

    CREATE TABLE IF NOT EXISTS drug_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        drug_a TEXT NOT NULL COLLATE NOCASE,
        drug_b TEXT NOT NULL COLLATE NOCASE,
        severity TEXT NOT NULL, -- CRITICAL, MODERATE, MINOR
        mechanism TEXT NOT NULL,
        clinical_consequence TEXT NOT NULL,
        recommendation TEXT NOT NULL,
        UNIQUE(drug_a, drug_b)
    );

    CREATE TABLE IF NOT EXISTS prescriptions_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        patient_name TEXT DEFAULT 'Anonymous Patient',
        patient_age INTEGER,
        patient_gender TEXT,
        patient_weight REAL,
        egfr REAL,
        renal_status TEXT,
        is_pregnant INTEGER DEFAULT 0,
        prescription_raw TEXT NOT NULL,
        parsed_drugs_json TEXT,
        safety_report_json TEXT,
        critical_alerts_count INTEGER DEFAULT 0,
        moderate_alerts_count INTEGER DEFAULT 0,
        minor_alerts_count INTEGER DEFAULT 0
    );
    """)

    conn.commit()
    conn.close()
    seed_database_if_empty()

def seed_database_if_empty():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM brands")
    count = cursor.fetchone()["count"]
    if count > 0:
        conn.close()
        return

    if not os.path.exists(SEED_PATH):
        conn.close()
        return

    with open(SEED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Insert ingredients
    for ing in data.get("ingredients", []):
        aliases_str = json.dumps(ing.get("aliases", []))
        cursor.execute("""
            INSERT OR IGNORE INTO ingredients 
            (name, aliases, drug_class, adult_max_daily_mg, geriatric_max_daily_mg, 
             pediatric_dose_mg_per_kg_dose, pediatric_max_daily_mg_per_kg, renal_notes, pregnancy_category, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ing["name"],
            aliases_str,
            ing.get("drug_class", "General"),
            ing.get("adult_max_daily_mg", 2000),
            ing.get("geriatric_max_daily_mg", 1000),
            ing.get("pediatric_dose_mg_per_kg_dose", 0),
            ing.get("pediatric_max_daily_mg_per_kg", 0),
            ing.get("renal_notes", ""),
            ing.get("pregnancy_category", "C"),
            ing.get("notes", "")
        ))

    # 2. Insert brands and brand_ingredients
    for br in data.get("brands", []):
        cursor.execute("""
            INSERT OR IGNORE INTO brands (brand_name, manufacturer, form, schedule)
            VALUES (?, ?, ?, ?)
        """, (br["brand_name"], br.get("manufacturer", ""), br.get("form", "Tablet"), br.get("schedule", "Schedule H")))
        
        cursor.execute("SELECT id FROM brands WHERE brand_name = ?", (br["brand_name"],))
        brand_row = cursor.fetchone()
        if not brand_row:
            continue
        brand_id = brand_row["id"]

        for item in br.get("ingredients", []):
            cursor.execute("SELECT id FROM ingredients WHERE name = ?", (item["name"],))
            ing_row = cursor.fetchone()
            if ing_row:
                ing_id = ing_row["id"]
                cursor.execute("""
                    INSERT OR REPLACE INTO brand_ingredients (brand_id, ingredient_id, strength_mg)
                    VALUES (?, ?, ?)
                """, (brand_id, ing_id, float(item["strength_mg"])))

    # 3. Insert interactions
    for inter in data.get("drug_interactions", []):
        cursor.execute("""
            INSERT OR IGNORE INTO drug_interactions 
            (drug_a, drug_b, severity, mechanism, clinical_consequence, recommendation)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            inter["drug_a"],
            inter["drug_b"],
            inter["severity"].upper(),
            inter["mechanism"],
            inter["clinical_consequence"],
            inter["recommendation"]
        ))

    conn.commit()
    conn.close()

def search_brand_in_db(brand_query: str) -> Optional[Dict[str, Any]]:
    """Finds a brand by exact or normalized name, returning its ingredients and details."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Exact match first
    cursor.execute("SELECT * FROM brands WHERE brand_name = ? COLLATE NOCASE", (brand_query.strip(),))
    brand = cursor.fetchone()

    # Try LIKE if not found
    if not brand:
        cursor.execute("SELECT * FROM brands WHERE brand_name LIKE ? COLLATE NOCASE LIMIT 1", (f"{brand_query.strip()}%",))
        brand = cursor.fetchone()

    # Try word-token containment
    if not brand:
        tokens = brand_query.strip().split()
        if tokens:
            cursor.execute("SELECT * FROM brands WHERE brand_name LIKE ? COLLATE NOCASE LIMIT 1", (f"%{tokens[0]}%",))
            brand = cursor.fetchone()

    if not brand:
        conn.close()
        return None

    brand_id = brand["id"]
    cursor.execute("""
        SELECT bi.strength_mg, i.name as ingredient_name, i.drug_class, i.adult_max_daily_mg, 
               i.geriatric_max_daily_mg, i.pediatric_dose_mg_per_kg_dose, i.pediatric_max_daily_mg_per_kg,
               i.renal_notes, i.pregnancy_category, i.notes
        FROM brand_ingredients bi
        JOIN ingredients i ON bi.ingredient_id = i.id
        WHERE bi.brand_id = ?
    """, (brand_id,))
    ingredients = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {
        "id": brand["id"],
        "brand_name": brand["brand_name"],
        "manufacturer": brand["manufacturer"],
        "form": brand["form"],
        "schedule": brand["schedule"],
        "ingredients": ingredients
    }

def get_all_brands() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM brands ORDER BY brand_name ASC")
    brands = [dict(row) for row in cursor.fetchall()]

    for b in brands:
        cursor.execute("""
            SELECT bi.strength_mg, i.name as ingredient_name, i.drug_class
            FROM brand_ingredients bi
            JOIN ingredients i ON bi.ingredient_id = i.id
            WHERE bi.brand_id = ?
        """, (b["id"],))
        b["ingredients"] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return brands

def get_all_interactions() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM drug_interactions ORDER BY severity ASC, drug_a ASC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def check_interaction_pair(drug_a: str, drug_b: str) -> Optional[Dict[str, Any]]:
    """Checks if an interaction exists between two active ingredients in either order."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM drug_interactions 
        WHERE (drug_a = ? COLLATE NOCASE AND drug_b = ? COLLATE NOCASE)
           OR (drug_a = ? COLLATE NOCASE AND drug_b = ? COLLATE NOCASE)
        LIMIT 1
    """, (drug_a, drug_b, drug_b, drug_a))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def save_prescription_audit(record: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO prescriptions_history 
        (patient_name, patient_age, patient_gender, patient_weight, egfr, renal_status, is_pregnant,
         prescription_raw, parsed_drugs_json, safety_report_json, critical_alerts_count, 
         moderate_alerts_count, minor_alerts_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.get("patient_name", "Anonymous"),
        record.get("patient_age"),
        record.get("patient_gender"),
        record.get("patient_weight"),
        record.get("egfr"),
        record.get("renal_status"),
        1 if record.get("is_pregnant") else 0,
        record.get("prescription_raw", ""),
        json.dumps(record.get("parsed_drugs", [])),
        json.dumps(record.get("safety_report", {})),
        record.get("critical_alerts_count", 0),
        record.get("moderate_alerts_count", 0),
        record.get("minor_alerts_count", 0)
    ))
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id

def add_custom_brand(brand_data: Dict[str, Any]) -> Dict[str, Any]:
    """Allows adding a new brand and its active ingredients to SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO brands (brand_name, manufacturer, form, schedule)
            VALUES (?, ?, ?, ?)
        """, (brand_data["brand_name"], brand_data.get("manufacturer", ""), brand_data.get("form", "Tablet"), brand_data.get("schedule", "Schedule H")))
        brand_id = cursor.lastrowid

        for ing in brand_data.get("ingredients", []):
            # Check if ingredient exists, else add
            cursor.execute("SELECT id FROM ingredients WHERE name = ? COLLATE NOCASE", (ing["name"],))
            ing_row = cursor.fetchone()
            if not ing_row:
                cursor.execute("""
                    INSERT INTO ingredients (name, drug_class, adult_max_daily_mg, geriatric_max_daily_mg)
                    VALUES (?, ?, ?, ?)
                """, (ing["name"], ing.get("drug_class", "General"), ing.get("adult_max_daily_mg", 2000), ing.get("geriatric_max_daily_mg", 1000)))
                ing_id = cursor.lastrowid
            else:
                ing_id = ing_row["id"]

            cursor.execute("""
                INSERT INTO brand_ingredients (brand_id, ingredient_id, strength_mg)
                VALUES (?, ?, ?)
            """, (brand_id, ing_id, float(ing["strength_mg"])))

        conn.commit()
        return {"success": True, "brand_id": brand_id, "brand_name": brand_data["brand_name"]}
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
