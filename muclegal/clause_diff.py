from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from muclegal.normalize.clauses import Clause


@dataclass(frozen=True)
class ClausePair:
    previous: Clause | None
    current: Clause | None
    similarity: float


def pair_clause_changes(
    previous: tuple[Clause, ...], current: tuple[Clause, ...]
) -> tuple[ClausePair, ...]:
    """Pair changed clauses structurally, then by text similarity; omit unchanged hashes."""
    current_hashes = {clause.clause_hash for clause in current}
    previous_hashes = {clause.clause_hash for clause in previous}
    removed = [clause for clause in previous if clause.clause_hash not in current_hashes]
    added = [clause for clause in current if clause.clause_hash not in previous_hashes]
    available = set(range(len(added)))
    pairs: list[ClausePair] = []

    for old in removed:
        ranked: list[tuple[float, float, int]] = []
        for index in available:
            new = added[index]
            similarity = SequenceMatcher(None, old.text, new.text).ratio()
            same_heading = bool(old.heading_path and old.heading_path == new.heading_path)
            ordinal_proximity = 1 / (1 + abs(old.ordinal - new.ordinal))
            score = similarity + (0.5 if same_heading else 0.0) + 0.1 * ordinal_proximity
            ranked.append((score, similarity, index))
        if not ranked:
            pairs.append(ClausePair(old, None, 0.0))
            continue
        _, similarity, best_index = max(ranked)
        best = added[best_index]
        structurally_same = (
            old.heading_path == best.heading_path and abs(old.ordinal - best.ordinal) <= 1
        )
        if similarity > 0.5 or structurally_same:
            available.remove(best_index)
            pairs.append(ClausePair(old, best, similarity))
        else:
            pairs.append(ClausePair(old, None, similarity))

    pairs.extend(ClausePair(None, added[index], 0.0) for index in sorted(available))
    return tuple(
        sorted(
            pairs,
            key=lambda pair: (
                pair.current.ordinal if pair.current else pair.previous.ordinal,
                pair.current is None,
            ),
        )
    )
