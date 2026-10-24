#  RxShield India: Prescription Safety Checker for Indian Brand Medicines

> **Hackathon Solution** for de-obfuscating Indian commercial brand medicines, unmasking hidden fixed-dose combination (FDC) toxicity, parsing clinical abbreviations, and mitigating clinical alert fatigue through intelligent tiered triage.

---

##  Problem Statement & Clinical Context

In India, more than **70% to 80% of prescriptions use trade/brand names** rather than generic international nonproprietary names (INN). Furthermore, India is one of the world's largest consumers of **Fixed Dose Combinations (FDCs)**.

### The Hidden Hazards in Indian Prescriptions:
1. **Unintentional Active Ingredient Duplication:**
   - A patient prescribed *Dolo 650* (Paracetamol 650mg TDS) plus *Combiflam* (Ibuprofen 400mg + Paracetamol 325mg BD) inadvertently receives **3,250 mg to 3,900 mg of Paracetamol per day**, pushing them to the brink of acute hepatotoxicity.
2. **Dual NSAID Poisoning:**
   - Combining *Combiflam* (Ibuprofen) with *Zerodol-P* (Aceclofenac) or *Voveran* (Diclofenac) provides zero additional pain relief while exponentially multiplying gastrointestinal ulceration, massive bleeding, and acute renal failure.
3. **Indian Medical Abbreviations:**
   - Frequency shorthands like **OD, BD, TDS, QID, SOS, HS, 1-0-1, 1-1-1, BBF (before breakfast), and PC (after meals)** dictate cumulative daily exposure.
4. **Organ Function & Demographics:**
   - Safe dosages depend heavily on **age, body weight, and kidney function (eGFR / CKD stage)**. For example, Metformin in severe CKD (eGFR < 30) risks fatal lactic acidosis; the classic *"Triple Whammy"* (ACEi/ARB + Diuretic + NSAID) precipitates acute kidney collapse.
5. **The Alert Fatigue Dilemma:**
   - Conventional checkers overwhelm clinicians with endless trivial warnings, causing doctors to dismiss all alerts—including life-threatening ones. **RxShield India solves alert fatigue via intelligent tiered prioritization and an Anti-Alert Fatigue Engine**.

---

