"""
Convert SBERT model to ONNX with int8 quantization.

Usage:
    python scripts/convert_model_to_onnx.py --model-path ./models/vietnamese-sbert
    python scripts/convert_model_to_onnx.py --model-path ./models/vietnamese-sbert --test

Requirements:
    - optimum[onnxruntime]
    - sentence-transformers
    - transformers
"""
import argparse
import os
from pathlib import Path
from typing import List

import numpy as np
import torch
from optimum.onnxruntime import ORTModelForFeatureExtraction, ORTQuantizer
from optimum.onnxruntime.configuration import AutoQuantizationConfig
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim
from transformers import AutoTokenizer


def convert_to_onnx(model_path: str, output_path: str) -> None:
    """
    Convert SentenceTransformer to ONNX format with int8 quantization.

    Args:
        model_path: Path to source PyTorch model
        output_path: Path to save ONNX model

    Raises:
        Exception: If conversion fails
    """
    import os
    import shutil
    import tempfile

    print(f"[1/3] Loading PyTorch model from {model_path}")

    # Create output directory
    os.makedirs(output_path, exist_ok=True)

    # Use a persistent temporary directory for conversion
    temp_dir = tempfile.mkdtemp(prefix="onnx_conversion_")

    try:
        # Export to ONNX (keep opset version 18 as suggested by PyTorch)
        print(f"[2/3] Exporting model to ONNX format...")
        ort_model = ORTModelForFeatureExtraction.from_pretrained(
            model_path,
            export=True,
            provider="CPUExecutionProvider",
            cache_dir=temp_dir  # Use persistent temp dir
        )

        # Save ONNX model to final location
        ort_model.save_pretrained(output_path)
        print(f"✅ ONNX model saved to {output_path}")

        # Apply int8 dynamic quantization
        print(f"[3/3] Applying int8 dynamic quantization...")
        try:
            quantizer = ORTQuantizer.from_pretrained(output_path)

            # Use dynamic quantization (works on all hardware)
            qconfig = AutoQuantizationConfig.avx512_vnni(is_static=False)

            quantizer.quantize(save_dir=output_path, quantization_config=qconfig)
            print(f"✅ Quantized model saved to {output_path}")
        except Exception as e:
            print(f"⚠️  Quantization failed: {e}")
            print(f"✅ ONNX model saved without quantization (still provides speedup)")
    finally:
        # Clean up temp directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


def benchmark_accuracy(
    pytorch_path: str, onnx_path: str, test_questions: List[str]
) -> bool:
    """
    Compare PyTorch vs ONNX embeddings for accuracy validation.

    Args:
        pytorch_path: Path to PyTorch model
        onnx_path: Path to ONNX model
        test_questions: List of Vietnamese test questions

    Returns:
        True if average similarity >0.99, False otherwise
    """
    print(f"\n[Benchmark] Comparing PyTorch vs ONNX embeddings...")

    # Load models
    pytorch_model = SentenceTransformer(pytorch_path)
    onnx_model = ORTModelForFeatureExtraction.from_pretrained(onnx_path)
    tokenizer = AutoTokenizer.from_pretrained(onnx_path)

    # Generate embeddings
    pytorch_emb = pytorch_model.encode(test_questions, convert_to_tensor=True)

    # ONNX embedding (requires tokenization + mean pooling)
    inputs = tokenizer(
        test_questions, return_tensors="pt", padding=True, truncation=True
    )
    with torch.no_grad():
        onnx_outputs = onnx_model(**inputs)

    # Mean pooling
    onnx_emb = onnx_outputs.last_hidden_state.mean(dim=1)

    # Compute cosine similarity
    similarities = [
        cos_sim(pytorch_emb[i], onnx_emb[i]).item() for i in range(len(test_questions))
    ]

    avg_similarity = np.mean(similarities)
    min_similarity = min(similarities)

    print(f"  Average similarity: {avg_similarity:.4f}")
    print(f"  Min similarity: {min_similarity:.4f}")
    print(f"  Max similarity: {max(similarities):.4f}")

    if avg_similarity < 0.99:
        print(f"  ❌ WARNING: Embeddings differ significantly (avg < 0.99)!")
        return False

    print(f"  ✅ Embeddings match (avg >= 0.99)")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Convert SentenceTransformer to ONNX with int8 quantization"
    )
    parser.add_argument(
        "--model-path",
        required=True,
        help="Path to source PyTorch model directory",
    )
    parser.add_argument(
        "--output-path",
        default=None,
        help="Path to save ONNX model (default: <model-path>_onnx)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run accuracy benchmark after conversion",
    )
    args = parser.parse_args()

    # Set output path
    output = args.output_path or f"{args.model_path}_onnx"

    # Validate model path
    if not os.path.exists(args.model_path):
        print(f"❌ Error: Model path not found: {args.model_path}")
        exit(1)

    # Convert to ONNX
    try:
        convert_to_onnx(args.model_path, output)
        print(f"\n✅ Conversion successful!")
    except Exception as e:
        print(f"\n❌ Conversion failed: {e}")
        exit(1)

    # Run accuracy benchmark
    if args.test:
        test_questions = [
            "Làm thế nào để giảm cân hiệu quả?",
            "Triệu chứng của tiểu đường là gì?",
            "Chế độ ăn cho người huyết áp cao",
            "Cách phòng ngừa bệnh tim mạch",
            "Tác dụng của vitamin C với sức khỏe",
        ]

        success = benchmark_accuracy(args.model_path, output, test_questions)
        if not success:
            print(
                f"\n⚠️  Accuracy test failed. Review embeddings before deployment."
            )
            exit(1)

        print(f"\n✅ All tests passed!")


if __name__ == "__main__":
    main()
