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
from . import heatmap

CO2_HEATMAP_ID = "co2-heatmap-graph"
CO2_SOURCES_ID = "co2-sources-radioitems"
CO2_FREEZE_SCALE_ID = "co2-freeze-scale"
CO2_DISPLAY_MODE_ID = "co2-display-mode-radioitems"
FREEZE_SCALE_VALUE = "Freeze Scale"
MODE_ABSOLUTE = "Absolute"
MODE_PERCENT = "Percent"

SOURCE_GAS = "Gas"
SOURCE_COAL = "Coal"
SOURCE_DIESEL = "Diesel"
SOURCE_MAZUT = "Mazut"
SOURCE_RENEWABLES = "Renewables"
SOURCE_RATIO = "Co2Ratio"
SOURCE_TOTAL = "Total"

SOURCE_TO_DB_TAG = {
    SOURCE_DIESEL: "Gasoil",
    SOURCE_MAZUT: "Fueloil",
    SOURCE_TOTAL: "Co2FromAllSitesWithoutRenewables",
}

MIN_CO2_VALUE = 0
MAX_CO2_VALUE = 50000
HEATMAP_ZMIN = 0
HEATMAP_ZMAX = 5000
RATIO_ZMIN = 0
RATIO_ZMAX = 0.5

WANTED_SOURCES = [
    SOURCE_GAS,
    SOURCE_COAL,
    SOURCE_DIESEL,
    SOURCE_MAZUT,
    SOURCE_RATIO,
    SOURCE_TOTAL,
    SOURCE_RENEWABLES,
]
NON_PERCENT_SOURCES = {SOURCE_TOTAL, SOURCE_RATIO}

select_source = SOURCE_GAS
start_date = "01-01-2024"

last_call = datetime.fromtimestamp(0)  # epoch

BROWN_BLACK_COLORSCALE = [
    [0.0, "rgb(245, 235, 220)"],
    [0.2, "rgb(210, 180, 140)"],
    [0.5, "rgb(120, 72, 32)"],
    [0.8, "rgb(60, 35, 15)"],
    [1.0, "rgb(0, 0, 0)"]
]

GREEN_COLORSCALE = [
    [0.0, "rgb(235, 248, 235)"],
    [0.2, "rgb(180, 228, 180)"],
    [0.5, "rgb(70, 165, 70)"],
    [0.8, "rgb(25, 110, 25)"],
    [1.0, "rgb(0, 60, 0)"]
]

dfs = {}
sources = []

global_freeze_source = None
last_zrange = {MODE_ABSOLUTE: None, MODE_PERCENT: None}
last_scatter_yrange = {MODE_ABSOLUTE: None, MODE_PERCENT: None}


def retrieve_data():
    global last_call, sources, dfs, start_date
    time_since_last_call = datetime.now() - last_call
    if time_since_last_call.total_seconds() < 3600 and dfs:
        logging.info("Time since last CO2 call: {} seconds. No URL call.".format(int(time_since_last_call.total_seconds())))
        return

    t_start = time_module.perf_counter()
    db_tags = [SOURCE_TO_DB_TAG.get(s, s) for s in WANTED_SOURCES]
    tags_param = ",".join(db_tags)
    co2_url = (
        f'http://0.0.0.0:9999/get?source=noga2&type=co2emission'
        f'&start_date={start_date}&tag={tags_param}&time=all&format=bin'
    )
    utils.retrieve_url(co2_url)
    fetched_dfs, latest_date = server.pop_df_result()
    if latest_date is None or not fetched_dfs:
        return

    start_date = latest_date.strftime("%d-%m-%Y")
    for source in WANTED_SOURCES:
        db_tag = SOURCE_TO_DB_TAG.get(source, source)
        if db_tag not in fetched_dfs:
            continue
        upper_bound = RATIO_ZMAX if source == SOURCE_RATIO else MAX_CO2_VALUE
        df = fetched_dfs[db_tag].clip(lower=MIN_CO2_VALUE, upper=upper_bound)
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
    sources = [s for s in WANTED_SOURCES if s in dfs]
    last_call = datetime.now()
    t_done = time_module.perf_counter()
    logging.info("co2.retrieve_data completed: total=%.2fs", t_done - t_start)


