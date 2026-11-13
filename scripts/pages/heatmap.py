from dash import dcc, html, Input, Output, State, callback_context
import dash_mantine_components as dmc
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import gc
import logging
import time as time_module
import pandas as pd

from scripts import server, utils
from . import ui

HEATMAP_ID = "heatmap-graph"
HEATMAP_TITLE_ID = "heatmap-title"
SOURCES_ID = "sources-radioitems"
FREEZE_SCALE_ID = "freeze-scale"
DISPLAY_MODE_ID = "display-mode-radioitems"
MODE_ABSOLUTE = "Absolute"
MODE_PERCENT = "Percent"

STORAGE_NET_SOURCES = {"PspNet", "BatteriesNet"}
COLOR_DISCHARGE = ui.COLOR_DISCHARGE
COLOR_CHARGE = ui.COLOR_CHARGE

SOURCE_LABELS = {
    "Coal": "פחם",
    "Gas": "גז",
    "Diesel": "סולר",
    "Mazut": "מזוט",
    "Other": "אחר",
    "Pv": "פוטו-וולטאי",
    "PvWithStorage": "PV משולב אגירה",
    "Thermo": "תרמו-סולארי",
    "Wind": "רוח",
    "BioGas": "ביוגז",
    "RenewableSum": "סך הכל",
    "ActualDemand": "ביקוש בפועל",
    "Psp": "אגירה שאובה",
    "PspNet": "אגירה שאובה (נטו)",
    "BatteriesNet": "סוללות (נטו)",
    "Storage": "אגירה",
}

SOURCE_ICONS = {
    "Coal": "🪨",
    "Gas": "🔥",
    "Diesel": "⛽",
    "Mazut": "🛢️",
    "Other": "⚙️",
    "Pv": "☀️",
    "PvWithStorage": "☀️🔋",
    "Thermo": "🔆",
    "Wind": "🌬️",
    "BioGas": "🌱",
    "RenewableSum": "♻️",
    "ActualDemand": "⚡",
    "Psp": "💧",
    "PspNet": "💧",
    "BatteriesNet": "🔋",
    "Storage": "💧🔋",
}

GENERAL_GROUP = "general"
# (key, title, icon, members). Sources not listed in any group fall into the general group.
SOURCE_GROUPS = [
    ("fossil", "דלקים פוסיליים", "flame", ["Gas", "Coal", "Diesel", "Mazut"]),
    ("renewables", "אנרגיות מתחדשות", "leaf", ["Pv", "PvWithStorage", "Wind", "Thermo", "BioGas", "Other", "RenewableSum"]),
    ("storage", "אגירה", "battery", ["Psp", "PspNet", "BatteriesNet", "Storage"]),
    (GENERAL_GROUP, "כללי", "bolt", ["ActualDemand"]),
]

DISPLAY_MODES = [
    {"label": "ערכים מוחלטים", "value": MODE_ABSOLUTE},
    {"label": "אחוז מהביקוש", "value": MODE_PERCENT},
]

select_source = "Pv"
start_date = "01-01-2024"

last_call = datetime.fromtimestamp(0)  # epoch

GOLD_RED_COLORSCALE = [
    [0, 'beige'],
    [0.1, 'gold'],
    [0.5, 'orange'],
    [0.8, 'red'],
    [1, 'darkred']
]

BLUE_RED_COLORSCALE = [
    [0, "rgb(69, 117, 180)"],
    [0.3, "rgb(172, 217, 233)"],
    [0.65, "rgb(253, 175,97)"],
    [1, 'rgb(215, 50, 40)']
]

dfs = {}
dfs_heatmap = None
dfs_zero = None
sources = []

global_freeze_source = None  # The source for which the scale is frozen

# Last-seen heatmap Z range and scatter Y range, keyed by display mode.
# Updated on every unfrozen draw; held and re-applied explicitly when frozen.
# None means 'not yet drawn in this mode' — first draw seeds the value even if frozen.
last_zrange = {MODE_ABSOLUTE: None, MODE_PERCENT: None}
last_scatter_yrange = {MODE_ABSOLUTE: None, MODE_PERCENT: None}


