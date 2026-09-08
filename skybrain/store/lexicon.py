"""Project Lexicon Harvester and Query Expansion Engine."""

import re
from typing import Dict, List, Set


# Common software & governance patterns for candidate term extraction
DOMAIN_PATTERNS = [
    re.compile(r"\b[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+\b"),     # e.g., 3-Tier, Zero-Fake, CI-CD
    re.compile(r"\b[A-Z]{3,}\b"),                           # e.g., PAD, FTS, VLM, RAG, MCP, API
    re.compile(r"\b(?:Gate|Tier|Phase|Stage)\s+[0-9A-Za-z]+\b", re.IGNORECASE),  # e.g., Gate 1, Tier 3
    re.compile(r"`([a-zA-Z0-9_\-\./]+)`"),                  # code backticks e.g., `make stage-pr`
]

STOPWORDS: Set[str] = {
    "THE", "AND", "FOR", "WITH", "THIS", "THAT", "FROM", "HTTP", "HTTPS", "FILE", "TRUE", "FALSE", "NULL"
}


class LexiconHarvester:
    """Extracts project-specific domain terms and handles query expansion."""

    @staticmethod
    def harvest(text: str) -> Dict[str, int]:
        """Harvests candidate domain terms from document text."""
        term_counts: Dict[str, int] = {}

        for pattern in DOMAIN_PATTERNS:
            for match in pattern.finditer(text):
                term = match.group(1) if match.groups() else match.group(0)
                term = term.strip().strip("`").strip()
                upper = term.upper()
                if len(term) < 2 or upper in STOPWORDS:
                    continue
                term_counts[term] = term_counts.get(term, 0) + 1

        return term_counts

    @staticmethod
    def expand_query(query: str, harvested_terms: List[Dict[str, any]]) -> str:
        """Expands query with matched high-frequency project terms."""
        expanded_tokens = [query]
        query_lower = query.lower()

        for row in harvested_terms[:20]:
            term = row["term"]
            # If part of the term matches the query words, add the exact term
            if term.lower() in query_lower and term not in query:
                expanded_tokens.append(term)

        return " ".join(expanded_tokens)
