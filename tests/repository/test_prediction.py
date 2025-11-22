"""
Tests for Prediction repository.
"""

import pytest
import asyncio
from datetime import datetime
from app.db.prediction import PredictionRepository


@pytest.fixture
async def prediction_repo(db_pool):
    """Create prediction repository fixture."""
    return PredictionRepository(db_pool)


@pytest.fixture
async def sample_user(db_pool):
    """Create sample user for testing."""
    # First create a user
    user_data = {
        "email": "testuser@example.com",
        "hashed_password": "hashedpassword123",
        "full_name": "Test User",
        "is_active": True,
        "is_superuser": False,
    }

    # Insert user directly
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            INSERT INTO users (email, hashed_password, full_name, is_active, is_superuser, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
            RETURNING id
        """,
            *user_data.values()
        )
        return result["id"]


@pytest.fixture
def sample_user_input():
    """Sample user input data."""
    return {
        "name": "Test User",
        "gender": "Male",
        "age": 30.0,
        "height": 1.75,
        "weight": 70.0,
        "family_history": False,
        "FAF": 1.0,
        "TUE": 1.0,
        "NCP": 3,
        "FCVC": 2.0,
        "CH2O": 2.0,
        "FAVC": 0,
        "CALC": 0,
        "CAEC": 2,
        "MTRANS_Calorie": 1,
    }


@pytest.fixture
def sample_prediction_data():
    """Sample prediction response data."""
    return {
        "id": "test-prediction-id",
        "timestamp": datetime.now().isoformat(),
        "userInput": {
            "name": "Test User",
            "gender": "Male",
            "age": 30.0,
            "height": 1.75,
            "weight": 70.0,
        },
        "prediction": {
            "level": "Normal_Weight",
            "confidence": 85.5,
            "bmi": 22.86,
            "status": "Bình thường",
            "reliability": "high",
        },
        "healthMetrics": {
            "weight": {"label": "Cân nặng", "value": 70.0, "unit": "kg"},
            "bmi": {"label": "BMI", "value": 22.86, "unit": ""},
            "height": {"label": "Chiều cao", "value": 1.75, "unit": "m"},
        },
        "healthAnalysis": {
            "paragraphs": [
                "Test health analysis paragraph 1",
                "Test health analysis paragraph 2",
            ]
        },
        "dietPlan": {"weeklyPlans": []},
        "workoutPlan": {"weeklyPlans": []},
    }


@pytest.mark.asyncio
async def test_create_prediction(
    prediction_repo, sample_user, sample_user_input, sample_prediction_data
):
    """Test creating a new prediction."""
    # Create prediction
    prediction = await prediction_repo.create(
        user_id=sample_user,
        user_input=sample_user_input,
        prediction_data=sample_prediction_data,
    )

    # Verify prediction was created
    assert prediction is not None
    assert prediction["user_id"] == sample_user
    assert prediction["user_input"] is not None
    assert prediction["prediction_data"] is not None
    assert prediction["id"] is not None
    assert prediction["created_at"] is not None
    assert prediction["deleted_at"] is None


@pytest.mark.asyncio
async def test_get_prediction_by_id_and_user(
    prediction_repo, sample_user, sample_user_input, sample_prediction_data
):
    """Test retrieving prediction by ID and user."""
    # Create prediction first
    created_prediction = await prediction_repo.create(
        user_id=sample_user,
        user_input=sample_user_input,
        prediction_data=sample_prediction_data,
    )
    prediction_id = created_prediction["id"]

    # Retrieve prediction
    retrieved_prediction = await prediction_repo.get_by_id_and_user(
        prediction_id=prediction_id, user_id=sample_user
    )

    # Verify retrieved prediction
    assert retrieved_prediction is not None
    assert retrieved_prediction["id"] == prediction_id
    assert retrieved_prediction["user_id"] == sample_user


@pytest.mark.asyncio
async def test_get_prediction_not_found(prediction_repo, sample_user):
    """Test retrieving non-existent prediction."""
    prediction = await prediction_repo.get_by_id_and_user(
        prediction_id=99999, user_id=sample_user
    )
    assert prediction is None


@pytest.mark.asyncio
async def test_get_prediction_wrong_user(
    prediction_repo, sample_user, sample_user_input, sample_prediction_data
):
    """Test retrieving prediction with wrong user ID."""
    # Create prediction for user 1
    created_prediction = await prediction_repo.create(
        user_id=sample_user,
        user_input=sample_user_input,
        prediction_data=sample_prediction_data,
    )
    prediction_id = created_prediction["id"]

    # Try to retrieve with different user ID
    retrieved_prediction = await prediction_repo.get_by_id_and_user(
        prediction_id=prediction_id, user_id=sample_user + 1000  # Different user
    )
    assert retrieved_prediction is None


@pytest.mark.asyncio
async def test_list_predictions_by_user(
    prediction_repo, sample_user, sample_user_input, sample_prediction_data
):
    """Test listing predictions for a user."""
    # Create multiple predictions
    predictions = []
    for i in range(3):
        prediction = await prediction_repo.create(
            user_id=sample_user,
            user_input=sample_user_input,
            prediction_data=sample_prediction_data,
        )
        predictions.append(prediction)

    # List predictions
    listed_predictions = await prediction_repo.list_by_user(
        user_id=sample_user, limit=10
    )

    # Verify
    assert len(listed_predictions) >= 3
    # Should be ordered by created_at DESC
    for i in range(len(listed_predictions) - 1):
        assert (
            listed_predictions[i]["created_at"]
            >= listed_predictions[i + 1]["created_at"]
        )


@pytest.mark.asyncio
async def test_list_predictions_by_user_with_pagination(
    prediction_repo, sample_user, sample_user_input, sample_prediction_data
):
    """Test listing predictions with pagination."""
    # Create multiple predictions
    predictions = []
    for i in range(5):
        prediction = await prediction_repo.create(
            user_id=sample_user,
            user_input=sample_user_input,
            prediction_data=sample_prediction_data,
        )
        predictions.append(prediction)

    # Test pagination
    first_page = await prediction_repo.list_by_user(
        user_id=sample_user, limit=2, offset=0
    )
    second_page = await prediction_repo.list_by_user(
        user_id=sample_user, limit=2, offset=2
    )

    # Verify
    assert len(first_page) == 2
    assert len(second_page) == 2
    # Ensure no overlap
    first_page_ids = {p["id"] for p in first_page}
    second_page_ids = {p["id"] for p in second_page}
    assert len(first_page_ids.intersection(second_page_ids)) == 0


@pytest.mark.asyncio
async def test_update_pdf_url(
    prediction_repo, sample_user, sample_user_input, sample_prediction_data
):
    """Test updating PDF URL for a prediction."""
    # Create prediction
    created_prediction = await prediction_repo.create(
        user_id=sample_user,
        user_input=sample_user_input,
        prediction_data=sample_prediction_data,
    )
    prediction_id = created_prediction["id"]

    # Update PDF URL
    pdf_url = "https://storage.googleapis.com/bucket/predictions/test.pdf"
    updated_prediction = await prediction_repo.update_pdf_url(
        prediction_id=prediction_id, user_id=sample_user, pdf_url=pdf_url
    )

    # Verify
    assert updated_prediction is not None
    assert updated_prediction["pdf_url"] == pdf_url
    assert updated_prediction["updated_at"] > created_prediction["updated_at"]


@pytest.mark.asyncio
async def test_delete_prediction(
    prediction_repo, sample_user, sample_user_input, sample_prediction_data
):
    """Test soft deleting a prediction."""
    # Create prediction
    created_prediction = await prediction_repo.create(
        user_id=sample_user,
        user_input=sample_user_input,
        prediction_data=sample_prediction_data,
    )
    prediction_id = created_prediction["id"]

    # Delete prediction
    delete_result = await prediction_repo.delete(
        prediction_id=prediction_id, user_id=sample_user
    )

    # Verify
    assert delete_result is True

    # Verify prediction is marked as deleted
    deleted_prediction = await prediction_repo.get_by_id_and_user(
        prediction_id=prediction_id, user_id=sample_user
    )
    assert deleted_prediction is None  # Should not return deleted predictions


@pytest.mark.asyncio
async def test_delete_prediction_not_found(prediction_repo, sample_user):
    """Test deleting non-existent prediction."""
    delete_result = await prediction_repo.delete(
        prediction_id=99999, user_id=sample_user
    )
    assert delete_result is False


@pytest.mark.asyncio
async def test_count_predictions_by_user(
    prediction_repo, sample_user, sample_user_input, sample_prediction_data
):
    """Test counting predictions for a user."""
    # Count predictions initially
    initial_count = await prediction_repo.count_predictions_by_user(user_id=sample_user)

    # Create predictions
    await prediction_repo.create(
        user_id=sample_user,
        user_input=sample_user_input,
        prediction_data=sample_prediction_data,
    )
    await prediction_repo.create(
        user_id=sample_user,
        user_input=sample_user_input,
        prediction_data=sample_prediction_data,
    )

    # Count again
    final_count = await prediction_repo.count_predictions_by_user(user_id=sample_user)

    # Verify
    assert final_count == initial_count + 2


@pytest.mark.asyncio
async def test_get_latest_prediction_by_user(
    prediction_repo, sample_user, sample_user_input, sample_prediction_data
):
    """Test getting latest prediction for a user."""
    # Create multiple predictions with slight delays
    prediction1 = await prediction_repo.create(
        user_id=sample_user,
        user_input=sample_user_input,
        prediction_data=sample_prediction_data,
    )

    # Small delay to ensure different timestamps
    await asyncio.sleep(0.1)

    prediction2 = await prediction_repo.create(
        user_id=sample_user,
        user_input=sample_user_input,
        prediction_data=sample_prediction_data,
    )

    # Get latest prediction
    latest_prediction = await prediction_repo.get_latest_prediction_by_user(
        user_id=sample_user
    )

    # Verify
    assert latest_prediction is not None
    assert (
        latest_prediction["id"] == prediction2["id"]
    )  # Should be the second (newer) prediction


@pytest.mark.asyncio
async def test_get_latest_prediction_no_predictions(prediction_repo, sample_user):
    """Test getting latest prediction when user has no predictions."""
    latest_prediction = await prediction_repo.get_latest_prediction_by_user(
        user_id=sample_user
    )
    assert latest_prediction is None


@pytest.mark.asyncio
async def test_get_predictions_by_date_range(
    prediction_repo, sample_user, sample_user_input, sample_prediction_data
):
    """Test getting predictions within a date range."""
    # Create a prediction
    prediction = await prediction_repo.create(
        user_id=sample_user,
        user_input=sample_user_input,
        prediction_data=sample_prediction_data,
    )

    # Get date range (today and tomorrow)
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (
        datetime.now()
        .replace(hour=23, minute=59, second=59)
        .strftime("%Y-%m-%d %H:%M:%S")
    )

    # Get predictions in range
    predictions = await prediction_repo.get_predictions_by_date_range(
        user_id=sample_user, start_date=today, end_date=tomorrow
    )

    # Verify
    assert len(predictions) >= 1
    prediction_ids = [p["id"] for p in predictions]
    assert prediction["id"] in prediction_ids