def retrieve_data():
    global last_call, dfs_zero, sources, dfs, start_date
    time_since_last_call = datetime.now() - last_call
    if time_since_last_call.total_seconds() < 3600:
        logging.info("Time since last call: {} seconds. No URL call.".format(int(time_since_last_call.total_seconds())))
        return

    t_start = time_module.perf_counter()
    heatmap_url = 'http://0.0.0.0:9999/get?source=noga2&type=energy&start_date=' + start_date + '&time=all&format=bin'
    utils.retrieve_url(heatmap_url)
    fetched_dfs, latest_date = server.pop_df_result()
    if latest_date is None or not fetched_dfs:
        return

    start_date = latest_date.strftime("%d-%m-%Y")
    for source, df in fetched_dfs.items():
        if source in dfs:
            old_df = dfs[source]
            keep_cols = old_df.columns.difference(df.columns, sort=False)
            merged = pd.concat([old_df[keep_cols], df], axis=1)
            if not merged.columns.is_monotonic_increasing:
                merged = merged.reindex(sorted(merged.columns), axis=1)
            merged.columns.name = "Date"
            dfs[source] = merged
        else:
            dfs[source] = df
    del fetched_dfs
    gc.collect()
    dfs_zero = pd.DataFrame(0, index=dfs[select_source].index, columns=dfs[select_source].columns, dtype='float32')
    sources = [s for s in list(dfs.keys()) if s not in ["DemandManagement", "Renewables"]]
    last_call = datetime.now()
    t_done = time_module.perf_counter()
    logging.info("heatmap.retrieve_data completed: total=%.2fs", t_done - t_start)


def compute_percent_df(source_df, demand_df):
    """Return source as a percentage of ActualDemand, aligned on shared columns/index."""
    aligned_source, aligned_demand = source_df.align(demand_df, join='inner')
    # Avoid division by zero — cells where demand is 0 become NaN
    percent_df = aligned_source.div(aligned_demand.replace(0, float('nan'))) * 100
    percent_df.index.name = source_df.index.name
    percent_df.columns.name = source_df.columns.name
    return percent_df


def _data_yrange(*scatter_series_list):
    """Compute a tight [ymin, ymax] from one or more scatter series, with a small 5% padding."""
    ymin = min(s.min() for s in scatter_series_list)
    ymax = max(s.max() for s in scatter_series_list)
    pad = (ymax - ymin) * 0.05 if ymax != ymin else abs(ymax) * 0.05 or 1
    return [ymin - pad, ymax + pad]


def source_chips(source_names, labels=SOURCE_LABELS, icons=SOURCE_ICONS):
    def chip_label(name):
        if not icons or name not in icons:
            return labels.get(name, name)
        return html.Span([html.Span(icons[name], className='chip-emoji'), labels.get(name, name)], className='chip-label')
    return [dmc.Chip(chip_label(name), value=name) for name in source_names]


def grouped_source_chips(source_names):
    """Chips laid out in titled rows by source group; empty groups are omitted."""
    grouped = {key: [] for key, *_ in SOURCE_GROUPS}
    member_group = {name: key for key, _, _, members in SOURCE_GROUPS for name in members}
    for name in source_names:
        grouped[member_group.get(name, GENERAL_GROUP)].append(name)

    cards = []
    for key, title, icon_name, members in SOURCE_GROUPS:
        # Listed members first in their defined order, then any unlisted sources
        names = [n for n in members if n in grouped[key]] + [n for n in grouped[key] if n not in members]
        if not names:
            continue
        cards.append(dmc.Card([
            dmc.Group([
                dmc.ThemeIcon(ui.icon(icon_name, 16), size=30, radius='md', variant='light'),
                dmc.Text(title, fw=700, size='sm'),
            ], gap=8, mb='sm', wrap='nowrap'),
            dmc.Group(source_chips(names), gap=8, className='chip-scroller'),
        ], padding='md',
            # Cards share a row, growing in proportion to how many sources they hold
            style={'flex': f'{len(names)} 1 260px'}))
    return dmc.Flex(cards, gap='md', wrap='wrap', align='stretch')


def chart_title(source):
    return html.Span(['תמהיל הייצור – ', html.Span(SOURCE_ICONS.get(source, ''), className='chip-emoji'), ' ',
                      SOURCE_LABELS.get(source, source)])


