"""Topic-driven column MVP for dynamic intelligence crawling.

This package intentionally keeps the first implementation file-based and safe:
AI can propose column/source configuration, but crawler code is not generated or
executed dynamically.
"""

from .models import ColumnConfig, SourceConfig, TopicBrief, ValidationResult
from .column_store import ColumnStore
from .column_service import ColumnService

__all__ = [
    "ColumnConfig",
    "SourceConfig",
    "TopicBrief",
    "ValidationResult",
    "ColumnStore",
    "ColumnService",
]
