# app/schemas/predict.py
from pydantic import BaseModel

class UserInput(BaseModel):
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
