from __future__ import annotations

from dataclasses import dataclass
from html import escape

from .grammar import Grammar
from .parsing import Tree


@dataclass
class Source:

    text: str
    spans: list[tuple[int, int, int, int]]

    def fragment(self, t: Tree) -> dict | None:
        if t.start == t.end:
            return None
        a, b = self.spans[t.start], self.spans[t.end - 1]
        end_line, end_col = _line_col(self.text, b[1])
        return {
            "start": {"offset": a[0], "line": a[2], "col": a[3]},
            "end": {"offset": b[1], "line": end_line, "col": end_col},
            "text": self.text[a[0] : b[1]],
        }


def _line_col(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    return line, offset - (text.rfind("\n", 0, offset) + 1) + 1


class Renderer:
    def __init__(self, g: Grammar, word: tuple[str, ...], source: Source | None = None):
        self.g, self.word, self.source = g, word, source

    def label(self, t: Tree) -> str:
        if t.is_epsilon:
            return "ε"
        if t.terminal:
            if self.source:
                a, b, _, _ = self.source.spans[t.start]
                return self.source.text[a:b]
            return t.symbol
        return self.g.show_symbol(t.symbol)

    def leaf_yield(self, t: Tree) -> list[str]:
        return [self.label(x) for x in t.leaves() if not x.is_epsilon]

    def text(self, t: Tree) -> str:
        lines: list[str] = []

        def walk(node: Tree, prefix: str, last: bool, root: bool) -> None:
            mark = "" if root else ("└── " if last else "├── ")
            extra = ""
            if self.source and not node.terminal and (f := self.source.fragment(node)):
                extra = f"   [{f['start']['line']}:{f['start']['col']}–{f['end']['line']}:{f['end']['col']}]"
            lines.append(prefix + mark + self.label(node) + extra)
            child_prefix = prefix + ("" if root else ("    " if last else "│   "))
            for i, c in enumerate(node.children):
                walk(c, child_prefix, i == len(node.children) - 1, False)

        walk(t, "", True, True)
        return "\n".join(lines)

    def to_dict(self, t: Tree) -> dict:
        d: dict = {
            "symbol": t.symbol,
            "kind": "epsilon" if t.is_epsilon else "terminal" if t.terminal else "nonterminal",
            "label": self.label(t),
            "span": [t.start, t.end],
        }
        if self.source and (f := self.source.fragment(t)):
            d["source"] = f
        if t.children:
            d["children"] = [self.to_dict(c) for c in t.children]
        return d

    def dot(self, t: Tree) -> str:
        out = ["digraph parse_tree {", "  node [fontname=\"Helvetica\"];"]
        counter = iter(range(10**9))

        def walk(node: Tree) -> str:
            nid = f"n{next(counter)}"
            shape = "plaintext" if node.terminal else "ellipse"
            lab = self.label(node).replace("\\", "\\\\").replace('"', '\\"')
            out.append(f'  {nid} [label="{lab}", shape={shape}];')
            for c in node.children:
                out.append(f"  {nid} -> {walk(c)};")
            return nid

        walk(t)
        out.append("}")
        return "\n".join(out)

    def svg(self, t: Tree) -> str:
        char_w, gap, level_h, pad = 8, 14, 60, 20
        pos: dict[int, tuple[float, int]] = {}
        cursor = [pad]

        def width(node: Tree) -> float:
            return len(self.label(node)) * char_w + 12

        def layout(node: Tree, depth: int) -> float:
            if not node.children:
                w = width(node)
                x = cursor[0] + w / 2
                cursor[0] += w + gap
            else:
                xs = [layout(c, depth + 1) for c in node.children]
                x = (xs[0] + xs[-1]) / 2
            pos[id(node)] = (x, depth)
            return x

        layout(t, 0)
        height = (t.depth() - 1) * level_h + 2 * pad + 20
        total_w = max(cursor[0], width(t) + 2 * pad)
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:.0f}" height="{height}" '
            f'viewBox="0 0 {total_w:.0f} {height}" font-family="Helvetica, Arial, sans-serif" font-size="13">',
            '<rect width="100%" height="100%" fill="white"/>',
        ]

        def y(depth: int) -> float:
            return pad + 10 + depth * level_h

        def walk(node: Tree) -> None:
            x, d = pos[id(node)]
            for c in node.children:
                cx, cd = pos[id(c)]
                parts.append(
                    f'<line x1="{x:.1f}" y1="{y(d) + 9:.1f}" x2="{cx:.1f}" y2="{y(cd) - 11:.1f}" stroke="#888"/>'
                )
                walk(c)
            w = width(node)
            colour = "#1f5fa8" if not node.terminal else ("#999" if node.is_epsilon else "#b3261e")
            title = ""
            if self.source and (f := self.source.fragment(node)):
                title = f"<title>{escape(f['text'])}</title>"
            if not node.terminal:
                parts.append(
                    f'<g>{title}<rect x="{x - w / 2:.1f}" y="{y(d) - 11:.1f}" width="{w:.1f}" height="20" rx="9" '
                    f'fill="#eef4fb" stroke="{colour}"/>'
                )
            else:
                parts.append(f"<g>{title}")
            label = escape(self.label(node))
            parts.append(
                f'<text x="{x:.1f}" y="{y(d) + 4:.1f}" text-anchor="middle" fill="{colour}">{label}</text></g>'
            )

        walk(t)
        parts.append("</svg>")
        return "\n".join(parts)
