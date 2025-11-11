"""
Google Cloud Storage download utility for Q&A models and data files.
"""

import logging
import os
import time
from pathlib import Path
from typing import List, Optional, Tuple

from google.cloud import storage
from google.api_core import retry
from google.api_core.exceptions import GoogleAPIError, NotFound

logger = logging.getLogger(__name__)


class GCSDownloader:
    """Utility for downloading files from Google Cloud Storage with retry logic."""

    def __init__(
        self,
        bucket_name: str,
        project_id: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 600,
    ):
        """
        Initialize GCS downloader.

        Args:
            bucket_name: Name of the GCS bucket
            project_id: GCP project ID (optional, uses default credentials if not provided)
            max_retries: Maximum number of retry attempts for downloads
            timeout: Timeout in seconds for each download operation
        """
        self.bucket_name = bucket_name
        self.project_id = project_id
        self.max_retries = max_retries
        self.timeout = timeout
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

    def download_file(
        self, blob_path: str, local_path: str, force: bool = False
    ) -> bool:
        """
        Download a single file from GCS.

        Args:
            blob_path: Path to the file in GCS bucket
            local_path: Local path where file should be saved
            force: If True, download even if file already exists

        Returns:
            True if download successful, False otherwise
        """
        local_file = Path(local_path)

        # Skip if file already exists and force is False
        if local_file.exists() and not force:
            logger.info(f"File already exists: {local_path}")
            return True

        # Create parent directory if it doesn't exist
        local_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            bucket = self._get_bucket()
            blob = bucket.blob(blob_path)

            if not blob.exists():
                logger.error(f"Blob not found in GCS: {blob_path}")
                return False

            logger.info(f"Downloading {blob_path} to {local_path}...")

            # Download with retry logic
            retry_count = 0
            while retry_count < self.max_retries:
                try:
                    blob.download_to_filename(local_path, timeout=self.timeout)
                    logger.info(f"Successfully downloaded: {blob_path}")
                    return True
                except Exception as e:
                    retry_count += 1
                    if retry_count >= self.max_retries:
                        logger.error(
                            f"Failed to download {blob_path} after {self.max_retries} attempts: {e}"
                        )
                        raise
                    wait_time = 2**retry_count  # Exponential backoff
                    logger.warning(
                        f"Download attempt {retry_count} failed, retrying in {wait_time}s: {e}"
                    )
                    time.sleep(wait_time)

        except Exception as e:
            logger.error(f"Error downloading file {blob_path}: {e}")
            # Clean up partial download
            if local_file.exists():
                try:
                    local_file.unlink()
                except Exception as cleanup_error:
                    logger.warning(
                        f"Failed to clean up partial download: {cleanup_error}"
                    )
            return False

    def download_directory(
        self, blob_prefix: str, local_dir: str, force: bool = False
    ) -> Tuple[int, int]:
        """
        Download all files with a given prefix from GCS.

        Args:
            blob_prefix: Prefix path in GCS bucket (e.g., "models/vietnamese-sbert/")
            local_dir: Local directory where files should be saved
            force: If True, download even if files already exist

        Returns:
            Tuple of (successful_downloads, failed_downloads)
        """
        local_path = Path(local_dir)
        local_path.mkdir(parents=True, exist_ok=True)

        try:
            bucket = self._get_bucket()
            # Ensure prefix ends with /
            if not blob_prefix.endswith("/"):
                blob_prefix += "/"

            blobs = list(bucket.list_blobs(prefix=blob_prefix))

            if not blobs:
                logger.warning(f"No files found with prefix: {blob_prefix}")
                return (0, 0)

            logger.info(f"Found {len(blobs)} files to download")

            successful = 0
            failed = 0

            for blob in blobs:
                # Skip directory markers
                if blob.name.endswith("/"):
                    continue

                # Calculate relative path
                relative_path = blob.name[len(blob_prefix) :]
                if not relative_path:
                    continue

                local_file_path = local_path / relative_path

                if self.download_file(blob.name, str(local_file_path), force=force):
                    successful += 1
                else:
                    failed += 1

            logger.info(f"Download complete: {successful} successful, {failed} failed")
            return (successful, failed)

        except Exception as e:
            logger.error(f"Error downloading directory {blob_prefix}: {e}")
            return (0, 1)

    def validate_files_exist(self, required_files: List[str], local_dir: str) -> bool:
        """
        Validate that all required files exist in local directory.

        Args:
            required_files: List of relative file paths that must exist
            local_dir: Local directory to check

        Returns:
            True if all files exist, False otherwise
        """
        local_path = Path(local_dir)
        missing_files = []

        for file_path in required_files:
            full_path = local_path / file_path
            if not full_path.exists():
                missing_files.append(file_path)

        if missing_files:
            logger.warning(f"Missing files in {local_dir}: {missing_files}")
            return False

        logger.info(f"All required files present in {local_dir}")
        return True

    def check_blob_exists(self, blob_path: str) -> bool:
        """
        Check if a blob exists in GCS without downloading.

        Args:
            blob_path: Path to the blob in GCS bucket

        Returns:
            True if blob exists, False otherwise
        """
        try:
            bucket = self._get_bucket()
            blob = bucket.blob(blob_path)
            return blob.exists()
        except Exception as e:
            logger.error(f"Error checking if blob exists {blob_path}: {e}")
            return False