##  System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        RxShield India UI Dashboard                     │
│    (Tailwind CSS • Lucide Icons • Live Dose Gauges • Anti-Fatigue Triage)│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / JSON
┌───────────────────────────────────▼────────────────────────────────────┐
│                         FastAPI Clinical Backend                       │
├───────────────────────────────────┬────────────────────────────────────┤
│ 1. Indian Prescription NLP Parser │ Regex & Indian Sig Decoder         │
│ 2. FDC De-obfuscation Engine      │ Multi-token Brand Decomposition    │
│ 3. Multi-Factor Safety Engine     │ Dose Accumulator & DDI Matrix      │
│ 4. Organ & Demographics Evaluator │ eGFR CKD Staging & Pediatric mg/kg │
│ 5. Anti-Alert Fatigue Classifier  │ Critical vs Moderate vs Advisory   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ SQL Queries
┌───────────────────────────────────▼────────────────────────────────────┐
│                    SQLite Database (prescription_safety.db)             │
│  • brands (56+ Indian Brands)      • brand_ingredients (FDC Mapping)   │
│  • ingredients (Max safe limits)   • drug_interactions (DDI pairs)     │
│  • prescriptions_history (Audit)                                       │
└────────────────────────────────────────────────────────────────────────┘
```

---

##  The 4 Benchmark Clinical Traps (Instant Demo)

RxShield India includes 4 pre-engineered benchmark clinical traps directly runnable from the top banner:

| Trap # | Title | Prescription Profile | Critical Clinical Danger |
|---|---|---|---|
| **Trap 1** | **Hidden Combination Overdose** | *Dolo 650 + Combiflam + Zerodol-P + Pan 40* | Combiflam and Zerodol-P both contain Paracetamol, pushing daily dose to >3,250mg. Co-prescribing Ibuprofen + Aceclofenac triggers **Dual NSAID** gastrointestinal bleeding hazard. |
| **Trap 2** | **The Elderly Diabetic 'Triple Whammy'** | *Glycomet-GP 2 + Telma-H + Combiflam* in 72yo (eGFR 26) | Metformin is **strictly contraindicated** at eGFR < 30 due to fatal Lactic Acidosis (MALA). Telmisartan + HCTZ + Ibuprofen triggers the lethal *"Triple Whammy"* renal hemodynamic collapse. |
| **Trap 3** | **Cardio-GI Hazard & CYP2C19 Blunting** | *Clopilet 75 + Ecosprin 75 + Omez 20 + Voveran 100* | Omeprazole (Omez) inhibits CYP2C19, preventing activation of Clopidogrel (Clopilet) and leaving coronary stents vulnerable to thrombosis. Concurrent Diclofenac + dual antiplatelets skyrockets ulcer hemorrhage risk. |
| **Trap 4** | **Pediatric Chelation & Overdose** | *Cifran 500 BD + Shelcal 500 OD* in 8yo (24 kg) | Calcium Carbonate binds Ciprofloxacin into an insoluble chelate, slashing antibiotic bioavailability. Adult tablet dosing causes pediatric fluoroquinolone overdose. |

---

##  Anti-Alert Fatigue Engine

The problem statement explicitly highlights:
> *"Too many minor alerts cause alert fatigue, so users ignore important warnings."*

RxShield India implements a multi-tier triage hierarchy:
- **Tier 1: CRITICAL STOP (Pulsing Red Card)**
  - Life-threatening emergencies: Cumulative Paracetamol overdose, Dual NSAIDs, Metformin in eGFR < 30, Triple Whammy AKI, Sildenafil + Nitrates, Clopidogrel + Omeprazole, Pediatric Aspirin (Reye's syndrome).
- **Tier 2: MODERATE CAUTION (Amber Card)**
  - Actionable clinical adjustments: Renal dose reduction (e.g. Ciprofloxacin in CKD), Fluoroquinolone + Calcium chelation spacing (2 hours apart), QT prolongation monitoring.
- **Tier 3: INFORMATIONAL ADVISORY (Sequestered Drawer)**
  - Minor non-urgent notes (food timing, routine B12 monitoring with long-term PPI + Metformin).
  - Kept in a collapsed drawer by default when **Anti-Alert Fatigue Mode** is ON, ensuring zero distraction from high-risk alerts!

---

##  Database Schema & Connectivity

The application connects to an embedded SQLite database (`prescription_safety.db`):
- `brands`: Stores Indian commercial brand names, manufacturers, dosage forms, and drug schedules (OTC, Schedule H, H1).
- `ingredients`: Active pharmaceutical ingredients, chemical class, adult maximum daily dose, geriatric ceiling, pediatric mg/kg limits, renal notes, and pregnancy category.
- `brand_ingredients`: Many-to-many junction table modeling Indian Fixed Dose Combinations (e.g., Combiflam -> Ibuprofen 400mg + Paracetamol 325mg).
- `drug_interactions`: Mechanism, clinical consequence, severity, and actionable recommendations.
- `prescriptions_history`: Full audit trail of checked prescriptions, patient details, and flagged safety violations.

---

##  Quick Start Guide

### 1. Requirements
- Python 3.9+
- Installed packages: `fastapi`, `uvicorn`, `pydantic` (already installed in the environment)

### 2. Run Clinical Verification Test Suite
```bash
python test_cases/test_checker.py
```

### 3. Launch Web Application
```bash
python run.py
```
Open your browser and navigate to:
**`http://127.0.0.1:8000`**

---

##  API Endpoints

- `POST /api/analyze` - Parses typed prescription text and executes multi-dimensional safety checks.
- `GET /api/brands` - Retrieves all Indian brands and their active ingredient breakdowns.
- `POST /api/brands` - Adds a custom Indian medicine or combination to the SQLite database.
- `GET /api/interactions` - Returns pairwise interaction matrix.
- `GET /api/samples` - Returns the benchmark clinical trap cases.
- `GET /api/history` - Fetches prescription audit logs.
- `GET /api/stats` - Returns live database record counters.
- `GET /docs` - Interactive OpenAPI / Swagger UI.

---
*Created for the Healthcare Innovation Hackathon 2026.*
