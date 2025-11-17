from fastapi import APIRouter, HTTPException
from app.schemas.predict import UserInput
from app.services.predict_service import ObesityPredictorComplete

router = APIRouter(prefix="/predict", tags=["Prediction"])
service = ObesityPredictorComplete()

@router.post("/")
def predict_obesity(data: UserInput):
    try:
        return service.predict_obesity_ai(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
