from __future__ import annotations

from dataclasses import dataclass
import math

from report_book_svg_base import PALETTE, esc


@dataclass(frozen=True)
class PlotArea:
    x: float
    y: float
    width: float
    height: float

    @property
    def x2(self) -> float:
        return self.x + self.width

    @property
    def y2(self) -> float:
        return self.y + self.height


def nice_ticks(min_value: float, max_value: float, approx_steps: int = 5) -> list[float]:
    if approx_steps < 2:
        approx_steps = 2
    if math.isclose(min_value, max_value):
        return [round(min_value, 2), round(min_value + 1, 2)]
    span = max_value - min_value
    raw_step = span / max(approx_steps - 1, 1)
    step = _nice_step(raw_step)
    start = math.floor(min_value / step) * step
    end = math.ceil(max_value / step) * step
    ticks: list[float] = []
    value = start
    while value <= end + step * 0.25:
        ticks.append(round(value, 6))
        value += step
    return ticks


def pad_domain(min_value: float, max_value: float, ratio: float = 0.08) -> tuple[float, float]:
    if math.isclose(min_value, max_value):
        pad = max(1.0, abs(min_value) * ratio or 1.0)
        return min_value - pad, max_value + pad
    span = max_value - min_value
    pad = span * ratio
    return min_value - pad, max_value + pad


def scale_x(value: float, domain: tuple[float, float], area: PlotArea) -> float:
    return _scale_linear(value, domain[0], domain[1], area.x, area.x2)


def scale_y(value: float, domain: tuple[float, float], area: PlotArea) -> float:
    return _scale_linear(value, domain[0], domain[1], area.y2, area.y)


def render_plot_shell(
    area: PlotArea,
    *,
    x_ticks: list[float],
    y_ticks: list[float],
    x_domain: tuple[float, float],
    y_domain: tuple[float, float],
    x_label: str,
    y_label: str,
    x_formatter,
    y_formatter,
) -> str:
    parts = [
        f'<rect x="{area.x:.1f}" y="{area.y:.1f}" width="{area.width:.1f}" height="{area.height:.1f}" fill="#FFFFFF" stroke="{PALETTE["line"]}" stroke-width="1.2"/>'
    ]
    for tick in y_ticks:
        if not _in_domain(tick, y_domain):
            continue
        y = scale_y(tick, y_domain, area)
        parts.append(
            f'<line x1="{area.x:.1f}" y1="{y:.1f}" x2="{area.x2:.1f}" y2="{y:.1f}" stroke="#E6EDF5" stroke-width="1"/>'
        )
        parts.append(
            f'<text class="s" x="{area.x - 10:.1f}" y="{y + 4:.1f}" text-anchor="end">{esc(y_formatter(tick))}</text>'
        )
    for tick in x_ticks:
        if not _in_domain(tick, x_domain):
            continue
        x = scale_x(tick, x_domain, area)
        parts.append(
            f'<line x1="{x:.1f}" y1="{area.y:.1f}" x2="{x:.1f}" y2="{area.y2:.1f}" stroke="#F1F5F9" stroke-width="1"/>'
        )
        parts.append(
            f'<text class="s" x="{x:.1f}" y="{area.y2 + 20:.1f}" text-anchor="middle">{esc(x_formatter(tick))}</text>'
        )
    parts.append(
        f'<text class="s" x="{area.x + area.width / 2:.1f}" y="{area.y2 + 44:.1f}" text-anchor="middle">{esc(x_label)}</text>'
    )
    parts.append(
        f'<text class="s" x="{area.x - 52:.1f}" y="{area.y + area.height / 2:.1f}" text-anchor="middle" transform="rotate(-90 {area.x - 52:.1f} {area.y + area.height / 2:.1f})">{esc(y_label)}</text>'
    )
    return "".join(parts)


def render_phase_band(
    area: PlotArea,
    *,
    start: float,
    end: float,
    x_domain: tuple[float, float],
    fill: str,
    label: str = "",
) -> str:
    x1 = scale_x(start, x_domain, area)
    x2 = scale_x(end, x_domain, area)
    parts = [
        f'<rect x="{x1:.1f}" y="{area.y:.1f}" width="{max(x2 - x1, 0):.1f}" height="{area.height:.1f}" fill="{fill}" opacity="0.45"/>'
    ]
    if label:
        parts.append(
            f'<text class="s" x="{(x1 + x2) / 2:.1f}" y="{area.y + 18:.1f}" text-anchor="middle">{esc(label)}</text>'
        )
    return "".join(parts)


