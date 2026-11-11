from dash import dcc, html, Input, Output, State
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
CO2_DISPLAY_MODE_ID = "co2-display-mode-radioitems"
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
RENEWABLES_YMAX = 30000

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


def _format_co2_val(val):
    if abs(val) >= 1_000_000:
        return f"{val / 1_000_000:,.2f} MtCO2"
    if abs(val) >= 1_000:
        return f"{val / 1_000:,.2f} ktCO2"
    return f"{val:,.2f} tCO2"


def _data_yrange(*scatter_series_list):
    """Compute a [0, ymax] range from one or more scatter series, excluding the top 8 peaks, with 5% top padding."""
    ymax = max(
        (s.nlargest(9).iloc[-1] if len(s.dropna()) > 8 else s.max())
        for s in scatter_series_list
    )
    pad = ymax * 0.05 if ymax > 0 else 1
    return [0, ymax + pad]


def co2_layout(nav_links):
    if not sources:
        retrieve_data()
    return html.Div([
        nav_links,
        dcc.Graph(
            id=CO2_HEATMAP_ID,
            style={'marginBottom': '0px'}
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
         Input(CO2_DISPLAY_MODE_ID, 'value')]
    )
    def update_co2_heatmap_output(source, display_mode):
        global dfs
        is_percent = display_mode == MODE_PERCENT

        retrieve_data()
        logging.info(f"Update CO2 heatmap: {source} [{display_mode}]")

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
            scatter_customdata = None
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
            scatter_customdata = None
            scatter_hover = '<i>%{x} : %{y:,.2f} tCO2/MWh</i><extra></extra>'
            scatter_yaxis_label = "tCO2/MWh"
            heatmap_hover = '<i>%{x} %{y}</i><br>%{z:,.2f} tCO2/MWh<extra></extra>'
        else:
            scatter_y = dfs_heatmap.sum() / 12
            scatter_customdata = [_format_co2_val(v) for v in scatter_y]
            scatter_hover = '<i>%{x} : %{customdata}</i><extra></extra>'
            scatter_yaxis_label = "tCO2"
            heatmap_hover = '<i>%{x} %{y}</i><br>%{z:,.2f} tCO2/h<extra></extra>'

        if source == SOURCE_RENEWABLES and not is_percent:
            scatter_yrange = [0, RENEWABLES_YMAX]
        else:
            scatter_yrange = _data_yrange(scatter_y)

        if is_percent:
            zmin = dfs_heatmap.min().min()
            zmax = dfs_heatmap.max().max()
        elif source == SOURCE_RATIO:
            zmin = RATIO_ZMIN
            zmax = RATIO_ZMAX
        else:
            zmin = HEATMAP_ZMIN
            zmax = HEATMAP_ZMAX

        heatmap_colorscale = GREEN_COLORSCALE if source == SOURCE_RENEWABLES else BROWN_BLACK_COLORSCALE

        fig = make_subplots(rows=2, cols=1, row_heights=[100, 600], vertical_spacing=0.05, shared_xaxes=True)

        if source == SOURCE_TOTAL:
            cols = dfs_heatmap.columns
            gas_y = dfs[SOURCE_GAS].reindex(columns=cols).sum() / 12
            coal_y = dfs[SOURCE_COAL].reindex(columns=cols).sum() / 12
            other_y = (dfs[SOURCE_DIESEL] + dfs[SOURCE_MAZUT]).reindex(columns=cols).sum() / 12
            total_y = gas_y + coal_y + other_y
            scatter_yaxis_label = "tCO2"
            scatter_yrange = _data_yrange(total_y)

            for area_name, area_y, area_color in [
                (SOURCE_GAS, gas_y, "rgb(210, 180, 140)"),
                (SOURCE_COAL, coal_y, "rgb(120, 72, 32)"),
                (f"{SOURCE_DIESEL} + {SOURCE_MAZUT}", other_y, "rgb(30, 18, 8)"),
            ]:
                area_pct = area_y.div(total_y).where(total_y > 0, 0) * 100
                customdata = [
                    (_format_co2_val(val), f"{pct:.2f}", _format_co2_val(tot))
                    for val, pct, tot in zip(area_y, area_pct, total_y)
                ]
                fig.add_trace(
                    go.Scatter(
                        x=cols.values,
                        y=area_y,
                        customdata=customdata,
                        name=area_name,
                        stackgroup="one",
                        line=dict(width=0.5, color=area_color),
                        fillcolor=area_color,
                        hovertemplate=(
                            f"<i>%{{x}}<br>"
                            f"{area_name}: %{{customdata[0]}} (%{{customdata[1]}}%)<br>"
                            f"Total: %{{customdata[2]}}</i><extra></extra>"
                        ),
                    ),
                    row=1, col=1)
        else:
            fig.add_trace(
                go.Scatter(
                    x=dfs_heatmap.columns.values,
                    y=scatter_y,
                    customdata=scatter_customdata,
                    line=dict(color="green") if source == SOURCE_RENEWABLES else None,
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
                text='CO2 פליטות'
            ),
        )
        return fig
