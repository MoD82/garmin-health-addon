from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional


class DailyData(BaseModel):
    date: date
    body_battery: Optional[int] = None
    body_battery_charged: Optional[int] = None
    body_battery_drained: Optional[int] = None
    sleep_score: Optional[int] = None
    hrv_status: Optional[str] = None
    stress_total: Optional[int] = None
    stress_high: Optional[int] = None
    vo2max: Optional[float] = None
    weight: Optional[float] = None
    body_fat: Optional[float] = None
    muscle_mass: Optional[float] = None
    spo2: Optional[int] = None
    spo2_lowest: Optional[int] = None
    respiration: Optional[float] = None
    readiness_score: Optional[int] = None


class Activity(BaseModel):
    date: date
    name: str
    activity_type: str = "unknown"
    distance_km: Optional[float] = None
    duration_min: Optional[int] = None
    elevation_m: Optional[int] = None
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    avg_power: Optional[int] = None
    max_power: Optional[int] = None
    norm_power: Optional[int] = None
    max_20min_power: Optional[int] = None
    tss: Optional[float] = None
    intensity_factor: Optional[float] = None
    aero_te: Optional[float] = None
    anaero_te: Optional[float] = None
    training_load: Optional[int] = None


class BloodPressure(BaseModel):
    measured_at: datetime
    systolic: int
    diastolic: int
    pulse: int


class Event(BaseModel):
    id: Optional[int] = None
    event_type: str  # race | vacation | note
    date_start: date
    date_end: Optional[date] = None
    title: str
    priority: Optional[str] = None  # A | B | C
    distance_km: Optional[float] = None
    elevation_m: Optional[int] = None
    goal: Optional[str] = None
    training_possible: bool = True
    status: str = "planned"  # planned | completed | dns | dnf


class DailyCheckin(BaseModel):
    date: date
    feeling: int  # 1–5
    note: Optional[str] = None


class Analysis(BaseModel):
    date: date
    readiness_score: Optional[int] = None
    gpt_response: Optional[str] = None
    weekly_plan: Optional[str] = None
    email_sent: bool = False
    status: str = "pending"  # pending | running | success | error
    error_message: Optional[str] = None


class PersonalRecord(BaseModel):
    activity_type: str
    category: str
    value: float
    date: date