def render_line_series(
    points: list[tuple[float, float]],
    *,
    x_domain: tuple[float, float],
    y_domain: tuple[float, float],
    area: PlotArea,
    color: str,
    width: float = 3.0,
    show_points: bool = True,
) -> str:
    mapped = [
        (
            scale_x(x_value, x_domain, area),
            scale_y(y_value, y_domain, area),
        )
        for x_value, y_value in points
    ]
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in mapped)
    parts = [
        f'<polyline points="{esc(polyline)}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>'
    ]
    if show_points:
        parts.extend(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{color}" stroke="#FFFFFF" stroke-width="1.2"/>'
            for x, y in mapped
        )
    return "".join(parts)


def render_horizontal_marker(
    area: PlotArea,
    *,
    value: float,
    y_domain: tuple[float, float],
    color: str,
    label: str,
) -> str:
    y = scale_y(value, y_domain, area)
    return (
        f'<line x1="{area.x:.1f}" y1="{y:.1f}" x2="{area.x2:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="2" stroke-dasharray="8 6"/>'
        f'<text class="s" x="{area.x + 6:.1f}" y="{y - 8:.1f}">{esc(label)}</text>'
    )


def render_vertical_marker(
    area: PlotArea,
    *,
    value: float,
    x_domain: tuple[float, float],
    color: str,
    label: str,
) -> str:
    x = scale_x(value, x_domain, area)
    return (
        f'<line x1="{x:.1f}" y1="{area.y:.1f}" x2="{x:.1f}" y2="{area.y2:.1f}" stroke="{color}" stroke-width="2.5" stroke-dasharray="8 6"/>'
        f'<text class="s" x="{x + 6:.1f}" y="{area.y + 18:.1f}">{esc(label)}</text>'
    )


def render_legend(x: float, y: float, items: list[tuple[str, str]]) -> str:
    parts = []
    offset = 0.0
    for label, color in items:
        parts.append(
            f'<line x1="{x + offset:.1f}" y1="{y:.1f}" x2="{x + offset + 18:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="3"/>'
            f'<circle cx="{x + offset + 9:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>'
            f'<text class="s" x="{x + offset + 26:.1f}" y="{y + 4:.1f}">{esc(label)}</text>'
        )
        offset += 112 + len(label) * 5.5
    return "".join(parts)


def render_grouped_bars(
    area: PlotArea,
    *,
    categories: list[str],
    series: list[tuple[str, str, list[float]]],
    y_domain: tuple[float, float],
    y_ticks: list[float],
    y_label: str,
    x_label: str = "指标类别",
    formatter,
) -> str:
    x_ticks = list(range(len(categories)))
    x_domain = (-0.6, len(categories) - 0.4)
    parts = [
        render_plot_shell(
            area,
            x_ticks=x_ticks,
            y_ticks=y_ticks,
            x_domain=x_domain,
            y_domain=y_domain,
            x_label=x_label,
            y_label=y_label,
            x_formatter=lambda value: categories[int(value)] if int(value) < len(categories) else "",
            y_formatter=formatter,
        )
    ]
    group_width = 0.68
    bar_width = group_width / max(len(series), 1)
    for group_index, _ in enumerate(categories):
        group_left = group_index - group_width / 2
        for series_index, (_label, color, values) in enumerate(series):
            left = group_left + series_index * bar_width
            right = left + bar_width * 0.9
            x1 = scale_x(left, x_domain, area)
            x2 = scale_x(right, x_domain, area)
            y1 = scale_y(values[group_index], y_domain, area)
            height = area.y2 - y1
            parts.append(
                f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{max(x2 - x1, 1):.1f}" height="{max(height, 0):.1f}" rx="6" fill="{color}" opacity="0.92"/>'
            )
            parts.append(
                f'<text class="s" x="{(x1 + x2) / 2:.1f}" y="{y1 - 8:.1f}" text-anchor="middle">{esc(formatter(values[group_index]))}</text>'
            )
    return "".join(parts)


def _nice_step(raw_step: float) -> float:
    if raw_step <= 0:
        return 1.0
    magnitude = 10 ** math.floor(math.log10(raw_step))
    residual = raw_step / magnitude
    if residual <= 1:
        factor = 1
    elif residual <= 2:
        factor = 2
    elif residual <= 5:
        factor = 5
    else:
        factor = 10
    return factor * magnitude


def _in_domain(value: float, domain: tuple[float, float]) -> bool:
    epsilon = max(abs(domain[1] - domain[0]) * 1e-6, 1e-9)
    return domain[0] - epsilon <= value <= domain[1] + epsilon


def _scale_linear(value: float, src_min: float, src_max: float, dst_min: float, dst_max: float) -> float:
    if math.isclose(src_min, src_max):
        return (dst_min + dst_max) / 2
    ratio = (value - src_min) / (src_max - src_min)
    return dst_min + ratio * (dst_max - dst_min)
