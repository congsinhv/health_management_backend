# Phase 3: Prediction Service Extraction

**Phase:** 3 of 5
**Duration:** 2-3 days
**Priority:** High
**Status:** Not Started
**Dependencies:** Phase 2 (Chat AI Extraction)

## Context

**Research Reports:**
- [FastAPI ML Patterns](./research/researcher-02-fastapi-ml-patterns.md) - sklearn ONNX conversion (5x speedup)
- [GCP Microservices](./research/researcher-01-gcp-microservices.md) - Min instances=0 for on-demand workloads

**Current Prediction Service:**
- Location: `app/services/predict_service.py` (monolithic, 18KB)
- Model: sklearn Random Forest (~50MB)
- Dependencies: PDF service (WeasyPrint), OpenAI API, database writes
- Usage: Async (not real-time critical)

## Overview

Extract health prediction service into standalone microservice with ONNX-optimized sklearn models (5x faster), on-demand scaling (min=0 instances), and Main API proxy pattern. Prediction service writes results via Main API proxy (no direct database access).

## Key Insights from Research

**ONNX Optimization for sklearn (Researcher-02):**
- Convert sklearn models to ONNX: 5x CPU speedup
- ONNX Runtime providers: CPUExecutionProvider (no GPU needed)
- One-time conversion; deploy .onnx file instead of .pkl

**On-Demand Scaling (Researcher-01):**
- Prediction workload: Async, tolerate cold starts
- Min instances=0 saves 100% idle cost (~$3.46/day)
- Cold start: 2-3s (acceptable for prediction workflow)

**Database Strategy:**
- Prediction service: NO direct database access
- Main API stores predictions via POST to `/api/v1/predictions`
- Prediction service returns data; Main API persists

## Requirements

**New Service Structure:**
```
prediction_service/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   └── predict.py
│   ├── services/
│   │   └── predict_service.py
│   ├── ml/
│   │   ├── model_loader.py     # ONNX model loader
│   │   └── feature_engineer.py # Feature engineering
│   └── core/
│       └── shared/              # Symlink
├── models/
│   └── obesity_classifier.onnx  # Converted model
├── tests/
├── Dockerfile
├── requirements.txt
└── README.md
```

**Main API Changes:**
```python
# app/api/predict.py (proxy pattern)
@router.post("/api/v1/predict")
async def predict(data: UserInput):
    # 1. Call Prediction service
    prediction = await prediction_client.predict(data)
    # 2. Store in database
    prediction_id = await prediction_repo.create(prediction)
    # 3. Return with ID
    return {**prediction, "id": prediction_id}
```

## Architecture Changes

**Before (Monolith):**
```
User → Main API /api/v1/predict
         ↓
       PredictService (in-process)
         ↓
       sklearn model → OpenAI → Database
         ↓
       Response
```

**After (Microservices):**
```
User → Main API /api/v1/predict
         ↓ HTTP+IAM
       Prediction Service /predict
         ↓
       sklearn-ONNX model → OpenAI
         ↓ (return prediction data)
       Main API
         ↓
       Database (persist prediction)
         ↓
       Response
```

**PDF Generation Flow:**
```
User → Main API /api/v1/predictions/{id}/pdf
         ↓
       Fetch prediction from database
         ↓
       PDF Service (still in Main API)
         ↓
       WeasyPrint → GCS upload
         ↓
       Response (PDF URL)
```

## Related Code Files

**Files to Move:**
- `app/services/predict_service.py` → `prediction_service/app/services/predict_service.py`
- `app/schemas/predict.py` → `prediction_service/app/schemas/predict.py`
- `models_obesity/obesity_classifier_final.pkl` → Convert to `.onnx`
- `models_obesity/label_encoder.pkl` → Convert to `.onnx`

**Files to Create:**
- `prediction_service/app/main.py`
- `prediction_service/app/ml/model_loader.py`
- `prediction_service/app/ml/feature_engineer.py`
- `prediction_service/scripts/convert_models_to_onnx.py`
- `app/clients/prediction_client.py` (Main API)

**Files to Update:**
- `app/api/predict.py` - Convert to proxy pattern
- `app/config.py` - Add `PREDICTION_SERVICE_URL`
- Keep PDF service in Main API (depends on database)

## Implementation Steps

### 1. Convert sklearn Models to ONNX (Day 1)

