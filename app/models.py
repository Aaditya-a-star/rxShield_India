from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class PatientProfile(BaseModel):
    name: Optional[str] = "Anonymous Patient"
    age: int = Field(default=35, ge=0, le=120)
    gender: str = Field(default="Male")
    weight_kg: float = Field(default=65.0, ge=1.0, le=300.0)
    egfr: float = Field(default=90.0, ge=5.0, le=200.0)
    renal_status: Optional[str] = "Normal (eGFR >= 60)"
    pregnant: bool = False

class AnalyzePrescriptionRequest(BaseModel):
    prescription_text: str
    patient: PatientProfile

class CustomIngredientItem(BaseModel):
    name: str
    strength_mg: float
    drug_class: Optional[str] = "General"
    adult_max_daily_mg: Optional[float] = 2000.0
    geriatric_max_daily_mg: Optional[float] = 1000.0

class AddBrandRequest(BaseModel):
    brand_name: str
    manufacturer: Optional[str] = "Generic Pharma"
    form: Optional[str] = "Tablet"
    schedule: Optional[str] = "Schedule H"
    ingredients: List[CustomIngredientItem]
