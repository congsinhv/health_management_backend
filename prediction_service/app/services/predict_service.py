"""Prediction service with ONNX models."""
import numpy as np
import logging
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
import json

from app.ml.model_loader import ONNXModelLoader
from app.ml.feature_engineer import FeatureEngineer
from app.config import settings

logger = logging.getLogger(__name__)


class PredictService:
    """Health prediction service with ONNX optimization."""

    def __init__(self, model_loader: ONNXModelLoader):
        self.model_loader = model_loader
        self.feature_engineer = FeatureEngineer()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    @classmethod
    async def create(cls):
        """Create and initialize service."""
        model_loader = ONNXModelLoader(
            model_path=settings.model_path,
            label_encoder_path=settings.label_encoder_path
        )
        await model_loader.initialize()
        return cls(model_loader)

    async def predict(self, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Generate health prediction."""
        try:
            # 1. Feature engineering
            features = self.feature_engineer.engineer_features(user_input)

            # 2. Model prediction (ONNX - faster inference)
            obesity_level, raw_prediction = self.model_loader.predict(features)

            # 3. Calculate health metrics
            height = user_input.get('height', 1.7)
            weight = user_input.get('weight', 70)
            age = user_input.get('age', 25)
            bmi = weight / (height ** 2)
            metabolic_age = self._calculate_metabolic_age(age, bmi, user_input)

            # 4. Generate AI recommendations (OpenAI)
            diet_plan = await self._generate_diet_plan(obesity_level, bmi)
            workout_plan = await self._generate_workout_plan(obesity_level, bmi)

            # 5. Return prediction data (Main API will persist)
            return {
                "obesity_level": obesity_level,
                "bmi": round(bmi, 1),
                "metabolic_age": int(round(metabolic_age)),
                "diet_plan": diet_plan,
                "workout_plan": workout_plan,
                "raw_prediction": raw_prediction.tolist() if hasattr(raw_prediction, 'tolist') else raw_prediction,
                "input_data": user_input
            }

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise

    def is_model_loaded(self) -> bool:
        """Check if model is loaded."""
        return self.model_loader.is_model_loaded()

    def _calculate_metabolic_age(self, age: float, bmi: float, user_input: Dict[str, Any]) -> float:
        """Calculate metabolic age based on various factors."""
        try:
            # Base metabolic age from BMI
            base_metabolic_age = age * bmi / 10

            # Adjustments based on lifestyle
            family_history_penalty = 5 if user_input.get('family_history', False) else 0
            physical_activity_bonus = self._calculate_activity_bonus(user_input)
            diet_penalty = self._calculate_diet_penalty(user_input)

            metabolic_age = base_metabolic_age + family_history_penalty - physical_activity_bonus + diet_penalty

            return max(10, min(80, metabolic_age))  # Reasonable bounds

        except Exception as e:
            logger.warning(f"Metabolic age calculation failed: {e}")
            return age  # Fallback to chronological age

    def _calculate_activity_bonus(self, user_input: Dict[str, Any]) -> float:
        """Calculate activity bonus for metabolic age."""
        try:
            faf = user_input.get('FAF', 1)  # Physical activity frequency
            tue = user_input.get('TUE', 2)  # Screen time

            # More activity and less screen time = better metabolic age
            if faf >= 3 and tue <= 2:
                return 8.0  # High activity bonus
            elif faf >= 2 and tue <= 3:
                return 4.0  # Medium activity bonus
            elif faf >= 1 and tue <= 4:
                return 2.0  # Low activity bonus
            else:
                return 0.0  # No bonus
        except:
            return 0.0

    def _calculate_diet_penalty(self, user_input: Dict[str, Any]) -> float:
        """Calculate diet penalty for metabolic age."""
        try:
            fcvc = user_input.get('FCVC', 2)  # Vegetable consumption
            favc = user_input.get('FAVC', 'no')  # High calorie food
            ch2o = user_input.get('CH2O', 2)  # Water consumption

            penalty = 0

            # Poor diet penalties
            if fcvc < 2:
                penalty += 3  # Low vegetable consumption
            if favc.lower() in ['yes', '1']:
                penalty += 5  # High calorie food consumption
            if ch2o < 2:
                penalty += 2  # Low water consumption

            return penalty
        except:
            return 0.0

    async def _generate_diet_plan(self, obesity_level: str, bmi: float) -> Dict[str, Any]:
        """Generate diet plan using OpenAI."""
        weight_category = 'overweight' if bmi >= 25 else 'normal' if bmi >= 18.5 else 'underweight'

        prompt = f"""
        You are a nutrition expert. Create a 7-day diet plan for a person with:
        - BMI: {bmi:.1f} ({weight_category})
        - Obesity level: {obesity_level}

        Create a JSON response with this structure:
        {{
            "healthAnalysis": [
                "Daily calorie target: X calories",
                "Key nutrients to focus on",
                "Foods to include more",
                "Foods to limit"
            ],
            "weeklyPlans": [
                {{
                    "day": 1,
                    "breakfast": [{{"name": "...", "calories": 100, "count": 1, "unit": "..."}}],
                    "lunch": [...],
                    "dinner": [...],
                    "snacks": [...],
                    "recommendedFoods": "...",
                    "foodsToLimit": "..."
                }}
                // ... continue for days 2-7
            ]
        }}

        IMPORTANT: All numeric values (calories, count) must be integers.
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error(f"Diet plan generation failed: {e}")
            return {
                "healthAnalysis": ["Unable to generate diet plan at this time."],
                "weeklyPlans": []
            }

    async def _generate_workout_plan(self, obesity_level: str, bmi: float) -> Dict[str, Any]:
        """Generate workout plan using OpenAI."""
        fitness_level = 'beginner' if bmi >= 30 else 'intermediate' if bmi >= 25 else 'advanced'

        prompt = f"""
        You are a fitness expert. Create a 7-day workout plan for a person with:
        - BMI: {bmi:.1f}
        - Fitness level: {fitness_level}
        - Obesity level: {obesity_level}

        Create a JSON response with this structure:
        {{
            "weeklyPlans": [
                {{
                    "name": "Cardio & Strength Day",
                    "day": 1,
                    "exercises": [
                        {{
                            "name": "Walking",
                            "duration": 30,
                            "unit": "minutes",
                            "description": "Brisk walking on flat surface",
                            "sets": null,
                            "reps": null
                        }},
                        {{
                            "name": "Bodyweight Squats",
                            "duration": 15,
                            "unit": "minutes",
                            "description": "Bodyweight squats with proper form",
                            "sets": 3,
                            "reps": 12
                        }}
                    ]
                }}
                // ... continue for days 2-7
            ]
        }}

        IMPORTANT: All numeric values (duration, sets, reps) must be integers.
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error(f"Workout plan generation failed: {e}")
            return {
                "weeklyPlans": []
            }