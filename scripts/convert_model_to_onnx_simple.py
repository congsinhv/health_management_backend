"""
Simple ONNX conversion script using torch.onnx directly.

This bypasses optimum's export mechanism which has issues with external data files.
"""
import argparse
import os
from pathlib import Path

import torch
from transformers import AutoModel, AutoTokenizer


def convert_to_onnx_simple(model_path: str, output_path: str) -> None:
    """
    Convert Transformers model to ONNX using torch.onnx directly.

    Args:
        model_path: Path to source PyTorch model
        output_path: Path to save ONNX model
    """
    print(f"[1/2] Loading model from {model_path}")

    # Load model and tokenizer
    model = AutoModel.from_pretrained(model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path)

    # Set model to eval mode
    model.eval()

    # Create output directory
    os.makedirs(output_path, exist_ok=True)

    # Create dummy input
    dummy_text = "Sample text for ONNX export"
    inputs = tokenizer(dummy_text, return_tensors="pt", padding=True, truncation=True)

    # Export to ONNX
    onnx_path = os.path.join(output_path, "model.onnx")
    print(f"[2/2] Exporting to ONNX: {onnx_path}")

    with torch.no_grad():
        torch.onnx.export(
            model,
            (inputs["input_ids"], inputs["attention_mask"]),
            onnx_path,
            input_names=["input_ids", "attention_mask"],
            output_names=["last_hidden_state"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "sequence"},
                "attention_mask": {0: "batch", 1: "sequence"},
                "last_hidden_state": {0: "batch", 1: "sequence"},
            },
            opset_version=14,
            do_constant_folding=True,
            export_params=True,
        )

    # Copy tokenizer files
    tokenizer.save_pretrained(output_path)

    # Copy config
    model.config.save_pretrained(output_path)

    print(f"✅ ONNX model exported to {output_path}")
    print(f"   - model.onnx")
    print(f"   - tokenizer files")
    print(f"   - config.json")


def main():
    parser = argparse.ArgumentParser(description="Convert model to ONNX (simple method)")
    parser.add_argument("--model-path", required=True, help="Path to source model")
    parser.add_argument("--output-path", required=True, help="Path to save ONNX model")
    args = parser.parse_args()

    if not os.path.exists(args.model_path):
        print(f"❌ Model path not found: {args.model_path}")
        exit(1)

    try:
        convert_to_onnx_simple(args.model_path, args.output_path)
        print(f"\n✅ Conversion successful!")
        print(f"\nNext steps:")
        print(f"1. Test the model: python scripts/benchmark_onnx.py")
        print(f"2. Upload to GCS: gsutil -m cp -r {args.output_path}/* gs://bucket/path/")
    except Exception as e:
        print(f"\n❌ Conversion failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
