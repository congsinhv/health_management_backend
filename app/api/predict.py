from fastapi import APIRouter, HTTPException, Depends, status
from typing_extensions import Annotated
import asyncpg
import logging
from app.schemas.predict import UserInput, PredictionResponse, PdfResponse
from app.services.predict_service import ObesityPredictorComplete
from app.services.pdf_service import PdfGeneratorService
from app.db.database import get_database_pool

logger = logging.getLogger(__name__)
router = APIRouter()


# Service initialization with dependency injection
def get_predict_service(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ObesityPredictorComplete:
    """
    Dependency to get prediction service with database connection.
    Falls back to service without database if connection fails.
    """
    try:
        return ObesityPredictorComplete(pool=db_pool)
    except Exception as e:
        logger.warning(f"Failed to initialize prediction service with database: {e}")
        # Fallback to service without database
        try:
            return ObesityPredictorComplete(pool=None)
        except Exception as fallback_error:
            logger.error(f"Failed to initialize prediction service: {fallback_error}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Prediction service unavailable - models not loaded",
            )


def get_pdf_service(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> PdfGeneratorService:
    """Dependency to get PDF generator service."""
    return PdfGeneratorService(db_pool)


@router.post("/", response_model=PredictionResponse, status_code=status.HTTP_200_OK)
async def predict_obesity(
    data: UserInput,
    predict_service: ObesityPredictorComplete = Depends(get_predict_service),
):
    """
    Generate obesity prediction (PUBLIC endpoint - no authentication required).

    **Request Body**:
    - User demographic and lifestyle data

    **Response**:
    - Comprehensive prediction with health analysis, diet plan, workout plan
    - Includes prediction_id for PDF generation

    **Errors**:
    - 503: Service unavailable (models not loaded)
    - 500: Internal server error
    """
    try:
        if predict_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Prediction service unavailable - models not loaded",
            )

        # Generate prediction with database save
        prediction = await predict_service.predict_obesity_ai(
            data=data, save_to_db=True
        )

        return prediction

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating prediction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate prediction",
        )


@router.get(
    "/export/{prediction_id}",
    response_model=PdfResponse,
    status_code=status.HTTP_200_OK,
)
async def export_prediction_pdf(
    prediction_id: str,
    pdf_service: PdfGeneratorService = Depends(get_pdf_service),
):
    """
    Export prediction as PDF (PUBLIC endpoint - no authentication required).

    **PUBLIC ACCESS**: Anyone with prediction_id can export PDF

    **Path Parameters**:
    - prediction_id: External prediction ID from PredictionResponse.id

    **Response**:
    - PDF public URL

    **Errors**:
    - 404: Not Found (prediction doesn't exist)
    - 500: Internal Server Error (PDF generation failed)

    **Note**: This endpoint regenerates the PDF each time. If a PDF already
    exists, it will be replaced with a new one.
    """
    try:
        # Generate and upload PDF (PUBLIC - no user authorization needed)
        pdf_url = await pdf_service.generate_and_upload_pdf(prediction_id=prediction_id)

        if not pdf_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate PDF",
            )

        logger.info(f"Generated PDF for prediction {prediction_id}")

        return PdfResponse(pdf_url=pdf_url)

    except ValueError as e:
        # Prediction not found
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prediction {prediction_id} not found",
            )
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        logger.error(
            f"Error generating PDF for prediction {prediction_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate PDF",
        )
