"""
Storage utility module for managing file access from local filesystem or GCS.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Union
from google.cloud import storage
from google.api_core import exceptions as gcp_exceptions

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Manages file storage operations for both local filesystem and Google Cloud Storage.
    Supports automatic downloading and caching of GCS files to local storage.
    """

    def __init__(
        self,
        storage_type: str = "local",
        gcs_bucket: Optional[str] = None,
        local_cache_dir: str = "/tmp/qa_cache",
    ):
        """
        Initialize the storage manager.

        Args:
            storage_type: Either 'local' or 'gcs'
            gcs_bucket: GCS bucket name (required if storage_type='gcs')
            local_cache_dir: Local directory for caching GCS files
        """
        self.storage_type = storage_type.lower()
        self.gcs_bucket = gcs_bucket
        self.local_cache_dir = Path(local_cache_dir)

        if self.storage_type not in ["local", "gcs"]:
            raise ValueError(
                f"Invalid storage_type: {storage_type}. Must be 'local' or 'gcs'"
            )

        if self.storage_type == "gcs":
            if not gcs_bucket:
                raise ValueError("gcs_bucket is required when storage_type='gcs'")

            try:
                self.gcs_client = storage.Client()
                self.bucket = self.gcs_client.bucket(gcs_bucket)
                logger.info(f"Initialized GCS client with bucket: {gcs_bucket}")
            except Exception as e:
                logger.error(f"Failed to initialize GCS client: {e}")
                raise
        else:
            self.gcs_client = None
            self.bucket = None
            logger.info("Initialized local storage manager")

        # Create cache directory if using GCS
        if self.storage_type == "gcs":
            self.local_cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Cache directory created at: {self.local_cache_dir}")

    def get_file_path(self, remote_path: str) -> str:
        """
        Get the local file path for a given file.
        If storage_type is 'gcs', downloads the file to local cache if not already present.

        Args:
            remote_path: Path to the file (local path or GCS blob path)

        Returns:
            Local file path

        Raises:
            FileNotFoundError: If file doesn't exist
            Exception: For GCS download errors
        """
        if self.storage_type == "local":
            # Return local path directly
            file_path = Path(remote_path)
            if not file_path.exists():
                raise FileNotFoundError(f"Local file not found: {remote_path}")
            return str(file_path.resolve())

        # GCS storage - download to cache if needed
        return self._download_from_gcs(remote_path)

    def get_directory_path(self, remote_path: str) -> str:
        """
        Get the local directory path for a given directory.
        If storage_type is 'gcs', downloads all files in the directory to local cache.

        Args:
            remote_path: Path to the directory (local path or GCS prefix)

        Returns:
            Local directory path

        Raises:
            FileNotFoundError: If directory doesn't exist
            Exception: For GCS download errors
        """
        if self.storage_type == "local":
            # Return local directory directly
            dir_path = Path(remote_path)
            if not dir_path.exists():
                raise FileNotFoundError(f"Local directory not found: {remote_path}")
            if not dir_path.is_dir():
                raise NotADirectoryError(f"Path is not a directory: {remote_path}")
            return str(dir_path.resolve())

        # GCS storage - download all files in prefix to cache
        return self._download_directory_from_gcs(remote_path)

    def _download_from_gcs(self, blob_path: str) -> str:
        """
        Download a single file from GCS to local cache.

        Args:
            blob_path: Path to the blob in GCS

        Returns:
            Local file path

        Raises:
            FileNotFoundError: If blob doesn't exist in GCS
            Exception: For download errors
        """
        try:
            # Create local cache path
            local_path = self.local_cache_dir / blob_path
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Check if file is already cached
            if local_path.exists():
                logger.info(f"File already cached: {local_path}")
                return str(local_path)

            # Download from GCS
            blob = self.bucket.blob(blob_path)

            if not blob.exists():
                raise FileNotFoundError(
                    f"GCS blob not found: gs://{self.gcs_bucket}/{blob_path}"
                )

            logger.info(f"Downloading from GCS: gs://{self.gcs_bucket}/{blob_path}")
            blob.download_to_filename(str(local_path))
            logger.info(f"Downloaded to: {local_path}")

            return str(local_path)

        except gcp_exceptions.NotFound:
            raise FileNotFoundError(
                f"GCS blob not found: gs://{self.gcs_bucket}/{blob_path}"
            )
        except Exception as e:
            logger.error(f"Error downloading from GCS: {e}")
            raise

    def _download_directory_from_gcs(self, prefix: str) -> str:
        """
        Download all files with a given prefix from GCS to local cache.

        Args:
            prefix: GCS prefix (directory path)

        Returns:
            Local directory path

        Raises:
            FileNotFoundError: If no files found with prefix
            Exception: For download errors
        """
        try:
            # Create local cache directory
            local_dir = self.local_cache_dir / prefix
            local_dir.mkdir(parents=True, exist_ok=True)

            # List all blobs with the prefix
            blobs = list(self.bucket.list_blobs(prefix=prefix))

            if not blobs:
                raise FileNotFoundError(
                    f"No files found in GCS with prefix: gs://{self.gcs_bucket}/{prefix}"
                )

            logger.info(f"Downloading {len(blobs)} files from GCS prefix: {prefix}")

            # Download each blob
            for blob in blobs:
                # Skip directory markers (blobs ending with /)
                if blob.name.endswith("/"):
                    continue

                # Create local path maintaining directory structure
                relative_path = blob.name[len(prefix) :].lstrip("/")
                local_file = local_dir / relative_path
                local_file.parent.mkdir(parents=True, exist_ok=True)

                # Download if not already cached
                if not local_file.exists():
                    logger.info(f"Downloading: gs://{self.gcs_bucket}/{blob.name}")
                    blob.download_to_filename(str(local_file))
                else:
                    logger.info(f"Already cached: {local_file}")

            logger.info(f"All files downloaded to: {local_dir}")
            return str(local_dir)

        except Exception as e:
            logger.error(f"Error downloading directory from GCS: {e}")
            raise

    def file_exists(self, path: str) -> bool:
        """
        Check if a file exists in storage.

        Args:
            path: Path to the file

        Returns:
            True if file exists, False otherwise
        """
        if self.storage_type == "local":
            return Path(path).exists()
        else:
            blob = self.bucket.blob(path)
            return blob.exists()

    def clear_cache(self):
        """Clear the local cache directory (only for GCS storage)."""
        if self.storage_type == "gcs" and self.local_cache_dir.exists():
            import shutil

            shutil.rmtree(self.local_cache_dir)
            self.local_cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Cache cleared: {self.local_cache_dir}")