def heatmap_layout():
    controls = dmc.Group([
        dmc.SegmentedControl(id=DISPLAY_MODE_ID, data=DISPLAY_MODES, value=MODE_ABSOLUTE),
        dmc.Switch(id=FREEZE_SCALE_ID, label='הקפאת סקאלה', checked=False),
    ], justify='space-between', wrap='wrap')

    return dmc.Stack([
        ui.page_header('תמהיל הייצור', 'הספק לפי שעה ביום (ציר אנכי) ולאורך זמן (ציר אופקי). הגרף העליון מציג את האנרגיה היומית.', 'layers',
                       right=controls),
        dmc.ChipGroup(grouped_source_chips(sources),
                      id=SOURCES_ID, value=select_source, multiple=False, deselectable=False),
        ui.chart_card(dcc.Graph(id=HEATMAP_ID, config=ui.GRAPH_CONFIG),
                      title=dmc.Text(chart_title(select_source), id=HEATMAP_TITLE_ID, fw=700, size='lg')),
    ], gap='md')


def register_callbacks(app):
    @app.callback(
        Output(SOURCES_ID, 'children'),
        Output(SOURCES_ID, 'value'),
        Input(DISPLAY_MODE_ID, 'value'),
        State(SOURCES_ID, 'value')
    )
    def update_source_options(display_mode, current_source):
        if display_mode == MODE_PERCENT:
            options = [s for s in sources if s != "ActualDemand"]
            value = select_source if current_source == "ActualDemand" else current_source
        else:
            options = sources
            value = current_source
        return grouped_source_chips(options), value

    @app.callback(
        Output(HEATMAP_TITLE_ID, 'children'),
        Input(SOURCES_ID, 'value'),
    )
    def update_heatmap_title(source):
        return chart_title(source)

    @app.callback(
        Output(HEATMAP_ID, 'figure'),
        [Input(SOURCES_ID, 'value'),
         Input(FREEZE_SCALE_ID, 'checked'),
         Input(DISPLAY_MODE_ID, 'value')]
    )
    def update_heatmap_output(source, freeze_checked, display_mode):
        global dfs, global_freeze_source, last_zrange, last_scatter_yrange
        freeze_checked = bool(freeze_checked)
        is_percent = display_mode == MODE_PERCENT
        triggered_id = callback_context.triggered[0]['prop_id'].split('.')[0]

        # Checking freeze: nothing to redraw, just record which source was active.
        # The Y range to freeze is whatever was last drawn for this mode, already stored
        # in last_scatter_yrange[display_mode].
        if triggered_id == FREEZE_SCALE_ID and freeze_checked:
            global_freeze_source = source
            raise PreventUpdate

        retrieve_data()
        logging.info(f"Update heatmap: {source} [{display_mode}]"
                     f"{' (frozen scale)' if freeze_checked else ''}")

        source_df = dfs[source]

        if is_percent:
            if "ActualDemand" not in dfs:
                logging.warning("ActualDemand source not available for percent mode.")
                dfs_heatmap = source_df
            else:
                dfs_heatmap = compute_percent_df(source_df, dfs["ActualDemand"])
        else:
            dfs_heatmap = source_df

        n_y = len(dfs_heatmap.index) / 4

        if is_percent:
            valid_counts = dfs_heatmap.count().replace(0, float('nan'))
            scatter_y = dfs_heatmap.mean()
            scatter_pos_y = dfs_heatmap[dfs_heatmap > 0].sum() / valid_counts
            scatter_neg_y = -dfs_heatmap[dfs_heatmap < 0].sum() / valid_counts
            scatter_hover = '<i>%{x} : %{y:,.1f}%</i><extra></extra>'
            scatter_yaxis_label = "%"
            heatmap_hover = '<i>%{x} %{y}</i><br>%{z:,.1f}%<extra></extra>'
        else:
            scatter_y = dfs_heatmap.sum() / 12
            scatter_pos_y = dfs_heatmap[dfs_heatmap > 0].sum() / 12
            scatter_neg_y = -dfs_heatmap[dfs_heatmap < 0].sum() / 12
            scatter_hover = '<i>%{x} : %{y:,.2f} MWh</i><extra></extra>'
            scatter_yaxis_label = "MWh"
            heatmap_hover = '<i>%{x} %{y}</i><br>%{z:,.2f} MW<extra></extra>'

        show_pos_neg = source in STORAGE_NET_SOURCES

        # Decide the scatter Y range to apply.
        #
        # freeze_checked=True:
        #   Use last_scatter_yrange[mode]. If it is None (e.g. page was just loaded and
        #   freeze was checked before any source switch), compute it from the current data
        #   and store it so subsequent source switches keep the same range.
        #
        # freeze_checked=False:
        #   Always compute from current data and update last_scatter_yrange[mode]
        #   so that if the user later checks freeze, we have the latest range ready.
        if show_pos_neg:
            current_data_yrange = _data_yrange(scatter_pos_y, scatter_neg_y)
        else:
            current_data_yrange = _data_yrange(scatter_y)

        if freeze_checked:
            if last_scatter_yrange[display_mode] is None:
                # First draw in this mode while frozen — seed the stored range
                last_scatter_yrange[display_mode] = current_data_yrange
            scatter_yrange = last_scatter_yrange[display_mode]
        else:
            last_scatter_yrange[display_mode] = current_data_yrange
            scatter_yrange = current_data_yrange

        # Heatmap Z range — same pattern as scatter Y range.
        current_zmin = dfs_heatmap.min().min()
        current_zmax = dfs_heatmap.max().max()
        if freeze_checked:
            if last_zrange[display_mode] is None:
                last_zrange[display_mode] = [current_zmin, current_zmax]
            zmin, zmax = last_zrange[display_mode]
        else:
            last_zrange[display_mode] = [current_zmin, current_zmax]
            zmin, zmax = current_zmin, current_zmax

        fig = make_subplots(rows=2, cols=1, row_heights=[100, 600], vertical_spacing=0.05, shared_xaxes=True)

        if show_pos_neg:
            fig.add_trace(
                go.Scatter(
                    x=dfs_heatmap.columns.values,
                    y=scatter_pos_y,
                    name='Discharge',
                    line=dict(color=COLOR_DISCHARGE),
                    **ui.area_fill(COLOR_DISCHARGE),
                    hovertemplate=scatter_hover
                ),
                row=1, col=1)
            fig.add_trace(
                go.Scatter(
                    x=dfs_heatmap.columns.values,
                    y=scatter_neg_y,
                    name='Charge',
                    line=dict(color=COLOR_CHARGE),
                    **ui.area_fill(COLOR_CHARGE),
                    hovertemplate=scatter_hover
                ),
                row=1, col=1)
        else:
            fig.add_trace(
                go.Scatter(
                    x=dfs_heatmap.columns.values,
                    y=scatter_y,
                    line=dict(color=ui.COLOR_LINE),
                    **ui.area_fill(ui.COLOR_LINE),
                    hovertemplate=scatter_hover
                ),
                row=1, col=1)

        fig.add_trace(
            go.Heatmap(
                x=dfs_heatmap.columns.values,
                y=dfs_heatmap.index,
                z=dfs_heatmap,
                colorscale=BLUE_RED_COLORSCALE,
                zmin=zmin,
                zmax=zmax,
                colorbar={
                    'len': 0.85,
                    'y': 0.42,
                    'ticksuffix': '%' if is_percent else '',
                    'title': {'text': '' if is_percent else 'MW', 'side': 'top'},
                },
                hovertemplate=heatmap_hover
            ),
            row=2, col=1)

        fig.update_xaxes(showticklabels=False, row=1, col=1)
        # Always set an explicit range on the scatter Y axis — this is the only reliable
        # way to control it. Plotly ignores uirevision for axis range when new trace data
        # is provided, so we must own the range completely rather than delegating to Plotly.
        fig.update_yaxes(range=scatter_yrange, col=1, row=1)
        ui.axis_unit(fig, scatter_yaxis_label)
        fig.update_yaxes(
            tickvals=[0, n_y - 1, n_y * 2 - 1, n_y * 3 - 1, n_y * 4 - 1],
            ticktext=['00:00', '06:00', '12:00', '18:00', '24:00'],
            row=2, col=1)
        fig.update_xaxes(showline=False)
        # White grid on the tinted daily graph
        fig.update_xaxes(gridcolor='white', row=1, col=1)
        fig.update_yaxes(gridcolor='white', row=1, col=1)
        fig.update_layout(
            height=760,
            # Only visible in the daily graph: the heatmap covers its whole plot area
            plot_bgcolor=ui.PLOT_TINT,
            showlegend=show_pos_neg,
            legend={"orientation": "h", "x": 0, "y": 1.06},
            margin={"t": 32, "r": 16},
            uirevision=True,
        )
        return fig