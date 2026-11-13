"""Shared look & feel: Mantine theme, Plotly template and reusable layout building blocks."""
from dash import dcc, html
import dash_mantine_components as dmc
import plotly.graph_objects as go
import plotly.io as pio

FONT_FAMILY = "Heebo, 'Segoe UI', Arial, sans-serif"
FONT_URL = "https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;600;700;800&display=swap"

PRIMARY = "teal"

# Text / surface tokens (Mantine gray scale)
TEXT_PRIMARY = "#212529"
TEXT_SECONDARY = "#495057"
TEXT_MUTED = "#868e96"
GRID = "#eef0f2"
AXIS_LINE = "#dee2e6"

# Semantic series colors
COLOR_RENEWABLE = "#1baf7a"
COLOR_CONVENTIONAL = "#868e96"
COLOR_DISCHARGE = "#1baf7a"
COLOR_CHARGE = "#eb6834"
COLOR_LINE = "#2a78d6"

MANTINE_THEME = {
    "primaryColor": PRIMARY,
    "fontFamily": FONT_FAMILY,
    "headings": {"fontFamily": FONT_FAMILY, "fontWeight": "700"},
    "defaultRadius": "md",
    "radius": {"md": "10px", "lg": "16px"},
    "shadows": {
        "sm": "0 1px 2px rgba(16, 24, 40, 0.04), 0 1px 3px rgba(16, 24, 40, 0.06)",
        "md": "0 4px 12px rgba(16, 24, 40, 0.06), 0 2px 4px rgba(16, 24, 40, 0.04)",
    },
    "components": {
        "Card": {"defaultProps": {"shadow": "sm", "withBorder": True, "radius": "lg", "padding": "lg"}},
        "SegmentedControl": {"defaultProps": {"radius": "md"}},
        "Chip": {"defaultProps": {"radius": "md", "variant": "light"}},
    },
}

GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}

pio.templates["energy"] = go.layout.Template(
    layout=dict(
        font=dict(family=FONT_FAMILY, size=13, color=TEXT_SECONDARY),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=[COLOR_LINE, "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
        margin=dict(l=60, r=24, t=24, b=48),
        hoverlabel=dict(bgcolor="white", bordercolor=AXIS_LINE,
                        font=dict(family=FONT_FAMILY, size=13, color=TEXT_PRIMARY)),
        xaxis=dict(gridcolor=GRID, linecolor=AXIS_LINE, zerolinecolor=AXIS_LINE, showline=True, ticks="", automargin=True),
        yaxis=dict(gridcolor=GRID, linecolor=AXIS_LINE, zerolinecolor=AXIS_LINE, ticks="", automargin=True),
        polar=dict(bgcolor="rgba(0,0,0,0)",
                   radialaxis=dict(gridcolor=AXIS_LINE, linecolor=AXIS_LINE),
                   angularaxis=dict(gridcolor=AXIS_LINE, linecolor=AXIS_LINE)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=12, color=TEXT_SECONDARY)),
        dragmode=False,
    ),
    data=dict(
        heatmap=[go.Heatmap(colorbar=dict(outlinewidth=0, thickness=12, tickfont=dict(size=12)))],
        scatter=[go.Scatter(line=dict(width=2))],
    ),
)
pio.templates.default = "plotly_white+energy"


def axis_unit(fig, text, yaxis="y"):
    """Label a y axis with its unit above the plot area instead of a rotated axis title,
    which Plotly can draw over the tick labels when the web font loads after layout."""
    fig.add_annotation(text=text, xref="paper", yref=f"{yaxis} domain", x=0, y=1, xanchor="right", yanchor="bottom",
                       xshift=-6, yshift=6, showarrow=False, font=dict(size=11, color=TEXT_MUTED))


def icon(name, size=18):
    """A monochrome SVG icon from assets/icons, tinted with the current text color."""
    return html.Span(className=f"icon icon-{name}", style={"width": size, "height": size})


def page_header(title, subtitle=None, icon_name=None, right=None):
    heading = dmc.Group([
        dmc.ThemeIcon(icon(icon_name, 22), size=44, radius="md", variant="light") if icon_name else None,
        dmc.Stack([
            dmc.Title(title, order=2, fw=800),
            dmc.Text(subtitle, c="dimmed", size="sm") if subtitle else None,
        ], gap=2),
    ], gap="md", wrap="nowrap")
    return dmc.Group([heading, right], justify="space-between", align="center", mb="lg", wrap="wrap")


def chart_card(graph, title=None, subtitle=None, controls=None, footer=None, **card_props):
    header = None
    if title is not None or controls is not None:
        header = dmc.Group([
            dmc.Stack([
                dmc.Text(title, fw=700, size="lg") if isinstance(title, str) else title,
                dmc.Text(subtitle, c="dimmed", size="xs") if subtitle else None,
            ], gap=0),
            controls,
        ], justify="space-between", align="center", mb="sm", wrap="wrap")
    return dmc.Card([
        header,
        dcc.Loading(graph, type="circle", color="var(--mantine-color-teal-6)", delay_show=300),
        footer,
    ], **card_props)


def stat_card(label, value, icon_name=None, color=PRIMARY, hint=None):
    return dmc.Card([
        dmc.Group([
            dmc.Stack([
                dmc.Text(label, c="dimmed", size="xs", tt="uppercase", fw=600),
                dmc.Text(value, fw=800, size="xl", className="stat-value"),
                dmc.Text(hint, c="dimmed", size="xs") if hint else None,
            ], gap=4),
            dmc.ThemeIcon(icon(icon_name, 20), size=42, radius="md", variant="light", color=color)
            if icon_name else None,
        ], justify="space-between", align="flex-start", wrap="nowrap"),
    ], padding="md")


def control_label(text):
    return dmc.Text(text, size="xs", fw=600, c="dimmed", mb=6)
