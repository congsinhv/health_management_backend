from datetime import time
from app.exceptions import (
    PredictionException,
    PredictionModelException,
    PredictionDataException,
    ModelNotLoadedException,
    ExternalServiceException,
    DatabaseException,
    ResourceNotFoundException,
    ValidationException,
    ServiceUnavailableException,
)
from app.services.schedule.service import ScheduleService
from app.db.schedule_plan import SchedulePlanRepository
from app.services.schedule.ai_planner import generate_weekly_plan
from app.services.schedule.scheduler import schedule_notifications_for_week

from app.core.error_context import ErrorContext
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
    DailyWorkoutPlan,
)
from app.db.notification import NotificationRepository
from app.schemas.schedule import ScheduleConfig, ScheduleMode
from app.utils.gcs_downloader import GCSDownloader
from app.db.prediction import PredictionRepository
import json
from app.db.user_profile import UserProfileRepository

logger = logging.getLogger(__name__)


class ObesityPredictorComplete:
    def __init__(self, pool: Optional[asyncpg.Pool] = None):
        # Database setup
        self.pool = pool
        self.prediction_repo = PredictionRepository(pool) if pool else None
        self.plan_repo = SchedulePlanRepository(pool)
        self.notification_repo = NotificationRepository(pool)
        self.user_profile_repo = UserProfileRepository(pool)
        # Define paths - use writable directory from config
        model_dir = r"C:\health\be\health_management_backend\tmp\models_obesity"
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
        """
        model_exists = os.path.exists(model_path)
        encoder_exists = os.path.exists(encoder_path)

        if model_exists and encoder_exists:
            logger.info("Obesity prediction models already exist locally")
            return

        if not settings.gcp_model_bucket:
            logger.error(
                "GCS bucket not configured. Please set gcp_model_bucket in settings "
                "or place model files manually in models_obesity/ directory"
            )
            raise PredictionModelException(
                message="Model files not found and GCS bucket not configured",
                details={"gcp_model_bucket": settings.gcp_model_bucket},
            )

        logger.info("Downloading obesity prediction models from GCS...")

        try:
            try:
                Path(model_dir).mkdir(parents=True, exist_ok=True)
                logger.info(f"Model directory ready: {model_dir}")
            except PermissionError as pe:
                raise RuntimeError(
                    f"Permission denied creating model directory {model_dir}. "
                    f"Ensure the directory is writable or set OBESITY_MODEL_DIR to a writable location like /tmp"
                ) from pe

            downloader = GCSDownloader(
                bucket_name=settings.gcp_model_bucket,
                project_id=settings.gcp_project_id,
                timeout=settings.model_download_timeout,
            )

            if not model_exists:
                blob_path = "models_obesity/obesity_classifier_final.pkl"
                logger.info(f"Downloading {blob_path}...")
                success = downloader.download_file(blob_path, model_path, force=False)
                if not success:
                    raise RuntimeError(
                        f"Failed to download model file from GCS: {blob_path}"
                    )

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
        """Generate obesity prediction with optional database storage."""
        result = self.predict_complete(data.dict())
        level = result["dự_đoán"]
        confidence_str = result["độ_tin_cậy"].replace("%", "")
        confidence = float(confidence_str)
        bmi = float(result["bmi"])

        ai_response = await self._generate_ai_advice(data, level, bmi)
        user_input_response = self._map_user_input_response(data)

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
                **self._sanitize_diet_plan(ai_response.get("dietPlan", {}))
            ),
            workoutPlan=WorkoutPlan(
                **self._sanitize_workout_plan(ai_response.get("workoutPlan", {}))
            ),
        )

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

        return prediction_response

    async def generate_plans_from_prediction(
        self, prediction_id: str
    ) -> PredictionResponse:
        """
        Generate diet and workout plans based on existing prediction data.

        Args:
            prediction_id: External prediction ID from PredictionResponse.id
        Returns:
            Updated PredictionResponse with diet and workout plans
        """
        try:
            # Kiểm tra repository
            if not self.prediction_repo:
                raise PredictionException(
                    message="Prediction repository not available",
                    details={"prediction_id": prediction_id},
                )

            # Lấy prediction từ DB
            prediction_record = await self.prediction_repo.get_prediction(prediction_id)
            if not prediction_record:
                raise PredictionException(
                    message="Prediction not found",
                    details={"prediction_id": prediction_id},
                )

            # Parse prediction_data
            prediction_data_raw = prediction_record.get("prediction_data", {})
            if isinstance(prediction_data_raw, str):
                try:
                    prediction_data = json.loads(prediction_data_raw)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in prediction_data: {e}")
                    raise PredictionException(
                        message="Invalid prediction_data JSON",
                        details={"prediction_id": prediction_id, "error": str(e)},
                    )
            else:
                prediction_data = prediction_data_raw

            logger.info(f"Prediction data keys: {list(prediction_data.keys())}")

            # Khởi tạo PredictionResponse
            prediction = PredictionResponse(**prediction_data)

            # Reconstruct UserInput từ prediction.userInput
            family_history = bool(getattr(prediction.userInput, "familyHistory", False))
            user_input = UserInput(
                name=prediction.userInput.name,
                gender=prediction.userInput.gender,
                age=prediction.userInput.age,
                height=prediction.userInput.height,
                weight=prediction.userInput.weight,
                family_history=family_history,
            )

            # Gọi AI tạo kế hoạch
            ai_response = await self._generate_ai_advice(
                data=user_input,
                level=prediction.prediction.level,
                bmi=prediction.prediction.bmi,
            )

            # Sanitize diet và workout plan
            diet_plan_data = self._sanitize_diet_plan(ai_response.get("dietPlan") or {})
            workout_plan_data = self._sanitize_workout_plan(
                ai_response.get("workoutPlan") or {}
            )

            # Ensure weeklyPlans đủ 7 ngày
            def fill_weekly_plans(plans, default_template):
                filled = []
                for day in range(1, 8):
                    plan_for_day = next((p for p in plans if p.get("day") == day), None)
                    if not plan_for_day:
                        plan_for_day = default_template.copy()
                        plan_for_day["day"] = day
                    filled.append(plan_for_day)
                return filled

            diet_plan_data["weeklyPlans"] = fill_weekly_plans(
                diet_plan_data.get("weeklyPlans", []),
                {
                    "day": 0,
                    "breakfast": [],
                    "lunch": [],
                    "dinner": [],
                    "recommendedFoods": "",
                    "foodsToLimit": "",
                },
            )
            workout_plan_data["weeklyPlans"] = fill_weekly_plans(
                workout_plan_data.get("weeklyPlans", []),
                {"day": 0, "name": "", "exercises": []},
            )

            # Update PredictionResponse
            prediction.dietPlan = DietPlan(**diet_plan_data)
            prediction.workoutPlan = WorkoutPlan(**workout_plan_data)

            if ai_response.get("healthAnalysis"):
                prediction.healthAnalysis = HealthAnalysis(
                    paragraphs=ai_response.get("healthAnalysis", [])
                )

            # Lưu lại DB
            await self.prediction_repo.update_prediction(
                prediction_id=prediction_id, prediction_data=prediction.dict()
            )

            logger.info(f"Generated plans for prediction {prediction_id}")
            return prediction

        except PredictionException:
            # Re-raise custom exception
            raise
        except Exception as e:
            logger.error(
                f"Error generating plans for prediction {prediction_id}: {e}",
                exc_info=True,
            )
            raise PredictionException(
                message="Failed to generate diet and workout plans",
                details={"prediction_id": prediction_id, "error": str(e)},
            )

    async def get_prediction_by_id(self, prediction_id: str) -> PredictionResponse:
        """Retrieve prediction by ID."""
        if not self.prediction_repo:
            raise ServiceUnavailableException("Prediction repository not available")

        record = await self.prediction_repo.get_prediction_by_id(prediction_id)
        if not record:
            raise ValidationException(
                message="Prediction not found", details={"prediction_id": prediction_id}
            )

        prediction_data_raw = record.get("prediction_data", {})
        if isinstance(prediction_data_raw, str):
            try:
                prediction_data = json.loads(prediction_data_raw)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in prediction_data: {e}")
                raise PredictionDataException(
                    message="Invalid prediction_data JSON",
                    details={"prediction_id": prediction_id, "error": str(e)},
                )
        else:
            prediction_data = prediction_data_raw

        return PredictionResponse(**prediction_data)

    @staticmethod
    def _parse_time(time_str: Optional[str]):
        """Parse time string to time object."""
        if not time_str:
            return None
        parts = str(time_str).split(":")
        return time(
            int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
        )

    async def generate_weekly_schedule_from_prediction(
        self,
        weeklyPlans: List[DailyWorkoutPlan],
        user_id: int,
        schedule: ScheduleConfig,
        timezone: str = "Asia/Ho_Chi_Minh",
    ) -> Dict[str, Any]:
        """Generate weekly schedule from ML prediction results."""

        # Step 1: Atomically deactivate existing and create new plan in one transaction
        plan_data = {
            "user_id": user_id,
            "timezone": timezone,
            "schedule_mode": schedule.mode.value,
            "selected_days": [d.value for d in schedule.selected_days],
        }

        # Handle fixed mode times
        if schedule.mode == ScheduleMode.FIXED and schedule.fixed_period:
            plan_data["fixed_start_time"] = self._parse_time(
                schedule.fixed_period.start_time
            )
            plan_data["fixed_end_time"] = self._parse_time(
                schedule.fixed_period.end_time
            )

        # Handle flexible mode periods
        if schedule.mode == ScheduleMode.FLEXIBLE and schedule.flexible_periods:
            plan_data["flexible_periods"] = {
                k.value: [{"startTime": p.start_time, "endTime": p.end_time} for p in v]
                for k, v in schedule.flexible_periods.items()
            }

        # Get user profile
        user_profile = await self.user_profile_repo.get_profile_by_user_id(user_id)
        if not user_profile:
            raise ResourceNotFoundException(
                message="User profile not found", details={"user_id": user_id}
            )
        height_cm = user_profile.get("height_cm") or 0
        plan_data["height_m"] = float(height_cm) / 100.0
        plan_data["weight_kg"] = user_profile.get("weight_kg") or 0
        plan_data["target_weight_kg"] = user_profile.get("weight_kg") or 0
        plan_data["goal"] = user_profile.get("goal") or "maintain"
        plan_data["sports_predefined"] = []

        # Create new plan and deactivate old ones atomically
        record = await self.plan_repo.deactivate_and_create(plan_data)
        plan_id = record["id"]

        # Step 2: Convert weekly_plan to correct format
        # Map day numbers to day names
        # prediction `day` values are 1..7 (Mon=1 .. Sun=7) so map accordingly
        day_mapping = {
            "monday": 1,
            "tuesday": 2,
            "wednesday": 3,
            "thursday": 4,
            "friday": 5,
            "saturday": 6,
            "sunday": 7,
        }

        weekly_plan = {}
        for day in schedule.selected_days:
            # Convert day number to day name
            day_key = day_mapping.get(day)
            if not day_key:
                continue  # Skip invalid day numbers

            # Calculate total duration and calories from exercises
            total_duration = 0
            total_calories = 0
            exercise_descriptions = []
            daily_plan = weeklyPlans[day_key - 1]

            if daily_plan.exercises:
                for exercise in daily_plan.exercises:
                    # Support both `duration` and `duration_minutes` field names
                    dur = getattr(exercise, "duration_minutes", None)
                    if dur is None:
                        dur = getattr(exercise, "duration", None)
                    if dur is not None:
                        try:
                            total_duration += int(dur)
                        except Exception:
                            pass

                    # Support both `estimated_calories` and `calories`
                    cal = getattr(exercise, "estimated_calories", None)
                    if cal is None:
                        cal = getattr(exercise, "calories", None)
                    if cal is not None:
                        try:
                            total_calories += int(cal)
                        except Exception:
                            pass

                    name = getattr(exercise, "name", None)
                    if name:
                        exercise_descriptions.append(name)

            # Use defaults if no exercises provided
            total_duration = total_duration or 60
            total_calories = total_calories or 300
            description = (
                ", ".join(exercise_descriptions)
                if exercise_descriptions
                else daily_plan.name
            )

            weekly_plan[day] = {
                "exercise": daily_plan.name,
                "duration_minutes": total_duration,
                "estimated_calories": total_calories,
                "description": description,
            }

        # Step 3: Update plan with converted weekly plan
        record = await self.plan_repo.update_weekly_plan(plan_id, weekly_plan)

        print(f"Plan data: {plan_data}")
        # Step 4: Schedule notifications for the week
        notifications = schedule_notifications_for_week(
            plan_id=plan_id,
            user_id=user_id,
            timezone=timezone,
            selected_days=plan_data["selected_days"],
            schedule_mode=plan_data["schedule_mode"],
            fixed_start_time=plan_data.get("fixed_start_time"),
            fixed_end_time=plan_data.get("fixed_end_time"),
            flexible_periods=plan_data.get("flexible_periods"),
            weekly_plan=weekly_plan,
        )

        if notifications:
            await self.notification_repo.create_batch(notifications)
        schedule_service = ScheduleService(self.pool)
        # Return the schedule response
        return await schedule_service._to_response(record)

    # 4 bước chính:
    # 1. Atomically deactivate existing and create new plan in one transaction
    # 2. Convert weekly_plan to correct format
    # Return JSON format:
    # {{
    #     "monday": {{
    #         "exercise": "Gym - Upper Body",
    #         "duration_minutes": 60,
    #         "estimated_calories": 350,
    #         "description": "Chest press, shoulder press, bicep curls"
    #     }}
    # }}
    # 3. Update plan with converted weeklyplan
    # 4. Schedule notifications for the week

    def _sanitize_diet_plan(self, diet_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize AI-generated diet plan to ensure all required fields exist."""
        weekly_plans = diet_plan.get("weeklyPlans", [])
        sanitized_plans = []

        for plan in weekly_plans:
            sanitized_plan = {
                "day": plan.get("day", 0),
                "breakfast": plan.get("breakfast", []),
                "lunch": plan.get("lunch", []),
                "dinner": plan.get("dinner", []),
                "recommendedFoods": plan.get("recommendedFoods", ""),
                "foodsToLimit": plan.get("foodsToLimit", ""),
            }
            sanitized_plans.append(sanitized_plan)

        return {"weeklyPlans": sanitized_plans}

    def _sanitize_workout_plan(self, workout_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize AI-generated workout plan to ensure all required fields exist."""
        weekly_plans = workout_plan.get("weeklyPlans", [])
        sanitized_plans = []

        for plan in weekly_plans:
            sanitized_plan = {
                "name": plan.get("name", ""),
                "day": plan.get("day", 0),
                "exercises": plan.get("exercises", []),
            }
            sanitized_plans.append(sanitized_plan)

        return {"weeklyPlans": sanitized_plans}

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

        LƯU Ý QUAN TRỌNG:
        - Tất cả các trường số (calories, count, duration, day, sets, reps) PHẢI là số nguyên, KHÔNG được là chuỗi.
        - Nếu không có giá trị cho sets hoặc reps, bỏ qua trường đó hoặc để null, KHÔNG dùng "N/A".
        - Đảm bảo phản hồi là JSON hợp lệ và đầy đủ 7 ngày kế hoạch.
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
            highCalorieFood="Thường xuyên" if data.FAVC else "Không",
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
            smoking="Không",
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
        """Save prediction to database (PUBLIC - no user_id)."""
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
