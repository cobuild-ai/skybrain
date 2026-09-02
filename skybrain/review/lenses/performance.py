"""Performance Review Lens — Memory, I/O, and complexity analysis."""

from skybrain.review.lenses.base import ReviewLens
from skybrain.review.models import Category


class PerformanceLens(ReviewLens):
    """Analyzes code for performance bottlenecks and resource issues.

    Focus areas: memory leaks, I/O efficiency, algorithmic complexity,
    resource lifecycle, and unnecessary allocations.
    """

    @property
    def name(self) -> str:
        return "Performance"

    @property
    def category(self) -> Category:
        return Category.PERFORMANCE

    @property
    def system_prompt(self) -> str:
        return (
            "You are a senior performance engineer specializing in Python "
            "and system-level optimization. You focus on memory efficiency, "
            "I/O throughput, and computational complexity.\n\n"
            "Analyze the code for these specific issues:\n"
            "1. **Memory Leaks**: Are there reference cycles, unclosed "
            "file handles, or generator objects that are never collected?\n"
            "2. **Resource Lifecycle**: Are heavy resources (LLM models, "
            "file descriptors, network connections) properly acquired and "
            "released using context managers or try/finally?\n"
            "3. **Lock Contention**: Are locks held for too long? Are "
            "there I/O operations inside critical sections that block "
            "other threads unnecessarily?\n"
            "4. **Algorithmic Complexity**: Are there O(n²) or worse "
            "patterns that could be optimized to O(n) or O(n log n)?\n"
            "5. **Unnecessary Allocations**: Are there repeated object "
            "creations, string concatenations, or list copies in hot paths?\n"
            "6. **Blocking I/O**: Are there synchronous network/disk calls "
            "that block the event loop or main thread?\n"
            "7. **Caching Opportunities**: Are there expensive computations "
            "that are repeated with the same inputs?\n\n"
            "Be precise: cite specific line numbers, data structures, and "
            "the expected vs actual complexity."
        )
