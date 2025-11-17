import os
import joblib
import pandas as pd
from typing import Dict
from openai import OpenAI
from app.config import settings
from app.schemas.predict import UserInput

BASE_DIR = os.getcwd()

class ObesityPredictorComplete:
    def __init__(self):
        # Load model và encoder
        model_path = os.path.join(BASE_DIR, "models_obesity", "obesity_classifier_final.pkl")
        encoder_path = os.path.join(BASE_DIR, "models_obesity", "label_encoder.pkl")
        self.model = joblib.load(model_path)
        self.le = joblib.load(encoder_path)

        self.features = [
            'Gender', 'Age', 'Height', 'Weight', 'BMI', 'BMI_Category_Detailed',
            'family_history_with_overweight', 'FAVC', 'FCVC', 'NCP', 'CAEC',
            'CH2O', 'FAF', 'TUE', 'CALC', 'MTRANS_Calorie',
            'Metabolic_Age', 'Family_Risk_Score', 'Lifestyle_Score', 'Diet_Quality'
        ]

        # Khởi tạo OpenAI client
        if not settings.openrouter_api_key:
            raise RuntimeError("OpenRouter API key is not set in settings.openrouter_api_key")

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key
        )

    def predict_complete(self, user_inputs: dict):
        age = user_inputs["age"]
        height = user_inputs["height"]
        weight = user_inputs["weight"]
        gender = user_inputs["gender"]
        family_history = user_inputs["family_history"]

        bmi = weight / (height ** 2)
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
            'Gender': 1 if gender.lower() in ['nam', 'male', '1'] else 0,
            'Age': age,
            'Height': height,
            'Weight': weight,
            'BMI': bmi,
            'BMI_Category_Detailed': bmi_cat,
            'family_history_with_overweight': 1 if family_history else 0,
            'FAVC': favc,
            'FCVC': fcvc,
            'NCP': ncp,
            'CAEC': caec,
            'CH2O': ch2o,
            'FAF': faf,
            'TUE': tue,
            'CALC': calc,
            'MTRANS_Calorie': mtrans,
            'Metabolic_Age': metabolic_age,
            'Family_Risk_Score': family_risk_score,
            'Lifestyle_Score': lifestyle_score,
            'Diet_Quality': diet_quality
        }

        df = pd.DataFrame([input_data])
        prediction = self.model.predict(df[self.features])[0]
        confidence = max(self.model.predict_proba(df[self.features])[0])

        return {
            "dự_đoán": self.le.inverse_transform([prediction])[0],
            "độ_tin_cậy": f"{confidence:.1%}",
            "bmi": f"{bmi:.1f}",
            "phân_loại_bmi": self._get_bmi_category(bmi)
        }

    def predict_obesity_ai(self, data: UserInput) -> Dict[str, str]:
        result = self.predict_complete(data.dict())
        bmi_formatted = self.format_bmi(result['bmi'])
        prompts = self.build_prompts(data, result, bmi_formatted)

        return {
            "prediction": result,
            "general_analysis": self.get_ai_suggestion(prompts["general"]),
            "detailed_diet_plan": self.get_ai_suggestion(prompts["diet"]),
            "detailed_exercise_plan": self.get_ai_suggestion(prompts["exercise"]),
        }

    def format_bmi(self, value) -> str:
        try:
            return f"{float(value):.1f}"
        except (ValueError, TypeError):
            return str(value)

    def build_prompts(self, data: UserInput, result: Dict[str, str], bmi_formatted: str) -> Dict[str, str]:
        bmi_type = result['phân_loại_bmi']
        prediction = result['dự_đoán']

        general_prompt = f"""
Bạn là chuyên gia dinh dưỡng và sức khỏe. Hãy phân tích tình trạng sức khỏe của người dùng sau:

- Giới tính: {data.gender}
- Tuổi: {data.age}
- Chiều cao: {data.height} m
- Cân nặng: {data.weight} kg
- BMI: {bmi_formatted} ({bmi_type})
- Dự đoán: {prediction}

Yêu cầu:
1. Phân tích tổng quan sức khỏe
2. Đề xuất chế độ ăn uống
3. Đề xuất tập luyện
4. Lời khuyên chung
"""

        diet_prompt = f"""
Tạo chế độ ăn 1 tuần phù hợp với người có tình trạng {prediction}.
Bao gồm:
1. Lượng calo khuyến nghị
2. Thực đơn 7 ngày (sáng, trưa, tối)
3. Thực phẩm nên/không nên dùng
"""

        exercise_prompt = f"""
Tạo kế hoạch tập luyện 1 tuần cho người có tình trạng {prediction}.
Bao gồm:
1. Các bài tập
2. Thời gian & cường độ
3. Lưu ý an toàn
"""

        return {
            "general": general_prompt.strip(),
            "diet": diet_prompt.strip(),
            "exercise": exercise_prompt.strip(),
        }

    def get_ai_suggestion(self, prompt_text: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=settings.openrouter_model,
                messages=[{"role": "user", "content": prompt_text}],
                temperature=settings.openrouter_temperature,
                max_tokens=settings.openrouter_max_tokens,
                timeout=settings.openrouter_timeout,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Không thể tạo khuyến nghị: {str(e)}"

    def _bmi_category_index(self, bmi):
        if bmi < 16: return 0
        elif bmi < 17: return 1
        elif bmi < 18.5: return 2
        elif bmi < 25: return 3
        elif bmi < 30: return 4
        elif bmi < 35: return 5
        elif bmi < 40: return 6
        else: return 7

    def _get_bmi_category(self, bmi):
        if bmi < 18.5: return "Thiếu cân"
        elif bmi < 25: return "Bình thường"
        elif bmi < 30: return "Thừa cân"
        elif bmi < 35: return "Béo phì cấp I"
        elif bmi < 40: return "Béo phì cấp II"
        else: return "Béo phì cấp III"
