import os
import joblib
import pandas as pd
import logging
from typing import Dict
from pathlib import Path
from openai import OpenAI
from app.config import settings
from app.schemas.predict import UserInput
from app.utils.gcs_downloader import GCSDownloader

logger = logging.getLogger(__name__)
BASE_DIR = os.getcwd()

class ObesityPredictorComplete:
    def __init__(self):
        # Define paths
        model_dir = os.path.join(BASE_DIR, "models_obesity")
        model_path = os.path.join(model_dir, "obesity_classifier_final.pkl")
        encoder_path = os.path.join(model_dir, "label_encoder.pkl")
        
        # Download models from GCS if they don't exist locally
        self._ensure_models_downloaded(model_path, encoder_path, model_dir)
        
        # Load model và encoder
        self.model = joblib.load(model_path)
        self.le = joblib.load(encoder_path)

        self.features = [
            'Gender', 'Age', 'Height', 'Weight', 'BMI', 'BMI_Category_Detailed',
            'family_history_with_overweight', 'FAVC', 'FCVC', 'NCP', 'CAEC',
            'CH2O', 'FAF', 'TUE', 'CALC', 'MTRANS_Calorie',
            'Metabolic_Age', 'Family_Risk_Score', 'Lifestyle_Score', 'Diet_Quality'
        ]

        self.client = OpenAI(api_key=settings.openai_api_key)

    def _ensure_models_downloaded(self, model_path: str, encoder_path: str, model_dir: str):
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
            Path(model_dir).mkdir(parents=True, exist_ok=True)
            
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
                    raise RuntimeError(f"Failed to download model file from GCS: {blob_path}")
            
            # Download encoder file if missing
            if not encoder_exists:
                blob_path = "models_obesity/label_encoder.pkl"
                logger.info(f"Downloading {blob_path}...")
                success = downloader.download_file(blob_path, encoder_path, force=False)
                if not success:
                    raise RuntimeError(f"Failed to download encoder file from GCS: {blob_path}")
            
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
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt_text}]
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
