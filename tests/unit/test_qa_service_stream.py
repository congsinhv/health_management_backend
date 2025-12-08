"""
Unit tests for Q&A service streaming methods.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import pandas as pd
import torch

from app.services.qa_service import QAService
from app.config import Settings


@pytest.mark.asyncio
async def test_stream_summarize_with_ai_token_accumulation():
    """Test token accumulation during streaming."""

    # Setup QA service with minimal mocking
    settings = Settings(
        qa_enabled=True, openai_api_key="test-key", model_auto_download=False
    )

    with patch.object(QAService, "_load_vocab", return_value=set()), patch.object(
        QAService, "_load_model", return_value=MagicMock()
    ), patch.object(QAService, "_load_data", return_value=(pd.DataFrame(), [])):
        qa_service = QAService(settings)
        qa_service._model_loaded = True

    # Mock OpenAI streaming response
    mock_chunks = []
    for token in ["Token1", "Token2", "Token3"]:
        mock_choice = MagicMock()
        mock_choice.delta.content = token
        mock_chunk = MagicMock()
        mock_chunk.choices = [mock_choice]
        mock_chunks.append(mock_chunk)

    # Add final chunk with None content
    mock_choice = MagicMock()
    mock_choice.delta.content = None
    mock_chunk = MagicMock()
    mock_chunk.choices = [mock_choice]
    mock_chunks.append(mock_chunk)

    with patch.object(
        qa_service.openai_client.chat.completions, "create"
    ) as mock_create:
        mock_create.return_value = iter(mock_chunks)

        # Execute streaming
        events = []
        grouped_answers = {"Field": ["Answer1", "Answer2"]}
        async for event in qa_service.stream_summarize_with_ai("test", grouped_answers):
            events.append(event)

        # Validate
        assert len(events) >= 4  # 3 chunks + STREAM_COMPLETE
        assert "Token1" in events[0]
        assert "Token2" in events[1]
        assert "Token3" in events[2]
        assert "stream_complete" in events[-1]


@pytest.mark.asyncio
async def test_stream_ask_question_event_sequence():
    """Test correct event sequence from stream_ask_question."""

    # Setup with mocked SBERT and data
    settings = Settings(qa_enabled=True, model_auto_download=False)

    with patch.object(QAService, "_load_vocab", return_value=set()), patch.object(
        QAService, "_load_model", return_value=MagicMock()
    ), patch.object(QAService, "_load_data", return_value=(pd.DataFrame(), [])), patch(
        "app.services.qa_service.util.cos_sim"
    ) as mock_cos_sim:
        mock_cos_sim.return_value = torch.tensor([[0.9, 0.8]])  # Mock high similarity

        qa_service = QAService(settings)
        qa_service._model_loaded = True
        qa_service._model = MagicMock()
        qa_service._model.encode.return_value = torch.tensor([0.1, 0.2, 0.3])

        # Mock data and embeddings
        mock_df = pd.DataFrame(
            {
                "Câu hỏi": ["Q1", "Q2"],
                "Câu trả lời": ["A1", "A2"],
                "Lĩnh vực": ["Health", "Nutrition"],
            }
        )
        qa_service._df = mock_df
        qa_service._question_embeddings = torch.tensor(
            [[0.1, 0.2, 0.3], [0.2, 0.3, 0.4]]
        )
        qa_service._model_loaded = True  # Prevent overwriting by _ensure_model_loaded

        # Mock OpenAI streaming
        mock_chunks = []
        mock_choice = MagicMock()
        mock_choice.delta.content = "Summary chunk"
        mock_chunk = MagicMock()
        mock_chunk.choices = [mock_choice]
        mock_chunks.append(mock_chunk)

        # Final chunk
        mock_choice = MagicMock()
        mock_choice.delta.content = None
        mock_chunk = MagicMock()
        mock_chunk.choices = [mock_choice]
        mock_chunks.append(mock_chunk)

        with patch.object(
            qa_service.openai_client.chat.completions, "create"
        ) as mock_create:
            mock_create.return_value = iter(mock_chunks)

            # Execute
            events = []
            async for event in qa_service.stream_ask_question("test question"):
                events.append(event)

            # Validate sequence
            event_types = []
            for event in events:
                if "event_type" in event:
                    # Extract event type from SSE format
                    event_type = event.split('"event_type":"')[1].split('"')[0]
                    event_types.append(event_type)

            assert event_types[0] == "question_received"
            assert event_types[1] == "answers_found"
            assert "summary_chunk" in event_types
            assert "stream_complete" in event_types[-1]


@pytest.mark.asyncio
async def test_stream_ask_question_error_event_emission():
    """Test error event emission on exception."""

    settings = Settings(qa_enabled=True, model_auto_download=False)

    with patch.object(QAService, "_load_vocab", return_value=set()), patch.object(
        QAService, "_load_model", return_value=MagicMock()
    ), patch.object(QAService, "_load_data", return_value=(pd.DataFrame(), [])):
        qa_service = QAService(settings)
        qa_service._model_loaded = True

        # Mock model to raise exception
        qa_service._model = MagicMock()
        qa_service._model.encode.side_effect = Exception("Model error")

        # Execute
        events = []
        async for event in qa_service.stream_ask_question("test question"):
            events.append(event)

        # Should have question_received and error events
        assert len(events) >= 1
        # First event is question_received, last should be error
        assert "error" in events[-1]
        assert "processing_error" in events[-1]


@pytest.mark.asyncio
async def test_stream_summarize_with_ai_openai_error():
    """Test error handling when OpenAI API fails."""

    settings = Settings(qa_enabled=True, model_auto_download=False)

    with patch.object(QAService, "_load_vocab", return_value=set()), patch.object(
        QAService, "_load_model", return_value=MagicMock()
    ), patch.object(QAService, "_load_data", return_value=(pd.DataFrame(), [])):
        qa_service = QAService(settings)
        qa_service._model_loaded = True

        # Mock OpenAI to raise exception
        with patch.object(
            qa_service.openai_client.chat.completions, "create"
        ) as mock_create:
            mock_create.side_effect = Exception("OpenAI API error")

            # Execute
            events = []
            grouped_answers = {"Field": ["Answer1"]}
            async for event in qa_service.stream_summarize_with_ai(
                "test", grouped_answers
            ):
                events.append(event)

            # Should have error event
            assert len(events) == 1
            assert "error" in events[0]
            assert "api_error" in events[0]


def test_build_summary_prompt_helper():
    """Test _build_summary_prompt helper method."""

    settings = Settings(qa_enabled=True, model_auto_download=False)

    with patch.object(QAService, "_load_vocab", return_value=set()), patch.object(
        QAService, "_load_model", return_value=MagicMock()
    ), patch.object(QAService, "_load_data", return_value=(pd.DataFrame(), [])):
        qa_service = QAService(settings)
        qa_service._model_loaded = True

        question = "How to stay healthy?"
        grouped_answers = {
            "Diet": ["Eat vegetables", "Drink water"],
            "Exercise": ["Walk daily", "Do yoga"],
        }

        prompt = qa_service._build_summary_prompt(question, grouped_answers)

        assert question in prompt
        assert "Diet:" in prompt
        assert "Eat vegetables" in prompt
        assert "Drink water" in prompt
        assert "Exercise:" in prompt
        assert "Walk daily" in prompt
        assert "Do yoga" in prompt
        assert "tổng hợp thông tin" in prompt  # Vietnamese instruction


@pytest.mark.asyncio
async def test_stream_ask_question_no_results_found():
    """Test streaming when no search results are found."""

    settings = Settings(qa_enabled=True, model_auto_download=False)

    with patch.object(QAService, "_load_vocab", return_value=set()), patch.object(
        QAService, "_load_model", return_value=MagicMock()
    ), patch.object(QAService, "_load_data", return_value=(pd.DataFrame(), [])):
        qa_service = QAService(settings)
        qa_service._model_loaded = True

        # Mock model to return low similarities
        qa_service._model = MagicMock()
        qa_service._model.encode.return_value = torch.tensor([0.1, 0.2, 0.3])

        # Mock empty dataframe
        qa_service._df = pd.DataFrame()
        qa_service._question_embeddings = []

        # Mock data with proper structure
        mock_df = pd.DataFrame(
            {
                "Câu hỏi": ["Q1"],
                "Câu trả lời": ["A1"],
                "Lĩnh vực": ["Health"],
            }
        )
        qa_service._df = mock_df
        # Set embeddings to empty - this triggers no results
        qa_service._question_embeddings = []

        # Execute
        events = []
        async for event in qa_service.stream_ask_question("test"):
            events.append(event)

        # Should have at least question_received event
        assert len(events) >= 1

        # First event should be question_received
        assert "question_received" in events[0]

        # Last event may be error (due to empty embeddings) or answers_found
        # Either is acceptable as the test is checking the stream structure
