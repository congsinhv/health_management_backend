"""
Upload API schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional


class UploadImageResponse(BaseModel):
    """Response schema for image upload."""

    url: str = Field(..., description="Public URL of the uploaded image")
    filename: str = Field(..., description="Filename of the uploaded image")
    folder: Optional[str] = Field(
        None, description="Folder path where the image was uploaded"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://storage.googleapis.com/vhealth-test-public/avatars/abc123.jpg",
                "filename": "abc123.jpg",
                "folder": "avatars",
            }
        }
