from dash import dcc, html, Input, Output, State, callback_context
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import gc
import logging
import time as time_module
import pandas as pd

from scripts import server, utils

HEATMAP_ID = "heatmap-graph"
SOURCES_ID = "sources-radioitems"
FREEZE_SCALE_ID = "freeze-scale"
DISPLAY_MODE_ID = "display-mode-radioitems"
FREEZE_SCALE_VALUE = "Freeze Scale"
MODE_ABSOLUTE = "Absolute"
MODE_PERCENT = "Percent"

STORAGE_NET_SOURCES = {"PspNet", "BatteriesNet"}
COLOR_DISCHARGE = "#10b981"
COLOR_CHARGE = "#f43f5e"

SOURCE_LABELS = {
    "Pv": "☀️ סולארי",
    "Gas": "🔥 גז טבעי",
    "Coal": "🪨 פחם",
    "Wind": "🌬️ רוח",
    "Thermo": "🔆 תרמו-סולארי",
    "BioGas": "🌱 ביוגז",
    "Solar": "⛽ דיזל",
    "Diesel": "⛽ דיזל",
    "Mazut": "🛢️ מזוט",
    "Other": "⚙️ אחר",
    "ActualDemand": "⚡ ביקוש משקי",
    "RenewableSum": "♻️ סה״כ מתחדשות",
    "PvWithStorage": "☀️🔋 סולארי משולב אגירה",
    "BatteriesNet": "🔋 סוללות (נטו)",
    "Psp": "💧 אגירה שאובה",
    "PspNet": "💧 אגירה שאובה (נטו)",
    "Storage": "🔋 סה״כ אגירה",
}

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


def _format_source_options(src_list):
    return [{"label": SOURCE_LABELS.get(s, s), "value": s} for s in src_list]


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


def heatmap_layout(nav_links):
    return html.Div([
        nav_links,
        html.Main([
            html.Div([
                html.Div([
                    html.H1("תמהיל הייצור במשק החשמל", className='nzo-page-title'),
                    html.P("מפה שעתית ברזולוציה של 5 דקות ומגמה יומית לכל מקורות האנרגיה", className='nzo-page-subtitle'),
                ]),
                html.Span("מקור הנתונים: נגה", className='nzo-source-pill'),
            ], className='nzo-page-header'),

            # Controls Toolbar Card
            html.Div([
                html.Div([
                    html.Div([
                        html.Span("תצוגת נתונים:", className='nzo-control-label'),
                        dcc.RadioItems(
                            id=DISPLAY_MODE_ID,
                            options=[
                                {'label': 'ערכים מוחלטים (MW / MWh)', 'value': MODE_ABSOLUTE},
                                {'label': 'אחוז מהביקוש (%)', 'value': MODE_PERCENT},
                            ],
                            value=MODE_ABSOLUTE,
                            inline=True,
                            className='nzo-segmented-radio'
                        ),
                    ], className='nzo-control-group'),

                    html.Div([
                        dcc.Checklist(
                            id=FREEZE_SCALE_ID,
                            options=[{'label': 'הקפאת סקאלה', 'value': FREEZE_SCALE_VALUE}],
                            value=[],
                            className='nzo-checklist-pill'
                        ),
                    ], className='nzo-control-group'),
                ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'width': '100%', 'flexWrap': 'wrap', 'gap': '12px', 'paddingBottom': '12px', 'borderBottom': '1px solid #e2e8f0'}),

                html.Div([
                    html.Span("מקור אנרגיה:", className='nzo-control-label'),
                    dcc.RadioItems(
                        id=SOURCES_ID,
                        options=_format_source_options(sources),
                        value=select_source,
                        inline=True,
                        className='nzo-pill-selector'
                    ),
                ], className='nzo-control-group', style={'width': '100%', 'paddingTop': '4px'}),
            ], className='nzo-toolbar-card'),

            # Chart Card
            html.Div([
                dcc.Graph(
                    id=HEATMAP_ID,
                    style={'marginBottom': '0px'},
                    config={'responsive': True}
                ),
            ], className='nzo-card-chart'),
        ], className='nzo-page-container'),
    ])


