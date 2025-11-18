"""
Unit tests for obesity prediction service.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from app.services.predict_service import ObesityPredictorComplete
from app.schemas.predict import UserInput


@pytest.mark.unit
class TestObesityPredictorComplete:
    """Tests for ObesityPredictorComplete service."""

    @pytest.fixture
    def mock_model_files(self, tmp_path):
        """Create temporary mock model files."""
        model_dir = tmp_path / "models_obesity"
        model_dir.mkdir()
        
        model_path = model_dir / "obesity_classifier_final.pkl"
        encoder_path = model_dir / "label_encoder.pkl"
        
        # Create empty files
        model_path.touch()
        encoder_path.touch()
        
        return {
            "model_dir": str(model_dir),
            "model_path": str(model_path),
            "encoder_path": str(encoder_path),
        }

    @pytest.fixture
    def mock_joblib(self):
        """Mock joblib.load to avoid loading actual model files."""
        with patch("app.services.predict_service.joblib.load") as mock_load:
            # Mock model
            mock_model = Mock()
            mock_model.predict.return_value = [3]  # Mock prediction
            mock_model.predict_proba.return_value = [[0.1, 0.2, 0.3, 0.4]]
            
            # Mock label encoder
            mock_encoder = Mock()
            mock_encoder.inverse_transform.return_value = ["Normal_Weight"]
            
            # Return model first, then encoder
            mock_load.side_effect = [mock_model, mock_encoder]
            
            yield mock_load

    def test_init_with_existing_local_files(self, mock_model_files, mock_joblib):
        """Test initialization when model files exist locally."""
        with patch("app.services.predict_service.BASE_DIR", mock_model_files["model_dir"].replace("/models_obesity", "")):
            with patch("app.services.predict_service.os.path.exists", return_value=True):
                predictor = ObesityPredictorComplete()
                
                assert predictor.model is not None
                assert predictor.le is not None
                assert len(predictor.features) == 20

    def test_ensure_models_downloaded_files_exist(self, mock_model_files):
        """Test _ensure_models_downloaded when files already exist."""
        predictor = ObesityPredictorComplete.__new__(ObesityPredictorComplete)
        
        with patch("os.path.exists", return_value=True):
            # Should not raise any exception
            predictor._ensure_models_downloaded(
                mock_model_files["model_path"],
                mock_model_files["encoder_path"],
                mock_model_files["model_dir"],
            )

    def test_ensure_models_downloaded_no_gcs_config(self, mock_model_files):
        """Test _ensure_models_downloaded raises error when GCS not configured."""
        predictor = ObesityPredictorComplete.__new__(ObesityPredictorComplete)
        
        with patch("os.path.exists", return_value=False):
            with patch("app.services.predict_service.settings") as mock_settings:
                mock_settings.gcp_model_bucket = None
                
                with pytest.raises(ValueError, match="Model files not found and GCS bucket not configured"):
                    predictor._ensure_models_downloaded(
                        mock_model_files["model_path"],
                        mock_model_files["encoder_path"],
                        mock_model_files["model_dir"],
                    )

    def test_ensure_models_downloaded_from_gcs(self, mock_model_files):
        """Test _ensure_models_downloaded downloads from GCS successfully."""
        predictor = ObesityPredictorComplete.__new__(ObesityPredictorComplete)
        
        with patch("os.path.exists", return_value=False):
            with patch("app.services.predict_service.settings") as mock_settings:
                mock_settings.gcp_model_bucket = "test-bucket"
                mock_settings.gcp_project_id = "test-project"
                mock_settings.model_download_timeout = 600
                
                with patch("app.services.predict_service.GCSDownloader") as mock_downloader_class:
                    mock_downloader = Mock()
                    mock_downloader.download_file.return_value = True
                    mock_downloader_class.return_value = mock_downloader
                    
                    with patch("pathlib.Path.mkdir"):
                        predictor._ensure_models_downloaded(
                            mock_model_files["model_path"],
                            mock_model_files["encoder_path"],
                            mock_model_files["model_dir"],
                        )
                    
                    # Verify downloader was initialized correctly
                    mock_downloader_class.assert_called_once_with(
                        bucket_name="test-bucket",
                        project_id="test-project",
                        timeout=600,
                    )
                    
                    # Verify both files were downloaded
                    assert mock_downloader.download_file.call_count == 2
                    
                    # Check the blob paths
                    calls = mock_downloader.download_file.call_args_list
                    assert calls[0][0][0] == "models_obesity/obesity_classifier_final.pkl"
                    assert calls[1][0][0] == "models_obesity/label_encoder.pkl"

    def test_ensure_models_downloaded_gcs_failure(self, mock_model_files):
        """Test _ensure_models_downloaded handles GCS download failure."""
        predictor = ObesityPredictorComplete.__new__(ObesityPredictorComplete)
        
        with patch("os.path.exists", return_value=False):
            with patch("app.services.predict_service.settings") as mock_settings:
                mock_settings.gcp_model_bucket = "test-bucket"
                mock_settings.gcp_project_id = "test-project"
                mock_settings.model_download_timeout = 600
                
                with patch("app.services.predict_service.GCSDownloader") as mock_downloader_class:
                    mock_downloader = Mock()
                    mock_downloader.download_file.return_value = False
                    mock_downloader_class.return_value = mock_downloader
                    
                    with patch("pathlib.Path.mkdir"):
                        with pytest.raises(RuntimeError, match="Failed to download model file from GCS"):
                            predictor._ensure_models_downloaded(
                                mock_model_files["model_path"],
                                mock_model_files["encoder_path"],
                                mock_model_files["model_dir"],
                            )

    def test_bmi_category_index(self, mock_model_files, mock_joblib):
        """Test BMI category index calculation."""
        with patch("app.services.predict_service.BASE_DIR", mock_model_files["model_dir"].replace("/models_obesity", "")):
            with patch("os.path.exists", return_value=True):
                predictor = ObesityPredictorComplete()
                
                assert predictor._bmi_category_index(15.5) == 0  # < 16
                assert predictor._bmi_category_index(16.5) == 1  # 16-17
                assert predictor._bmi_category_index(17.5) == 2  # 17-18.5
                assert predictor._bmi_category_index(22.0) == 3  # 18.5-25
                assert predictor._bmi_category_index(27.0) == 4  # 25-30
                assert predictor._bmi_category_index(32.0) == 5  # 30-35
                assert predictor._bmi_category_index(37.0) == 6  # 35-40
                assert predictor._bmi_category_index(42.0) == 7  # > 40

    def test_get_bmi_category(self, mock_model_files, mock_joblib):
        """Test BMI category string."""
        with patch("app.services.predict_service.BASE_DIR", mock_model_files["model_dir"].replace("/models_obesity", "")):
            with patch("os.path.exists", return_value=True):
                predictor = ObesityPredictorComplete()
                
                assert predictor._get_bmi_category(17.0) == "Thiếu cân"
                assert predictor._get_bmi_category(22.0) == "Bình thường"
                assert predictor._get_bmi_category(27.0) == "Thừa cân"
                assert predictor._get_bmi_category(32.0) == "Béo phì cấp I"
                assert predictor._get_bmi_category(37.0) == "Béo phì cấp II"
                assert predictor._get_bmi_category(42.0) == "Béo phì cấp III"

    def test_predict_complete(self, mock_model_files, mock_joblib):
        """Test complete prediction flow."""
        with patch("app.services.predict_service.BASE_DIR", mock_model_files["model_dir"].replace("/models_obesity", "")):
            with patch("os.path.exists", return_value=True):
                predictor = ObesityPredictorComplete()
                
                user_inputs = {
                    "age": 25,
                    "height": 1.75,
                    "weight": 70,
                    "gender": "male",
                    "family_history": False,
                }
                
                result = predictor.predict_complete(user_inputs)
                
                assert "dự_đoán" in result
                assert "độ_tin_cậy" in result
                assert "bmi" in result
                assert "phân_loại_bmi" in result
                assert result["dự_đoán"] == "Normal_Weight"

    def test_format_bmi(self, mock_model_files, mock_joblib):
        """Test BMI formatting."""
        with patch("app.services.predict_service.BASE_DIR", mock_model_files["model_dir"].replace("/models_obesity", "")):
            with patch("os.path.exists", return_value=True):
                predictor = ObesityPredictorComplete()
                
                assert predictor.format_bmi(22.5) == "22.5"
                assert predictor.format_bmi("22.5") == "22.5"
                assert predictor.format_bmi(22.567) == "22.6"
                assert predictor.format_bmi("invalid") == "invalid"

    def test_build_prompts(self, mock_model_files, mock_joblib):
        """Test AI prompt building."""
        with patch("app.services.predict_service.BASE_DIR", mock_model_files["model_dir"].replace("/models_obesity", "")):
            with patch("os.path.exists", return_value=True):
                predictor = ObesityPredictorComplete()
                
                data = UserInput(
                    age=25,
                    height=1.75,
                    weight=70,
                    gender="male",
                    family_history=False,
                )
                
                result = {
                    "dự_đoán": "Normal_Weight",
                    "độ_tin_cậy": "80.0%",
                    "bmi": "22.9",
                    "phân_loại_bmi": "Bình thường",
                }
                
                prompts = predictor.build_prompts(data, result, "22.9")
                
                assert "general" in prompts
                assert "diet" in prompts
                assert "exercise" in prompts
                assert "Normal_Weight" in prompts["general"]
                assert "Normal_Weight" in prompts["diet"]
                assert "Normal_Weight" in prompts["exercise"]

    def test_get_ai_suggestion_success(self, mock_model_files, mock_joblib):
        """Test AI suggestion generation success."""
        with patch("app.services.predict_service.BASE_DIR", mock_model_files["model_dir"].replace("/models_obesity", "")):
            with patch("os.path.exists", return_value=True):
                predictor = ObesityPredictorComplete()
                
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "Test suggestion"
                
                predictor.client.chat.completions.create = Mock(return_value=mock_response)
                
                result = predictor.get_ai_suggestion("Test prompt")
                
                assert result == "Test suggestion"

    def test_get_ai_suggestion_failure(self, mock_model_files, mock_joblib):
        """Test AI suggestion generation handles errors."""
        with patch("app.services.predict_service.BASE_DIR", mock_model_files["model_dir"].replace("/models_obesity", "")):
            with patch("os.path.exists", return_value=True):
                predictor = ObesityPredictorComplete()
                
                predictor.client.chat.completions.create = Mock(side_effect=Exception("API Error"))
                
                result = predictor.get_ai_suggestion("Test prompt")
                
                assert "Không thể tạo khuyến nghị" in result
                assert "API Error" in result

