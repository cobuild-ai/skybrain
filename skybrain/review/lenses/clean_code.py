"""Clean Code Review Lens — Robert C. Martin's principles."""

from skybrain.review.lenses.base import ReviewLens
from skybrain.review.models import Category


class CleanCodeLens(ReviewLens):
    """Analyzes code against Robert C. Martin's Clean Code principles.

    Focus areas: naming conventions, function length, Single Responsibility,
    DRY violations, magic numbers, comment quality, and readability.
    """

    @property
    def name(self) -> str:
        return "Clean Code"

    @property
    def category(self) -> Category:
        return Category.CLEAN_CODE

    @property
    def system_prompt(self) -> str:
        return (
            "You are a senior software engineer and Clean Code expert. "
            "You rigorously apply Robert C. Martin's Clean Code principles.\n\n"
            "Analyze the code for these specific violations:\n"
            "1. **SRP (Single Responsibility Principle)**: Does each function/class "
            "have exactly one reason to change?\n"
            "2. **Naming**: Are variable, function, and class names self-documenting, "
            "intention-revealing, and free of abbreviations?\n"
            "3. **Function Length**: Are functions short (ideally < 20 lines) and "
            "doing one thing well?\n"
            "4. **DRY (Don't Repeat Yourself)**: Is there duplicated logic that "
            "should be extracted into a shared function?\n"
            "5. **Magic Numbers/Strings**: Are there unexplained literal values "
            "that should be named constants?\n"
            "6. **Error Handling**: Are exceptions handled specifically (not bare "
            "except) and do error messages provide enough context?\n"
            "7. **Comments**: Are comments explaining 'why' not 'what'? "
            "Is there dead/commented-out code?\n\n"
            "Be precise: cite specific line numbers, variable names, and "
            "the exact Clean Code principle violated."
        )
