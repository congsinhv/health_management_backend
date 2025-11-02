# Vietnamese SBERT Model

This directory should contain the Vietnamese Sentence-BERT model files used for semantic search in the Q&A service.

## Model Information

- **Model Name**: keepitreal/vietnamese-sbert
- **Model Type**: Sentence Transformer (SBERT)
- **Purpose**: Semantic similarity search for Vietnamese health-related questions
- **Source**: Hugging Face Model Hub

## Storage Location

**Important**: Model files are NOT stored in git due to their large size. Instead, they are:
1. Stored in Google Cloud Storage (GCS)
2. Automatically downloaded at runtime when the service starts
3. Cached locally in this directory

## Required Files

The model requires the following files (automatically downloaded):
- `config.json` - Model configuration
- `modules.json` - Module configuration
- `sentence_bert_config.json` - Sentence-BERT specific configuration
- `config_sentence_transformers.json` - Sentence transformers configuration
- `model.safetensors` - Model weights
- `tokenizer_config.json` - Tokenizer configuration
- `vocab.txt` - Vocabulary file
- `special_tokens_map.json` - Special tokens mapping
- `1_Pooling/config.json` - Pooling layer configuration
- And other supporting files

## Manual Download from GCS

If you need to manually download the model files from Google Cloud Storage:

### Using gsutil

```bash
# Download all model files
gsutil -m cp -r gs://vhealth-dev-models/models/vietnamese-sbert/* ./models/vietnamese-sbert/

# Or for production
gsutil -m cp -r gs://vhealth-prod-models/models/vietnamese-sbert/* ./models/vietnamese-sbert/
```

### Using Google Cloud Console

1. Navigate to: https://console.cloud.google.com/storage/browser
2. Select the appropriate bucket: `vhealth-{environment}-models`
3. Browse to `models/vietnamese-sbert/`
4. Download all files to this directory

## Manual Download from Hugging Face

Alternatively, the model can be downloaded directly from Hugging Face:

```python
from sentence_transformers import SentenceTransformer

# Download and save model
model = SentenceTransformer("keepitreal/vietnamese-sbert")
model.save("./models/vietnamese-sbert")
```

## Uploading to GCS

If you need to upload a new version of the model to GCS:

```bash
# Upload model files to dev bucket
gsutil -m cp -r ./models/vietnamese-sbert/* gs://vhealth-dev-models/models/vietnamese-sbert/

# Upload model files to prod bucket
gsutil -m cp -r ./models/vietnamese-sbert/* gs://vhealth-prod-models/models/vietnamese-sbert/
```

## Automatic Download

When the application starts with `MODEL_AUTO_DOWNLOAD=true` (default), the service will:
1. Check if model files exist locally
2. If missing or incomplete, download from GCS
3. If GCS download fails, fallback to Hugging Face
4. Cache the model locally for future use

## Configuration

Model download behavior can be configured via environment variables:

```bash
# Enable/disable automatic download
MODEL_AUTO_DOWNLOAD=true

# GCS bucket name (default: vhealth-{environment}-models)
GCP_MODEL_BUCKET=vhealth-dev-models

# Path within bucket
GCP_MODEL_BLOB_PATH=models/vietnamese-sbert/

# Download timeout (seconds)
MODEL_DOWNLOAD_TIMEOUT=600
```

## Troubleshooting

### Model Not Found
If you see "Model not found" errors:
1. Check that GCS bucket is configured: `GCP_MODEL_BUCKET`
2. Verify service account has Storage Object Viewer permissions
3. Ensure model files exist in the GCS bucket
4. Check network connectivity to GCS

### Incomplete Model
If the model downloads but doesn't work:
1. Delete all files in this directory
2. Restart the service to trigger fresh download
3. Check logs for specific missing files

### Manual Recovery
To manually reset the model cache:
```bash
# Remove all cached files except README
find ./models/vietnamese-sbert -type f ! -name 'README.md' -delete
```

## Model Version

Current model version: **v1.0**
Last updated: 2024-11-02

## License

This model is subject to the licensing terms of the original model on Hugging Face.
Please refer to: https://huggingface.co/keepitreal/vietnamese-sbert
