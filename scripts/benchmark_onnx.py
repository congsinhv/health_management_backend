"""
Benchmark ONNX vs PyTorch inference speed and memory usage.

Usage:
    python scripts/benchmark_onnx.py
    python scripts/benchmark_onnx.py --iterations 50

Requirements:
    - app.services.qa_service (QAService)
    - app.config (settings)
"""
import argparse
import time
import tracemalloc
from typing import Dict, List

from app.config import settings
from app.services.qa_service import QAService


def benchmark_inference(
    model_format: str, questions: List[str], iterations: int = 10
) -> Dict:
    """
    Measure inference time and memory usage for specified model format.

    Args:
        model_format: "pytorch" or "onnx"
        questions: List of Vietnamese test questions
        iterations: Number of iterations per question

    Returns:
        Dict with benchmark metrics (load_time, avg_inference_ms, memory_peak_mb)
    """
    print(f"\n{'='*60}")
    print(f"Benchmarking {model_format.upper()} model")
    print(f"{'='*60}")

    # Configure settings
    config = settings.model_copy(deep=True)
    config.qa_model_format = model_format

    # Start memory tracking
    tracemalloc.start()

    # Load model (measure load time)
    print(f"Loading {model_format} model...")
    start_load = time.time()
    qa_service = QAService(config)
    load_time = time.time() - start_load
    print(f"  Load time: {load_time:.2f}s")

    # Warm-up (first inference is often slower)
    print(f"Warming up...")
    qa_service.model.encode(questions[0])

    # Benchmark inference
    print(f"Running benchmark ({iterations} iterations x {len(questions)} questions)...")
    start = time.time()
    for _ in range(iterations):
        for q in questions:
            qa_service.model.encode(q)

    total_time = time.time() - start
    avg_time_ms = (total_time / (iterations * len(questions))) * 1000

    # Memory snapshot
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    results = {
        "model_format": model_format,
        "load_time_s": round(load_time, 2),
        "avg_inference_ms": round(avg_time_ms, 2),
        "memory_current_mb": round(current / 1024 / 1024, 2),
        "memory_peak_mb": round(peak / 1024 / 1024, 2),
    }

    print(f"\nResults:")
    print(f"  Load time: {results['load_time_s']}s")
    print(f"  Avg inference: {results['avg_inference_ms']}ms")
    print(f"  Current memory: {results['memory_current_mb']}MB")
    print(f"  Peak memory: {results['memory_peak_mb']}MB")

    return results


def print_comparison(pytorch_results: Dict, onnx_results: Dict) -> None:
    """Print comparison summary between PyTorch and ONNX."""
    print(f"\n{'='*60}")
    print(f"COMPARISON SUMMARY")
    print(f"{'='*60}")

    speedup = pytorch_results["avg_inference_ms"] / onnx_results["avg_inference_ms"]
    memory_reduction = (
        pytorch_results["memory_peak_mb"] / onnx_results["memory_peak_mb"]
    )

    print(f"\nInference Speed:")
    print(f"  PyTorch: {pytorch_results['avg_inference_ms']}ms")
    print(f"  ONNX: {onnx_results['avg_inference_ms']}ms")
    print(f"  Speedup: {speedup:.2f}x")

    print(f"\nMemory Usage:")
    print(f"  PyTorch: {pytorch_results['memory_peak_mb']}MB")
    print(f"  ONNX: {onnx_results['memory_peak_mb']}MB")
    print(f"  Reduction: {memory_reduction:.2f}x")

    print(f"\nLoad Time:")
    print(f"  PyTorch: {pytorch_results['load_time_s']}s")
    print(f"  ONNX: {onnx_results['load_time_s']}s")
    print(f"  Difference: {pytorch_results['load_time_s'] - onnx_results['load_time_s']:.2f}s")

    # Success criteria check
    print(f"\nSuccess Criteria Check:")
    success_criteria = {
        "Inference speedup ≥2x": speedup >= 2.0,
        "Memory reduction ≥3x": memory_reduction >= 3.0,
        "Inference <25ms": onnx_results["avg_inference_ms"] < 25,
        "Memory <500MB": onnx_results["memory_peak_mb"] < 500,
    }

    for criterion, passed in success_criteria.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} {criterion}")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark ONNX vs PyTorch inference performance"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of iterations per question (default: 10)",
    )
    args = parser.parse_args()

    # Vietnamese test questions
    questions = [
        "Làm thế nào để giảm cân hiệu quả?",
        "Triệu chứng của tiểu đường là gì?",
        "Chế độ ăn cho người huyết áp cao",
    ]

    # Benchmark PyTorch
    pytorch_results = benchmark_inference("pytorch", questions, args.iterations)

    # Benchmark ONNX
    onnx_results = benchmark_inference("onnx", questions, args.iterations)

    # Print comparison
    print_comparison(pytorch_results, onnx_results)

    print(f"\n{'='*60}")
    print(f"Benchmark complete!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
