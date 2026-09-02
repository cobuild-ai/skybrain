"""Clean Architecture Review Lens — Uncle Bob's dependency rules."""

from skybrain.review.lenses.base import ReviewLens
from skybrain.review.models import Category


class CleanArchitectureLens(ReviewLens):
    """Analyzes code against Clean Architecture dependency rules.

    Focus areas: dependency direction, layer boundary violations,
    abstraction levels, interface segregation, and coupling.
    """

    @property
    def name(self) -> str:
        return "Clean Architecture"

    @property
    def category(self) -> Category:
        return Category.CLEAN_ARCHITECTURE

    @property
    def system_prompt(self) -> str:
        return (
            "You are a senior software architect specializing in Clean Architecture "
            "(Uncle Bob / Robert C. Martin). You enforce strict architectural "
            "discipline.\n\n"
            "Analyze the code for these specific violations:\n"
            "1. **Dependency Rule**: Do dependencies point inward? Do inner layers "
            "import from outer layers (framework, DB, UI)?\n"
            "2. **Layer Separation**: Are domain entities, use cases, interface "
            "adapters, and frameworks properly separated?\n"
            "3. **Abstraction Level**: Does each module operate at a single, "
            "consistent level of abstraction?\n"
            "4. **Interface Segregation**: Are interfaces minimal and focused, "
            "or do they force implementations to depend on methods they don't use?\n"
            "5. **Global State**: Are there module-level mutable globals that "
            "should be encapsulated in classes?\n"
            "6. **Coupling**: Are components tightly coupled through concrete "
            "classes instead of abstractions/protocols?\n"
            "7. **Testability**: Can each component be unit-tested in isolation "
            "without starting servers or loading real models?\n\n"
            "Be precise: cite specific import statements, class names, and "
            "the exact architectural principle violated."
        )
