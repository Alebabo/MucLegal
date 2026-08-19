from muclegal.normalize.core import (
    NORMALIZER_VERSION,
    NormalizationConfig,
    NormalizationError,
    NormalizedDocument,
    VolatileRule,
    normalize_html,
    normalize_plain_text,
)
from muclegal.normalize.clauses import Clause, split_clauses

__all__ = [
    "NORMALIZER_VERSION",
    "NormalizationConfig",
    "NormalizationError",
    "NormalizedDocument",
    "VolatileRule",
    "normalize_html",
    "normalize_plain_text",
    "Clause",
    "split_clauses",
]