def compute_percent_df(source_df, total_df):
    """Return source as a percentage of Co2FromAllSitesWithoutRenewables, aligned on shared columns/index."""
    aligned_source, aligned_total = source_df.align(total_df, join='inner')
    percent_df = aligned_source.div(aligned_total).where(aligned_total > 0, 0) * 100
    percent_df = percent_df.clip(lower=0, upper=100)
    percent_df.index.name = source_df.index.name
    percent_df.columns.name = source_df.columns.name
    return percent_df


def _data_yrange(*scatter_series_list):
    """Compute a tight [ymin, ymax] from one or more scatter series, with a small 5% padding."""
    ymin = min(s.min() for s in scatter_series_list)
    ymax = max(s.max() for s in scatter_series_list)
    pad = (ymax - ymin) * 0.05 if ymax != ymin else abs(ymax) * 0.05 or 1
    return [ymin - pad, ymax + pad]


def co2_layout(nav_links):
    if not sources:
        retrieve_data()
    return html.Div([
        nav_links,
        dcc.Graph(
            id=CO2_HEATMAP_ID,
            style={'marginBottom': '0px'}
        ),
        html.Div([
            dcc.Checklist(id=CO2_FREEZE_SCALE_ID, options=[FREEZE_SCALE_VALUE], value=[])
        ],
            style={
                'display': 'flex',
                'justifyContent': 'flex-end',
                'width': '100%',
                'marginRight': '20px',
                'marginTop': '-50px',
                'marginBottom': '50px',
                'position': 'relative',
                'zIndex': '10'
            }
        ),
        dcc.RadioItems(
            id=CO2_DISPLAY_MODE_ID,
            options=[MODE_ABSOLUTE, MODE_PERCENT],
            value=MODE_ABSOLUTE,
            inline=True,
            style={'textAlign': 'center', 'fontSize': 18, 'marginBottom': '6px'}
        ),
        dcc.RadioItems(
            id=CO2_SOURCES_ID,
            options=sources,
            value=select_source,
            inline=True,
            style={'textAlign': 'center', 'fontSize': 20, 'marginTop': '0px'}
        ),
    ])


