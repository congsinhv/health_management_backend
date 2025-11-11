import io
import pytest
from fastapi import status
from unittest.mock import MagicMock


@pytest.mark.integration
@pytest.mark.api
class TestUploadAPI:
    @pytest.fixture
    def app(self):
        # Use the real application with routers mounted
        from app.main import app as real_app

        return real_app

    @pytest.fixture
    def mock_uploader(self, app, monkeypatch):
        # Provide a synchronous mock uploader compatible with the endpoint
        uploader = MagicMock()
        uploader.upload_file.return_value = (
            "https://storage.googleapis.com/test-bucket/test-file.jpg"
        )
        uploader.delete_file.return_value = True
        uploader.get_signed_url.return_value = (
            "https://storage.googleapis.com/test-bucket/test-file.jpg?signed=true"
        )
        # Override FastAPI dependency directly so DI uses our mock
        from app.api.upload import get_gcs_uploader as dep_get_gcs_uploader

        app.dependency_overrides[dep_get_gcs_uploader] = lambda: uploader
        return uploader

    @pytest.fixture
    def authed_client(
        self,
        app,
        auth_headers,
        override_dependencies,
        override_authenticated_user,
        mock_uploader,
    ):
        from fastapi.testclient import TestClient

        client = TestClient(app)
        client.headers.update(auth_headers)
        return client

    @pytest.fixture
    def plain_client(self, app, override_dependencies, mock_uploader):
        from fastapi.testclient import TestClient

        return TestClient(app)

    def test_upload_image_success(self, authed_client, sample_file_upload):
        files = {
            "file": ("test.jpg", sample_file_upload.read(), "image/jpeg"),
        }
        data = {"folder": "avatars"}

        response = authed_client.post("/api/v1/upload/image", files=files, data=data)

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert "url" in body and body["url"].startswith("https://")
        assert body["filename"].endswith(".jpg")
        assert body["folder"] == "avatars"

    def test_upload_image_unauthorized(self, plain_client, sample_file_upload):
        files = {
            "file": ("test.jpg", sample_file_upload.read(), "image/jpeg"),
        }
        response = plain_client.post("/api/v1/upload/image", files=files)
        # HTTPBearer returns 403 when credentials are missing
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_upload_image_invalid_type(self, authed_client):
        fake_text = io.BytesIO(b"not an image")
        files = {
            "file": ("note.txt", fake_text.read(), "text/plain"),
        }
        response = authed_client.post("/api/v1/upload/image", files=files)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid file type" in response.text

    def test_upload_image_too_large(self, authed_client):
        # Create content slightly over 10MB
        oversized = io.BytesIO(b"\x00" * (10 * 1024 * 1024 + 1))
        files = {
            "file": ("big.jpg", oversized.read(), "image/jpeg"),
        }
        response = authed_client.post("/api/v1/upload/image", files=files)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "File size exceeds" in response.text

    def test_upload_image_empty_file(self, authed_client):
        empty = io.BytesIO(b"")
        files = {
            "file": ("empty.jpg", empty.read(), "image/jpeg"),
        }
        response = authed_client.post("/api/v1/upload/image", files=files)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "File is empty" in response.text

    def test_upload_image_missing_file(self, authed_client):
        # Missing required form field 'file' should raise 422 from FastAPI
        response = authed_client.post("/api/v1/upload/image", files={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_upload_image_extension_mismatch_adjusts_content_type(
        self, authed_client, mock_uploader
    ):
        # Provide .png filename but jpeg content_type; API should normalize to image/png
        content = io.BytesIO(b"\x89PNG\r\n\x1a\n")
        files = {
            "file": ("mismatch.png", content.read(), "image/jpeg"),
        }
        response = authed_client.post("/api/v1/upload/image", files=files)
        assert response.status_code == status.HTTP_201_CREATED
        # Ensure uploader was invoked with normalized content_type
        assert mock_uploader.upload_file.called
        _, kwargs = mock_uploader.upload_file.call_args
        assert kwargs.get("content_type") == "image/png"

    def test_upload_image_uploader_failure(self, authed_client, mock_uploader):
        mock_uploader.upload_file.side_effect = RuntimeError("boom")
        content = io.BytesIO(b"\xff\xd8\xff")  # jpeg header
        files = {
            "file": ("photo.jpg", content.read(), "image/jpeg"),
        }
        response = authed_client.post("/api/v1/upload/image", files=files)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to upload image" in response.text

    def test_upload_image_bucket_not_configured(self, app, authed_client, monkeypatch):
        # Remove dependency override to exercise real dependency that checks settings
        from app.api.upload import get_gcs_uploader as dep_get_gcs_uploader

        app.dependency_overrides.pop(dep_get_gcs_uploader, None)

        # Force bucket to be empty to trigger 500 during dependency resolution
        from app.config import settings

        monkeypatch.setattr(settings, "gcp_public_bucket", "", raising=False)

        content = io.BytesIO(b"\xff\xd8\xff")
        files = {
            "file": ("x.jpg", content.read(), "image/jpeg"),
        }
        response = authed_client.post("/api/v1/upload/image", files=files)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "GCS public bucket not configured" in response.text

        # Restore: ensure subsequent tests still use mock override if needed
        # (The next test's fixture will re-apply the override.)
