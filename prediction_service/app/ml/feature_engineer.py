"""Feature engineering for obesity prediction."""
import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Feature engineering for obesity prediction models."""

    def engineer_features(self, user_input: Dict[str, Any]) -> np.ndarray:
        """Engineer features from user input.

        Args:
            user_input: Dictionary with user input data

        Returns:
            np.ndarray: Engineered features array (20 features)
        """
        try:
            # Extract basic inputs
            age = user_input.get('age', 25)
            height = user_input.get('height', 1.7)  # in meters
            weight = user_input.get('weight', 70)  # in kg
            gender = user_input.get('gender', 'male')
            family_history = user_input.get('family_history', False)

            # Calculate BMI
            bmi = weight / (height ** 2)
            bmi_category_detailed = self._get_bmi_category_detailed(bmi)

            # Lifestyle inputs (default values)
            favc = user_input.get('FAVC', 'no').lower() in ['yes', '1', 'true']
            fcvc = user_input.get('FCVC', 2.0)  # Vegetable consumption frequency
            ncp = user_input.get('NCP', 3)  # Number of main meals
            caec = self._map_caec(user_input.get('CAEC', 'Sometimes'))
            ch2o = user_input.get('CH2O', 2.0)  # Water consumption
            faf = user_input.get('FAF', 1.0)  # Physical activity frequency
            tue = user_input.get('TUE', 2.0)  # Screen time
            calc = self._map_calc(user_input.get('CALC', 'Sometimes'))
            mtrans_calorie = self._map_mtrans(user_input.get('MTRANS', 'Automobile'))

            # Calculate derived features
            metabolic_age = age * bmi / 10
            family_risk_score = (1 if family_history else 0) * bmi_category_detailed
            lifestyle_score = (faf + tue) * ncp
            diet_quality = fcvc + ch2o - (1 if favc else 0)

            # Gender encoding (1 for male, 0 for female)
            gender_encoded = 1 if gender.lower() in ['male', 'nam', '1'] else 0

            # Create feature array in the correct order (20 features)
            features = np.array([
                gender_encoded,  # Gender
                age,  # Age
                height,  # Height
                weight,  # Weight
                bmi,  # BMI
                bmi_category_detailed,  # BMI_Category_Detailed
                1 if family_history else 0,  # family_history_with_overweight
                1 if favc else 0,  # FAVC
                fcvc,  # FCVC
                ncp,  # NCP
                caec,  # CAEC
                ch2o,  # CH2O
                faf,  # FAF
                tue,  # TUE
                calc,  # CALC
                mtrans_calorie,  # MTRANS_Calorie
                metabolic_age,  # Metabolic_Age
                family_risk_score,  # Family_Risk_Score
                lifestyle_score,  # Lifestyle_Score
                diet_quality  # Diet_Quality
            ], dtype=np.float32)

            logger.debug(f"Engineered {len(features)} features")
            return features

        except Exception as e:
            logger.error(f"Feature engineering failed: {e}")
            raise

    def _get_bmi_category_detailed(self, bmi: float) -> int:
        """Get detailed BMI category index."""
        if bmi < 16:
            return 0  # Underweight
        elif bmi < 17:
            return 1
        elif bmi < 18.5:
            return 2
        elif bmi < 25:
            return 3  # Normal weight
        elif bmi < 30:
            return 4  # Overweight
        elif bmi < 35:
            return 5
        elif bmi < 40:
            return 6
        else:
            return 7

    def _map_caec(self, caec_value: str) -> int:
        """Map CAEC (Consumption of food between meals) to numeric."""
        mapping = {
            'no': 0,
            'sometimes': 1,
            'frequently': 2,
            'always': 3
        }
        return mapping.get(caec_value.lower(), 1)

    def _map_calc(self, calc_value: str) -> int:
        """Map CALC (Consumption of alcohol) to numeric."""
        mapping = {
            'no': 0,
            'sometimes': 1,
            'frequently': 2,
            'always': 3
        }
        return mapping.get(calc_value.lower(), 1)

    def _map_mtrans(self, mtrans_value: str) -> float:
        """Map MTRANS (Transportation used) to calorie value."""
        # Higher values indicate less physical activity in transport
        mapping = {
            'automobile': 2.0,
            'motorbike': 1.5,
            'bike': 1.0,
            'public_transportation': 1.25,
            'walking': 0.5
        }
        return mapping.get(mtrans_value.lower(), 1.0)