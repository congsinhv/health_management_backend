# app/schemas/predict.py
from pydantic import BaseModel

class UserInput(BaseModel):
    name: str | None = "User"
    gender: str
    age: float
    height: float
    weight: float
    family_history: bool = False
    FAF: float | None = 1.0
    TUE: float | None = 1.0
    NCP: int | None = 3
    FCVC: float | None = 2.0
    CH2O: float | None = 2.0
    FAVC: int | None = 0
    CALC: int | None = 0
    CAEC: int | None = 2
    MTRANS_Calorie: int | None = 1

class Metric(BaseModel):
    label: str
    value: float
    unit: str

class HealthMetrics(BaseModel):
    weight: Metric
    bmi: Metric
    height: Metric

class HealthAnalysis(BaseModel):
    paragraphs: list[str]

class FoodItem(BaseModel):
    name: str
    calories: int
    count: float
    unit: str

class DailyDietPlan(BaseModel):
    day: int
    breakfast: list[FoodItem]
    lunch: list[FoodItem]
    dinner: list[FoodItem]
    recommendedFoods: str
    foodsToLimit: str

class DietPlan(BaseModel):
    weeklyPlans: list[DailyDietPlan]

class Exercise(BaseModel):
    name: str
    duration: int
    unit: str
    description: str
    sets: int | None = None
    reps: int | None = None

class DailyWorkoutPlan(BaseModel):
    name: str
    day: int
    exercises: list[Exercise]

class WorkoutPlan(BaseModel):
    weeklyPlans: list[DailyWorkoutPlan]

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
