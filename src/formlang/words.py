from __future__ import annotations

from collections import deque

from .grammar import Grammar
from .parsing import nullable_set
from .transform import remove_epsilon

Word = tuple[str, ...]


def generate_words(g: Grammar, max_len: int, max_forms: int = 200_000) -> set[Word]:
    words: set[Word] = {()} if g.start in nullable_set(g) else set()
    g2 = remove_epsilon(g).grammar
    seen = {(g2.start,)}
    queue = deque(seen)
    while queue:
        form = queue.popleft()
        k = next((i for i, s in enumerate(form) if g2.is_nt(s)), None)
        if k is None:
            words.add(form)
            continue
        for rhs in g2.rules_for(form[k]):
            new = form[:k] + rhs + form[k + 1 :]
            if len(new) <= max_len and new not in seen:
                if len(seen) >= max_forms:
                    raise RuntimeError(f"перевищено ліміт {max_forms} словоформ; зменште --max-len")
                seen.add(new)
                queue.append(new)
    return words


def sort_words(ws) -> list[Word]:
    return sorted(ws, key=lambda w: (len(w), w))


def show_word(w: Word) -> str:
    if not w:
        return "ε"
    return "".join(w) if all(len(s) == 1 for s in w) else " ".join(w)


def show_language(ws, limit: int = 40) -> str:
    items = [show_word(w) for w in sort_words(ws)]
    if not items:
        return "∅"
    more = f", … (ще {len(items) - limit})" if len(items) > limit else ""
    return "{" + ", ".join(items[:limit]) + more + "}"
