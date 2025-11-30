"""Simple benchmark ONNX vs sklearn prediction performance."""
import time
import joblib
import numpy as np
import onnxruntime as ort
import json

def main():
    print("=== ONNX vs Sklearn Benchmark ===")

    # Load sklearn models
    print("Loading sklearn models...")
    sklearn_model = joblib.load('obesity_classifier_final.pkl')
    label_encoder = joblib.load('label_encoder.pkl')

    # Load ONNX models
    print("Loading ONNX models...")
    onnx_session = ort.InferenceSession('models/obesity_classifier.onnx', providers=['CPUExecutionProvider'])

    with open('models/label_encoder.json', 'r') as f:
        onnx_label_encoder = json.load(f)

    # Generate test data
    print("Generating test data...")
    test_features = np.random.rand(1000, 20).astype(np.float32)

    # Benchmark sklearn
    print("Benchmarking sklearn...")
    sklearn_times = []
    for _ in range(10):
        start = time.time()
        sklearn_model.predict(test_features)
        end = time.time()
        sklearn_times.append(end - start)

    sklearn_avg = sum(sklearn_times) / len(sklearn_times)
    sklearn_per_sec = len(test_features) / sklearn_avg

    # Benchmark ONNX
    print("Benchmarking ONNX...")
    input_name = onnx_session.get_inputs()[0].name
    output_name = onnx_session.get_outputs()[0].name

    onnx_times = []
    for _ in range(10):
        start = time.time()
        onnx_session.run([output_name], {input_name: test_features})
        end = time.time()
        onnx_times.append(end - start)

    onnx_avg = sum(onnx_times) / len(onnx_times)
    onnx_per_sec = len(test_features) / onnx_avg

    # Calculate speedup
    speedup = sklearn_per_sec / onnx_per_sec

    print(f"\nResults:")
    print(f"Sklearn: {sklearn_avg:.3f}s ({sklearn_per_sec:.0f} predictions/sec)")
    print(f"ONNX:    {onnx_avg:.3f}s ({onnx_per_sec:.0f} predictions/sec)")
    print(f"Speedup:  {speedup:.2f}x faster")

    if speedup >= 2.0:
        print("✅ Benchmark PASSED: ONNX is at least 2x faster")
        return True
    else:
        print(f"❌ Benchmark FAILED: ONNX is only {speedup:.2f}x faster (need ≥2x)")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)