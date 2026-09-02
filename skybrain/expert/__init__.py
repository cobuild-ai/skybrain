"""SkyBrain Expert System.

Decoupled Knowledge Layer Projections (ExpertLens) with 2/3 Majority Consensus.
"""

from skybrain.expert.engine import ExpertEngine
from skybrain.expert.models import (
    AssessmentFinding,
    ConsensusItem,
    ConsensusVerdict,
    EvaluationCriterion,
    ExpertLens,
    ExpertReport,
    Severity,
)
from skybrain.expert.registry import LensRegistry, default_registry
from skybrain.expert.specs import (
    CLEAN_ARCHITECTURE_LENS,
    CLEAN_CODE_LENS,
    DESIGN_PATTERNS_LENS,
    PERFORMANCE_LENS,
    SECURITY_LENS,
    STANDARD_EXPERT_LENSES,
    TEST_RULES_LENS,
)
from skybrain.expert.voter import ConsensusVoter

__all__ = [
    "CLEAN_ARCHITECTURE_LENS",
    "CLEAN_CODE_LENS",
    "DESIGN_PATTERNS_LENS",
    "PERFORMANCE_LENS",
    "SECURITY_LENS",
    "STANDARD_EXPERT_LENSES",
    "TEST_RULES_LENS",
    "AssessmentFinding",
    "ConsensusItem",
    "ConsensusVerdict",
    "ConsensusVoter",
    "EvaluationCriterion",
    "ExpertEngine",
    "ExpertLens",
    "ExpertReport",
    "LensRegistry",
    "Severity",
    "default_registry",
]