def register_callbacks(app):
    @app.callback(
        Output(SOURCES_ID, 'options'),
        Output(SOURCES_ID, 'value'),
        Input(DISPLAY_MODE_ID, 'value'),
        State(SOURCES_ID, 'value')
    )
    def update_source_options(display_mode, current_source):
        if display_mode == MODE_PERCENT:
            filtered = [s for s in sources if s != "ActualDemand"]
            value = select_source if current_source == "ActualDemand" else current_source
        else:
            filtered = sources
            value = current_source
        return _format_source_options(filtered), value

    @app.callback(
        Output(HEATMAP_ID, 'figure'),
        [Input(SOURCES_ID, 'value'),
         Input(FREEZE_SCALE_ID, 'value'),
         Input(DISPLAY_MODE_ID, 'value')]
    )
    def update_heatmap_output(source, freeze_scale_value, display_mode):
        global dfs, global_freeze_source, last_zrange, last_scatter_yrange
        freeze_checked = FREEZE_SCALE_VALUE in freeze_scale_value
        is_percent = display_mode == MODE_PERCENT
        triggered_id = callback_context.triggered[0]['prop_id'].split('.')[0]

        if triggered_id == FREEZE_SCALE_ID and freeze_checked:
            global_freeze_source = source
            raise PreventUpdate

        retrieve_data()
        logging.info(f"Update heatmap: {source} [{display_mode}]"
                     f"{(' (' + FREEZE_SCALE_VALUE + ')') if freeze_checked else ''}")

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
            scatter_hover = '<b>%{x}</b>: %{y:,.1f}%<extra></extra>'
            scatter_yaxis_label = "ממוצע יומי (%)"
            heatmap_hover = '<b>%{x} | %{y}</b><br>%{z:,.1f}%<extra></extra>'
        else:
            scatter_y = dfs_heatmap.sum() / 12
            scatter_pos_y = dfs_heatmap[dfs_heatmap > 0].sum() / 12
            scatter_neg_y = -dfs_heatmap[dfs_heatmap < 0].sum() / 12
            scatter_hover = '<b>%{x}</b>: %{y:,.2f} MWh<extra></extra>'
            scatter_yaxis_label = "אנרגיה יומית (MWh)"
            heatmap_hover = '<b>%{x} | %{y}</b><br>%{z:,.2f} MW<extra></extra>'

        show_pos_neg = source in STORAGE_NET_SOURCES

        if show_pos_neg:
            current_data_yrange = _data_yrange(scatter_pos_y, scatter_neg_y)
        else:
            current_data_yrange = _data_yrange(scatter_y)

        if freeze_checked:
            if last_scatter_yrange[display_mode] is None:
                last_scatter_yrange[display_mode] = current_data_yrange
            scatter_yrange = last_scatter_yrange[display_mode]
        else:
            last_scatter_yrange[display_mode] = current_data_yrange
            scatter_yrange = current_data_yrange

        current_zmin = dfs_heatmap.min().min()
        current_zmax = dfs_heatmap.max().max()
        if freeze_checked:
            if last_zrange[display_mode] is None:
                last_zrange[display_mode] = [current_zmin, current_zmax]
            zmin, zmax = last_zrange[display_mode]
        else:
            last_zrange[display_mode] = [current_zmin, current_zmax]
            zmin, zmax = current_zmin, current_zmax

        fig = make_subplots(rows=2, cols=1, row_heights=[140, 580], vertical_spacing=0.04, shared_xaxes=True)

        if show_pos_neg:
            fig.add_trace(
                go.Scatter(
                    x=dfs_heatmap.columns.values,
                    y=scatter_pos_y,
                    name='פריקה',
                    line=dict(color=COLOR_DISCHARGE, width=2),
                    hovertemplate=scatter_hover
                ),
                row=1, col=1)
            fig.add_trace(
                go.Scatter(
                    x=dfs_heatmap.columns.values,
                    y=scatter_neg_y,
                    name='טעינה',
                    line=dict(color=COLOR_CHARGE, width=2),
                    hovertemplate=scatter_hover
                ),
                row=1, col=1)
        else:
            fig.add_trace(
                go.Scatter(
                    x=dfs_heatmap.columns.values,
                    y=scatter_y,
                    line=dict(color="#0284c7", width=2),
                    fill='tozeroy',
                    fillcolor='rgba(2, 132, 199, 0.10)',
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
                    'len': 0.78,
                    'y': 0.39,
                    'thickness': 16,
                    'outlinewidth': 0,
                    'ticksuffix': '%' if is_percent else ' MW'
                },
                hovertemplate=heatmap_hover
            ),
            row=2, col=1)

        fig.update_xaxes(showticklabels=False, gridcolor="#e2e8f0", row=1, col=1)
        fig.update_xaxes(gridcolor="#e2e8f0", tickfont={"size": 13, "color": "#475569"}, row=2, col=1)
        fig.update_yaxes(
            title_text=scatter_yaxis_label,
            title_font={"size": 13, "color": "#475569"},
            tickfont={"size": 12, "color": "#475569"},
            gridcolor="#e2e8f0",
            range=scatter_yrange,
            col=1, row=1
        )
        fig.update_yaxes(
            title_text="שעה ביממה",
            title_font={"size": 13, "color": "#475569"},
            tickvals=[0, n_y - 1, n_y * 2 - 1, n_y * 3 - 1, n_y * 4 - 1],
            ticktext=['00:00', '06:00', '12:00', '18:00', '24:00'],
            tickfont={"size": 13, "color": "#475569"},
            row=2, col=1
        )

        source_display = SOURCE_LABELS.get(source, source)
        fig.update_layout(
            height=760,
            font={"family": "Heebo, Inter, sans-serif", "color": "#0f172a"},
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='#ffffff',
            margin=dict(l=70, r=40, t=55, b=45),
            showlegend=show_pos_neg,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            uirevision=True,
            hoverlabel=dict(
                bgcolor="#0f172a",
                font_size=13,
                font_family="Heebo, Inter, sans-serif",
            ),
            title=go.layout.Title(
                x=0.5,
                xanchor='center',
                font={"family": "Heebo, Inter, sans-serif", "size": 22, "color": "#0f172a"},
                text=f"תמהיל הייצור • {source_display}"
            ),
        )
        return fig
