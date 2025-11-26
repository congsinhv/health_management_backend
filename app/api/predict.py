from fastapi import APIRouter, Depends, status
from typing_extensions import Annotated
import asyncpg
import logging
from app.schemas.predict import UserInput, PredictionResponse, PdfResponse
from app.services.predict_service import ObesityPredictorComplete
from app.services.pdf_service import PdfGeneratorService, PdfGenerationError
from app.db.database import get_database_pool
from app.core.error_context import ErrorContext
from app.exceptions import (
    ServiceUnavailableException,
    ValidationException,
    ResourceNotFoundException,
    FileNotFoundException,
    StorageException,
    PredictionException,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# Service initialization with dependency injection
def create_predict_service(
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
            raise ServiceUnavailableException(
                "Prediction service unavailable - models not loaded"
            )


def create_pdf_service(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> PdfGeneratorService:
    """Dependency to get PDF generator service."""
    return PdfGeneratorService(db_pool)


@router.post("/", response_model=PredictionResponse, status_code=status.HTTP_200_OK)
async def predict_obesity(
    data: UserInput,
    predict_service: ObesityPredictorComplete = Depends(create_predict_service),
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
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "predict_obesity")
    ErrorContext.add_context("operation", "obesity_prediction")

    with ErrorContext(
        "predict_obesity",
        {
            "has_data": bool(data),
            "age": data.age if hasattr(data, "age") else None,
            "gender": data.gender if hasattr(data, "gender") else None,
        },
    ):
        if predict_service is None:
            raise ServiceUnavailableException(
                "Prediction service unavailable - models not loaded"
            )

        # Generate prediction with database save
        prediction = await predict_service.predict_obesity_ai(
            data=data, save_to_db=True
        )

        ErrorContext.add_context("prediction_id", prediction.id)
        return prediction


@router.get(
    "/export/{prediction_id}",
    response_model=PdfResponse,
    status_code=status.HTTP_200_OK,
)
async def export_prediction_pdf(
    prediction_id: str,
    pdf_service: PdfGeneratorService = Depends(create_pdf_service),
):
    """
    Export prediction as PDF (PUBLIC endpoint - no authentication required).

    **PUBLIC ACCESS**: Anyone with prediction_id can export PDF

    **Path Parameters**:
    - prediction_id: External prediction ID from PredictionResponse.id

    **Query Parameters**:
    - template_version: PDF template version ("v1" for original, "v2" for improved design)

    **Response**:
    - PDF public URL

    **Errors**:
    - 404: Not Found (prediction doesn't exist)
    - 422: Validation Error (invalid template version)
    - 500: Internal Server Error (PDF generation failed)

    **Note**: This endpoint regenerates the PDF each time. If a PDF already
    exists, it will be replaced with a new one.
    """
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "export_prediction_pdf")
    ErrorContext.add_context("operation", "pdf_generation")
    ErrorContext.add_context("prediction_id", prediction_id)

    with ErrorContext("export_prediction_pdf", {"prediction_id": prediction_id}):
        # Validate template version

        # Generate and upload PDF with specified template (PUBLIC - no user authorization needed)
        pdf_url = await pdf_service.generate_and_upload_pdf(prediction_id=prediction_id)

        logger.info(f"Generated PDF for prediction {prediction_id}")
        ErrorContext.add_context("pdf_url", pdf_url)

        return PdfResponse(pdf_url=pdf_url)
