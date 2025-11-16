"""
Unit tests for Q&A service streaming methods.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import pandas as pd

from app.services.qa_service import QAService
from app.config import Settings


@pytest.mark.asyncio
async def test_stream_summarize_with_ai_token_accumulation():
    """Test token accumulation during streaming."""

    # Setup QA service with minimal mocking
    settings = Settings(qa_enabled=True, openai_api_key="test-key")

    with patch.object(QAService, '_load_model'), \
         patch.object(QAService, '_load_data'):
        qa_service = QAService(settings)

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

    with patch.object(qa_service.openai_client.chat.completions, 'create') as mock_create:
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
    settings = Settings(qa_enabled=True)

    with patch.object(QAService, '_load_model') as mock_model, \
         patch.object(QAService, '_load_data') as mock_data:

        # Mock SBERT model
        qa_service = QAService(settings)
        qa_service.model = MagicMock()
        qa_service.model.encode.return_value = [0.1, 0.2, 0.3]

        # Mock data and embeddings
        mock_df = pd.DataFrame({
            "Câu hỏi": ["Q1", "Q2"],
            "Câu trả lời": ["A1", "A2"],
            "Lĩnh vực": ["Health", "Nutrition"]
        })
        qa_service.df = mock_df
        qa_service.question_embeddings = [[0.1, 0.2, 0.3], [0.2, 0.3, 0.4]]

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

        with patch.object(qa_service.openai_client.chat.completions, 'create') as mock_create:
            mock_create.return_value = iter(mock_chunks)

            # Execute
            events = []
            async for event in qa_service.stream_ask_question("test question"):
                events.append(event)

            # Validate sequence
            event_types = []
            for event in events:
                if 'event_type' in event:
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

    settings = Settings(qa_enabled=True)

    with patch.object(QAService, '_load_model'), \
         patch.object(QAService, '_load_data'):
        qa_service = QAService(settings)

        # Mock model to raise exception
        qa_service.model = MagicMock()
        qa_service.model.encode.side_effect = Exception("Model error")

        # Execute
        events = []
        async for event in qa_service.stream_ask_question("test question"):
            events.append(event)

        # Should have error event
        assert len(events) == 1
        assert "error" in events[0]
        assert "processing_error" in events[0]


@pytest.mark.asyncio
async def test_stream_summarize_with_ai_openai_error():
    """Test error handling when OpenAI API fails."""

    settings = Settings(qa_enabled=True)

    with patch.object(QAService, '_load_model'), \
         patch.object(QAService, '_load_data'):
        qa_service = QAService(settings)

        # Mock OpenAI to raise exception
        with patch.object(qa_service.openai_client.chat.completions, 'create') as mock_create:
            mock_create.side_effect = Exception("OpenAI API error")

            # Execute
            events = []
            grouped_answers = {"Field": ["Answer1"]}
            async for event in qa_service.stream_summarize_with_ai("test", grouped_answers):
                events.append(event)

            # Should have error event
            assert len(events) == 1
            assert "error" in events[0]
            assert "api_error" in events[0]


def test_build_summary_prompt_helper():
    """Test _build_summary_prompt helper method."""

    settings = Settings(qa_enabled=True)

    with patch.object(QAService, '_load_model'), \
         patch.object(QAService, '_load_data'):
        qa_service = QAService(settings)

        question = "How to stay healthy?"
        grouped_answers = {
            "Diet": ["Eat vegetables", "Drink water"],
            "Exercise": ["Walk daily", "Do yoga"]
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

    settings = Settings(qa_enabled=True)

    with patch.object(QAService, '_load_model'), \
         patch.object(QAService, '_load_data'):
        qa_service = QAService(settings)

        # Mock model to return low similarities
        qa_service.model = MagicMock()
        qa_service.model.encode.return_value = [0.1, 0.2, 0.3]

        # Mock empty dataframe
        qa_service.df = pd.DataFrame()
        qa_service.question_embeddings = []

        # Execute
        events = []
        async for event in qa_service.stream_ask_question("test"):
            events.append(event)

        # Should still have question_received and answers_found events
        assert len(events) >= 2

        # First event should be question_received
        assert "question_received" in events[0]

        # Should have answers_found with empty results
        assert "answers_found" in events[1]
        assert '"count":0' in events[1]