**1.1 Create Conversion Script:**
```python
# prediction_service/scripts/convert_models_to_onnx.py
"""Convert sklearn models to ONNX format."""
import pickle
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
import onnx

def convert_classifier_to_onnx():
    """Convert obesity classifier to ONNX."""
    # Load sklearn model
    with open("models_obesity/obesity_classifier_final.pkl", "rb") as f:
        rf_model = pickle.load(f)

    # Define input shape (19 features based on current implementation)
    initial_type = [("float_input", FloatTensorType([None, 19]))]

    # Convert to ONNX
    onnx_model = convert_sklearn(
        rf_model,
        initial_types=initial_type,
        target_opset=12
    )

    # Save ONNX model
    with open("models/obesity_classifier.onnx", "wb") as f:
        f.write(onnx_model.SerializeToString())

    print("Obesity classifier converted to ONNX")
    print(f"Model size: {len(onnx_model.SerializeToString()) / 1024 / 1024:.2f} MB")

def convert_label_encoder_to_onnx():
    """Convert label encoder to ONNX."""
    with open("models_obesity/label_encoder.pkl", "rb") as f:
        label_encoder = pickle.load(f)

    # Label encoders are simple mappings; store as JSON
    import json
    classes = {i: label for i, label in enumerate(label_encoder.classes_)}

    with open("models/label_encoder.json", "w") as f:
        json.dump(classes, f)

    print("Label encoder converted to JSON")

if __name__ == "__main__":
    convert_classifier_to_onnx()
    convert_label_encoder_to_onnx()
```

**1.2 Run Conversion:**
```bash
cd prediction_service
python scripts/convert_models_to_onnx.py

# Verify ONNX model
python -c "import onnx; model = onnx.load('models/obesity_classifier.onnx'); onnx.checker.check_model(model)"
```

### 2. Create Prediction Service (Day 1)

**2.1 Create Main Application:**
```python
# prediction_service/app/main.py
"""Prediction Service - Health predictions with ONNX."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .api import predict
from .services.predict_service import PredictService

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    logger.info("Starting Prediction Service...")

    # Initialize prediction service with ONNX models
    try:
        app.state.predict_service = await PredictService.create(settings)
        logger.info("Prediction service initialized with ONNX models")
    except Exception as e:
        logger.error(f"Failed to initialize prediction service: {e}")
        raise

    yield

    logger.info("Shutting down Prediction Service...")

app = FastAPI(
    title="VHealth Prediction Service",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict.router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    """Health check."""
    return {
        "status": "healthy",
        "service": "prediction",
        "model_loaded": app.state.predict_service.is_model_loaded()
    }
```

**2.2 Create ONNX Model Loader:**
```python
# prediction_service/app/ml/model_loader.py
"""ONNX model loader for sklearn models."""
import onnxruntime as ort
import numpy as np
import json
import logging

logger = logging.getLogger(__name__)

class ONNXModelLoader:
    """Load and run ONNX models."""

    def __init__(self, model_path: str, label_encoder_path: str):
        self.model_path = model_path
        self.label_encoder_path = label_encoder_path
        self.session = None
        self.label_encoder = None

    async def initialize(self):
        """Load ONNX model."""
        logger.info(f"Loading ONNX model from {self.model_path}")

        # Create ONNX Runtime session
        self.session = ort.InferenceSession(
            self.model_path,
            providers=["CPUExecutionProvider"]
        )

        # Load label encoder
        with open(self.label_encoder_path, "r") as f:
            self.label_encoder = json.load(f)

        logger.info("ONNX model loaded successfully")

    def predict(self, features: np.ndarray) -> tuple:
        """Run prediction with ONNX model."""
        # Get input/output names
        input_name = self.session.get_inputs()[0].name
        output_name = self.session.get_outputs()[0].name

        # Run inference (5x faster than sklearn)
        predictions = self.session.run(
            [output_name],
            {input_name: features.astype(np.float32)}
        )

        # Decode label
        label_index = int(predictions[0][0])
        label = self.label_encoder.get(str(label_index), "Unknown")

        return label, predictions[0]
```

**2.3 Update Prediction Service:**
```python
# prediction_service/app/services/predict_service.py
"""Prediction service with ONNX models."""
import numpy as np
from app.ml.model_loader import ONNXModelLoader
from app.ml.feature_engineer import FeatureEngineer
from app.schemas.predict import UserInput, PredictionResponse

class PredictService:
    """Health prediction service."""

    def __init__(self, model_loader: ONNXModelLoader):
        self.model_loader = model_loader
        self.feature_engineer = FeatureEngineer()

    @classmethod
    async def create(cls, settings):
        """Create and initialize service."""
        model_loader = ONNXModelLoader(
            model_path=settings.model_path,
            label_encoder_path=settings.label_encoder_path
        )
        await model_loader.initialize()
        return cls(model_loader)

    async def predict(self, user_input: UserInput) -> PredictionResponse:
        """Generate health prediction."""
        # 1. Feature engineering
        features = self.feature_engineer.engineer_features(user_input)

        # 2. Model prediction (ONNX - 5x faster)
        obesity_level, raw_prediction = self.model_loader.predict(features)

        # 3. Calculate health metrics
        bmi = self._calculate_bmi(user_input.weight, user_input.height)
        metabolic_age = self._calculate_metabolic_age(
            user_input.age, bmi, user_input
        )

        # 4. Generate AI recommendations (OpenAI)
        diet_plan = await self._generate_diet_plan(obesity_level, bmi)
        workout_plan = await self._generate_workout_plan(obesity_level, bmi)

        # 5. Return prediction data (Main API will persist)
        return PredictionResponse(
            obesity_level=obesity_level,
            bmi=bmi,
            metabolic_age=metabolic_age,
            diet_plan=diet_plan,
            workout_plan=workout_plan,
            raw_prediction=raw_prediction.tolist()
        )

    def is_model_loaded(self) -> bool:
        """Check if model is loaded."""
        return self.model_loader.session is not None
```

