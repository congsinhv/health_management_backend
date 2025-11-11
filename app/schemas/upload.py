"""
Upload API schemas.
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class UploadImageResponse(BaseModel):
    """Response schema for image upload."""

    url: str = Field(..., description="Public URL of the uploaded image")
    filename: str = Field(..., description="Filename of the uploaded image")
    folder: Optional[str] = Field(
        None, description="Folder path where the image was uploaded"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://storage.googleapis.com/vhealth-dev-public/avatars/abc123.jpg",
                "filename": "abc123.jpg",
                "folder": "avatars",
            }
        }
    )
