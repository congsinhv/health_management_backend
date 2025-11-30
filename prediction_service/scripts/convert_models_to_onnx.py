"""Convert sklearn models to ONNX format."""
import joblib
import json
import numpy as np
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
import onnx
import os

def convert_classifier_to_onnx():
    """Convert obesity classifier to ONNX."""
    print("Loading sklearn model...")

    # Load sklearn model using joblib (consistent with existing code)
    rf_model = joblib.load("../../models_obesity/obesity_classifier_final.pkl")

    # Check if it's a fitted model
    if not hasattr(rf_model, 'feature_names_in_'):
        raise ValueError("Model is not fitted or doesn't have feature information")

    print(f"Model type: {type(rf_model)}")
    print(f"Number of features: {len(rf_model.feature_names_in_)}")
    print(f"Feature names: {rf_model.feature_names_in_}")

    # Define input shape based on model features
    initial_type = [("float_input", FloatTensorType([None, len(rf_model.feature_names_in_)]))]

    # Convert to ONNX
    print("Converting to ONNX...")
    onnx_model = convert_sklearn(
        rf_model,
        initial_types=initial_type,
        target_opset=12
    )

    # Save ONNX model
    os.makedirs("../../models", exist_ok=True)
    with open("../../models/obesity_classifier.onnx", "wb") as f:
        f.write(onnx_model.SerializeToString())

    print(f"Obesity classifier converted to ONNX")
    print(f"Model size: {len(onnx_model.SerializeToString()) / 1024 / 1024:.2f} MB")

    return onnx_model

def convert_label_encoder_to_onnx():
    """Convert label encoder to ONNX."""
    print("Loading label encoder...")

    label_encoder = joblib.load("../../models_obesity/label_encoder.pkl")

    print(f"Label encoder classes: {label_encoder.classes_}")

    # Label encoders are simple mappings; store as JSON for easy use
    classes = {str(i): label for i, label in enumerate(label_encoder.classes_)}

    os.makedirs("../../models", exist_ok=True)
    with open("../../models/label_encoder.json", "w") as f:
        json.dump(classes, f, indent=2)

    print("Label encoder converted to JSON")
    print(f"Number of classes: {len(classes)}")

    return classes

def verify_onnx_model():
    """Verify the ONNX model can be loaded and checked."""
    print("Verifying ONNX model...")

    try:
        onnx_model = onnx.load("../../models/obesity_classifier.onnx")
        onnx.checker.check_model(onnx_model)
        print("✓ ONNX model verification passed")

        # Print model inputs/outputs
        print(f"Model inputs: {[input.name for input in onnx_model.graph.input]}")
        print(f"Model outputs: {[output.name for output in onnx_model.graph.output]}")

        return True
    except Exception as e:
        print(f"✗ ONNX model verification failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Converting sklearn models to ONNX ===")

    try:
        # Convert models
        onnx_model = convert_classifier_to_onnx()
        classes = convert_label_encoder_to_onnx()

        # Verify ONNX model
        if verify_onnx_model():
            print("\n=== Conversion successful! ===")
            print("Files created:")
            print("- ../models/obesity_classifier.onnx")
            print("- ../models/label_encoder.json")
        else:
            print("\n=== Conversion failed! ===")
            exit(1)

    except Exception as e:
        print(f"\n=== Conversion failed: {e} ===")
        exit(1)