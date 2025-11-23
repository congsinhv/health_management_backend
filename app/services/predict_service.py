import os
import joblib
import pandas as pd
import logging
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from openai import AsyncOpenAI
import asyncpg
from app.config import settings
from app.schemas.predict import (
    UserInput,
    PredictionResponse,
    UserInputResponse,
    PredictionDetail,
    HealthMetrics,
    Metric,
    HealthAnalysis,
    DietPlan,
    WorkoutPlan,
)
from app.utils.gcs_downloader import GCSDownloader
from app.db.prediction import PredictionRepository

logger = logging.getLogger(__name__)


class ObesityPredictorComplete:
    def __init__(self, pool: Optional[asyncpg.Pool] = None):
        # Database setup
        self.pool = pool
        self.prediction_repo = PredictionRepository(pool) if pool else None

        # Define paths - use writable directory from config
        model_dir = settings.obesity_model_dir
        model_path = os.path.join(model_dir, "obesity_classifier_final.pkl")
        encoder_path = os.path.join(model_dir, "label_encoder.pkl")

        # Download models from GCS if they don't exist locally
        self._ensure_models_downloaded(model_path, encoder_path, model_dir)

        # Load model và encoder
        self.model = joblib.load(model_path)
        self.le = joblib.load(encoder_path)

        self.features = [
            "Gender",
            "Age",
            "Height",
            "Weight",
            "BMI",
            "BMI_Category_Detailed",
            "family_history_with_overweight",
            "FAVC",
            "FCVC",
            "NCP",
            "CAEC",
            "CH2O",
            "FAF",
            "TUE",
            "CALC",
            "MTRANS_Calorie",
            "Metabolic_Age",
            "Family_Risk_Score",
            "Lifestyle_Score",
            "Diet_Quality",
        ]

        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    def _ensure_models_downloaded(
        self, model_path: str, encoder_path: str, model_dir: str
    ):
        """
        Ensure obesity prediction models are downloaded from GCS if not present locally.

        Args:
            model_path: Path to the model file
            encoder_path: Path to the encoder file
            model_dir: Directory where models should be stored
        """
        model_exists = os.path.exists(model_path)
        encoder_exists = os.path.exists(encoder_path)

        # If both files exist, no need to download
        if model_exists and encoder_exists:
            logger.info("Obesity prediction models already exist locally")
            return

        # Check if GCS bucket is configured
        if not settings.gcp_model_bucket:
            logger.error(
                "GCS bucket not configured. Please set gcp_model_bucket in settings "
                "or place model files manually in models_obesity/ directory"
            )
            raise ValueError("Model files not found and GCS bucket not configured")

        logger.info("Downloading obesity prediction models from GCS...")

        try:
            # Create model directory if it doesn't exist
            try:
                Path(model_dir).mkdir(parents=True, exist_ok=True)
                logger.info(f"Model directory ready: {model_dir}")
            except PermissionError as pe:
                raise RuntimeError(
                    f"Permission denied creating model directory {model_dir}. "
                    f"Ensure the directory is writable or set OBESITY_MODEL_DIR to a writable location like /tmp"
                ) from pe

            # Initialize GCS downloader
            downloader = GCSDownloader(
                bucket_name=settings.gcp_model_bucket,
                project_id=settings.gcp_project_id,
                timeout=settings.model_download_timeout,
            )

            # Download model file if missing
            if not model_exists:
                blob_path = "models_obesity/obesity_classifier_final.pkl"
                logger.info(f"Downloading {blob_path}...")
                success = downloader.download_file(blob_path, model_path, force=False)
                if not success:
                    raise RuntimeError(
                        f"Failed to download model file from GCS: {blob_path}"
                    )

            # Download encoder file if missing
            if not encoder_exists:
                blob_path = "models_obesity/label_encoder.pkl"
                logger.info(f"Downloading {blob_path}...")
                success = downloader.download_file(blob_path, encoder_path, force=False)
                if not success:
                    raise RuntimeError(
                        f"Failed to download encoder file from GCS: {blob_path}"
                    )

            logger.info("Successfully downloaded obesity prediction models from GCS")

        except Exception as e:
            logger.error(f"Error downloading models from GCS: {e}")
            raise RuntimeError(
                f"Failed to download obesity prediction models from GCS: {e}. "
                "Please ensure the files exist in the bucket or place them manually "
                f"in {model_dir}/"
            )

    def predict_complete(self, user_inputs: dict):
        age = user_inputs["age"]
        height = user_inputs["height"]
        weight = user_inputs["weight"]
        gender = user_inputs["gender"]
        family_history = user_inputs["family_history"]

        bmi = weight / (height**2)
        bmi_cat = self._bmi_category_index(bmi)
        metabolic_age = age * bmi / 10
        family_risk_score = (1 if family_history else 0) * bmi_cat

        faf = user_inputs.get("FAF", 1.0)
        tue = user_inputs.get("TUE", 1.0)
        ncp = user_inputs.get("NCP", 3)
        fcvc = user_inputs.get("FCVC", 2.0)
        ch2o = user_inputs.get("CH2O", 2.0)
        favc = user_inputs.get("FAVC", 0)
        calc = user_inputs.get("CALC", 0)
        caec = user_inputs.get("CAEC", 2)
        mtrans = user_inputs.get("MTRANS_Calorie", 1)

        lifestyle_score = (faf + tue) * ncp
        diet_quality = fcvc + ch2o - (1 if favc else 0)

        input_data = {
            "Gender": 1 if gender.lower() in ["nam", "male", "1"] else 0,
            "Age": age,
            "Height": height,
            "Weight": weight,
            "BMI": bmi,
            "BMI_Category_Detailed": bmi_cat,
            "family_history_with_overweight": 1 if family_history else 0,
            "FAVC": favc,
            "FCVC": fcvc,
            "NCP": ncp,
            "CAEC": caec,
            "CH2O": ch2o,
            "FAF": faf,
            "TUE": tue,
            "CALC": calc,
            "MTRANS_Calorie": mtrans,
            "Metabolic_Age": metabolic_age,
            "Family_Risk_Score": family_risk_score,
            "Lifestyle_Score": lifestyle_score,
            "Diet_Quality": diet_quality,
        }

        df = pd.DataFrame([input_data])
        prediction = self.model.predict(df[self.features])[0]
        confidence = max(self.model.predict_proba(df[self.features])[0])

        return {
            "dự_đoán": self.le.inverse_transform([prediction])[0],
            "độ_tin_cậy": f"{confidence:.1%}",
            "bmi": f"{bmi:.1f}",
            "phân_loại_bmi": self._get_bmi_category(bmi),
        }

    async def predict_obesity_ai(
        self, data: UserInput, save_to_db: bool = True
    ) -> PredictionResponse:
        """
        Generate obesity prediction with optional database storage.

        Args:
            data: User input data
            save_to_db: Whether to save prediction to database (default: True)

        Returns:
            PredictionResponse with database save attempted if save_to_db=True
        """
        # 1. Get base prediction
        result = self.predict_complete(data.dict())
        level = result["dự_đoán"]
        confidence_str = result["độ_tin_cậy"].replace("%", "")
        confidence = float(confidence_str)
        bmi = float(result["bmi"])

        # 2. Generate AI advice
        ai_response = await self._generate_ai_advice(data, level, bmi)

        # 3. Construct UserInputResponse
        user_input_response = self._map_user_input_response(data)

        # 4. Construct prediction response
        prediction_response = PredictionResponse(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            userInput=user_input_response,
            prediction=PredictionDetail(
                level=level,
                confidence=confidence,
                bmi=bmi,
                status=self._map_status(level),
                reliability="high" if confidence > 70 else "medium",
            ),
            healthMetrics=HealthMetrics(
                weight=Metric(label="Cân nặng", value=data.weight, unit="kg"),
                bmi=Metric(label="BMI", value=bmi, unit=""),
                height=Metric(label="Chiều cao", value=data.height, unit="m"),
            ),
            healthAnalysis=HealthAnalysis(
                paragraphs=ai_response.get("healthAnalysis", [])
            ),
            dietPlan=DietPlan(
                weeklyPlans=ai_response.get("dietPlan", {}).get("weeklyPlans", [])
            ),
            workoutPlan=WorkoutPlan(
                weeklyPlans=ai_response.get("workoutPlan", {}).get("weeklyPlans", [])
            ),
        )

        # 5. Save to database if requested and repository is available
        if save_to_db and self.prediction_repo:
            try:
                saved_record = await self._save_prediction(
                    prediction_id=prediction_response.id,
                    user_input=data.dict(),
                    prediction_response=prediction_response.dict(),
                )
                if saved_record:
                    logger.info(
                        f"Saved prediction {prediction_response.id} to database"
                    )
                else:
                    logger.warning(
                        f"Failed to save prediction {prediction_response.id} to database"
                    )
            except Exception as e:
                logger.error(f"Failed to save prediction {prediction_response.id}: {e}")
                # Don't fail the request if save fails - graceful degradation

        return prediction_response

    async def _generate_ai_advice(
        self, data: UserInput, level: str, bmi: float
    ) -> Dict[str, Any]:
        prompt = f"""
        Bạn là chuyên gia dinh dưỡng và huấn luyện viên cá nhân.
        Người dùng có thông tin:
        - Giới tính: {data.gender}
        - Tuổi: {data.age}
        - Chiều cao: {data.height}m, Cân nặng: {data.weight}kg
        - BMI: {bmi:.1f}
        - Tình trạng: {self._map_status(level)} ({level})
        
        Hãy tạo một kế hoạch sức khỏe chi tiết dưới dạng JSON với cấu trúc sau:
        {{
            "healthAnalysis": ["đoạn 1", "đoạn 2", "đoạn 3"],
            "dietPlan": {{
                "weeklyPlans": [
                    {{
                        "day": 1,
                        "breakfast": [{{"name": "...", "calories": 100, "count": 1, "unit": "..."}}],
                        "lunch": [...],
                        "dinner": [...],
                        "recommendedFoods": "...",
                        "foodsToLimit": "..."
                    }}
                ]
            }},
            "workoutPlan": {{
                "weeklyPlans": [
                    {{
                        "name": "Tên buổi tập",
                        "day": 1,
                        "exercises": [
                            {{"name": "...", "duration": 30, "unit": "phút", "description": "...", "sets": 3, "reps": 10}}
                        ]
                    }}
                ]
            }}
        }}

        Đảm bảo phản hồi là JSON hợp lệ và đầy đủ 7 ngày kế hoạch.
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error(f"Error generating AI advice: {e}")
            # Return empty structure on error to avoid crash
            return {
                "healthAnalysis": ["Không thể tạo phân tích lúc này."],
                "dietPlan": {"weeklyPlans": []},
                "workoutPlan": {"weeklyPlans": []},
            }

    def _map_status(self, level: str) -> str:
        mapping = {
            "Insufficient_Weight": "Thiếu cân",
            "Normal_Weight": "Bình thường",
            "Overweight_Level_I": "Thừa cân cấp độ I",
            "Overweight_Level_II": "Thừa cân cấp độ II",
            "Obesity_Type_I": "Béo phì độ I",
            "Obesity_Type_II": "Béo phì độ II",
            "Obesity_Type_III": "Béo phì độ III",
        }
        return mapping.get(level, level)

    def _map_user_input_response(self, data: UserInput) -> UserInputResponse:
        return UserInputResponse(
            name=data.name or "User",
            gender=data.gender,
            age=data.age,
            height=data.height,
            weight=data.weight,
            familyHistory="Có" if data.family_history else "Không",
            highCalorieFood="Thường xuyên"
            if data.FAVC
            else "Không",  # FAVC is usually binary yes/no
            vegetableFrequency=self._map_frequency(
                data.FCVC, ["Không bao giờ", "Thỉnh thoảng", "Thường xuyên"]
            ),
            waterIntake=self._map_frequency(data.CH2O, ["< 1L", "1-2L", "> 2L"]),
            mainMeals=int(data.NCP) if data.NCP else 3,
            snackFrequency=self._map_frequency(
                data.CAEC,
                ["Không", "Thỉnh thoảng", "Thường xuyên", "Luôn luôn"],
                offset=0,
            ),
            physicalActivity=self._map_frequency(
                data.FAF, ["Không", "1-2 ngày", "2-4 ngày", "> 4 ngày"], offset=0
            ),
            screenTime=self._map_frequency(
                data.TUE, ["0-2h", "3-5h", "> 5h"], offset=0
            ),
            transportation=self._map_transport(data.MTRANS_Calorie),
            smoking="Không",  # Default as not in input
            alcohol=self._map_frequency(
                data.CALC,
                ["Không", "Thỉnh thoảng", "Thường xuyên", "Luôn luôn"],
                offset=0,
            )
            if data.CALC is not None
            else "Không",
        )

    def _map_frequency(
        self, value: Optional[float], labels: List[str], offset: int = 1
    ) -> str:
        if value is None:
            return labels[0]
        idx = int(round(value)) - offset
        idx = max(0, min(idx, len(labels) - 1))
        return labels[idx]

    def _map_transport(self, value: Optional[int]) -> str:
        # Mapping based on dataset encoding usually:
        # 0: Automobile, 1: Motorbike, 2: Bike, 3: Public_Transportation, 4: Walking
        # But check the model training encoding. Assuming standard mapping or just returning generic.
        # In the original code, MTRANS_Calorie default is 1.
        # Let's use a generic mapping or just return the value if unknown.
        # User example says "Xe đạp".
        mapping = {
            0: "Ô tô",
            1: "Xe máy",
            2: "Xe đạp",
            3: "Phương tiện công cộng",
            4: "Đi bộ",
        }
        return mapping.get(value, "Khác")

    def _bmi_category_index(self, bmi):
        if bmi < 16:
            return 0
        elif bmi < 17:
            return 1
        elif bmi < 18.5:
            return 2
        elif bmi < 25:
            return 3
        elif bmi < 30:
            return 4
        elif bmi < 35:
            return 5
        elif bmi < 40:
            return 6
        else:
            return 7

    async def _save_prediction(
        self,
        prediction_id: str,
        user_input: Dict[str, Any],
        prediction_response: Dict[str, Any],
    ) -> Optional[asyncpg.Record]:
        """
        Save prediction to database (PUBLIC - no user_id).

        Args:
            prediction_id: External prediction ID from PredictionResponse.id
            user_input: UserInput dict
            prediction_response: PredictionResponse dict

        Returns:
            Saved prediction record or None
        """
        if not self.prediction_repo:
            logger.warning("Prediction repository not available - skipping save")
            return None

        return await self.prediction_repo.create_prediction(
            prediction_id=prediction_id,
            user_input=user_input,
            prediction_data=prediction_response,
        )

    def _get_bmi_category(self, bmi):
        if bmi < 18.5:
            return "Thiếu cân"
        elif bmi < 25:
            return "Bình thường"
        elif bmi < 30:
            return "Thừa cân"
        elif bmi < 35:
            return "Béo phì cấp I"
        elif bmi < 40:
            return "Béo phì cấp II"
        else:
            return "Béo phì cấp III"
