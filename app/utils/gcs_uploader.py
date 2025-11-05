"""
Google Cloud Storage upload utility for file uploads.
"""

import logging
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime

from google.cloud import storage
from google.api_core.exceptions import GoogleAPIError

logger = logging.getLogger(__name__)


class GCSUploader:
    """Utility for uploading files to Google Cloud Storage."""

    def __init__(
        self,
        bucket_name: str,
        project_id: Optional[str] = None,
    ):
        """
        Initialize GCS uploader.

        Args:
            bucket_name: Name of the GCS bucket
            project_id: GCP project ID (optional, uses default credentials if not provided)
        """
        self.bucket_name = bucket_name
        self.project_id = project_id
        self._client = None
        self._bucket = None

    def _get_client(self) -> storage.Client:
        """Get or create GCS client."""
        if self._client is None:
            try:
                if self.project_id:
                    self._client = storage.Client(project=self.project_id)
                else:
                    self._client = storage.Client()
                logger.info("GCS client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize GCS client: {e}")
                raise
        return self._client

    def _get_bucket(self) -> storage.Bucket:
        """Get or create bucket reference."""
        if self._bucket is None:
            try:
                client = self._get_client()
                self._bucket = client.bucket(self.bucket_name)
                logger.info(f"Connected to GCS bucket: {self.bucket_name}")
            except Exception as e:
                logger.error(f"Failed to access bucket '{self.bucket_name}': {e}")
                raise
        return self._bucket

    def upload_file(
        self,
        file_content: bytes,
        file_name: str,
        folder: Optional[str] = None,
        content_type: Optional[str] = None,
        make_public: bool = True,
    ) -> str:
        """
        Upload a file to GCS and return the public URL.

        Args:
            file_content: File content as bytes
            file_name: Original file name
            folder: Optional folder path in the bucket (e.g., 'avatars', 'profile-pictures')
            content_type: MIME type of the file (e.g., 'image/jpeg')
            make_public: Whether to make the file publicly accessible

        Returns:
            Public URL of the uploaded file

        Raises:
            Exception: If upload fails
        """
        try:
            bucket = self._get_bucket()

            # Generate unique filename to avoid collisions
            file_extension = Path(file_name).suffix
            unique_filename = f"{uuid.uuid4()}{file_extension}"

            # Build blob path
            if folder:
                # Normalize folder path (remove leading/trailing slashes)
                folder = folder.strip("/")
                blob_path = f"{folder}/{unique_filename}"
            else:
                blob_path = unique_filename

            # Create blob and upload
            blob = bucket.blob(blob_path)
            blob.upload_from_string(
                file_content,
                content_type=content_type,
            )

            public_url = blob.public_url

            logger.info(f"Successfully uploaded file to {blob_path}, URL: {public_url}")
            return public_url

        except GoogleAPIError as e:
            logger.error(f"GCS API error uploading file {file_name}: {e}")
            raise Exception(f"Failed to upload file to GCS: {str(e)}")
        except Exception as e:
            logger.error(f"Error uploading file {file_name}: {e}")
            raise Exception(f"Failed to upload file: {str(e)}")

