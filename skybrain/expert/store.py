"""Consensus Context Store.

Manages frozen, tamper-proof ConsensusContext baselines.
Once a set of findings passes the strict 2/3 consensus threshold, it is frozen
and persisted. Subsequent requests (follow-up evaluations, refactoring instructions)
MUST exclusively build upon this frozen baseline, without intermediate modifications.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Sequence

from skybrain.expert.models import AssessmentFinding, ConsensusContext, Severity

logger = logging.getLogger("skybrain.expert.store")

DEFAULT_CONSENSUS_CACHE_DIR = Path.home() / ".skybrain" / "cache" / "consensus"


class ConsensusContextStore:
    """Persistent and in-memory store for frozen ConsensusContexts."""

    def __init__(self, cache_dir: Optional[Path] = None, enabled: bool = True) -> None:
        self.cache_dir = cache_dir or DEFAULT_CONSENSUS_CACHE_DIR
        self.enabled = enabled
        self._memory_index: Dict[str, ConsensusContext] = {}
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def freeze(
        self,
        file_path: str,
        source_code: str,
        agreed_findings: Sequence[AssessmentFinding],
        generation: int = 1,
    ) -> ConsensusContext:
        """Freeze verified findings into an immutable ConsensusContext and persist it.

        The context_id is a deterministic SHA-256 digest of:
          - source_code content
          - sorted finding signatures
          - generation
        """
        # Deterministic digest
        hasher = hashlib.sha256()
        hasher.update(source_code.encode("utf-8"))
        hasher.update(f":gen{generation}:".encode("utf-8"))
        for f in sorted(agreed_findings, key=lambda x: (x.file, x.line or 0, x.rule_id)):
            hasher.update(f"{f.rule_id}:{f.line}:{f.description}".encode("utf-8"))
        context_id = hasher.hexdigest()[:16]

        context = ConsensusContext(
            context_id=context_id,
            file_path=file_path,
            source_code=source_code,
            agreed_findings=tuple(agreed_findings),
            generation=generation,
        )

        self._memory_index[context_id] = context

        if self.enabled:
            self._save_to_disk(context)

        logger.info(
            "❄️ Frozen ConsensusContext [%s] (Gen %d) with %d agreed facts",
            context_id,
            generation,
            len(agreed_findings),
        )
        return context

    def get(self, context_id: str) -> Optional[ConsensusContext]:
        """Retrieve a frozen context by ID (checks memory, then disk)."""
        if context_id in self._memory_index:
            return self._memory_index[context_id]

        if not self.enabled:
            return None

        file_path = self.cache_dir / f"{context_id}.json"
        if not file_path.exists():
            return None

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            context = self._deserialize(data)
            self._memory_index[context_id] = context
            return context
        except Exception as exc:
            logger.warning("Failed to read consensus context %s: %exc", context_id, exc)
            return None

    def get_latest_for_file(self, file_path: str) -> Optional[ConsensusContext]:
        """Find the latest generation consensus context for a file."""
        candidates = [
            c for c in self._memory_index.values()
            if c.file_path == file_path
        ]
        if candidates:
            return max(candidates, key=lambda c: (c.generation, c.created_at))

        # Scan disk directory
        if self.enabled and self.cache_dir.exists():
            for p in self.cache_dir.glob("*.json"):
                ctx = self.get(p.stem)
                if ctx and ctx.file_path == file_path:
                    candidates.append(ctx)

        if candidates:
            return max(candidates, key=lambda c: (c.generation, c.created_at))
        return None

    def _save_to_disk(self, ctx: ConsensusContext) -> None:
        target = self.cache_dir / f"{ctx.context_id}.json"
        data = {
            "context_id": ctx.context_id,
            "file_path": ctx.file_path,
            "source_code": ctx.source_code,
            "generation": ctx.generation,
            "created_at": ctx.created_at,
            "agreed_findings": [
                {
                    "file": f.file,
                    "line": f.line,
                    "rule_id": f.rule_id,
                    "principle": f.principle,
                    "description": f.description,
                    "suggestion": f.suggestion,
                    "severity": f.severity.name,
                    "lens_id": f.lens_id,
                    "confidence": f.confidence,
                    "finding_id": f.finding_id,
                }
                for f in ctx.agreed_findings
            ],
        }
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _deserialize(data: dict) -> ConsensusContext:
        findings = []
        for d in data.get("agreed_findings", []):
            findings.append(
                AssessmentFinding(
                    file=d["file"],
                    line=d.get("line"),
                    rule_id=d["rule_id"],
                    principle=d["principle"],
                    description=d["description"],
                    suggestion=d["suggestion"],
                    severity=Severity[d["severity"]],
                    lens_id=d.get("lens_id", "unknown"),
                    confidence=d.get("confidence", 1.0),
                    finding_id=d.get("finding_id", ""),
                )
            )
        return ConsensusContext(
            context_id=data["context_id"],
            file_path=data["file_path"],
            source_code=data["source_code"],
            agreed_findings=tuple(findings),
            generation=data.get("generation", 1),
            created_at=data.get("created_at", 0.0),
        )


# Global default store singleton
default_context_store = ConsensusContextStore()
