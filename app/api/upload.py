"""
File upload API endpoints.
"""

import logging
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from app.auth.dependencies import get_current_active_user
from app.schemas.user import UserInDB
from app.schemas.upload import UploadImageResponse
from app.config import settings
from app.utils.gcs_uploader import GCSUploader

logger = logging.getLogger(__name__)

router = APIRouter()

# Allowed image MIME types
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
}

# Maximum file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes

# File extension to MIME type mapping
EXTENSION_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def get_gcs_uploader() -> GCSUploader:
    """Dependency to get GCS uploader instance."""
    if not settings.gcp_public_bucket:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GCS public bucket not configured",
        )
    return GCSUploader(
        bucket_name=settings.gcp_public_bucket,
        project_id=settings.gcp_project_id,
    )


def validate_image_file(file: UploadFile) -> tuple[str, bytes]:
    """
    Validate and read image file.

    Args:
        file: Uploaded file

    Returns:
        Tuple of (content_type, file_content)

    Raises:
        HTTPException: If validation fails
    """
    # Read file content
    try:
        # Reset file pointer to beginning if possible
        try:
            file.file.seek(0)
        except (AttributeError, OSError):
            pass  # Some file types don't support seek

        file_content = file.file.read()

        # Check file size after reading
        file_size = len(file_content)

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024 * 1024):.0f}MB",
            )

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read file",
        )

    # Validate content type
    content_type = file.content_type
    if not content_type:
        # Try to infer from filename
        file_extension = None
        if file.filename:
            file_extension = "." + file.filename.rsplit(".", 1)[-1].lower()
            content_type = EXTENSION_TO_MIME.get(file_extension)

    if not content_type or content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}",
        )

    # Validate file extension matches content type
    if file.filename:
        file_extension = "." + file.filename.rsplit(".", 1)[-1].lower()
        expected_mime = EXTENSION_TO_MIME.get(file_extension)
        if expected_mime and expected_mime != content_type:
            logger.warning(
                f"File extension {file_extension} doesn't match content type {content_type}"
            )
            # Use the content type from extension if available
            content_type = expected_mime

    return content_type, file_content


@router.post("/image", response_model=UploadImageResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    file: UploadFile = File(..., description="Image file to upload"),
    folder: Optional[str] = Form(
        None, description="Optional folder path in the bucket (e.g., 'avatars', 'profile-pictures')"
    ),
    uploader: GCSUploader = Depends(get_gcs_uploader),
):
    """
    Upload an image file to Google Cloud Storage.

    This endpoint allows authenticated users to upload image files to the GCS bucket
    and receive a public URL for the uploaded file.

    **File Requirements:**
    - Allowed types: JPEG, JPG, PNG, WebP, GIF
    - Maximum size: 10MB
    - File extension must match the MIME type

    **Authentication:**
    - Requires Bearer token authentication
    - Token must be valid and not expired

    **Response:**
    - Returns the public URL of the uploaded image
    - Includes the filename and folder path
    """
    try:
        # Validate file
        content_type, file_content = validate_image_file(file)

        # Upload to GCS
        public_url = uploader.upload_file(
            file_content=file_content,
            file_name=file.filename or "image",
            folder=folder,
            content_type=content_type,
            make_public=True,
        )

        # Extract filename from URL
        filename = public_url.split("/")[-1]

        logger.info(
            f"User {current_user.id} uploaded image: {filename} to folder: {folder or 'root'}"
        )

        return UploadImageResponse(
            url=public_url,
            filename=filename,
            folder=folder,
        )

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    except Exception as e:
        logger.error(f"Error uploading image for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image",
        )

