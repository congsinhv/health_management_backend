"""Benchmark ONNX vs sklearn prediction performance."""
import time
import joblib
import numpy as np
import onnxruntime as ort
import json
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_sklearn_models():
    """Load sklearn models."""
    print("Loading sklearn models...")
    sklearn_model = joblib.load("obesity_classifier_final.pkl")
    label_encoder = joblib.load("label_encoder.pkl")

    print(f"Sklearn model type: {type(sklearn_model)}")
    print(f"Number of features: {len(sklearn_model.feature_names_in_)}")

    return sklearn_model, label_encoder


def load_onnx_models():
    """Load ONNX models."""
    print("Loading ONNX models...")
    onnx_session = ort.InferenceSession(
        "models/obesity_classifier.onnx", providers=["CPUExecutionProvider"]
    )

    with open("models/label_encoder.json", "r") as f:
        label_encoder = json.load(f)

    print(f"ONNX model inputs: {[input.name for input in onnx_session.get_inputs()]}")
    print(
        f"ONNX model outputs: {[output.name for output in onnx_session.get_outputs()]}"
    )

    return onnx_session, label_encoder


def generate_test_data(n_samples=1000):
    """Generate test data for benchmarking."""
    print(f"Generating {n_samples} test samples...")

    # Generate random test data with realistic ranges
    test_data = []
    for i in range(n_samples):
        sample = {
            "Gender": np.random.randint(0, 2),
            "Age": np.random.randint(18, 65),
            "Height": np.random.uniform(1.4, 2.0),
            "Weight": np.random.uniform(40, 120),
            "BMI": 0,  # Will be calculated
            "BMI_Category_Detailed": np.random.randint(0, 7),
            "family_history_with_overweight": np.random.randint(0, 2),
            "FAVC": np.random.randint(0, 2),
            "FCVC": np.random.uniform(1, 3),
            "NCP": np.random.randint(1, 4),
            "CAEC": np.random.randint(0, 4),
            "CH2O": np.random.uniform(1, 3),
            "FAF": np.random.uniform(0, 3),
            "TUE": np.random.uniform(0, 3),
            "CALC": np.random.randint(0, 4),
            "MTRANS_Calorie": np.random.uniform(0.5, 2.5),
            "Metabolic_Age": np.random.uniform(10, 50),
            "Family_Risk_Score": np.random.uniform(0, 10),
            "Lifestyle_Score": np.random.uniform(1, 12),
            "Diet_Quality": np.random.uniform(0, 5),
        }

        # Calculate BMI
        sample["BMI"] = sample["Weight"] / (sample["Height"] ** 2)

        test_data.append(sample)

    return test_data


def prepare_sklearn_features(test_data, sklearn_model):
    """Prepare features for sklearn model."""
    feature_names = sklearn_model.feature_names_in_
    features_list = []

    for sample in test_data:
        features = [sample[feature] for feature in feature_names]
        features_list.append(features)

    return np.array(features_list, dtype=np.float32)


