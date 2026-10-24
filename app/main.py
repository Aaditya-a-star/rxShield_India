import os
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import (
    init_db,
    get_all_brands,
    get_all_interactions,
    save_prescription_audit,
    add_custom_brand,
    get_db_connection
)
from app.parser import parse_prescription_text
from app.safety_engine import SafetyEngine
from app.models import AnalyzePrescriptionRequest, AddBrandRequest

app = FastAPI(
    title="RxShield India - Prescription Safety Checker",
    description="Intelligent Clinical Safety Checker for Indian Brand Medicines, Combinations, and Abbreviations",
    version="2.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure database is initialized on startup
@app.on_event("startup")
def on_startup():
    init_db()

# Mount static folder
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return "<h1>RxShield India API is active. UI file loading...</h1>"

@app.post("/api/analyze")
def analyze_prescription(req: AnalyzePrescriptionRequest):
    if not req.prescription_text.strip():
        raise HTTPException(status_code=400, detail="Prescription text cannot be empty.")

    # 1. Parse prescription text
    parsed_drugs = parse_prescription_text(req.prescription_text)

    # 2. Run safety engine
    patient_dict = req.patient.model_dump()
    engine = SafetyEngine(parsed_drugs, patient_dict)
    report = engine.analyze()

    # 3. Save audit record to SQLite database
    audit_id = save_prescription_audit({
        "patient_name": req.patient.name,
        "patient_age": req.patient.age,
        "patient_gender": req.patient.gender,
        "patient_weight": req.patient.weight_kg,
        "egfr": req.patient.egfr,
        "renal_status": req.patient.renal_status,
        "is_pregnant": req.patient.pregnant,
        "prescription_raw": req.prescription_text,
        "parsed_drugs": parsed_drugs,
        "safety_report": report,
        "critical_alerts_count": report["summary"]["critical_count"],
        "moderate_alerts_count": report["summary"]["moderate_count"],
        "minor_alerts_count": report["summary"]["minor_count"]
    })

    return {
        "audit_id": audit_id,
        "patient": patient_dict,
        "parsed_drugs": parsed_drugs,
        "report": report
    }

@app.get("/api/brands")
def list_brands():
    return get_all_brands()

@app.get("/api/interactions")
def list_interactions():
    return get_all_interactions()

@app.get("/api/samples")
def get_sample_cases():
    seed_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "seed_data.json")
    if os.path.exists(seed_path):
        with open(seed_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("sample_prescriptions", [])
    return []

@app.post("/api/brands")
def create_brand(payload: AddBrandRequest):
    try:
        res = add_custom_brand(payload.model_dump())
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/history")
def get_audit_history(limit: int = 10):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, created_at, patient_name, patient_age, patient_gender, 
               critical_alerts_count, moderate_alerts_count, minor_alerts_count,
               prescription_raw
        FROM prescriptions_history
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.get("/api/stats")
def get_database_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM brands")
    total_brands = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM ingredients")
    total_ingredients = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM drug_interactions")
    total_interactions = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM prescriptions_history")
    total_checks = cursor.fetchone()["count"]

    conn.close()
    return {
        "total_brands": total_brands,
        "total_ingredients": total_ingredients,
        "total_interactions": total_interactions,
        "total_checks": total_checks
    }
