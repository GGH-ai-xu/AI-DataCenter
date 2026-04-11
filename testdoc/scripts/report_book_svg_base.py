from __future__ import annotations

import html


PALETTE = {
    "bg": "#F4F7FB",
    "card": "#FFFFFF",
    "text": "#102033",
    "muted": "#566579",
    "line": "#D7E1EC",
    "blue": "#2563EB",
    "green": "#059669",
    "amber": "#D97706",
    "red": "#DC2626",
    "slate": "#64748B",
    "cyan": "#0891B2",
}


def esc(value: str) -> str:
    return html.escape(str(value), quote=True)


def svg_frame(title: str, subtitle: str, width: int, height: int, body: str) -> str:
    p = PALETTE
    style = (
        ".bg{fill:%s}.card{fill:%s;stroke:%s;stroke-width:1.4}"
        ".title{font:700 32px 'Microsoft YaHei','Noto Sans SC',sans-serif;fill:%s}"
        ".subtitle{font:500 16px 'Microsoft YaHei','Noto Sans SC',sans-serif;fill:%s}"
        ".h{font:700 18px 'Microsoft YaHei','Noto Sans SC',sans-serif;fill:%s}"
        ".p{font:500 14px 'Microsoft YaHei','Noto Sans SC',sans-serif;fill:%s}"
        ".s{font:500 12px 'Microsoft YaHei','Noto Sans SC',sans-serif;fill:%s}"
        ".k{font:700 14px 'Microsoft YaHei','Noto Sans SC',sans-serif;fill:%s}"
    ) % (p["bg"], p["card"], p["line"], p["text"], p["muted"], p["text"], p["muted"], p["muted"], p["text"])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f"<style>{style}</style>"
        f'<rect class="bg" x="0" y="0" width="{width}" height="{height}" rx="28"/>'
        f'<text class="title" x="42" y="58">{esc(title)}</text>'
        f'<text class="subtitle" x="42" y="86">{esc(subtitle)}</text>'
        f"{body}</svg>"
    )


def text_block(x: int, y: int, lines: list[str], cls: str = "p", line_height: int = 18) -> str:
    parts = []
    for index, line in enumerate(lines):
        dy = 0 if index == 0 else line_height
        parts.append(f'<tspan x="{x}" dy="{dy}">{esc(line)}</tspan>')
    return f'<text class="{cls}" x="{x}" y="{y}">{"".join(parts)}</text>'


def card(x: int, y: int, width: int, height: int, title: str, lines: list[str], accent: str) -> str:
    return (
        f'<rect class="card" x="{x}" y="{y}" width="{width}" height="{height}" rx="22"/>'
        f'<rect x="{x + 18}" y="{y + 18}" width="86" height="10" rx="5" fill="{accent}"/>'
        f'<text class="h" x="{x + 18}" y="{y + 52}">{esc(title)}</text>'
        f'{text_block(x + 18, y + 78, lines, "p", 22)}'
    )


def chip(x: int, y: int, width: int, label: str, value: str, accent: str) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="64" rx="18" fill="{PALETTE["card"]}" stroke="{accent}" stroke-width="1.4"/>'
        f'<text class="s" x="{x + 18}" y="{y + 25}">{esc(label)}</text>'
        f'<text class="h" x="{x + 18}" y="{y + 47}" fill="{accent}">{esc(value)}</text>'
    )


def arrow(x1: int, y1: int, x2: int, y2: int, color: str) -> str:
    head = f"{x2},{y2} {x2 - 12},{y2 - 6} {x2 - 12},{y2 + 6}"
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2 - 12}" y2="{y2}" stroke="{color}" stroke-width="4" stroke-linecap="round"/>'
        f'<polygon points="{head}" fill="{color}"/>'
    )


def bar(x: int, base_y: int, width: int, height: int, value: int, max_value: int, color: str, label: str) -> str:
    scaled = 0 if max_value <= 0 else max(8, int(height * value / max_value))
    y = base_y - scaled
    return (
        f'<rect x="{x}" y="{base_y - height}" width="{width}" height="{height}" rx="14" fill="#E7EEF7"/>'
        f'<rect x="{x}" y="{y}" width="{width}" height="{scaled}" rx="14" fill="{color}"/>'
        f'<text class="k" x="{x}" y="{base_y + 26}">{esc(label)}</text>'
        f'<text class="s" x="{x}" y="{base_y + 44}">{value}</text>'
    )


def matrix_cell(x: int, y: int, width: int, height: int, fill: str, text: str) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="10" fill="{fill}" stroke="{PALETTE["line"]}" stroke-width="1"/>'
        f'<text class="s" x="{x + 14}" y="{y + 23}" fill="{PALETTE["text"]}">{esc(text)}</text>'
    )