def prepare_onnx_features(test_data):
    """Prepare features for ONNX model."""
    # Same feature order as sklearn
    feature_names = [
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

    features_list = []
    for sample in test_data:
        features = [sample[feature] for feature in feature_names]
        features_list.append(features)

    return np.array(features_list, dtype=np.float32)


def benchmark_sklearn(sklearn_model, label_encoder, test_features, n_runs=100):
    """Benchmark sklearn prediction performance."""
    print(f"Benchmarking sklearn ({n_runs} runs)...")

    # Warm up
    sklearn_model.predict(test_features[:10])

    # Benchmark
    start_time = time.time()
    for _ in range(n_runs):
        sklearn_model.predict(test_features)
    end_time = time.time()

    total_time = end_time - start_time
    avg_time = total_time / n_runs
    predictions_per_second = len(test_features) / avg_time

    return {
        "total_time": total_time,
        "avg_time": avg_time,
        "predictions_per_second": predictions_per_second,
    }


def benchmark_onnx(onnx_session, label_encoder, test_features, n_runs=100):
    """Benchmark ONNX prediction performance."""
    print(f"Benchmarking ONNX ({n_runs} runs)...")

    # Get input/output names
    input_name = onnx_session.get_inputs()[0].name
    output_name = onnx_session.get_outputs()[0].name

    # Warm up
    onnx_session.run([output_name], {input_name: test_features[:10]})

    # Benchmark
    start_time = time.time()
    for _ in range(n_runs):
        onnx_session.run([output_name], {input_name: test_features})
    end_time = time.time()

    total_time = end_time - start_time
    avg_time = total_time / n_runs
    predictions_per_second = len(test_features) / avg_time

    return {
        "total_time": total_time,
        "avg_time": avg_time,
        "predictions_per_second": predictions_per_second,
    }


def verify_predictions(sklearn_model, label_encoder, onnx_session, test_features):
    """Verify that sklearn and ONNX predictions match."""
    print("Verifying prediction consistency...")

    # Get predictions from both models
    sklearn_preds = sklearn_model.predict(test_features[:10])

    input_name = onnx_session.get_inputs()[0].name
    output_name = onnx_session.get_outputs()[0].name
    onnx_preds = onnx_session.run([output_name], {input_name: test_features[:10]})

    # Compare predictions
    sklearn_labels = label_encoder.inverse_transform(sklearn_preds)
    onnx_labels = [label_encoder[str(int(pred[0]))] for pred in onnx_preds[0]]

    matches = sum(1 for sk, on in zip(sklearn_labels, onnx_labels) if sk == on)
    consistency = matches / len(sklearn_preds) * 100

    print(
        f"Prediction consistency: {consistency:.1f}% ({matches}/{len(sklearn_preds)})"
    )

    if consistency < 95:
        print("⚠️  Warning: Low prediction consistency between sklearn and ONNX")
        for i, (sk, on) in enumerate(zip(sklearn_labels, onnx_labels)):
            if sk != on:
                print(f"  Sample {i}: sklearn={sk}, onnx={on}")

    return consistency


def main():
    """Run benchmark comparison."""
    print("=== ONNX vs Sklearn Benchmark ===\n")

    # Load models
    sklearn_model, sklearn_label_encoder = load_sklearn_models()
    onnx_session, onnx_label_encoder = load_onnx_models()

    # Generate test data
    test_data = generate_test_data(n_samples=1000)

    # Prepare features
    sklearn_features = prepare_sklearn_features(test_data, sklearn_model)
    onnx_features = prepare_onnx_features(test_data)

    print(f"Test data shape: {sklearn_features.shape}")
    print(f"Feature names: {list(sklearn_model.feature_names_in_)}\n")

    # Verify prediction consistency
    consistency = verify_predictions(
        sklearn_model, sklearn_label_encoder, onnx_session, sklearn_features
    )
    print()

    # Benchmark sklearn
    sklearn_results = benchmark_sklearn(
        sklearn_model, sklearn_label_encoder, sklearn_features
    )

    # Benchmark ONNX
    onnx_results = benchmark_onnx(onnx_session, onnx_label_encoder, onnx_features)

    # Print results
    print("=== Benchmark Results ===")
    print(f"Sklearn:")
    print(f"  Total time: {sklearn_results['total_time']:.3f}s")
    print(f"  Average time per run: {sklearn_results['avg_time']:.3f}s")
    print(f"  Predictions per second: {sklearn_results['predictions_per_second']:.0f}")
    print()

    print(f"ONNX:")
    print(f"  Total time: {onnx_results['total_time']:.3f}s")
    print(f"  Average time per run: {onnx_results['avg_time']:.3f}s")
    print(f"  Predictions per second: {onnx_results['predictions_per_second']:.0f}")
    print()

    # Calculate speedup
    speedup = (
        sklearn_results["predictions_per_second"]
        / onnx_results["predictions_per_second"]
    )
    print(f"Performance Comparison:")
    print(f"  Speedup: {speedup:.2f}x faster")
    print(
        f"  Time reduction: {(1 - onnx_results['avg_time']/sklearn_results['avg_time'])*100:.1f}%"
    )
    print(f"  Prediction consistency: {consistency:.1f}%")

    # Evaluate success criteria
    print("\n=== Success Criteria ===")
    if speedup >= 2.0:
        print(f"✅ Speedup: {speedup:.2f}x (≥2x required)")
    else:
        print(f"❌ Speedup: {speedup:.2f}x (≥2x required)")

    if consistency >= 95:
        print(f"✅ Consistency: {consistency:.1f}% (≥95% required)")
    else:
        print(f"❌ Consistency: {consistency:.1f}% (≥95% required)")

    if speedup >= 2.0 and consistency >= 95:
        print("\n🎉 Benchmark PASSED: ONNX conversion successful!")
        return True
    else:
        print("\n⚠️  Benchmark FAILED: Criteria not met")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
