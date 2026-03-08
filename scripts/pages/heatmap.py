from dash import dcc, html, Input, Output, callback_context
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import logging
import pandas as pd

from scripts import utils

HEATMAP_ID = "heatmap-graph"
SOURCES_ID = "sources-radioitems"
FREEZE_SCALE_ID = "freeze-scale"
DISPLAY_MODE_ID = "display-mode-radioitems"
FREEZE_SCALE_VALUE = "Freeze Scale"
MODE_ABSOLUTE = "Absolute"
MODE_PERCENT = "Percent"

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

global_zmin = 0
global_zmax = 1
global_freeze_source = None # The source for which the scale is frozen

def retrieve_data():
    global last_call, dfs_zero, sources, dfs, start_date
    time_since_last_call = datetime.now() - last_call
    if time_since_last_call.total_seconds() < 3600:
        logging.info("Time since last call: {} seconds. No URL call.".format(int(time_since_last_call.total_seconds())))
        return

    heatmap_url = f'http://0.0.0.0:9999/get?source=noga2&type=energy&start_date={start_date}&time=all&format=bin'
    json_list = utils.retrieve_url(heatmap_url)
    e = dict(sorted(json_list["noga2.energy"].items(), key=lambda d: datetime.strptime(d[0], "%d-%m-%Y")))
    d2 = {}
    date = None
    for _date, time_dict in e.items():
        date = datetime.strptime(_date, "%d-%m-%Y")
        for time, sources_dict in time_dict.items():
            # Noga has spurious data on 03-07-2025,14:36 and 28-05-2024,12:18
            if time == '12:18':
                time = '12:15'  # No data for 12:15 so use 12:18 instead.
            if time == '14:36':
                continue  # There are points for 14:35 and 14:40, so just skip it.
            for source, value in sources_dict.items():
                s = "Diesel" if source == "Solar" else source
                d2.setdefault(s, {}).setdefault(date, {})[time] = value
    start_date = date.strftime("%d-%m-%Y")
    for source, date_dict in d2.items():
        df = pd.DataFrame(date_dict).fillna(0)
        df.index.name = "Time"
        df.columns.name = "Date"
        df = df.reindex(sorted(df.columns), axis=1).sort_index()
        if source in dfs:
            dfs[source] = df.combine_first(dfs[source])
        else:
            dfs[source] = df
    dfs_zero = pd.DataFrame(0, index=dfs[select_source].index, columns=dfs[select_source].columns)
    sources = [s for s in list(d2.keys()) if s not in ["Actualdemand", "DemandManagement", "Renewables"]]
    last_call = datetime.now()


def compute_percent_df(source_df, demand_df):
    """Return source as a percentage of ActualDemand, aligned on shared columns/index."""
    aligned_source, aligned_demand = source_df.align(demand_df, join='inner')
    # Avoid division by zero — cells where demand is 0 become NaN
    percent_df = aligned_source.div(aligned_demand.replace(0, float('nan'))) * 100
    percent_df.index.name = source_df.index.name
    percent_df.columns.name = source_df.columns.name
    return percent_df


def heatmap_layout(nav_links):
    return html.Div([
        nav_links,
        dcc.Graph(
            id=HEATMAP_ID,
            style={'marginBottom': '0px'}
        ),
        html.Div([
            dcc.Checklist(id=FREEZE_SCALE_ID, options=[FREEZE_SCALE_VALUE], value=[])
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
            id=DISPLAY_MODE_ID,
            options=[MODE_ABSOLUTE, MODE_PERCENT],
            value=MODE_ABSOLUTE,
            inline=True,
            style={'textAlign': 'center', 'fontSize': 18, 'marginBottom': '6px'}
        ),
        dcc.RadioItems(
            id=SOURCES_ID,
            options=sources,
            value=select_source,
            inline=True,
            style={'textAlign': 'center', 'fontSize': 20, 'marginTop': '0px'}),
    ])

def register_callbacks(app):
    @app.callback(
        Output(HEATMAP_ID, 'figure'),
        [Input(SOURCES_ID, 'value'),
         Input(FREEZE_SCALE_ID, 'value'),
         Input(DISPLAY_MODE_ID, 'value')]
    )
    def update_heatmap_output(source, freeze_scale_value, display_mode):
        global dfs, global_zmin, global_zmax, global_freeze_source
        freeze_checked = FREEZE_SCALE_VALUE in freeze_scale_value
        is_percent = display_mode == MODE_PERCENT
        triggered_id = callback_context.triggered[0]['prop_id'].split('.')[0]
        if triggered_id == FREEZE_SCALE_ID:
            if freeze_checked: # When freezing the scale, no need to update the figure
                global_freeze_source = source # Keep track for which source the scale was frozen
                raise PreventUpdate
            else: # Freeze scale is unchecked
                if source == global_freeze_source: # If source is the same as the one when scale was frozen then no update
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
        fig = make_subplots(rows=2, cols=1, row_heights=[100, 600], vertical_spacing=0.05, shared_xaxes=True)

        if is_percent:
            # Top chart: mean daily percentage
            scatter_y = dfs_heatmap.mean()
            scatter_hover = '<i>%{x} : %{y:,.1f}%</i><extra></extra>'
            scatter_yaxis_label = "%"
            heatmap_hover = '<i>%{x} %{y}</i><br>%{z:,.1f}%<extra></extra>'
        else:
            scatter_y = dfs_heatmap.sum() / 12
            scatter_hover = '<i>%{x} : %{y:,.2f} MWh</i><extra></extra>'
            scatter_yaxis_label = "MWh"
            heatmap_hover = '<i>%{x} %{y}</i><br>%{z:,.2f} MW<extra></extra>'

        fig.add_trace(
            go.Scatter(
                x=dfs_heatmap.columns.values,
                y=scatter_y,
                hovertemplate=scatter_hover
            ),
            row=1, col=1)

        if not freeze_checked:
            global_zmin = dfs_heatmap.min().min()
            global_zmax = dfs_heatmap.max().max()

        fig.add_trace(
            go.Heatmap(
                x=dfs_heatmap.columns.values,
                y=dfs_heatmap.index,
                z=dfs_heatmap,
                colorscale=BLUE_RED_COLORSCALE,
                zmin=global_zmin,
                zmax=global_zmax,
                colorbar={
                    'len': 0.8,
                    'y': 0.4,
                    'ticksuffix': '%' if is_percent else ''
                },
                hovertemplate=heatmap_hover
            ),
            row=2, col=1)
        fig.update_xaxes(showticklabels=False, row=1, col=1)
        fig.update_yaxes(title_text=scatter_yaxis_label, col=1, row=1)
        fig.update_yaxes(
            tickvals=[0, n_y - 1, n_y * 2 - 1, n_y * 3 - 1, n_y * 4 - 1],
            ticktext=['00:00', '06:00', '12:00', '18:00', '24:00'],
            row=2, col=1)
        fig.update_layout(
            height=800,
            uirevision=True,
            title=go.layout.Title(
                x=0.5,
                xanchor='center',
                font={"family": "Hebrew", "size": 36},
                text='תמהיל הייצור'
            ),
        )
        return fig