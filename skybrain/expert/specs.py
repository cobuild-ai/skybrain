"""Pre-defined Expert Lenses (Knowledge Layers).

Each lens represents an index of specialized software engineering principles,
decoupled into atomic criteria with concrete negative/positive signals.
"""

from __future__ import annotations

from skybrain.expert.models import EvaluationCriterion, ExpertLens, Severity

# ── 1. Clean Code Lens (Robert C. Martin) ───────────────────────────
CLEAN_CODE_LENS = ExpertLens(
    lens_id="clean_code_v1",
    name="Clean Code",
    domain="code_quality",
    persona="Master Craftsman specializing in Robert C. Martin's Clean Code principles",
    criteria=(
        EvaluationCriterion(
            rule_id="CC-SRP-001",
            name="Single Responsibility Principle (SRP)",
            question="Does this class or function have more than one reason to change?",
            negative_signals=("manager", "helper", "process_and_save", "do_everything", "and_"),
            positive_signals=("focused function", "single action", "pure function"),
            severity=Severity.HIGH,
        ),
        EvaluationCriterion(
            rule_id="CC-NAM-002",
            name="Intention-Revealing Naming",
            question="Are variable, function, and class names ambiguous, cryptic, or abbreviated?",
            negative_signals=("tmp", "data", "ret", "x", "val", "flag", "do_it"),
            positive_signals=("descriptive", "noun for class", "verb for function"),
            severity=Severity.MEDIUM,
        ),
        EvaluationCriterion(
            rule_id="CC-LEN-003",
            name="Small Focused Functions",
            question="Is this function longer than 25 lines or doing multiple levels of abstraction?",
            negative_signals=("nested loops", "deep indentation > 3", "long block"),
            positive_signals=("short < 20 lines", "single level of abstraction"),
            severity=Severity.LOW,
        ),
        EvaluationCriterion(
            rule_id="CC-DRY-004",
            name="Don't Repeat Yourself (DRY)",
            question="Is there duplicated logic, boilerplate, or copy-pasted blocks?",
            negative_signals=("identical branch", "repeated formatting", "duplicate checks"),
            positive_signals=("extracted helper", "reusable utility"),
            severity=Severity.MEDIUM,
        ),
        EvaluationCriterion(
            rule_id="CC-MAG-005",
            name="Avoid Magic Literals",
            question="Are raw numbers, timeouts, or magic strings hardcoded without named constants?",
            negative_signals=("raw numbers", "hardcoded timeout 300", "magic string"),
            positive_signals=("UPPER_SNAKE_CASE constant", "enum"),
            severity=Severity.LOW,
        ),
        EvaluationCriterion(
            rule_id="CC-ERR-006",
            name="Specific Error Handling",
            question="Does the code catch bare Exception without re-raising or context?",
            negative_signals=("except Exception: pass", "bare except:", "swallowed error"),
            positive_signals=("specific error", "contextual log", "custom exception"),
            severity=Severity.HIGH,
        ),
    ),
)

# ── 2. Clean Architecture Lens (Uncle Bob) ──────────────────────────
CLEAN_ARCHITECTURE_LENS = ExpertLens(
    lens_id="clean_arch_v1",
    name="Clean Architecture",
    domain="architecture",
    persona="Principal Software Architect enforcing Clean Architecture dependency boundaries",
    criteria=(
        EvaluationCriterion(
            rule_id="CA-DEP-001",
            name="Inward Dependency Rule",
            question="Does a core domain or business logic module import from outer frameworks, DB, or UI?",
            negative_signals=("domain imports fastapi", "core imports sqlalchemy", "use_case imports ui"),
            positive_signals=("pure python domain", "interfaces/protocols in core"),
            severity=Severity.CRITICAL,
        ),
        EvaluationCriterion(
            rule_id="CA-BND-002",
            name="Layer Boundary Isolation",
            question="Are use cases directly manipulating HTTP request/response objects or DB cursors?",
            negative_signals=("use_case takes Request", "domain returns JSONResponse"),
            positive_signals=("DTO", "plain dataclass", "isolated ports and adapters"),
            severity=Severity.HIGH,
        ),
        EvaluationCriterion(
            rule_id="CA-DIP-003",
            name="Dependency Inversion Principle (DIP)",
            question="Are high-level modules tightly coupled to concrete implementations rather than abstractions?",
            negative_signals=("direct instantiating concrete client", "hardcoded dependency"),
            positive_signals=("constructor injection", "Protocol", "ABC interface"),
            severity=Severity.HIGH,
        ),
        EvaluationCriterion(
            rule_id="CA-GLO-004",
            name="Encapsulation of Global State",
            question="Are there mutable module-level global variables shared across callers?",
            negative_signals=("global _instance", "module-level mutable list/dict"),
            positive_signals=("encapsulated in class", "thread-safe state"),
            severity=Severity.MEDIUM,
        ),
    ),
)