### 3. Create Prediction API Endpoint (Day 1-2)

```python
# prediction_service/app/api/predict.py
"""Prediction API endpoints."""
from fastapi import APIRouter, Depends, Request
from app.schemas.predict import UserInput, PredictionResponse

router = APIRouter(prefix="/predict", tags=["Predictions"])

def get_predict_service(request: Request):
    """Get prediction service from app state."""
    return request.app.state.predict_service

@router.post("/", response_model=PredictionResponse)
async def predict(
    user_input: UserInput,
    predict_service = Depends(get_predict_service)
):
    """Generate health prediction."""
    prediction = await predict_service.predict(user_input)
    return prediction

@router.get("/health")
async def health_check(predict_service = Depends(get_predict_service)):
    """Check prediction service health."""
    return {
        "status": "healthy",
        "model_loaded": predict_service.is_model_loaded()
    }
```

### 4. Update Main API Proxy (Day 2)

**4.1 Create Prediction Client:**
```python
# app/clients/prediction_client.py
"""HTTP client for Prediction service."""
from app.core.shared.http_client import ServiceClient
from app.schemas.predict import UserInput, PredictionResponse
from app.config import settings

class PredictionClient(ServiceClient):
    """Prediction service client."""

    def __init__(self):
        super().__init__(
            base_url=settings.prediction_service_url,
            timeout=120  # Longer timeout for ML inference + OpenAI
        )

    async def predict(self, user_input: UserInput) -> PredictionResponse:
        """Get health prediction from Prediction service."""
        response = await self.post(
            "/api/v1/predict/",
            json=user_input.dict()
        )
        return PredictionResponse(**response)

# Singleton
prediction_client = PredictionClient()
```

**4.2 Update Main API Predict Router:**
```python
# app/api/predict.py (Main API)
"""Prediction API - Proxy to Prediction service + DB persistence."""
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.predict import UserInput, PredictionResponse
from app.clients.prediction_client import prediction_client
from app.db.prediction import PredictionRepository
from app.db.database import get_db_pool
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/predict", tags=["Predictions"])

@router.post("/", response_model=PredictionResponse)
async def predict(
    user_input: UserInput,
    current_user = Depends(get_current_user),
    pool = Depends(get_db_pool)
):
    """Generate health prediction (proxied + persisted)."""
    try:
        # 1. Call Prediction service
        prediction = await prediction_client.predict(user_input)

        # 2. Persist to database
        prediction_repo = PredictionRepository(pool)
        prediction_id = await prediction_repo.create_prediction(
            user_id=current_user.id,
            prediction_data={
                "obesity_level": prediction.obesity_level,
                "bmi": prediction.bmi,
                "metabolic_age": prediction.metabolic_age,
                "diet_plan": prediction.diet_plan,
                "workout_plan": prediction.workout_plan,
                "raw_prediction": prediction.raw_prediction,
                "input_data": user_input.dict()
            }
        )

        # 3. Return with ID
        return PredictionResponse(
            id=prediction_id,
            **prediction.dict()
        )

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Prediction service unavailable: {str(e)}"
        )

# PDF generation stays in Main API (requires database access)
@router.post("/{prediction_id}/pdf")
async def generate_pdf(
    prediction_id: str,
    current_user = Depends(get_current_user),
    pool = Depends(get_db_pool)
):
    """Generate PDF report for prediction."""
    # This stays in Main API - uses existing PDF service
    prediction_repo = PredictionRepository(pool)
    prediction = await prediction_repo.get_prediction(prediction_id)

    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    # Use existing PDF service (in Main API)
    from app.services.pdf_service import PdfGeneratorService
    pdf_service = PdfGeneratorService()
    pdf_url = await pdf_service.generate_and_upload_pdf(prediction)

    return {"pdf_url": pdf_url}
```

### 5. Create Dockerfile (Day 2)

