"""
Semantic chart type → Chart.js config mapping.
5 supported types: comparison, trend, distribution, ranking, timeline.
All configs use monospace font, #e63946 as primary color, #000 borders.
"""

import json

ACCENT = "#e63946"
ACCENT_ALPHA = "rgba(230, 57, 70, 0.15)"
PALETTE = ["#e63946", "#222", "#555", "#888", "#bbb"]

FONT = {
    "family": "'Courier New', Courier, monospace",
    "size": 12,
}

AXIS_DEFAULTS = {
    "ticks": {"font": FONT, "color": "#000"},
    "grid": {"color": "rgba(0,0,0,0.08)"},
    "border": {"color": "#000"},
}


def _base_options(title: str, unit: str = "") -> dict:
    label_suffix = f" ({unit})" if unit else ""
    return {
        "responsive": True,
        "maintainAspectRatio": False,
        "plugins": {
            "legend": {
                "labels": {"font": FONT, "color": "#000"},
            },
            "title": {
                "display": bool(title),
                "text": title,
                "font": {**FONT, "size": 13, "weight": "bold"},
                "color": "#000",
                "padding": {"bottom": 12},
            },
            "tooltip": {
                "callbacks": {
                    "label": f"function(ctx){{return ctx.parsed.y !== undefined ? ctx.parsed.y + '{label_suffix}' : ctx.parsed + '{label_suffix}';}}"
                }
            },
        },
    }


def _comparison(chart: dict) -> dict:
    labels = chart.get("labels", [])
    values = chart.get("values", [])
    unit = chart.get("unit", "")
    title = chart.get("title", "")

    opts = _base_options(title, unit)
    opts["scales"] = {
        "x": {**AXIS_DEFAULTS, "ticks": {**AXIS_DEFAULTS["ticks"]}},
        "y": {
            **AXIS_DEFAULTS,
            "ticks": {**AXIS_DEFAULTS["ticks"], "callback": f"function(v){{return v + ' {unit}';}}" if unit else {}},
        },
    }

    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": title,
                "data": values,
                "backgroundColor": ACCENT,
                "borderColor": "#000",
                "borderWidth": 1,
            }],
        },
        "options": opts,
    }


def _trend(chart: dict) -> dict:
    labels = chart.get("labels", [])
    values = chart.get("values", [])
    unit = chart.get("unit", "")
    title = chart.get("title", "")

    opts = _base_options(title, unit)
    opts["scales"] = {
        "x": {**AXIS_DEFAULTS},
        "y": {
            **AXIS_DEFAULTS,
            "ticks": {**AXIS_DEFAULTS["ticks"], "callback": f"function(v){{return v + ' {unit}';}}" if unit else {}},
        },
    }

    return {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": title,
                "data": values,
                "borderColor": ACCENT,
                "backgroundColor": ACCENT_ALPHA,
                "fill": True,
                "tension": 0.2,
                "pointBackgroundColor": ACCENT,
                "pointBorderColor": "#000",
                "pointBorderWidth": 1,
            }],
        },
        "options": opts,
    }


def _distribution(chart: dict) -> dict:
    labels = chart.get("labels", [])
    values = chart.get("values", [])
    title = chart.get("title", "")

    opts = _base_options(title)
    opts["plugins"]["legend"]["position"] = "right"

    colors = (PALETTE * ((len(labels) // len(PALETTE)) + 1))[:len(labels)]

    return {
        "type": "doughnut",
        "data": {
            "labels": labels,
            "datasets": [{
                "data": values,
                "backgroundColor": colors,
                "borderColor": "#000",
                "borderWidth": 1,
            }],
        },
        "options": opts,
    }


def _ranking(chart: dict) -> dict:
    labels = chart.get("labels", [])
    values = chart.get("values", [])
    unit = chart.get("unit", "")
    title = chart.get("title", "")

    # Sort descending
    pairs = sorted(zip(labels, values), key=lambda x: x[1], reverse=True)
    labels = [p[0] for p in pairs]
    values = [p[1] for p in pairs]

    opts = _base_options(title, unit)
    opts["indexAxis"] = "y"
    opts["scales"] = {
        "x": {
            **AXIS_DEFAULTS,
            "ticks": {**AXIS_DEFAULTS["ticks"], "callback": f"function(v){{return v + ' {unit}';}}" if unit else {}},
        },
        "y": {**AXIS_DEFAULTS},
    }

    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": title,
                "data": values,
                "backgroundColor": ACCENT,
                "borderColor": "#000",
                "borderWidth": 1,
            }],
        },
        "options": opts,
    }


def _timeline(chart: dict) -> dict:
    labels = chart.get("labels", [])
    values = chart.get("values", [])
    unit = chart.get("unit", "")
    title = chart.get("title", "")

    opts = _base_options(title, unit)
    opts["scales"] = {
        "x": {**AXIS_DEFAULTS},
        "y": {
            **AXIS_DEFAULTS,
            "ticks": {**AXIS_DEFAULTS["ticks"], "callback": f"function(v){{return v + ' {unit}';}}" if unit else {}},
        },
    }

    return {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": title,
                "data": values,
                "borderColor": ACCENT,
                "backgroundColor": ACCENT_ALPHA,
                "fill": False,
                "tension": 0,
                "pointBackgroundColor": ACCENT,
                "pointBorderColor": "#000",
                "pointBorderWidth": 1,
            }],
        },
        "options": opts,
    }


_BUILDERS = {
    "comparison": _comparison,
    "trend": _trend,
    "distribution": _distribution,
    "ranking": _ranking,
    "timeline": _timeline,
}


def build_config(chart: dict) -> dict:
    chart_type = chart.get("type", "comparison")
    builder = _BUILDERS.get(chart_type, _comparison)
    return builder(chart)


def build_config_json(chart: dict) -> str:
    config = build_config(chart)
    return json.dumps(config, ensure_ascii=False)
