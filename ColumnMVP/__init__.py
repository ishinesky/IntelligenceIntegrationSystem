"""Topic-driven column MVP for dynamic intelligence crawling.

This package intentionally keeps the first implementation file-based and safe:
AI can propose column/source configuration, but crawler code is not generated or
executed dynamically.
"""

from .models import ColumnConfig, SourceConfig, TopicBrief, ValidationResult
from .column_store import ColumnStore
from .column_service import ColumnService
from .source_candidate_service import SourceCandidateService
from .source_quality import SourceQualityReport, SourceQualityService
from .source_search_provider import SourceSearchCandidate, get_source_search_provider
from .web_service_integration import register_opc_column_routes, patch_intelligence_hub_web_service

__all__ = [
    "ColumnConfig",
    "SourceConfig",
    "TopicBrief",
    "ValidationResult",
    "ColumnStore",
    "ColumnService",
    "SourceCandidateService",
    "SourceQualityReport",
    "SourceQualityService",
    "SourceSearchCandidate",
    "get_source_search_provider",
    "register_opc_column_routes",
    "patch_intelligence_hub_web_service",
]