```dockerfile
# prediction_service/Dockerfile
FROM python:3.13-slim

# Minimal dependencies (no fonts needed - no PDF generation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /home/appuser/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY models/ ./models/

RUN chown -R appuser:appuser /home/appuser
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')" || exit 1

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**requirements.txt:**
```
fastapi==0.115.0
uvicorn[standard]==0.32.0
onnxruntime==1.18.0  # ONNX runtime (5x speedup)
numpy==1.26.0
openai==2.8.0
aiohttp==3.9.0
google-auth>=2.23.0
pydantic-settings>=2.0.0
```

### 6. Testing and Deployment (Day 3)

**6.1 Benchmark ONNX vs sklearn:**
```python
# tests/benchmark_onnx_sklearn.py
"""Benchmark ONNX vs sklearn prediction."""
import time
import pickle
import numpy as np
from onnxruntime import InferenceSession

# Load sklearn model
with open("models_obesity/obesity_classifier_final.pkl", "rb") as f:
    sklearn_model = pickle.load(f)

# Load ONNX model
onnx_session = InferenceSession("models/obesity_classifier.onnx")

# Test data
X_test = np.random.rand(100, 19).astype(np.float32)

# Benchmark sklearn
start = time.time()
for _ in range(100):
    sklearn_model.predict(X_test)
sklearn_time = time.time() - start

# Benchmark ONNX
input_name = onnx_session.get_inputs()[0].name
output_name = onnx_session.get_outputs()[0].name

start = time.time()
for _ in range(100):
    onnx_session.run([output_name], {input_name: X_test})
onnx_time = time.time() - start

print(f"sklearn: {sklearn_time:.3f}s")
print(f"ONNX: {onnx_time:.3f}s")
print(f"Speedup: {sklearn_time / onnx_time:.2f}x")
```

**6.2 Deploy Prediction Service:**
```bash
# Build image
docker build -t prediction-service:latest prediction_service/

# Deploy to Cloud Run (min=0 for on-demand)
gcloud run deploy prediction-service \
  --image gcr.io/PROJECT/prediction-service:latest \
  --region asia-southeast1 \
  --memory 768Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars OPENAI_API_KEY=${OPENAI_API_KEY}

# Get URL
PREDICTION_URL=$(gcloud run services describe prediction-service --format='value(status.url)')

# Update Main API
gcloud run services update main-api-service \
  --set-env-vars PREDICTION_SERVICE_URL=${PREDICTION_URL}

# Grant IAM permissions
gcloud run services add-iam-policy-binding prediction-service \
  --member=serviceAccount:main-api-sa@PROJECT.iam.gserviceaccount.com \
  --role=roles/run.invoker
```

## Todo List

- [ ] Create sklearn to ONNX conversion script
- [ ] Run conversion script and verify ONNX models
- [ ] Benchmark ONNX vs sklearn (verify 5x speedup)
- [ ] Create `prediction_service/` directory structure
- [ ] Create `prediction_service/app/main.py`
- [ ] Create ONNX model loader in `app/ml/model_loader.py`
- [ ] Create feature engineering module
- [ ] Migrate `predict_service.py` with ONNX integration
- [ ] Create Prediction API endpoints
- [ ] Create Prediction service Dockerfile
- [ ] Create `requirements.txt` with onnxruntime
- [ ] Create `app/clients/prediction_client.py` in Main API
- [ ] Update Main API `app/api/predict.py` to proxy pattern
- [ ] Keep PDF generation in Main API
- [ ] Add `prediction_service_url` to Main API config
- [ ] Run local tests (both services)
- [ ] Build Prediction service Docker image
- [ ] Deploy Prediction service to Cloud Run (min=0)
- [ ] Configure IAM permissions
- [ ] Update Main API with Prediction service URL
- [ ] Test end-to-end prediction flow
- [ ] Validate cold start time < 3s

## Success Criteria

**Performance:**
- ONNX inference 5x faster than sklearn
- Prediction service cold start < 3s
- Service-to-service latency < 50ms

**Cost:**
- Min instances = 0 (saves $3.46/day)
- Only charged when processing predictions
- Main API memory further reduced

**Reliability:**
- All prediction tests passing
- Graceful degradation if service unavailable
- PDF generation still works

## Risk Assessment

**ONNX Conversion Accuracy:**
- Risk: ONNX predictions differ from sklearn
- Mitigation: Unit tests comparing outputs
- Validation: Regression tests on test dataset

**Cold Start Latency:**
- Risk: Users experience 3s delay
- Mitigation: Acceptable for async prediction workflow
- Alternative: Set min=1 if needed

## Security Considerations

**No Database Access:**
- Prediction service cannot write directly to database
- All persistence via Main API proxy
- Reduces attack surface

**Model Storage:**
- ONNX models in GCS bucket
- Downloaded at container startup
- Versioned for rollback capability

## Next Steps

**After Phase 3 Completion:**
- Phase 4: Update Terraform for 3 services
- Phase 4: Create Jenkins pipelines
- Monitor prediction service usage patterns
