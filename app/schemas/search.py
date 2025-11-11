"""
Search schemas for request/response validation.
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.base import BaseResponse


class SearchParams(BaseModel):
    """Base search parameters."""

    query: Optional[str] = Field(None, min_length=1, max_length=200)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = Field(
        default="relevance", pattern="^(relevance|created_at|updated_at|title)$"
    )
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


class ConversationSearchParams(SearchParams):
    """Search parameters for conversations."""

    tags: Optional[List[str]] = Field(None, max_length=10)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    pinned_only: bool = False
    include_messages: bool = True
    search_in_answers: bool = True


class MessageSearchParams(SearchParams):
    """Search parameters for messages."""

    conversation_id: Optional[int] = None
    role: Optional[str] = Field(None, pattern="^(user|assistant|system)$")
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    include_content: bool = True
    include_answers: bool = True
    search_highlights: bool = True


class SearchResultHighlight(BaseModel):
    """Search result highlight."""

    field: str
    fragment: str
    highlights: List[str] = []


class ConversationSearchResult(BaseModel):
    """Single conversation search result."""

    conversation_id: int
    title: Optional[str]
    question: Optional[str]
    tags: List[str] = []
    is_pinned: bool = False
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    relevance_score: float = 0.0
    highlights: List[SearchResultHighlight] = []
    matched_fields: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class MessageSearchResult(BaseModel):
    """Single message search result."""

    message_id: int
    conversation_id: int
    conversation_title: Optional[str]
    role: str
    content: str
    created_at: datetime
    updated_at: datetime
    relevance_score: float = 0.0
    highlights: List[SearchResultHighlight] = []
    matched_fields: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseResponse):
    """Base search response."""

    query: str
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
    search_time_ms: float = 0.0
    suggestions: List[str] = []
    facets: Dict[str, Dict[str, int]] = {}


class ConversationSearchResponse(SearchResponse):
    """Conversation search response."""

    results: List[ConversationSearchResult] = []


class MessageSearchResponse(SearchResponse):
    """Message search response."""

    results: List[MessageSearchResult] = []


class SearchSuggestionRequest(BaseModel):
    """Request for search suggestions."""

    query: str = Field(..., min_length=1, max_length=50)
    limit: int = Field(default=5, ge=1, le=20)
    type: str = Field(default="all", pattern="^(conversations|messages|tags|all)$")


class SearchSuggestion(BaseModel):
    """Single search suggestion."""

    text: str
    type: str
    count: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class SearchSuggestionResponse(BaseResponse):
    """Search suggestions response."""

    suggestions: List[SearchSuggestion] = []
    query: str


class SearchHistoryRequest(BaseModel):
    """Request for search history."""

    limit: int = Field(default=10, ge=1, le=50)
    type: Optional[str] = Field(None, pattern="^(conversations|messages|all)$")


class SearchHistoryItem(BaseModel):
    """Single search history item."""

    query: str
    type: str
    result_count: int
    searched_at: datetime
    clicked_result_id: Optional[int] = None


class SearchHistoryResponse(BaseResponse):
    """Search history response."""

    history: List[SearchHistoryItem] = []
    total_searches: int = 0


class SearchAnalyticsRequest(BaseModel):
    """Request for search analytics."""

    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    group_by: str = Field(default="day", pattern="^(hour|day|week|month)$")


class SearchAnalyticsResponse(BaseResponse):
    """Search analytics response."""

    total_searches: int = 0
    unique_queries: int = 0
    average_results_per_search: float = 0.0
    top_queries: List[Dict[str, Any]] = []
    search_trends: List[Dict[str, Any]] = []
    no_result_queries: List[str] = []


class SearchFilterRequest(BaseModel):
    """Request for search filters."""

    query: Optional[str] = None
    available_filters: List[str] = Field(default_factory=list)


class SearchFilter(BaseModel):
    """Single search filter."""

    name: str
    label: str
    type: str  # text, date, select, multiselect
    options: Optional[List[Dict[str, Any]]] = None
    min_value: Optional[Union[int, float, datetime]] = None
    max_value: Optional[Union[int, float, datetime]] = None
    default_value: Any = None


class SearchFilterResponse(BaseResponse):
    """Search filters response."""

    filters: List[SearchFilter] = []
    active_filters: Dict[str, Any] = {}


class SearchSaveRequest(BaseModel):
    """Request to save a search."""

    query: str
    name: str = Field(..., min_length=1, max_length=50)
    filters: Dict[str, Any] = Field(default_factory=dict)
    is_public: bool = False


class SavedSearch(BaseModel):
    """Saved search model."""

    id: int
    name: str
    query: str
    filters: Dict[str, Any] = {}
    is_public: bool = False
    result_count: int = 0
    created_at: datetime
    last_used_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SavedSearchListResponse(BaseResponse):
    """Saved searches list response."""

    saved_searches: List[SavedSearch] = []
    total: int = 0


class SavedSearchResponse(BaseResponse):
    """Saved search response."""

    saved_search: SavedSearch


class SearchIndexRequest(BaseModel):
    """Request for search index operations."""

    operation: str = Field(..., pattern="^(refresh|rebuild|status)$")
    type: Optional[str] = Field(None, pattern="^(conversations|messages|all)$")


class SearchIndexResponse(BaseResponse):
    """Search index operation response."""

    operation: str
    status: str = Field(..., pattern="^(started|in_progress|completed|failed)$")
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    message: Optional[str] = None
    indexed_count: int = 0
    total_count: Optional[int] = None
    estimated_time_remaining: Optional[int] = None  # seconds


class SearchAutocompleteRequest(BaseModel):
    """Request for search autocomplete."""

    query: str = Field(..., min_length=1, max_length=50)
    limit: int = Field(default=5, ge=1, le=10)
    context: Optional[str] = Field(None, pattern="^(conversation|message|tag)$")


class SearchAutocompleteResponse(BaseResponse):
    """Search autocomplete response."""

    suggestions: List[str] = []
    completions: List[Dict[str, Any]] = []
    query: str


class AdvancedSearchRequest(BaseModel):
    """Advanced search request with complex queries."""

    query: Optional[str] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    boolean_query: Optional[str] = None  # For complex boolean logic
    fuzzy_search: bool = True
    boost_recent: bool = True
    exclude_ids: List[int] = Field(default_factory=list)
    include_ids: List[int] = Field(default_factory=list)
    min_relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)


class SearchExplanation(BaseModel):
    """Explanation of why a result matched."""

    field: str
    value: str
    score: float
    explanation: str


class AdvancedSearchResponse(BaseResponse):
    """Advanced search response with explanations."""

    results: List[Union[ConversationSearchResult, MessageSearchResult]] = []
    query_plan: Optional[str] = None
    execution_time_ms: float = 0.0
    index_used: Optional[str] = None
    explanations: Dict[int, List[SearchExplanation]] = {}
