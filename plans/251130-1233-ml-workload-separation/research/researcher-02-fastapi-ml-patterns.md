# FastAPI Microservices & ML Model Deployment Patterns Research

**Date:** 2025-11-30
**Focus:** Shared code strategies, dependency injection, ML model serving optimization

---

## 1. Shared Code Strategies for FastAPI Microservices

### Monorepo vs Multi-Repo Analysis

**Monorepo Approach (Recommended for VHealth):**
- Single repository containing QA service, Predict service, Auth/User service
- Enables atomic commits across services + shared tooling
- Challenge: Requires thoughtful packaging to avoid tight coupling

**Multi-Repo with Shared Packages (Alternative):**
- Each service in separate repo with shared libraries as wheels
- Greater isolation but deployment complexity increases
- Wheel distribution via internal package repositories

**Decision:** Use **monorepo with separate service directories** (`app/services/qa/`, `app/services/predict/`, `app/services/shared/`) since you're on Python 3.13 with Poetry—achieves both code reuse and deployment isolation.

### Code Sharing Pattern for FastAPI

```python
# app/core/shared/schemas.py (shared Pydantic models)
class BaseResponse(BaseModel):
    status: str
    timestamp: datetime
    request_id: Optional[str] = None

class ErrorResponse(BaseResponse):
    error: str
    details: Optional[Dict] = None

# app/core/shared/exceptions.py (custom exceptions across services)
class MLServiceException(Exception):
    def __init__(self, message: str, service: str, retry_after: int = 60):
        self.message = message
        self.service = service
        self.retry_after = retry_after

# Each microservice imports and extends
from app.core.shared.schemas import BaseResponse
from app.core.shared.exceptions import MLServiceException
```

**Best Practice:** Core shared code in `app/core/shared/` as import-only module—NO circular dependencies, NO service-specific logic.

---

## 2. Dependency Injection Pattern for Shared Code

FastAPI's native DI system enables clean service architecture:

```python
# app/core/dependencies.py
from typing import AsyncGenerator

async def get_db_pool() -> AsyncGenerator:
    """Shared database connection pool dependency."""
    pool = await create_pool()
    try:
        yield pool
    finally:
        await pool.close()

async def get_cache_service(
    pool: asyncpg.Pool = Depends(get_db_pool)
) -> CacheService:
    """Shared cache service dependency."""
    return CacheService(pool, settings.redis_url)

# app/api/qa.py (in QA service)
@router.post("/ask")
async def ask_question(
    req: QARequest,
    db: asyncpg.Pool = Depends(get_db_pool),
    cache: CacheService = Depends(get_cache_service)
):
    """QA endpoint uses injected dependencies."""
    qa_service = QAService(db, cache)
    return await qa_service.process(req)

# app/api/predict.py (in Predict service)
@router.post("/predict")
async def predict(
    req: PredictRequest,
    db: asyncpg.Pool = Depends(get_db_pool),
    cache: CacheService = Depends(get_cache_service)
):
    """Predict endpoint reuses same dependency injection."""
    predict_service = PredictService(db, cache)
    return await predict_service.predict(req)
```

**Key Benefit:** Single dependency initialization at startup (`app/main.py:lifespan()`) shared across all services.

---

## 3. ML Model Serving: SBERT Production Patterns

### Model Loading Strategy (Eliminates Cold Start)

```python
# app/core/ml/sbert_loader.py
from sentence_transformers import SentenceTransformer

class SBERTModelManager:
    _instance: Optional["SBERTModelManager"] = None

    def __init__(self, model_name: str = "distiluse-base-multilingual-case-sensitive-v2"):
        self.model = SentenceTransformer(
            model_name,
            backend="onnx",  # Use ONNX backend (2-5x faster)
            cache_folder="/models/sbert"  # Persistent cache
        )
        self._embeddings_cache = {}

    @classmethod
    async def create(cls, settings: Settings) -> "SBERTModelManager":
        """Initialize once at startup (blocking operation)."""
        if cls._instance is None:
            cls._instance = cls(settings.sbert_model_name)
        return cls._instance

    async def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Encode with optional caching."""
        embeddings = self.model.encode(texts, batch_size=batch_size, convert_to_numpy=True)
        return embeddings

# app/main.py (startup)
async def lifespan(app: FastAPI):
    # Load model ONCE at startup
    app.state.sbert_model = await SBERTModelManager.create(settings)
    app.state.predict_models = await PredictModelManager.create(settings)
    yield
    # Cleanup if needed

app = FastAPI(lifespan=lifespan)

# app/api/qa.py (usage)
@router.post("/ask")
async def ask(
    req: QARequest,
    request: Request
) -> QAResponse:
    sbert = request.app.state.sbert_model
    embeddings = await sbert.encode([req.question])  # Fast—model already loaded
    # ... continue QA logic
```

### ONNX Optimization for SBERT

**Enable 2-5x inference speedup:**

