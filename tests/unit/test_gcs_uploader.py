"""
Tests for the GCS uploader utility.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
from app.utils.gcs_uploader import GCSUploader
from google.api_core.exceptions import GoogleAPIError


@pytest.mark.unit
@pytest.mark.service
class TestGCSUploader:
    """Tests for GCSUploader."""

    @pytest.fixture
    def uploader(self):
        """Create GCS uploader instance."""
        return GCSUploader(bucket_name="test-bucket", project_id="test-project")

    @pytest.fixture
    def mock_storage_client(self):
        """Mock Google Cloud Storage client."""
        with patch("app.utils.gcs_uploader.storage.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            yield mock_client_class

    @pytest.fixture
    def mock_bucket(self):
        """Mock GCS bucket."""
        bucket = MagicMock()
        bucket.name = "test-bucket"
        return bucket

    @pytest.fixture
    def mock_blob(self):
        """Mock GCS blob."""
        blob = MagicMock()
        blob.public_url = "https://storage.googleapis.com/test-bucket/uuid123.jpg"
        return blob

    def test_init_with_project_id(self):
        """Test initializing uploader with project ID."""
        uploader = GCSUploader(bucket_name="test-bucket", project_id="test-project")
        assert uploader.bucket_name == "test-bucket"
        assert uploader.project_id == "test-project"
        assert uploader._client is None
        assert uploader._bucket is None

    def test_init_without_project_id(self):
        """Test initializing uploader without project ID."""
        uploader = GCSUploader(bucket_name="test-bucket")
        assert uploader.bucket_name == "test-bucket"
        assert uploader.project_id is None

    def test_get_client_with_project_id(self, uploader, mock_storage_client):
        """Test getting GCS client with project ID."""
        # Act
        client = uploader._get_client()

        # Assert
        assert client == mock_storage_client.return_value
        mock_storage_client.assert_called_once_with(project="test-project")
        assert uploader._client == mock_storage_client.return_value

    def test_get_client_without_project_id(self, uploader, mock_storage_client):
        """Test getting GCS client without project ID."""
        # Arrange
        uploader.project_id = None

        # Act
        client = uploader._get_client()

        # Assert
        assert client == mock_storage_client.return_value
        mock_storage_client.assert_called_once_with()
        assert uploader._client == mock_storage_client.return_value

    def test_get_client_cached(self, uploader, mock_storage_client):
        """Test that client is cached after first call."""
        # Act
        client1 = uploader._get_client()
        client2 = uploader._get_client()

        # Assert
        assert client1 == client2 == mock_storage_client.return_value
        mock_storage_client.assert_called_once()

    def test_get_client_initialization_error(self, uploader):
        """Test error handling when client initialization fails."""
        # Arrange
        with patch(
            "app.utils.gcs_uploader.storage.Client", side_effect=Exception("Auth error")
        ):
            # Act & Assert
            with pytest.raises(Exception, match="Auth error"):
                uploader._get_client()

    def test_get_bucket_success(self, uploader, mock_storage_client, mock_bucket):
        """Test getting bucket reference successfully."""
        # Arrange
        uploader._client = mock_storage_client
        mock_storage_client.bucket.return_value = mock_bucket

        # Act
        bucket = uploader._get_bucket()

        # Assert
        assert bucket == mock_bucket
        mock_storage_client.bucket.assert_called_once_with("test-bucket")
        assert uploader._bucket == mock_bucket

    def test_get_bucket_cached(self, uploader, mock_bucket):
        """Test that bucket is cached after first call."""
        # Arrange
        uploader._bucket = mock_bucket

        # Act
        bucket = uploader._get_bucket()

        # Assert
        assert bucket == mock_bucket

    def test_get_bucket_error(self, uploader, mock_storage_client):
        """Test error handling when bucket access fails."""
        # Arrange
        uploader._client = mock_storage_client
        mock_storage_client.bucket.side_effect = Exception("Bucket not found")

        # Act & Assert
        with pytest.raises(Exception, match="Bucket not found"):
            uploader._get_bucket()

    def test_upload_file_success(self, uploader, mock_bucket, mock_blob):
        """Test successful file upload."""
        # Arrange
        uploader._bucket = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.public_url = "https://storage.googleapis.com/test-bucket/uuid123.jpg"

        file_content = b"test file content"
        file_name = "test.jpg"
        folder = "uploads"
        content_type = "image/jpeg"

        # Act
        result = uploader.upload_file(
            file_content, file_name, folder=folder, content_type=content_type
        )

        # Assert
        assert result == "https://storage.googleapis.com/test-bucket/uuid123.jpg"
        mock_bucket.blob.assert_called_once()

        # Verify blob path includes folder
        call_args = mock_bucket.blob.call_args[0]
        assert call_args[0].startswith("uploads/")
        assert call_args[0].endswith(".jpg")

        # Verify blob upload was called
        mock_blob.upload_from_string.assert_called_once_with(
            file_content, content_type=content_type
        )

    def test_upload_file_without_folder(self, uploader, mock_bucket, mock_blob):
        """Test uploading file without specifying folder."""
        # Arrange
        uploader._bucket = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.public_url = "https://storage.googleapis.com/test-bucket/uuid123.txt"

        file_content = b"test file content"
        file_name = "test.txt"

        # Act
        result = uploader.upload_file(file_content, file_name)

        # Assert
        assert result == "https://storage.googleapis.com/test-bucket/uuid123.txt"
        mock_bucket.blob.assert_called_once()

        # Verify blob path doesn't include folder
        call_args = mock_bucket.blob.call_args[0]
        assert "/" not in call_args[0]
        assert call_args[0].endswith(".txt")

    def test_upload_file_with_content_type_detection(
        self, uploader, mock_bucket, mock_blob
    ):
        """Test uploading file without explicit content type."""
        # Arrange
        uploader._bucket = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.public_url = "https://storage.googleapis.com/test-bucket/uuid123.png"

        file_content = b"test file content"
        file_name = "test.png"

        # Act
        result = uploader.upload_file(file_content, file_name, content_type=None)

        # Assert
        assert result == "https://storage.googleapis.com/test-bucket/uuid123.png"
        mock_blob.upload_from_string.assert_called_once_with(
            file_content, content_type=None
        )

    def test_upload_file_without_make_public(self, uploader, mock_bucket, mock_blob):
        """Test uploading file without making it public."""
        # Arrange
        uploader._bucket = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.public_url = "https://storage.googleapis.com/test-bucket/uuid123.doc"

        file_content = b"test file content"
        file_name = "test.doc"

        # Act
        result = uploader.upload_file(file_content, file_name, make_public=False)

        # Assert
        assert result == "https://storage.googleapis.com/test-bucket/uuid123.doc"
        # Note: The current implementation always returns public_url regardless of make_public

    def test_upload_file_unique_filename_generation(
        self, uploader, mock_bucket, mock_blob
    ):
        """Test that unique filenames are generated to avoid collisions."""
        # Arrange
        uploader._bucket = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        file_content = b"test file content"
        file_name = "duplicate.jpg"

        # Act
        result1 = uploader.upload_file(file_content, file_name)
        result2 = uploader.upload_file(file_content, file_name)

        # Assert
        assert (
            result1 == result2
        )  # Same mock URL, but different blob paths should be called

        # Verify different blob paths were called
        call_args1 = mock_bucket.blob.call_args_list[0][0][0]
        call_args2 = mock_bucket.blob.call_args_list[1][0][0]
        assert call_args1 != call_args2
        assert call_args1.endswith(".jpg")
        assert call_args2.endswith(".jpg")

    def test_upload_file_folder_path_normalization(
        self, uploader, mock_bucket, mock_blob
    ):
        """Test folder path normalization (removing leading/trailing slashes)."""
        # Arrange
        uploader._bucket = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        file_content = b"test file content"
        file_name = "test.jpg"

        # Test various folder formats
        test_cases = [
            ("uploads", "uploads/"),
            ("/uploads", "uploads/"),
            ("uploads/", "uploads/"),
            ("/uploads/", "uploads/"),
            ("deep/nested/path", "deep/nested/path/"),
            ("/deep/nested/path/", "deep/nested/path/"),
        ]

        for folder_input, expected_prefix in test_cases:
            mock_bucket.blob.reset_mock()

            # Act
            uploader.upload_file(file_content, file_name, folder=folder_input)

            # Assert
            call_args = mock_bucket.blob.call_args[0][0]
            assert call_args.startswith(expected_prefix)
            assert not call_args.startswith("//")  # No double slashes

    def test_upload_file_gcs_api_error(self, uploader, mock_bucket):
        """Test handling of GCS API errors during upload."""
        # Arrange
        uploader._bucket = mock_bucket
        mock_blob = MagicMock()
        mock_blob.upload_from_string.side_effect = GoogleAPIError("Permission denied")
        mock_bucket.blob.return_value = mock_blob

        file_content = b"test file content"
        file_name = "test.jpg"

        # Act & Assert
        with pytest.raises(
            Exception, match="Failed to upload file to GCS: Permission denied"
        ):
            uploader.upload_file(file_content, file_name)

    def test_upload_file_general_error(self, uploader, mock_bucket):
        """Test handling of general errors during upload."""
        # Arrange
        uploader._bucket = mock_bucket
        mock_bucket.blob.side_effect = Exception("Connection failed")

        file_content = b"test file content"
        file_name = "test.jpg"

        # Act & Assert
        with pytest.raises(Exception, match="Failed to upload file: Connection failed"):
            uploader.upload_file(file_content, file_name)

    @patch("app.utils.gcs_uploader.uuid.uuid4")
    def test_upload_file_uuid_generation(
        self, mock_uuid, uploader, mock_bucket, mock_blob
    ):
        """Test that UUID is properly generated for unique filenames."""
        # Arrange
        uploader._bucket = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_uuid.return_value.hex = "test-uuid-123"

        file_content = b"test file content"
        file_name = "test.jpg"

        # Act
        uploader.upload_file(file_content, file_name, folder="uploads")

        # Assert
        mock_uuid.assert_called_once()
        call_args = mock_bucket.blob.call_args[0][0]
        assert "test-uuid-123" in call_args

    def test_upload_file_different_extensions(self, uploader, mock_bucket, mock_blob):
        """Test uploading files with different extensions."""
        # Arrange
        uploader._bucket = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        test_files = [
            ("image.jpg", b"image content"),
            ("document.pdf", b"pdf content"),
            ("archive.zip", b"zip content"),
            ("no_extension", b"no extension content"),
            ("multiple.dots.name.txt", b"text content"),
        ]

        for file_name, content in test_files:
            mock_bucket.blob.reset_mock()

            # Act
            uploader.upload_file(content, file_name)

            # Assert
            call_args = mock_bucket.blob.call_args[0][0]
            expected_extension = Path(file_name).suffix
            if expected_extension:
                assert call_args.endswith(expected_extension)
            mock_blob.upload_from_string.assert_called_once_with(
                content, content_type=None
            )

    def test_upload_file_empty_content(self, uploader, mock_bucket, mock_blob):
        """Test uploading file with empty content."""
        # Arrange
        uploader._bucket = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        file_content = b""
        file_name = "empty.txt"

        # Act
        result = uploader.upload_file(file_content, file_name)

        # Assert
        assert result == "https://storage.googleapis.com/test-bucket/uuid123.txt"
        mock_blob.upload_from_string.assert_called_once_with(b"", content_type=None)

    def test_upload_file_large_content(self, uploader, mock_bucket, mock_blob):
        """Test uploading file with large content."""
        # Arrange
        uploader._bucket = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Create 1MB of content
        file_content = b"x" * (1024 * 1024)
        file_name = "large.bin"

        # Act
        result = uploader.upload_file(
            file_content, file_name, content_type="application/octet-stream"
        )

        # Assert
        assert result == "https://storage.googleapis.com/test-bucket/uuid123.bin"
        mock_blob.upload_from_string.assert_called_once_with(
            file_content, content_type="application/octet-stream"
        )

    def test_upload_file_special_characters_in_name(
        self, uploader, mock_bucket, mock_blob
    ):
        """Test uploading file with special characters in name."""
        # Arrange
        uploader._bucket = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        file_content = b"test content"
        file_name = "file with spaces & symbols!@#$%.jpg"

        # Act
        result = uploader.upload_file(file_content, file_name)

        # Assert
        assert result == "https://storage.googleapis.com/test-bucket/uuid123.jpg"
        # The original file name with extension should be preserved
        mock_bucket.blob.assert_called_once()
        call_args = mock_bucket.blob.call_args[0][0]
        assert call_args.endswith(".jpg")  # Extension preserved
