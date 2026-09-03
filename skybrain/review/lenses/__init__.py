"""Review Lenses package — Strategy Pattern implementations."""

from skybrain.review.lenses.clean_architecture import CleanArchitectureLens
from skybrain.review.lenses.clean_code import CleanCodeLens
from skybrain.review.lenses.performance import PerformanceLens
from skybrain.review.lenses.security import SecurityLens
from skybrain.review.lenses.ai_conduct import AIConductLens

ALL_LENSES = [CleanCodeLens, CleanArchitectureLens, SecurityLens, PerformanceLens, AIConductLens]

__all__ = [
    "ALL_LENSES",
    "CleanArchitectureLens",
    "CleanCodeLens",
    "PerformanceLens",
    "SecurityLens",
    "AIConductLens",
]
