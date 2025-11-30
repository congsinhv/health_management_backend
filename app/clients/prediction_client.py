"""HTTP client for Prediction service."""
import logging
from typing import Dict, Any, Optional

from app.core.shared.http_client import ServiceClient
from app.config import settings

logger = logging.getLogger(__name__)


class PredictionClient(ServiceClient):
    """Prediction service client."""

    def __init__(self):
        super().__init__(
            base_url=settings.prediction_service_url,
            timeout=120  # Longer timeout for ML inference + OpenAI
        )

    async def predict(self, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Get health prediction from Prediction service."""
        try:
            response = await self.post(
                "/api/v1/predict/",
                json=user_input
            )
            return response
        except Exception as e:
            logger.error(f"Prediction service request failed: {e}")
            raise


# Singleton instance
prediction_client = PredictionClient()