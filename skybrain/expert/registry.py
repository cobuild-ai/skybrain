"""Registry for Expert Lenses (Knowledge Layers).

Allows dynamic registration, retrieval by domain/id, and custom extension.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, Optional

from skybrain.expert.models import EvaluationCriterion, ExpertLens, Severity
from skybrain.expert.specs import STANDARD_EXPERT_LENSES


class LensRegistry:
    """Registry maintaining available Knowledge Layers for the ExpertEngine."""

    def __init__(self, initial_lenses: Optional[Iterable[ExpertLens]] = None) -> None:
        self._lenses: Dict[str, ExpertLens] = {}
        # Register standard default lenses
        lenses = initial_lenses if initial_lenses is not None else STANDARD_EXPERT_LENSES
        for lens in lenses:
            self.register(lens)

    def register(self, lens: ExpertLens) -> None:
        """Register a new ExpertLens."""
        self._lenses[lens.lens_id] = lens

    def get(self, lens_id: str) -> Optional[ExpertLens]:
        """Retrieve a lens by unique identifier."""
        return self._lenses.get(lens_id)

    def get_by_name_or_domain(self, query: str) -> list[ExpertLens]:
        """Lookup lenses by partial name or domain."""
        q = query.lower()
        return [
            l for l in self._lenses.values()
            if q in l.lens_id.lower() or q in l.name.lower() or q in l.domain.lower()
        ]

    def all_lenses(self) -> list[ExpertLens]:
        """Return all registered lenses."""
        return list(self._lenses.values())

    def load_from_json(self, json_path: Path | str) -> ExpertLens:
        """Load an ExpertLens dynamically from a JSON definition file."""
        path = Path(json_path)
        data = json.loads(path.read_text(encoding="utf-8"))

        criteria = []
        for c in data.get("criteria", []):
            criteria.append(
                EvaluationCriterion(
                    rule_id=c["rule_id"],
                    name=c["name"],
                    question=c["question"],
                    negative_signals=tuple(c.get("negative_signals", [])),
                    positive_signals=tuple(c.get("positive_signals", [])),
                    severity=Severity[c.get("severity", "MEDIUM").upper()],
                )
            )

        lens = ExpertLens(
            lens_id=data["lens_id"],
            name=data["name"],
            domain=data.get("domain", "custom"),
            persona=data.get("persona", "Software Expert"),
            criteria=tuple(criteria),
            version=data.get("version", "1.0.0"),
        )
        self.register(lens)
        return lens


# Default global registry singleton
default_registry = LensRegistry()
