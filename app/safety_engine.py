from typing import List, Dict, Any, Optional
from app.database import check_interaction_pair, get_all_interactions

class SafetyEngine:
    def __init__(self, parsed_prescription: List[Dict[str, Any]], patient_profile: Dict[str, Any]):
        self.prescription = parsed_prescription
        self.patient = patient_profile
        self.age = patient_profile.get("age", 35)
        self.gender = patient_profile.get("gender", "Unknown")
        self.weight_kg = patient_profile.get("weight_kg", 60)
        self.egfr = patient_profile.get("egfr", 90.0)
        self.is_pregnant = patient_profile.get("pregnant", False)

    def analyze(self) -> Dict[str, Any]:
        """Runs the complete clinical safety analysis across all safety dimensions."""
        # 1. Aggregate active molecules across all brands (maps molecule name -> list of contributions)
        molecules_map = {}
        for med in self.prescription:
            if med.get("unrecognized"):
                continue
            for ing in med.get("active_ingredients", []):
                name = ing["name"]
                if name not in molecules_map:
                    molecules_map[name] = {
                        "name": name,
                        "drug_class": ing["drug_class"],
                        "adult_max_daily_mg": ing["adult_max_daily_mg"],
                        "geriatric_max_daily_mg": ing["geriatric_max_daily_mg"],
                        "pediatric_dose_mg_per_kg_dose": ing.get("pediatric_dose_mg_per_kg_dose", 0),
                        "pediatric_max_daily_mg_per_kg": ing.get("pediatric_max_daily_mg_per_kg", 0),
                        "renal_notes": ing.get("renal_notes", ""),
                        "pregnancy_category": ing.get("pregnancy_category", "C"),
                        "notes": ing.get("notes", ""),
                        "total_daily_dose_mg": 0.0,
                        "contributions": []
                    }
                molecules_map[name]["total_daily_dose_mg"] += ing["daily_dose_mg"]
                molecules_map[name]["contributions"].append({
                    "brand_name": med["brand_name"],
                    "single_strength_mg": ing["strength_per_unit_mg"],
                    "units": med["units_per_dose"],
                    "frequency": med["frequency_description"],
                    "daily_mg": ing["daily_dose_mg"]
                })

        # 2. Check for Duplicate Active Ingredients
        duplicate_ingredient_alerts = self._check_duplicate_ingredients(molecules_map)

        # 3. Check for Class / Therapeutic Duplications (e.g. dual NSAIDs, dual PPIs)
        class_duplication_alerts = self._check_class_duplications(molecules_map)

        # 4. Check for Excessive Dosing (Adult, Geriatric, Pediatric)
        dose_alerts = self._check_excessive_doses(molecules_map)

        # 5. Check Drug-Drug Interactions (DDI)
        ddi_alerts = self._check_drug_interactions(list(molecules_map.keys()))

        # 6. Check Patient-Specific Contraindications (Renal, Age, Pregnancy)
        patient_alerts = self._check_patient_contraindications(molecules_map)

        # 7. Check 'Triple Whammy' Nephrotoxicity (ACEi/ARB + Diuretic + NSAID)
        triple_whammy = self._check_triple_whammy(molecules_map)
        if triple_whammy:
            patient_alerts.append(triple_whammy)

        # Collate all alerts into triage tiers to combat alert fatigue
        all_alerts = duplicate_ingredient_alerts + class_duplication_alerts + dose_alerts + ddi_alerts + patient_alerts

        critical_alerts = [a for a in all_alerts if a["severity"] == "CRITICAL"]
        moderate_alerts = [a for a in all_alerts if a["severity"] == "MODERATE"]
        minor_alerts = [a for a in all_alerts if a["severity"] == "MINOR" or a["severity"] == "INFORMATIONAL"]

        # Sort within each group
        critical_alerts.sort(key=lambda x: x.get("priority_score", 100), reverse=True)

        return {
            "summary": {
                "total_brands": len(self.prescription),
                "total_active_molecules": len(molecules_map),
                "critical_count": len(critical_alerts),
                "moderate_count": len(moderate_alerts),
                "minor_count": len(minor_alerts),
                "safety_score": self._calculate_safety_score(critical_alerts, moderate_alerts, minor_alerts),
                "status": "DANGER" if len(critical_alerts) > 0 else ("WARNING" if len(moderate_alerts) > 0 else "SAFE")
            },
            "active_molecules_matrix": list(molecules_map.values()),
            "alerts": {
                "critical": critical_alerts,
                "moderate": moderate_alerts,
                "minor": minor_alerts
            }
        }

    def _check_duplicate_ingredients(self, molecules_map: Dict[str, Any]) -> List[Dict[str, Any]]:
        alerts = []
        for name, data in molecules_map.items():
            if len(data["contributions"]) > 1:
                brands_list = [c["brand_name"] for c in data["contributions"]]
                brands_str = ", ".join(brands_list)
                total_dose = data["total_daily_dose_mg"]
                max_safe = data["geriatric_max_daily_mg"] if self.age >= 65 else data["adult_max_daily_mg"]

                # If duplicate paracetamol or cumulative exceeds limit -> CRITICAL
                is_exceeded = total_dose > max_safe
                severity = "CRITICAL" if (is_exceeded or name.lower() == "paracetamol") else "MODERATE"

                alerts.append({
                    "id": f"dup_ing_{name}",
                    "type": "DUPLICATE_ACTIVE_INGREDIENT",
                    "severity": severity,
                    "title": f"Duplicate Active Ingredient: {name}",
                    "subtitle": f"Found in {len(data['contributions'])} prescribed brands: {brands_str}",
                    "details": f"The patient is receiving '{name}' concurrently from multiple brands ({brands_str}). Cumulative daily dose is {total_dose:.1f} mg (Maximum safe ceiling: {max_safe:.0f} mg/day).",
                    "clinical_action": f"Discontinue redundant brands. Ensure only ONE single product containing {name} is dispensed to avoid cumulative toxicity.",
                    "contributions": data["contributions"],
                    "priority_score": 95 if severity == "CRITICAL" else 70
                })
        return alerts

    def _check_class_duplications(self, molecules_map: Dict[str, Any]) -> List[Dict[str, Any]]:
        alerts = []
        classes = {}
        for name, data in molecules_map.items():
            drug_class = data["drug_class"]
            if drug_class not in classes:
                classes[drug_class] = []
            classes[drug_class].append(name)

        # Check dual NSAIDs
        nsaids = classes.get("NSAID", [])
        if len(nsaids) > 1:
            alerts.append({
                "id": "dup_class_nsaid",
                "type": "DUPLICATE_DRUG_CLASS",
                "severity": "CRITICAL",
                "title": "Severe Risk: Dual NSAID Co-Prescription",
                "subtitle": f"Concurrent NSAIDs detected: {', '.join(nsaids)}",
                "details": f"The prescription combines multiple distinct Non-Steroidal Anti-Inflammatory Drugs ({', '.join(nsaids)}). Co-prescribing multiple NSAIDs provides no added analgesic efficacy while exponentially multiplying the risk of massive upper GI perforation, ulceration, bleeding, and acute renal papillary necrosis.",
                "clinical_action": "Strictly discontinue one of the NSAIDs. Never co-prescribe two systemic NSAIDs simultaneously.",
                "priority_score": 98
            })

        # Check dual PPIs
        ppis = classes.get("Proton Pump Inhibitor (PPI)", [])
        if len(ppis) > 1:
            alerts.append({
                "id": "dup_class_ppi",
                "type": "DUPLICATE_DRUG_CLASS",
                "severity": "MODERATE",
                "title": "Redundant Therapy: Multiple Proton Pump Inhibitors (PPIs)",
                "subtitle": f"Duplicate PPIs: {', '.join(ppis)}",
                "details": f"The prescription contains more than one PPI ({', '.join(ppis)}). Multiple PPIs offer no additional acid suppression benefit and increase long-term hypomagnesemia and infection risks.",
                "clinical_action": "Consolidate to a single daily PPI regimen (e.g. Pantoprazole 40mg OD BBF).",
                "priority_score": 60
            })

        return alerts

    def _check_excessive_doses(self, molecules_map: Dict[str, Any]) -> List[Dict[str, Any]]:
        alerts = []
        for name, data in molecules_map.items():
            total = data["total_daily_dose_mg"]
            
            # Check pediatric limit
            if self.age < 12 and data["pediatric_max_daily_mg_per_kg"] > 0:
                ped_max = data["pediatric_max_daily_mg_per_kg"] * self.weight_kg
                if total > ped_max:
                    alerts.append({
                        "id": f"ped_overdose_{name}",
                        "type": "EXCESSIVE_PEDIATRIC_DOSE",
                        "severity": "CRITICAL",
                        "title": f"Pediatric Overdose Warning: {name}",
                        "subtitle": f"Total {total:.1f} mg/day exceeds pediatric weight ceiling ({ped_max:.1f} mg/day)",
                        "details": f"For an age of {self.age} years and body weight of {self.weight_kg} kg, the maximum safe pediatric limit is {ped_max:.1f} mg/day ({data['pediatric_max_daily_mg_per_kg']} mg/kg/day). Current calculated intake is {total:.1f} mg/day.",
                        "clinical_action": f"Reduce dose to pediatric weight-appropriate range ({data['pediatric_dose_mg_per_kg_dose']} mg/kg/dose).",
                        "priority_score": 99
                    })
                continue

            # Geriatric limit check
            if self.age >= 65 and data["geriatric_max_daily_mg"] > 0:
                if total > data["geriatric_max_daily_mg"]:
                    alerts.append({
                        "id": f"ger_overdose_{name}",
                        "type": "EXCESSIVE_GERIATRIC_DOSE",
                        "severity": "CRITICAL" if total > data["adult_max_daily_mg"] else "MODERATE",
                        "title": f"Geriatric Dose Ceiling Exceeded: {name}",
                        "subtitle": f"Daily total {total:.1f} mg exceeds elderly maximum of {data['geriatric_max_daily_mg']:.0f} mg/day",
                        "details": f"Elderly patients (age >= 65) have reduced hepatic clearance and renal reserves. Maximum recommended dose in geriatrics is {data['geriatric_max_daily_mg']:.0f} mg/day.",
                        "clinical_action": f"Adjust daily dose down to <= {data['geriatric_max_daily_mg']:.0f} mg/day.",
                        "priority_score": 90
                    })
                continue

            # Standard adult limit check
            if data["adult_max_daily_mg"] > 0 and total > data["adult_max_daily_mg"]:
                alerts.append({
                    "id": f"adult_overdose_{name}",
                    "type": "EXCESSIVE_ADULT_DOSE",
                    "severity": "CRITICAL",
                    "title": f"Maximum Daily Dose Exceeded: {name}",
                    "subtitle": f"Calculated {total:.1f} mg/day exceeds adult ceiling of {data['adult_max_daily_mg']:.0f} mg/day",
                    "details": f"Cumulative prescribed intake of {name} ({total:.1f} mg) is beyond the standard safe maximum daily dose of {data['adult_max_daily_mg']:.0f} mg/day. High toxicity risk.",
                    "clinical_action": f"Ceiling violation! Reduce daily frequency or single strength to stay within {data['adult_max_daily_mg']:.0f} mg/day.",
                    "priority_score": 96
                })

        return alerts

    def _check_drug_interactions(self, molecules: List[str]) -> List[Dict[str, Any]]:
        alerts = []
        seen_pairs = set()

        for i in range(len(molecules)):
            for j in range(i + 1, len(molecules)):
                drug_a = molecules[i]
                drug_b = molecules[j]
                pair_key = tuple(sorted([drug_a.lower(), drug_b.lower()]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                interaction = check_interaction_pair(drug_a, drug_b)
                if interaction:
                    sev = interaction["severity"].upper()
                    alerts.append({
                        "id": f"ddi_{drug_a}_{drug_b}",
                        "type": "DRUG_INTERACTION",
                        "severity": sev,
                        "title": f"Interaction: {drug_a} + {drug_b}",
                        "subtitle": f"Severity: {sev} | Mechanism: {interaction['mechanism'][:60]}...",
                        "details": interaction["clinical_consequence"],
                        "mechanism": interaction["mechanism"],
                        "clinical_action": interaction["recommendation"],
                        "drugs_involved": [drug_a, drug_b],
                        "priority_score": 97 if sev == "CRITICAL" else (75 if sev == "MODERATE" else 40)
                    })
        return alerts

    def _check_patient_contraindications(self, molecules_map: Dict[str, Any]) -> List[Dict[str, Any]]:
        alerts = []

        # 1. Renal impairment checks
        for name, data in molecules_map.items():
            # Metformin in severe renal impairment
            if name.lower() == "metformin":
                if self.egfr < 30:
                    alerts.append({
                        "id": "renal_metformin_contraindicated",
                        "type": "RENAL_CONTRAINDICATION",
                        "severity": "CRITICAL",
                        "title": "ABSOLUTE CONTRAINDICATION: Metformin in Severe CKD",
                        "subtitle": f"Patient eGFR is {self.egfr:.1f} mL/min (Stage 4/5 CKD)",
                        "details": "Metformin is cleared by renal tubular secretion. In severe renal impairment (eGFR < 30 mL/min/1.73m²), Metformin accumulates rapidly, precipitating potentially fatal Metformin-Associated Lactic Acidosis (MALA), with mortality rates exceeding 40%.",
                        "clinical_action": "IMMEDIATELY STOP METFORMIN. Switch to an insulin-based regimen or a renally-safe DPP-4 inhibitor (such as Linagliptin, which requires no renal dose adjustment).",
                        "priority_score": 100
                    })
                elif self.egfr < 45 and data["total_daily_dose_mg"] > 1000:
                    alerts.append({
                        "id": "renal_metformin_high_dose",
                        "type": "RENAL_DOSE_ADJUSTMENT",
                        "severity": "MODERATE",
                        "title": "Metformin Dose Reduction Required for eGFR 30-44",
                        "subtitle": f"Current dose: {data['total_daily_dose_mg']:.0f} mg/day | Recommended ceiling: 1000 mg/day",
                        "details": f"In patients with moderate kidney impairment (eGFR {self.egfr:.1f}), the maximum daily Metformin dose is 1000 mg (or 500 mg initial). Current prescribed dose exceeds this threshold.",
                        "clinical_action": "Reduce Metformin to max 500mg - 1000mg daily and monitor eGFR every 3-6 months.",
                        "priority_score": 75
                    })

            # NSAIDs in severe renal failure
            if data["drug_class"] == "NSAID" and self.egfr < 30:
                alerts.append({
                    "id": f"renal_nsaid_{name}",
                    "type": "RENAL_CONTRAINDICATION",
                    "severity": "CRITICAL",
                    "title": f"NSAID Contraindicated in Severe CKD: {name}",
                    "subtitle": f"Patient eGFR is {self.egfr:.1f} mL/min",
                    "details": f"{name} inhibits renal prostaglandin synthesis (PGE2, PGI2), causing acute renal vasoconstriction, precipitous reduction in glomerular filtration, sodium/water retention, and accelerated progression to end-stage kidney disease.",
                    "clinical_action": f"Avoid {name}. Use Paracetamol (at appropriate non-toxic doses) or topical analgesics for pain relief.",
                    "priority_score": 94
                })

            # Ciprofloxacin dose adjustment in renal impairment
            if name.lower() == "ciprofloxacin" and self.egfr < 30:
                if data["total_daily_dose_mg"] > 500:
                    alerts.append({
                        "id": "renal_cipro_dose",
                        "type": "RENAL_DOSE_ADJUSTMENT",
                        "severity": "MODERATE",
                        "title": "Ciprofloxacin Dose Reduction Required for Severe CKD",
                        "subtitle": f"Current dose {data['total_daily_dose_mg']:.0f} mg/day exceeds recommended 500 mg/day",
                        "details": f"In patients with eGFR < 30 mL/min, Ciprofloxacin clearance is substantially impaired, heightening the risk of neurotoxicity and QT prolongation.",
                        "clinical_action": "Reduce Ciprofloxacin dose to 250-500 mg every 18 to 24 hours.",
                        "priority_score": 72
                    })

            # Pregnancy contraindications
            if self.is_pregnant:
                if data["pregnancy_category"] in ["D", "X"]:
                    alerts.append({
                        "id": f"preg_danger_{name}",
                        "type": "TERATOGENIC_RISK",
                        "severity": "CRITICAL",
                        "title": f"Teratogenic Warning: {name} in Pregnancy",
                        "subtitle": f"FDA Category {data['pregnancy_category']} - Fetal Risk Established",
                        "details": f"{name} is classified as Category {data['pregnancy_category']}. In pregnant patients, exposure can cause severe fetal malformations, fetal renal dysgenesis (ARBs/ACEi), oligohydramnios, or premature closure of the fetal ductus arteriosus (NSAIDs).",
                        "clinical_action": f"Discontinue {name} immediately and consult maternal-fetal medicine specialist for safe pregnancy alternatives.",
                        "priority_score": 99
                    })

            # Pediatric Aspirin contraindication (Reye's syndrome)
            if self.age < 16 and name.lower() == "aspirin":
                alerts.append({
                    "id": "pediatric_aspirin_reye",
                    "type": "PEDIATRIC_CONTRAINDICATION",
                    "severity": "CRITICAL",
                    "title": "Contraindicated: Aspirin in Pediatric Patients (<16 yrs)",
                    "subtitle": "High Risk of Fatal Reye's Syndrome",
                    "details": "Aspirin administration in children and adolescents recovering from viral infections is directly linked to Reye's syndrome, characterized by acute encephalopathy and fatty liver failure with high fatality rates.",
                    "clinical_action": "DO NOT DISPENSE ASPIRIN. Use Paracetamol or Ibuprofen (if age appropriate) for antipyresis and pain.",
                    "priority_score": 100
                })

            # Pediatric Fluoroquinolones precaution
            if self.age < 16 and data["drug_class"] == "Fluoroquinolone Antibiotic":
                alerts.append({
                    "id": f"ped_fluoroquinolone_{name}",
                    "type": "PEDIATRIC_WARNING",
                    "severity": "MODERATE",
                    "title": f"Fluoroquinolone Precaution in Children: {name}",
                    "subtitle": "Risk of Cartilage Toxicity / Arthropathy",
                    "details": f"Fluoroquinolones like {name} are not first-line agents in pediatrics due to weight-bearing joint arthropathy and tendon vulnerability.",
                    "clinical_action": "Consider safer pediatric first-line antimicrobials (e.g. Amoxicillin-Clavulanate, Cephalosporins, or Macrolides) unless specifically indicated for pseudomonal infection.",
                    "priority_score": 70
                })

        return alerts

    def _check_triple_whammy(self, molecules_map: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Detects the clinical 'Triple Whammy' triad:
        1. RAAS Inhibitor (ACEi or ARB: Telmisartan, Ramipril)
        2. Diuretic (Hydrochlorothiazide)
        3. NSAID (Ibuprofen, Aceclofenac, Diclofenac)
        """
        has_raas = False
        has_diuretic = False
        has_nsaid = False
        raas_drugs = []
        diuretic_drugs = []
        nsaid_drugs = []

        for name, data in molecules_map.items():
            cls = data["drug_class"]
            if "Angiotensin" in cls or "ACE" in cls:
                has_raas = True
                raas_drugs.append(name)
            elif "Diuretic" in cls:
                has_diuretic = True
                diuretic_drugs.append(name)
            elif cls == "NSAID":
                has_nsaid = True
                nsaid_drugs.append(name)

        if has_raas and has_diuretic and has_nsaid:
            return {
                "id": "triple_whammy_aki",
                "type": "TRIPLE_WHAMMY_NEPHROTOXICITY",
                "severity": "CRITICAL",
                "title": "EMERGENCY ALERT: 'Triple Whammy' Nephrotoxic Triad Detected",
                "subtitle": f"RAAS Inhibitor ({', '.join(raas_drugs)}) + Diuretic ({', '.join(diuretic_drugs)}) + NSAID ({', '.join(nsaid_drugs)})",
                "details": "This lethal combination collapses renal filtration pressure via three distinct simultaneous hemodynamics: NSAID constricts afferent arteriole, ACEi/ARB dilates efferent arteriole, and Diuretic reduces intravascular volume. This produces acute prerenal renal failure, sharp eGFR collapse, and severe hyperkalemia, especially in hypertensive/elderly patients.",
                "clinical_action": "STOP THE NSAID IMMEDIATELY. Replace with topical analgesic or Paracetamol monotherapy. Check serum creatinine, eGFR, and electrolytes within 48-72 hours.",
                "priority_score": 100
            }
        return None

    def _calculate_safety_score(self, critical: List, moderate: List, minor: List) -> int:
        score = 100
        score -= len(critical) * 35
        score -= len(moderate) * 15
        score -= len(minor) * 3
        return max(0, min(100, score))