def register_callbacks(app):
    @app.callback(
        Output(CO2_SOURCES_ID, 'options'),
        Output(CO2_SOURCES_ID, 'value'),
        Input(CO2_DISPLAY_MODE_ID, 'value'),
        State(CO2_SOURCES_ID, 'value')
    )
    def update_co2_source_options(display_mode, current_source):
        if display_mode == MODE_PERCENT:
            options = [s for s in sources if s not in NON_PERCENT_SOURCES]
            value = select_source if current_source in NON_PERCENT_SOURCES else current_source
        else:
            options = sources
            value = current_source
        return options, value

    @app.callback(
        Output(CO2_HEATMAP_ID, 'figure'),
        [Input(CO2_SOURCES_ID, 'value'),
         Input(CO2_FREEZE_SCALE_ID, 'value'),
         Input(CO2_DISPLAY_MODE_ID, 'value')]
    )
    def update_co2_heatmap_output(source, freeze_scale_value, display_mode):
        global dfs, global_freeze_source, last_zrange, last_scatter_yrange
        freeze_checked = FREEZE_SCALE_VALUE in freeze_scale_value
        is_percent = display_mode == MODE_PERCENT
        triggered_id = callback_context.triggered[0]['prop_id'].split('.')[0]

        if triggered_id == CO2_FREEZE_SCALE_ID and freeze_checked:
            global_freeze_source = source
            raise PreventUpdate

        retrieve_data()
        logging.info(f"Update CO2 heatmap: {source} [{display_mode}]"
                     f"{(' (' + FREEZE_SCALE_VALUE + ')') if freeze_checked else ''}")

        source_df = dfs[source]

        if is_percent:
            if SOURCE_TOTAL not in dfs:
                logging.warning("Total CO2 not available for percent mode.")
                dfs_heatmap = source_df
            else:
                dfs_heatmap = compute_percent_df(source_df, dfs[SOURCE_TOTAL])
        else:
            dfs_heatmap = source_df

        n_y = len(dfs_heatmap.index) / 4

        if is_percent:
            scatter_y = dfs_heatmap.mean()
            scatter_hover = '<i>%{x} : %{y:,.1f}%</i><extra></extra>'
            scatter_yaxis_label = "%"
            heatmap_hover = '<i>%{x} %{y}</i><br>%{z:,.1f}%<extra></extra>'
        elif source == SOURCE_RATIO:
            if "ActualDemand" not in heatmap.dfs:
                heatmap.retrieve_data()
            if SOURCE_TOTAL in dfs and "ActualDemand" in heatmap.dfs:
                daily_co2 = dfs[SOURCE_TOTAL].reindex(columns=dfs_heatmap.columns).sum() / 12
                daily_gen = heatmap.dfs["ActualDemand"].reindex(columns=dfs_heatmap.columns).sum() / 12
                scatter_y = daily_co2.div(daily_gen).where(daily_gen > 0, 0).clip(lower=RATIO_ZMIN, upper=RATIO_ZMAX)
            else:
                scatter_y = dfs_heatmap.mean()
            scatter_hover = '<i>%{x} : %{y:,.2f} tCO2/MWh</i><extra></extra>'
            scatter_yaxis_label = "tCO2/MWh"
            heatmap_hover = '<i>%{x} %{y}</i><br>%{z:,.2f} tCO2/MWh<extra></extra>'
        else:
            scatter_y = dfs_heatmap.sum() / 12
            scatter_hover = '<i>%{x} : %{y:,.2f} tCO2</i><extra></extra>'
            scatter_yaxis_label = "tCO2"
            heatmap_hover = '<i>%{x} %{y}</i><br>%{z:,.2f} tCO2/h<extra></extra>'

        current_data_yrange = _data_yrange(scatter_y)

        if freeze_checked:
            if last_scatter_yrange[display_mode] is None:
                last_scatter_yrange[display_mode] = current_data_yrange
            scatter_yrange = last_scatter_yrange[display_mode]
        else:
            last_scatter_yrange[display_mode] = current_data_yrange
            scatter_yrange = current_data_yrange

        if is_percent:
            current_zmin = dfs_heatmap.min().min()
            current_zmax = dfs_heatmap.max().max()
        elif source == SOURCE_RATIO:
            current_zmin = RATIO_ZMIN
            current_zmax = RATIO_ZMAX
        else:
            current_zmin = HEATMAP_ZMIN
            current_zmax = HEATMAP_ZMAX
        if freeze_checked:
            if last_zrange[display_mode] is None:
                last_zrange[display_mode] = [current_zmin, current_zmax]
            zmin, zmax = last_zrange[display_mode]
        else:
            last_zrange[display_mode] = [current_zmin, current_zmax]
            zmin, zmax = current_zmin, current_zmax

        heatmap_colorscale = GREEN_COLORSCALE if source == SOURCE_RENEWABLES else BROWN_BLACK_COLORSCALE

        fig = make_subplots(rows=2, cols=1, row_heights=[100, 600], vertical_spacing=0.05, shared_xaxes=True)

        fig.add_trace(
            go.Scatter(
                x=dfs_heatmap.columns.values,
                y=scatter_y,
                hovertemplate=scatter_hover
            ),
            row=1, col=1)

        fig.add_trace(
            go.Heatmap(
                x=dfs_heatmap.columns.values,
                y=dfs_heatmap.index,
                z=dfs_heatmap,
                colorscale=heatmap_colorscale,
                zmin=zmin,
                zmax=zmax,
                colorbar={
                    'len': 0.8,
                    'y': 0.4,
                    'ticksuffix': '%' if is_percent else ''
                },
                hovertemplate=heatmap_hover
            ),
            row=2, col=1)

        fig.update_xaxes(showticklabels=False, row=1, col=1)
        fig.update_yaxes(title_text=scatter_yaxis_label, range=scatter_yrange, col=1, row=1)
        fig.update_yaxes(
            tickvals=[0, n_y - 1, n_y * 2 - 1, n_y * 3 - 1, n_y * 4 - 1],
            ticktext=['00:00', '06:00', '12:00', '18:00', '24:00'],
            row=2, col=1)
        fig.update_layout(
            height=800,
            showlegend=False,
            uirevision=True,
            title=go.layout.Title(
                x=0.5,
                xanchor='center',
                font={"family": "Hebrew", "size": 36},
                text='פליטות CO2'
            ),
        )
        return fig