# ── 3. Rule of Test Code Creation Lens (TDD / FIRST) ────────────────
TEST_RULES_LENS = ExpertLens(
    lens_id="test_rules_v1",
    name="Test Engineering Rules",
    domain="testing",
    persona="Senior QA/SDET Architect specializing in reliable test automation and F.I.R.S.T rules",
    criteria=(
        EvaluationCriterion(
            rule_id="TR-FIR-001",
            name="F.I.R.S.T Principles Compliance",
            question="Is the test slow, order-dependent, unrepeatable, or manual?",
            negative_signals=("sleep in test", "order dependent", "hits external network in unit test"),
            positive_signals=("fast < 50ms", "hermetic", "deterministic"),
            severity=Severity.HIGH,
        ),
        EvaluationCriterion(
            rule_id="TR-AAA-002",
            name="Arrange-Act-Assert (AAA) Structure",
            question="Is the test logic convoluted without clear setup, invocation, and verification sections?",
            negative_signals=("interleaved calls and asserts", "logic inside test", "looping inside assert"),
            positive_signals=("clean 3-block structure", "single act step"),
            severity=Severity.MEDIUM,
        ),
        EvaluationCriterion(
            rule_id="TR-ISO-003",
            name="Mock & Fake Isolation",
            question="Does the unit test rely on a running server, real filesystem writes, or global state?",
            negative_signals=("real network call", "real socket", "un-mocked global file write"),
            positive_signals=("mocked client", "in-memory fake", "tmp_path fixture"),
            severity=Severity.HIGH,
        ),
        EvaluationCriterion(
            rule_id="TR-ASP-004",
            name="Assertion Precision",
            question="Does the test use vague assertions like `assert result is not None` instead of exact equality?",
            negative_signals=("assert bool(res)", "assert res is not None", "missing specific field check"),
            positive_signals=("assert res.status == 200", "assert len(items) == 3"),
            severity=Severity.LOW,
        ),
    ),
)

# ── 4. Design Patterns & MVC/MVVM Lens ──────────────────────────────
DESIGN_PATTERNS_LENS = ExpertLens(
    lens_id="design_patterns_v1",
    name="Design Patterns & Structural Integrity",
    domain="design_patterns",
    persona="Software Engineering Consultant specializing in GoF patterns and MVC/MVVM separations",
    criteria=(
        EvaluationCriterion(
            rule_id="DP-MVC-001",
            name="Separation of Concerns (MVC / Presentation vs Domain)",
            question="Is presentation or serialization logic mixed into data processing entities?",
            negative_signals=("controller contains raw SQL", "model builds HTML/JSON string"),
            positive_signals=("controller delegates to service", "serializer layer separated"),
            severity=Severity.HIGH,
        ),
        EvaluationCriterion(
            rule_id="DP-STR-002",
            name="Strategy Pattern for Variability",
            question="Does the code use large switch/if-elif chains for algorithm variants instead of polymorphism?",
            negative_signals=("if type == 'a': ... elif type == 'b':", "giant conditional ladder"),
            positive_signals=("Strategy interface", "polymorphic dispatch"),
            severity=Severity.MEDIUM,
        ),
        EvaluationCriterion(
            rule_id="DP-FAC-003",
            name="Factory / Builder for Complex Instantiations",
            question="Are complex objects with multiple configurations created via giant parameter lists?",
            negative_signals=("constructor with > 7 params", "complex init logic in caller"),
            positive_signals=("Builder pattern", "Factory class/method"),
            severity=Severity.LOW,
        ),
    ),
)

