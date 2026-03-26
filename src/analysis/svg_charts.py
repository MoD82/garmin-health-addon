"""
Server-seitiger SVG-Chart-Generator — kein JavaScript erforderlich.
Alle Funktionen geben einen fertigen SVG-String zurück.
"""

CTL_DAYS = 42
ATL_DAYS = 7

PAD_L = 45
PAD_R = 15
PAD_T = 15
PAD_B = 30


def _scale(value: float, min_val: float, max_val: float, px_min: float, px_max: float) -> float:
    if max_val == min_val:
        return (px_min + px_max) / 2
    return px_min + (value - min_val) / (max_val - min_val) * (px_max - px_min)


def line_chart(
    labels: list[str],
    series: list[dict],
    width: int = 600,
    height: int = 200,
    title: str = "",
) -> str:
    """Liniendiagramm für Zeitreihen."""
    W = width
    H = height
    px_left = PAD_L
    px_right = W - PAD_R
    px_top = PAD_T
    px_bottom = H - PAD_B

    if not labels or not series:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">'
            f'<text x="{W//2}" y="{H//2}" text-anchor="middle" fill="#888" font-size="12">'
            f'Keine Daten</text></svg>'
        )

    all_vals = [v for s in series for v in s["values"] if v is not None]
    min_v = min(all_vals) if all_vals else 0
    max_v = max(all_vals) if all_vals else 1
    if max_v == min_v:
        max_v = min_v + 1

    n = len(labels)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1a1a2e;border-radius:6px;">'
    ]

    for i in range(5):
        val = min_v + (max_v - min_v) * i / 4
        y = _scale(val, min_v, max_v, px_bottom, px_top)
        parts.append(
            f'<line x1="{px_left}" y1="{y:.1f}" x2="{px_right}" y2="{y:.1f}" '
            f'stroke="#333" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{px_left - 5}" y="{y + 4:.1f}" text-anchor="end" '
            f'fill="#888" font-size="10">{val:.0f}</text>'
        )

    for idx in [0, n // 2, n - 1]:
        if idx < len(labels):
            x = _scale(idx, 0, n - 1, px_left, px_right)
            lbl = labels[idx][-5:] if len(labels[idx]) > 5 else labels[idx]
            parts.append(
                f'<text x="{x:.1f}" y="{H - 5}" text-anchor="middle" '
                f'fill="#888" font-size="10">{lbl}</text>'
            )

    for s in series:
        vals = s["values"]
        color = s.get("color", "#3498db")
        points = []
        for i, v in enumerate(vals):
            if v is None:
                continue
            x = _scale(i, 0, n - 1, px_left, px_right)
            y = _scale(v, min_v, max_v, px_bottom, px_top)
            points.append(f"{x:.1f},{y:.1f}")
        if points:
            pts_str = " ".join(points)
            parts.append(
                f'<polyline points="{pts_str}" fill="none" '
                f'stroke="{color}" stroke-width="2" stroke-linejoin="round"/>'
            )

    if title:
        parts.append(
            f'<text x="{px_left}" y="12" fill="#ccc" font-size="11">{title}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def bar_chart(
    labels: list[str],
    values: list[float],
    color: str = "#3498db",
    width: int = 600,
    height: int = 160,
    title: str = "",
) -> str:
    """Balkendiagramm für Wochenvolumen (immer 12 Balken)."""
    W = width
    H = height
    px_left = PAD_L
    px_right = W - PAD_R
    px_top = PAD_T
    px_bottom = H - PAD_B

    SLOTS = 12
    lbls = (labels + [""] * SLOTS)[:SLOTS]
    vals = (list(values) + [0.0] * SLOTS)[:SLOTS]

    max_v = max(vals) if any(v > 0 for v in vals) else 1.0
    bar_w = (px_right - px_left) / SLOTS

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1a1a2e;border-radius:6px;">'
    ]

    for i in range(3):
        val = max_v * i / 2
        y = _scale(val, 0, max_v, px_bottom, px_top)
        parts.append(
            f'<text x="{px_left - 5}" y="{y + 4:.1f}" text-anchor="end" '
            f'fill="#888" font-size="10">{val:.0f}</text>'
        )
        parts.append(
            f'<line x1="{px_left}" y1="{y:.1f}" x2="{px_right}" y2="{y:.1f}" '
            f'stroke="#333" stroke-width="1"/>'
        )

    for i, (lbl, val) in enumerate(zip(lbls, vals)):
        x = px_left + i * bar_w + bar_w * 0.1
        bw = bar_w * 0.8
        bar_h = _scale(val, 0, max_v, 0, px_bottom - px_top)
        y = px_bottom - bar_h
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" '
            f'fill="{color}" rx="2"/>'
        )
        if lbl:
            lx = x + bw / 2
            parts.append(
                f'<text x="{lx:.1f}" y="{H - 5}" text-anchor="middle" '
                f'fill="#888" font-size="9">{lbl}</text>'
            )

    if title:
        parts.append(
            f'<text x="{px_left}" y="12" fill="#ccc" font-size="11">{title}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def pmc_chart(
    pmc_data: list[dict],
    width: int = 700,
    height: int = 220,
) -> str:
    """
    Performance Management Chart: CTL (blau), ATL (rot), TSB (grün).
    Duale Y-Achse: links CTL/ATL, rechts TSB.
    """
    W = width
    H = height
    px_left = PAD_L
    px_right = W - PAD_R - 30
    px_top = PAD_T
    px_bottom = H - PAD_B

    if not pmc_data:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">'
            f'<text x="{W//2}" y="{H//2}" text-anchor="middle" fill="#888" font-size="12">'
            f'Keine Daten</text></svg>'
        )

    n = len(pmc_data)
    ctls = [d["ctl"] for d in pmc_data]
    atls = [d["atl"] for d in pmc_data]
    tsbs = [d["tsb"] for d in pmc_data]

    max_la = max(max(ctls), max(atls), 1.0)
    min_la = 0.0
    max_tsb = max(max(tsbs), 0.0) + 5
    min_tsb = min(min(tsbs), 0.0) - 5

    def yx(val: float) -> float:
        return _scale(val, min_la, max_la, px_bottom, px_top)

    def ytsb(val: float) -> float:
        return _scale(val, min_tsb, max_tsb, px_bottom, px_top)

    def xi(i: int) -> float:
        return _scale(i, 0, n - 1, px_left, px_right)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1a1a2e;border-radius:6px;">'
    ]

    y0 = ytsb(0.0)
    parts.append(
        f'<line x1="{px_left}" y1="{y0:.1f}" x2="{px_right}" y2="{y0:.1f}" '
        f'stroke="#444" stroke-width="1" stroke-dasharray="4,4"/>'
    )

    for i in range(4):
        val = max_la * i / 3
        y = yx(val)
        parts.append(
            f'<text x="{px_left - 5}" y="{y + 4:.1f}" text-anchor="end" '
            f'fill="#6ab" font-size="10">{val:.0f}</text>'
        )

    for i in range(3):
        val = min_tsb + (max_tsb - min_tsb) * i / 2
        y = ytsb(val)
        parts.append(
            f'<text x="{px_right + 5}" y="{y + 4:.1f}" text-anchor="start" '
            f'fill="#6c6" font-size="10">{val:.0f}</text>'
        )

    for idx in [0, n // 4, n // 2, 3 * n // 4, n - 1]:
        if idx < n:
            x = xi(idx)
            lbl = pmc_data[idx]["date"][5:]
            parts.append(
                f'<text x="{x:.1f}" y="{H - 5}" text-anchor="middle" '
                f'fill="#888" font-size="10">{lbl}</text>'
            )

    tsb_line = " ".join(f"{xi(i):.1f},{ytsb(d['tsb']):.1f}" for i, d in enumerate(pmc_data))
    parts.append(
        f'<polyline points="{tsb_line}" fill="none" '
        f'stroke="#2ecc71" stroke-width="2" stroke-linejoin="round" opacity="0.9"/>'
    )

    atl_line = " ".join(f"{xi(i):.1f},{yx(d['atl']):.1f}" for i, d in enumerate(pmc_data))
    parts.append(
        f'<polyline points="{atl_line}" fill="none" '
        f'stroke="#e74c3c" stroke-width="2" stroke-linejoin="round"/>'
    )

    ctl_line = " ".join(f"{xi(i):.1f},{yx(d['ctl']):.1f}" for i, d in enumerate(pmc_data))
    parts.append(
        f'<polyline points="{ctl_line}" fill="none" '
        f'stroke="#3498db" stroke-width="2.5" stroke-linejoin="round"/>'
    )

    legend_y = px_top + 12
    parts.extend([
        f'<rect x="{px_left + 5}" y="{legend_y}" width="12" height="3" fill="#3498db"/>',
        f'<text x="{px_left + 20}" y="{legend_y + 4}" fill="#3498db" font-size="10">Fitness (CTL)</text>',
        f'<rect x="{px_left + 95}" y="{legend_y}" width="12" height="3" fill="#e74c3c"/>',
        f'<text x="{px_left + 110}" y="{legend_y + 4}" fill="#e74c3c" font-size="10">Müdigkeit (ATL)</text>',
        f'<rect x="{px_left + 195}" y="{legend_y}" width="12" height="3" fill="#2ecc71"/>',
        f'<text x="{px_left + 210}" y="{legend_y + 4}" fill="#2ecc71" font-size="10">Form (TSB)</text>',
    ])

    parts.append("</svg>")
    return "".join(parts)
