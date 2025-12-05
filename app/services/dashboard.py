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