# ── 5. Security & Defensive Programming Lens ────────────────────────
SECURITY_LENS = ExpertLens(
    lens_id="security_defensive_v1",
    name="Security & Defensive Architecture",
    domain="security",
    persona="Application Security Auditor enforcing OWASP Top 10 and defensive programming standards",
    criteria=(
        EvaluationCriterion(
            rule_id="SC-INP-001",
            name="Input Validation & Boundary Checking",
            question="Are untrusted inputs from users or network processed without type/length validation?",
            negative_signals=("unescaped path traversal", "unchecked string formatting", "eval()", "exec()"),
            positive_signals=("pydantic validation", "path.resolve() sandbox check"),
            severity=Severity.CRITICAL,
        ),
        EvaluationCriterion(
            rule_id="SC-SEC-002",
            name="Secret & Credential Protection",
            question="Are API keys, tokens, or internal passwords embedded or logged in plaintext?",
            negative_signals=("sk-", "password = ", "logger.info(token)", "hardcoded secret"),
            positive_signals=("env variable", "secret manager", "masked logging"),
            severity=Severity.CRITICAL,
        ),
        EvaluationCriterion(
            rule_id="SC-RES-003",
            name="Resource Leak & Lifecycle Safety",
            question="Are files, sockets, locks, or child processes opened without guaranteed release?",
            negative_signals=("open() without with", "lock.acquire() without try/finally", "zombie process"),
            positive_signals=("context manager", "try-finally release"),
            severity=Severity.HIGH,
        ),
    ),
)

# ── 6. Performance & Scalability Lens ───────────────────────────────
PERFORMANCE_LENS = ExpertLens(
    lens_id="performance_v1",
    name="Performance & Resource Optimization",
    domain="performance",
    persona="Systems Performance Specialist focusing on memory footprint, algorithmic complexity, and I/O throughput",
    criteria=(
        EvaluationCriterion(
            rule_id="PF-ALG-001",
            name="Algorithmic Complexity & Hot Paths",
            question="Are there quadratic O(N^2) loops or repeated lookups in lists instead of sets/dicts?",
            negative_signals=("nested loop over large list", "linear search in hot path", "item in list inside loop"),
            positive_signals=("dict lookup O(1)", "set membership", "generator expression"),
            severity=Severity.HIGH,
        ),
        EvaluationCriterion(
            rule_id="PF-MEM-002",
            name="Memory Allocation & Leakage Prevention",
            question="Does the code keep growing global caches or accumulate heavy objects without bounds?",
            negative_signals=("unbounded cache list", "retaining heavy tensor/image in memory"),
            positive_signals=("bounded LRU cache", "weakref", "explicit cleanup"),
            severity=Severity.MEDIUM,
        ),
        EvaluationCriterion(
            rule_id="PF-LCK-003",
            name="Lock Contention & Blocking Operations",
            question="Are expensive I/O operations (network, disk, model load) held inside a thread lock?",
            negative_signals=("urllib inside with lock", "file read inside critical section"),
            positive_signals=("minimal critical section", "lock only around shared state mutation"),
            severity=Severity.HIGH,
        ),
    ),
)

# Default registry list
STANDARD_EXPERT_LENSES = (
    CLEAN_CODE_LENS,
    CLEAN_ARCHITECTURE_LENS,
    TEST_RULES_LENS,
    DESIGN_PATTERNS_LENS,
    SECURITY_LENS,
    PERFORMANCE_LENS,
)
