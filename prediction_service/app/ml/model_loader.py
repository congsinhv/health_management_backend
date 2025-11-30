"""ONNX model loader for sklearn models."""
import onnxruntime as ort
import numpy as np
import json
import logging
from typing import Dict, List, Tuple, Any
import os

logger = logging.getLogger(__name__)


class ONNXModelLoader:
    """Load and run ONNX models."""

    def __init__(self, model_path: str, label_encoder_path: str):
        self.model_path = model_path
        self.label_encoder_path = label_encoder_path
        self.session = None
        self.label_encoder = None
        self._model_loaded = False

    async def initialize(self):
        """Load ONNX model and label encoder."""
        logger.info(f"Loading ONNX model from {self.model_path}")

        try:
            # Validate file existence
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"ONNX model not found: {self.model_path}")

            if not os.path.exists(self.label_encoder_path):
                raise FileNotFoundError(
                    f"Label encoder not found: {self.label_encoder_path}"
                )

            # Create ONNX Runtime session
            self.session = ort.InferenceSession(
                self.model_path, providers=["CPUExecutionProvider"]
            )

            # Load label encoder
            with open(self.label_encoder_path, "r") as f:
                self.label_encoder = json.load(f)

            # Validate model inputs/outputs
            inputs = [input.name for input in self.session.get_inputs()]
            outputs = [output.name for output in self.session.get_outputs()]

            logger.info(f"ONNX model loaded successfully")
            logger.info(f"Model inputs: {inputs}")
            logger.info(f"Model outputs: {outputs}")
            logger.info(f"Label encoder classes: {list(self.label_encoder.values())}")

            self._model_loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load ONNX model: {e}")
            self._model_loaded = False
            raise

    def predict(self, features: np.ndarray) -> Tuple[str, np.ndarray]:
        """Run prediction with ONNX model."""
        if not self._model_loaded:
            raise RuntimeError("Model not loaded. Call initialize() first.")

        # Validate input shape
        expected_shape = (None, 20)  # 20 features expected
        if len(features.shape) == 1:
            features = features.reshape(1, -1)

        if features.shape[1] != 20:
            raise ValueError(f"Expected 20 features, got {features.shape[1]}")

        # Get input/output names
        input_name = self.session.get_inputs()[0].name
        output_names = [output.name for output in self.session.get_outputs()]

        # Run inference
        try:
            results = self.session.run(
                output_names, {input_name: features.astype(np.float32)}
            )

            # Extract prediction (first output is usually label)
            if len(results) == 0:
                raise RuntimeError("No output from ONNX model")

            prediction_output = results[0]

            # Handle different output formats
            if len(prediction_output.shape) == 1:
                # Single output - label indices
                label_indices = prediction_output
            elif len(prediction_output.shape) == 2:
                # Two outputs - labels and probabilities
                label_indices = (
                    prediction_output[:, 0]
                    if prediction_output.shape[0] > 1
                    else prediction_output[0]
                )
            else:
                raise RuntimeError(
                    f"Unexpected output shape: {prediction_output.shape}"
                )

            # Get first prediction (for batch size 1)
            if len(label_indices.shape) == 1:
                label_index = int(label_indices[0])
            else:
                label_index = int(label_indices[0][0])

            # Decode label
            label = self.label_encoder.get(str(label_index), "Unknown")

            return label, prediction_output

        except Exception as e:
            logger.error(f"ONNX inference failed: {e}")
            raise

    def is_model_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model_loaded

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        if not self._model_loaded:
            return {"loaded": False}

        return {
            "loaded": True,
            "model_path": self.model_path,
            "inputs": [input.name for input in self.session.get_inputs()],
            "outputs": [output.name for output in self.session.get_outputs()],
            "num_classes": len(self.label_encoder),
            "classes": list(self.label_encoder.values()),
        }

    def __del__(self):
        """Cleanup resources."""
        if hasattr(self, "session") and self.session is not None:
            # ONNX Runtime session cleanup
            self.session = None