```python
from sentence_transformers import SentenceTransformer
from optimum.onnxruntime import ORTModelForSentenceTransformers

# Approach 1: Use native SBERT ONNX backend (simplest)
model = SentenceTransformer(
    "distiluse-base-multilingual-case-sensitive-v2",
    backend="onnx",
    cache_folder="/models"
)

# Approach 2: Quantize to int8 for additional 30-40% speedup
model.export_optimized_onnx_model(
    optimization_config="O3",  # Extended optimizations + GELU approx
    model_name_or_path="/models/sbert-quantized"
)

# Load optimized model
optimized_model = ORTModelForSentenceTransformers.from_pretrained(
    "/models/sbert-quantized"
)
embeddings = optimized_model.encode(texts)  # 30-50% faster than torch
```

---

## 4. scikit-learn Model Optimization via ONNX

### Convert & Deploy scikit-learn Models

```python
# Training (offline)
from skl2onnx import convert_sklearn
import onnx

rf_model = RandomForestRegressor(n_estimators=100)
rf_model.fit(X_train, y_train)

# Convert to ONNX (one-time)
onnx_model = convert_sklearn(rf_model, initial_types=[("float_input", FloatTensorType([None, X_train.shape[1]]))])
with open("/models/predict.onnx", "wb") as f:
    f.write(onnx_model.SerializeToString())

# Production serving (fast)
from onnxruntime import InferenceSession
import numpy as np

class PredictModelManager:
    def __init__(self, model_path: str = "/models/predict.onnx"):
        self.session = InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"]  # GPU: ["CUDAExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    async def predict(self, X: np.ndarray) -> np.ndarray:
        """ONNX inference is 5x faster than scikit-learn."""
        predictions = self.session.run(
            [self.output_name],
            {self.input_name: X.astype(np.float32)}
        )
        return predictions[0]

# In app/main.py
app.state.predict_model = PredictModelManager(settings.predict_model_path)
```

**Performance Gains:** 5x speedup on CPU, ~5-10x on GPU vs sklearn.predict()

---

## 5. Database Patterns: Connection Pooling in Microservices

### Shared Pool Architecture

```python
# app/db/database.py (single source of truth)
class DatabasePool:
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_pool(cls, dsn: str) -> asyncpg.Pool:
        """Lazy-init pool, reuse across all services."""
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                dsn,
                min_size=5,
                max_size=20,
                timeout=30.0,
                command_timeout=30.0
            )
        return cls._pool

    @classmethod
    async def close_pool(cls):
        if cls._pool:
            await cls._pool.close()

# app/main.py (startup/shutdown)
async def lifespan(app: FastAPI):
    pool = await DatabasePool.get_pool(settings.database_url)
    app.state.db_pool = pool
    yield
    await DatabasePool.close_pool()

# Each service shares the same pool
class QARepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_conversations(self, user_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM conversations WHERE user_id = $1", user_id)

class PredictRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def save_prediction(self, prediction_data):
        async with self.pool.acquire() as conn:
            return await conn.fetchval("INSERT INTO predictions (...) VALUES (...) RETURNING id")
```

**Data Ownership:** Each service owns write-access to its tables; reads may cross service boundaries with versioning.

---

## 6. Cold Start Optimization Summary

| Technique | Speedup | Implementation |
|-----------|---------|---|
| ONNX SBERT | 2-5x | `backend="onnx"` in SentenceTransformer |
| SBERT quantization (int8) | +30-40% | export_optimized_onnx_model(O3) |
| scikit-learn ONNX | 5x | InferenceSession + skl2onnx |
| Model pre-loading at startup | Eliminates cold start | Singleton pattern + lifespan() |
| Connection pool reuse | Saves 100-200ms | Single asyncpg pool across services |

---

## Recommendations for VHealth

1. **Keep monorepo structure** with `app/services/{qa,predict,user}/` directories
2. **Move shared utilities to `app/core/shared/`** (schemas, exceptions, validators)
3. **Implement SBERT ONNX backend** in QA service—2-3x inference speedup
4. **Convert scikit-learn models to ONNX** before next predict service update
5. **Use dependency injection** for all services—inject db_pool, cache_service, models at startup
6. **Load all ML models in FastAPI lifespan()** to eliminate per-request cold starts

---

## Sources

- [Mastering Dependency Injection in FastAPI - Medium](https://medium.com/@azizmarzouki/mastering-dependency-injection-in-fastapi-clean-scalable-and-testable-apis-5f78099c3362)
- [Layered Architecture & Dependency Injection in FastAPI - DEV](https://dev.to/markoulis/layered-architecture-dependency-injection-a-recipe-for-clean-and-testable-fastapi-code-3ioo)
- [Speeding up Inference with SBERT - Sentence Transformers docs](https://www.sbert.net/docs/sentence_transformer/usage/efficiency.html)
- [ONNX for SBERT Speedup - Medium](https://patilswaraj22.medium.com/unleashing-the-power-of-onnx-for-speedier-sbert-inference-27db2208f777)
- [Monorepo Guide for Microservices - Aviator](https://www.aviator.co/blog/monorepo-a-hands-on-guide-for-managing-repositories-and-microservices/)
- [Python Monorepo Best Practices - Tweag](https://www.tweag.io/blog/2023-04-04-python-monorepo-1/)
- [Accelerate scikit-learn with ONNX Runtime - Microsoft Blog](https://opensource.microsoft.com/blog/2020/12/17/accelerate-simplify-scikit-learn-model-inference-onnx-runtime/)
- [ONNX Runtime Documentation](https://onnxruntime.ai/)
