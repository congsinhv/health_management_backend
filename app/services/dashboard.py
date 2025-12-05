from app.db.dashboard import DashboardRepository
from app.schemas.user_profile import UserProfileResponse
from app.exceptions import (
    ResourceNotFoundException,
    DatabaseException,
)
from app.core.error_context import ErrorContext
import json
from openai import AsyncOpenAI
from app.config import settings
from decimal import Decimal
from typing import Optional
from typing import Dict, Any, List, Optional  
class DashboardService:
    def __init__(self, repository: DashboardRepository):
        self.repository = repository
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.prompt_template = """
        Bạn là một trợ lý sức khỏe AI. Nhiệm vụ của bạn là tạo bản tóm tắt sức khỏe cá nhân dựa trên dữ liệu người dùng.

        Chỉ trả về TEXT, KHÔNG JSON. Phong cách: thân thiện, ngắn gọn, tích cực.

        Cấu trúc xuất ra:

        Thông tin chi tiết
        Đề xuất cá nhân hóa dựa trên dữ liệu của bạn

        🎯 Hoạt động của bạn
        - Đánh giá dựa trên exercise_minutes (mức khuyến nghị WHO: 30 phút/ngày).

        💧 Uống nước
        - water_intake hôm nay, so với lượng nước lý tưởng (weight * 0.03 L).

        ⚖️ Chỉ số BMI
        - BMI = {bmi}, nhận xét (gầy / bình thường / thừa cân / béo phì).

        Dữ liệu người dùng:
        - Name: {name}
        - Age: {age}
        - Gender: {gender}
        - Weight (kg): {weight}
        - Height (cm): {height}
        - BMI: {bmi}
        - Water intake: {water} L
        - Ideal water: {ideal_water} L
        - Remaining water: {remaining} L
        - Exercise minutes today: {exercise}
        - Heart rate: {heart_rate} BPM
        - Sleep hours: {sleep_hours} h
        - Goal: {goal}

        Hãy viết ngắn gọn, dễ đọc, giống ví dụ sau:

        🎯 Hoạt động tuyệt vời!
        Bạn đã đạt 84% mục tiêu bước chân hôm nay. Tiếp tục duy trì!

        💧 Nhắc nhở uống nước
        Bạn cần uống thêm 0.7L nước để đạt mục tiêu hôm nay.

        ⚖️ BMI lý tưởng
        BMI của bạn là 22.9, nằm trong khoảng cân nặng khỏe mạnh. Tuyệt vời!
        """
    
    async def get_user_profile(self, user_id: int) -> UserProfileResponse:
        try:
            record = await self.repository.get_profile_by_user_id(user_id)

            # Nếu record là asyncpg.Record → convert sang dict
            if hasattr(record, '_mapping'):  # asyncpg.Record
                record_dict = dict(record._mapping)
            elif isinstance(record, dict):
                record_dict = record
            else:
                record_dict = dict(record)

            return UserProfileResponse(**record_dict)

        except ResourceNotFoundException:
            # Ném lại để FastAPI handler convert thành response JSON
            raise

        except DatabaseException:
            raise

        except Exception as e:
            raise DatabaseException(
                message="Unexpected error in DashboardService.get_user_profile",
                details={"error": str(e)},
            )
        
    # Bieu do hoat dong hang ngay
    async def get_daily_activity(self, user_id: int):
        try:
            records = await self.repository.get_daily_activity(user_id)
            result = []
            for record in records:
                # Xử lý record để lấy dữ liệu an toàn
                if hasattr(record, '_mapping'):  # asyncpg.Record
                    record_data = dict(record._mapping)
                elif isinstance(record, dict):
                    record_data = record
                else:
                    record_data = dict(record)
                
                result.append({
                    "date": record_data.get("date"),
                    "exercise_minutes": record_data.get("exercise_minutes"),
                    "calories": record_data.get("calories")
                })
            return result
        except DatabaseException:
            raise
        except Exception as e:
            raise DatabaseException(
                message="Unexpected error in DashboardService.get_daily_activity",
                details={"error": str(e)},
            )
    
    # Bieu do hoat dong hang tuan
    async def get_weekly_activity(self, user_id: int):
        try:
            records = await self.repository.get_weekly_activity(user_id)
            result = []
            for record in records:
                # Xử lý record để lấy dữ liệu an toàn
                if hasattr(record, '_mapping'):  # asyncpg.Record
                    record_data = dict(record._mapping)
                elif isinstance(record, dict):
                    record_data = record
                else:
                    record_data = dict(record)
                
                result.append({
                    "day": record_data.get("day"),
                    "total_minutes": record_data.get("total_minutes"),
                })
            return result
        except DatabaseException:
            raise
        except Exception as e:
            raise DatabaseException(
                message="Unexpected error in DashboardService.get_weekly_activity",
                details={"error": str(e)},
            )
        
    # Bieu do hoat dong hang thang
    async def get_monthly_activity(self, user_id: int):
        try:
            records = await self.repository.get_monthly_activity(user_id)
            result = []
            for record in records:
                # Xử lý record để lấy dữ liệu an toàn
                if hasattr(record, '_mapping'):  # asyncpg.Record
                    record_data = dict(record._mapping)
                elif isinstance(record, dict):
                    record_data = record
                else:
                    record_data = dict(record)
                
                result.append({
                    "month": record_data.get("month"),
                    "avg_exercise": record_data.get("avg_exercise"),
                })
            return result
        except DatabaseException:
            raise
        except Exception as e:
            raise DatabaseException(
                message="Unexpected error in DashboardService.get_monthly_activity",
                details={"error": str(e)},
            )

    # Helper function to safely convert Decimal to float
    def _safe_convert(self, value: Optional[Decimal | int | float]) -> float:
        if value is None:
            return 0.0
        if isinstance(value, Decimal):
            return float(value)
        return float(value)
    
    # Helper function to get string value safely
    def _safe_str(self, value: Optional[str]) -> str:
        return value or ""

    # Viết PROMPT generate_personal_health_summary
    async def generate_personal_health_summary(self, profile: UserProfileResponse):
        try:
            # ---- Safe values with type conversion ----
            weight = self._safe_convert(profile.weight_kg)  # Optional[Decimal] -> float
            height = self._safe_convert(profile.height_cm)  # Optional[Decimal] -> float
            water_intake = self._safe_convert(profile.water_intake)  # Optional[float] -> float
            exercise = self._safe_convert(profile.exercise_minutes)  # Optional[int] -> float
            heart_rate = self._safe_convert(profile.heart_rate)  # Optional[int] -> float
            sleep_hours = self._safe_convert(profile.sleep_hours)  # Optional[float] -> float
            
            # Handle age separately since it's Optional[int]
            age = profile.age if profile.age is not None else 0
            
            # String values
            first_name = self._safe_str(profile.first_name)
            gender = self._safe_str(profile.gender)
            goal = self._safe_str(profile.goal)

            # ---- Health calculations ----
            # Avoid division by zero
            height_m = height / 100.0
            if height_m > 0:
                bmi = round(weight / (height_m ** 2), 1)
            else:
                bmi = 0.0
            
            ideal_water = round(weight * 0.03, 1)
            remaining = max(0.0, ideal_water - water_intake)

            # ---- Build prompt ----
            prompt = self.prompt_template.format(
                name=first_name,
                age=age,
                gender=gender,
                weight=weight,
                height=height,
                bmi=bmi,
                water=water_intake,
                ideal_water=ideal_water,
                remaining=remaining,
                exercise=exercise,
                heart_rate=heart_rate,
                sleep_hours=sleep_hours,
                goal=goal,
            )

            # ---- Call AI model ----
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
            )

            return response.choices[0].message.content

        except Exception as e:
            raise DatabaseException(
                message="Unexpected error in DashboardService.generate_personal_health_summary",
                details={"error": str(e)},
            )
    
    # Trong DashboardService class
    async def get_health_overview(self, user_id: int) -> Dict[str, Any]:
        """
        Get comprehensive health overview
        """
        try:
            # Get user profile
            profile = await self.get_user_profile(user_id)
            
            # Get activity data
            daily_activity = await self.get_daily_activity(user_id)
            weekly_activity = await self.get_weekly_activity(user_id)
            monthly_activity = await self.get_monthly_activity(user_id)
            
            # Get health summary from AI
            health_summary = await self.generate_personal_health_summary(profile)
            
            # ---- Calculate basic metrics ----
            weight = self._safe_convert(profile.weight_kg)
            height = self._safe_convert(profile.height_cm)
            water_intake = self._safe_convert(profile.water_intake)
            exercise = self._safe_convert(profile.exercise_minutes)
            heart_rate = self._safe_convert(profile.heart_rate)
            sleep_hours = self._safe_convert(profile.sleep_hours)
            
            # Calculate BMI
            height_m = height / 100.0
            bmi = round(weight / (height_m ** 2), 1) if height_m > 0 else 0.0
            
            # Determine BMI category
            if bmi < 18.5:
                bmi_category = "Thiếu cân"
                bmi_status = "warning"
            elif 18.5 <= bmi < 23:
                bmi_category = "Bình thường"
                bmi_status = "good"
            elif 23 <= bmi < 25:
                bmi_category = "Tiền béo phì"
                bmi_status = "warning"
            elif 25 <= bmi < 30:
                bmi_category = "Thừa cân"
                bmi_status = "warning"
            else:
                bmi_category = "Béo phì"
                bmi_status = "danger"
            
            # Calculate exercise percentage (WHO: 30 mins/day)
            exercise_percentage = min(100, (exercise / 30) * 100) if exercise else 0
            if exercise_percentage >= 100:
                exercise_status = "excellent"
            elif exercise_percentage >= 70:
                exercise_status = "good"
            elif exercise_percentage >= 30:
                exercise_status = "warning"
            else:
                exercise_status = "danger"
            
            # Calculate water intake
            ideal_water = round(weight * 0.03, 1)
            water_percentage = min(100, (water_intake / ideal_water) * 100) if ideal_water > 0 else 0
            if water_percentage >= 100:
                water_status = "excellent"
            elif water_percentage >= 80:
                water_status = "good"
            elif water_percentage >= 50:
                water_status = "warning"
            else:
                water_status = "danger"
            
            # Sleep analysis
            if 7 <= sleep_hours <= 9:
                sleep_status = "good"
                sleep_comment = "Đạt chuẩn"
            elif 6 <= sleep_hours < 7:
                sleep_status = "warning"
                sleep_comment = "Hơi thiếu"
            elif sleep_hours < 6:
                sleep_status = "danger"
                sleep_comment = "Thiếu ngủ"
            else:
                sleep_status = "warning"
                sleep_comment = "Quá nhiều"
            
            # Heart rate analysis
            if 60 <= heart_rate <= 100:
                heart_status = "good"
                heart_comment = "Bình thường"
            elif heart_rate < 60:
                heart_status = "warning"
                heart_comment = "Chậm"
            else:
                heart_status = "warning"
                heart_comment = "Nhanh"
            
            # Calculate overall health score (simple average)
            metrics_scores = []
            if bmi_status == "good":
                metrics_scores.append(100)
            elif bmi_status == "warning":
                metrics_scores.append(60)
            else:
                metrics_scores.append(30)
                
            if exercise_status == "excellent":
                metrics_scores.append(100)
            elif exercise_status == "good":
                metrics_scores.append(80)
            elif exercise_status == "warning":
                metrics_scores.append(50)
            else:
                metrics_scores.append(30)
                
            if water_status == "excellent":
                metrics_scores.append(100)
            elif water_status == "good":
                metrics_scores.append(80)
            elif water_status == "warning":
                metrics_scores.append(50)
            else:
                metrics_scores.append(30)
                
            if sleep_status == "good":
                metrics_scores.append(100)
            elif sleep_status == "warning":
                metrics_scores.append(60)
            else:
                metrics_scores.append(30)
                
            if heart_status == "good":
                metrics_scores.append(100)
            elif heart_status == "warning":
                metrics_scores.append(60)
            else:
                metrics_scores.append(30)
            
            overall_score = round(sum(metrics_scores) / len(metrics_scores)) if metrics_scores else 0
            
            # Determine overall status
            if overall_score >= 85:
                overall_status = "Tuyệt vời"
                overall_color = "success"
            elif overall_score >= 70:
                overall_status = "Tốt"
                overall_color = "info"
            elif overall_score >= 50:
                overall_status = "Trung bình"
                overall_color = "warning"
            else:
                overall_status = "Cần cải thiện"
                overall_color = "danger"
            
            # Get recent activities
            recent_activities = daily_activity[:5] if daily_activity else []
            
            # Calculate weekly total exercise
            weekly_total = sum(item.get("total_minutes", 0) for item in weekly_activity)
            
            # Get current month data
            current_month = None
            if monthly_activity:
                current_month = monthly_activity[-1] if monthly_activity else None
            
            # ---- Compose overview response ----
            return {
                "user_info": {
                    "user_id": user_id,
                    "name": profile.first_name or "Người dùng",
                    "age": profile.age,
                    "goal": profile.goal
                },
                "health_score": {
                    "overall": overall_score,
                    "status": overall_status,
                    "color": overall_color,
                    
                },
                "key_metrics": {
                    "bmi": {
                        "value": bmi,
                        "category": bmi_category,
                        "status": bmi_status,
                        "message": f"BMI: {bmi} ({bmi_category})"
                    },
                    "exercise": {
                        "daily": exercise,
                        "percentage": round(exercise_percentage),
                        "status": exercise_status,
                        "message": f"Hoạt động: {exercise} phút ({round(exercise_percentage)}% mục tiêu)"
                    },
                    "water": {
                        "intake": water_intake,
                        "percentage": round(water_percentage),
                        "ideal": ideal_water,
                        "status": water_status,
                        "message": f"Nước: {water_intake}L/{ideal_water}L ({round(water_percentage)}%)"
                    },
                    "sleep": {
                        "hours": sleep_hours,
                        "status": sleep_status,
                        "comment": sleep_comment,
                        "message": f"Ngủ: {sleep_hours} giờ ({sleep_comment})"
                    },
                    "heart_rate": {
                        "bpm": heart_rate,
                        "status": heart_status,
                        "comment": heart_comment,
                        "message": f"Nhịp tim: {heart_rate} BPM ({heart_comment})"
                    }
                },
                "activity_summary": {
                    "daily": {
                        "count": len(recent_activities),
                        "last_date": recent_activities[0].get("date") if recent_activities else None
                    },
                    "weekly": {
                        "total_minutes": weekly_total,
                        "days_active": len(weekly_activity)
                    },
                    "monthly": {
                        "avg_exercise": current_month.get("avg_exercise") if current_month else 0,
                        "month": current_month.get("month") if current_month else None
                    }
                },
                "ai_summary": health_summary,
                "quick_tips": [
                    "Duy trì 30 phút vận động mỗi ngày",
                    "Uống đủ nước theo cân nặng",
                    "Ngủ đủ 7-9 giờ mỗi đêm",
                    "Theo dõi cân nặng thường xuyên"
                ]
            }
            
        except Exception as e:
            raise DatabaseException(
                message="Unexpected error in DashboardService.get_health_overview",
                details={"error": str(e), "user_id": user_id},
            )