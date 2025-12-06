
from pydantic import BaseModel, field_validator
from typing import Optional, List


class UserInput(BaseModel):
    name: Optional[str] = "User"
    gender: str
    age: float
    height: float
    weight: float
    family_history: bool = False
    FAF: Optional[float] = 1.0
    TUE: Optional[float] = 1.0
    NCP: Optional[int] = 3
    FCVC: Optional[float] = 2.0
    CH2O: Optional[float] = 2.0
    FAVC: Optional[int] = 0
    CALC: Optional[int] = 0
    CAEC: Optional[int] = 2
    MTRANS_Calorie: Optional[int] = 1


class Metric(BaseModel):
    label: str
    value: float
    unit: str


class HealthMetrics(BaseModel):
    weight: Metric
    bmi: Metric
    height: Metric


class HealthAnalysis(BaseModel):
    paragraphs: List[str]


class FoodItem(BaseModel):
    name: str
    calories: int = 0
    count: float = 1.0
    unit: str = ""


class DailyDietPlan(BaseModel):
    day: int
    breakfast: List[FoodItem] = []
    lunch: List[FoodItem] = []
    dinner: List[FoodItem] = []
    recommendedFoods: str = ""
    foodsToLimit: str = ""


class DietPlan(BaseModel):
    weeklyPlans: List[DailyDietPlan]


class Exercise(BaseModel):
    name: str
    duration: int
    unit: str
    description: str
    sets: Optional[int] = None
    reps: Optional[int] = None

    @field_validator("sets", "reps", mode="before")
    @classmethod
    def convert_na_to_none(cls, v):
        """Convert 'N/A' string to None for integer fields."""
        if isinstance(v, str) and v.upper() in ("N/A", "NA", "NONE", ""):
            return None
        return v


class DailyWorkoutPlan(BaseModel):
    name: str
    day: int
    exercises: List[Exercise]


class WorkoutPlan(BaseModel):
    weeklyPlans: List[DailyWorkoutPlan]


class UserInputResponse(BaseModel):
    name: str
    gender: str
    age: float
    height: float
    weight: float
    familyHistory: str
    highCalorieFood: str
    vegetableFrequency: str
    waterIntake: str
    mainMeals: int
    snackFrequency: str
    physicalActivity: str
    screenTime: str
    transportation: str
    smoking: str
    alcohol: str


class PredictionDetail(BaseModel):
    level: str
    confidence: float
    bmi: float
    status: str
    reliability: str


class PredictionResponse(BaseModel):
    id: str
    timestamp: str
    userInput: UserInputResponse
    prediction: PredictionDetail
    healthMetrics: HealthMetrics
    healthAnalysis: HealthAnalysis
    dietPlan: DietPlan
    workoutPlan: WorkoutPlan


class PdfResponse(BaseModel):
    """PDF generation response."""

    pdf_url: str
