"""
Tests for PredictionRepository.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from app.db.prediction import PredictionRepository
from tests.conftest import create_asyncpg_record


@pytest.fixture
def mock_pool():
    """Create mock asyncpg connection pool."""
    pool = AsyncMock()
    return pool


@pytest.fixture
def mock_connection():
    """Create mock asyncpg connection."""
    connection = AsyncMock()
    return connection


@pytest.fixture
def prediction_repo(mock_pool):
    """Create PredictionRepository with mock pool."""
    return PredictionRepository(mock_pool)


@pytest.mark.asyncio
async def test_create_prediction_success(prediction_repo, mock_connection):
    """Test creating a prediction."""
    import json
    
    # Setup
    user_input = {"age": 30, "gender": "male", "weight": 75, "height": 175}
    prediction_data = {
        "level": "Normal_Weight",
        "bmi": 22.5,
        "diet_recommendations": ["Balanced diet"],
        "workout_recommendations": ["Light exercise"],
    }

    # Create a mock record that behaves like asyncpg.Record
    mock_record = create_asyncpg_record(
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "prediction_id": "pred_12345",
            "user_input": user_input,
            "prediction_data": prediction_data,
            "pdf_url": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )

    # Mock the fetch_one method directly
    prediction_repo.fetch_one = AsyncMock(return_value=mock_record)

    # Execute
    result = await prediction_repo.create_prediction(
        "pred_12345", user_input, prediction_data
    )

    # Assert
    assert result is not None
    assert result["prediction_id"] == "pred_12345"
    assert result["user_input"] == user_input
    assert result["prediction_data"] == prediction_data
    
    # Verify fetch_one was called with JSON-serialized dicts
    prediction_repo.fetch_one.assert_called_once()
    call_args = prediction_repo.fetch_one.call_args
    assert call_args[0][1] == "pred_12345"  # prediction_id
    assert call_args[0][2] == json.dumps(user_input)  # user_input as JSON
    assert call_args[0][3] == json.dumps(prediction_data)  # prediction_data as JSON


@pytest.mark.asyncio
async def test_get_prediction_by_prediction_id_success(
    prediction_repo, mock_connection
):
    """Test getting prediction by prediction_id."""
    # Setup
    expected_record = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "prediction_id": "pred_12345",
        "user_input": {"age": 30},
        "prediction_data": {"level": "Normal_Weight"},
        "pdf_url": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    mock_connection.fetchrow.return_value = expected_record

    # Mock the pool.acquire context manager
    prediction_repo.pool.acquire = MagicMock()
    prediction_repo.pool.acquire.__aenter__ = AsyncMock(return_value=mock_connection)
    prediction_repo.pool.acquire.__aexit__ = AsyncMock(return_value=None)

    # Execute
    result = await prediction_repo.get_prediction_by_prediction_id("pred_12345")

    # Assert
    assert result is not None
    assert result["prediction_id"] == "pred_12345"
    mock_connection.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_get_prediction_by_prediction_id_not_found(
    prediction_repo, mock_connection
):
    """Test getting non-existent prediction."""
    # Setup
    mock_connection.fetchrow.return_value = None

    # Mock the pool.acquire context manager
    prediction_repo.pool.acquire = MagicMock()
    prediction_repo.pool.acquire.__aenter__ = AsyncMock(return_value=mock_connection)
    prediction_repo.pool.acquire.__aexit__ = AsyncMock(return_value=None)

    # Execute
    result = await prediction_repo.get_prediction_by_prediction_id("non_existent")

    # Assert
    assert result is None
    mock_connection.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_update_pdf_url_success(prediction_repo, mock_connection):
    """Test updating PDF URL."""
    # Setup
    pdf_url = "https://storage.googleapis.com/bucket/prediction_pred_12345.pdf"
    expected_record = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "prediction_id": "pred_12345",
        "pdf_url": pdf_url,
        "updated_at": datetime.utcnow(),
    }

    mock_connection.fetchrow.return_value = expected_record

    # Mock the pool.acquire context manager
    prediction_repo.pool.acquire = MagicMock()
    prediction_repo.pool.acquire.__aenter__ = AsyncMock(return_value=mock_connection)
    prediction_repo.pool.acquire.__aexit__ = AsyncMock(return_value=None)

    # Execute
    result = await prediction_repo.update_pdf_url("pred_12345", pdf_url)

    # Assert
    assert result is not None
    assert result["pdf_url"] == pdf_url
    assert result["prediction_id"] == "pred_12345"
    mock_connection.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_delete_prediction_success(prediction_repo, mock_connection):
    """Test soft deleting prediction."""
    # Setup
    expected_record = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "prediction_id": "pred_12345",
        "deleted_at": datetime.utcnow(),
    }

    mock_connection.fetchrow.return_value = expected_record

    # Mock the pool.acquire context manager
    prediction_repo.pool.acquire = MagicMock()
    prediction_repo.pool.acquire.__aenter__ = AsyncMock(return_value=mock_connection)
    prediction_repo.pool.acquire.__aexit__ = AsyncMock(return_value=None)

    # Execute
    result = await prediction_repo.delete_prediction("pred_12345")

    # Assert
    assert result is not None
    assert result["prediction_id"] == "pred_12345"
    assert "deleted_at" in result
    mock_connection.fetchrow.assert_called_once()
