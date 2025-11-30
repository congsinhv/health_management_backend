"""
Service interface contracts for VHealth microservices.

This package defines abstract interfaces for all microservices to ensure
consistent contracts and enable easy mocking for testing.

Available interfaces:
- IQAService: Q&A service contract for Vietnamese health questions
- IPredictionService: Health prediction service contract
- IChatAIService: Future Chat AI service contract

Usage:
    from app.interfaces.qa_interface import IQAService, QARequest, QAResponse
    from app.interfaces.predict_interface import IPredictionService
"""