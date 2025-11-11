"""
Schema validation tests for conversations, messages, branching, versions, and uploads.
"""

import pytest
from pydantic import ValidationError

from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationSearchRequest,
    ConversationTagRequest,
)
from app.schemas.message import (
    MessageCreate,
    MessageUpdate,
    MessageBranchRequest,
    MessageVersionRollbackRequest,
)
from app.schemas.branching import BranchCreate, BranchMerge
from app.schemas.upload import UploadImageResponse


@pytest.mark.unit
class TestConversationSchemas:
    def test_conversation_create_valid(self):
        data = {
            "title": "Test",
            "question": "What?",
            "answer": "This is the answer",
            "tags": ["tag1", "tag2"],
            "metadata": {"key": "value"},
        }
        schema = ConversationCreate(**data)
        assert schema.title == "Test"
        assert schema.tags == ["tag1", "tag2"]
        assert schema.metadata == {"key": "value"}

    def test_conversation_create_title_too_long(self):
        data = {"title": "x" * 256}
        with pytest.raises(ValidationError):
            ConversationCreate(**data)

    def test_conversation_create_tags_limit(self):
        data = {"tags": [f"tag{i}" for i in range(11)]}
        with pytest.raises(ValidationError):
            ConversationCreate(**data)

    def test_conversation_update_valid(self):
        data = {
            "title": "Updated Title",
            "tags": ["a", "b"],
            "is_pinned": True,
            "metadata": {"a": 1},
        }
        schema = ConversationUpdate(**data)
        assert schema.is_pinned is True
        assert schema.tags == ["a", "b"]

    def test_conversation_search_request_defaults(self):
        schema = ConversationSearchRequest()
        assert schema.page == 1
        assert schema.page_size == 20
        assert schema.sort_order == "desc"

    def test_conversation_search_request_invalid_sort(self):
        with pytest.raises(ValidationError):
            ConversationSearchRequest(sort_by="invalid")

    def test_conversation_tag_request_min_items(self):
        with pytest.raises(ValidationError):
            ConversationTagRequest(tags=[])


@pytest.mark.unit
class TestMessageSchemas:
    def test_message_create_valid(self):
        data = {
            "content": "Hello",
            "content_cleaned": "Hello",
            "answers": {"answer": ["one"]},
            "metadata": {"k": "v"},
            "parent_message_id": 1,
        }
        schema = MessageCreate(**data)
        assert schema.content == "Hello"
        assert schema.parent_message_id == 1

    def test_message_create_content_required(self):
        with pytest.raises(ValidationError):
            MessageCreate()

    def test_message_update_valid(self):
        data = {"content": "Updated content", "create_version": False}
        schema = MessageUpdate(**data)
        assert schema.content == "Updated content"
        assert schema.create_version is False

    def test_message_update_content_length(self):
        with pytest.raises(ValidationError):
            MessageUpdate(content="")

    def test_message_branch_request_valid(self):
        schema = MessageBranchRequest(content="Branch content")
        assert schema.content == "Branch content"

    def test_message_version_rollback_request(self):
        schema = MessageVersionRollbackRequest(
            version_number=2, create_backup_version=True
        )
        assert schema.version_number == 2
        assert schema.create_backup_version is True

    def test_message_version_rollback_min_version(self):
        with pytest.raises(ValidationError):
            MessageVersionRollbackRequest(version_number=0)


@pytest.mark.unit
class TestBranchingSchemas:
    def test_branch_create_valid(self):
        data = {
            "parent_message_id": 1,
            "role": "user",
            "content": "Branch here",
            "branch_name": "Option A",
        }
        schema = BranchCreate(**data)
        assert schema.parent_message_id == 1
        assert schema.branch_name == "Option A"

    def test_branch_create_content_required(self):
        with pytest.raises(ValidationError):
            BranchCreate(parent_message_id=1, role="user", content="")

    def test_branch_merge_default_strategy(self):
        schema = BranchMerge(source_message_id=1, target_message_id=2)
        assert schema.merge_strategy == "replace"

    def test_branch_merge_invalid_strategy(self):
        with pytest.raises(ValidationError):
            BranchMerge(
                source_message_id=1, target_message_id=2, merge_strategy="invalid"
            )


@pytest.mark.unit
class TestUploadSchemas:
    def test_upload_image_response_valid(self):
        schema = UploadImageResponse(
            url="https://storage.googleapis.com/bucket/file.jpg",
            filename="file.jpg",
            folder="avatars",
        )
        assert schema.filename.endswith(".jpg")
