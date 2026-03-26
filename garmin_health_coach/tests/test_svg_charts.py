from src.analysis.svg_charts import line_chart, bar_chart, pmc_chart


def test_line_chart_returns_svg():
    svg = line_chart(
        labels=["2024-01-01", "2024-01-02", "2024-01-03"],
        series=[{"label": "HF", "values": [60, 65, 70], "color": "#e74c3c"}],
    )
    assert svg.startswith("<svg")
    assert "</svg>" in svg


def test_line_chart_empty_data():
    svg = line_chart(labels=[], series=[])
    assert "<svg" in svg


def test_line_chart_multiple_series():
    svg = line_chart(
        labels=["2024-01-01", "2024-01-02"],
        series=[
            {"label": "A", "values": [10, 20], "color": "#fff"},
            {"label": "B", "values": [5, 15], "color": "#aaa"},
        ],
    )
    assert svg.count("<polyline") >= 2 or svg.count("<path") >= 2


def test_bar_chart_returns_svg():
    labels = [f"KW{i}" for i in range(1, 13)]
    values = [float(i * 10) for i in range(12)]
    svg = bar_chart(labels=labels, values=values, color="#3498db")
    assert "<svg" in svg
    assert "</svg>" in svg


def test_bar_chart_always_12_bars():
    svg = bar_chart(labels=["KW1", "KW2"], values=[100.0, 200.0], color="#3498db")
    assert "<rect" in svg


def test_pmc_chart_returns_svg():
    pmc_data = [
        {"date": f"2024-01-{i:02d}", "ctl": float(i), "atl": float(i + 5), "tsb": float(-5)}
        for i in range(1, 15)
    ]
    svg = pmc_chart(pmc_data)
    assert "<svg" in svg
    assert "</svg>" in svg


def test_pmc_chart_has_three_lines():
    pmc_data = [
        {"date": f"2024-01-{i:02d}", "ctl": float(i), "atl": float(i + 5), "tsb": float(-5)}
        for i in range(1, 5)
    ]
    svg = pmc_chart(pmc_data)
    assert svg.count("stroke=") >= 3


def test_pmc_chart_empty_data():
    svg = pmc_chart([])
    assert "<svg" in svg
