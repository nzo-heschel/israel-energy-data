from datetime import datetime
import os
import logging
import utils

from dash import Dash, dcc, html, callback_context, Input, Output
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import pandas as pd

from pages.home import home_layout
# from pages.heatmap import heatmap_layout
import pages.bar_chart as bar_chart

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_PATH = os.path.join(ROOT_DIR, 'assets')
dash_app = Dash(__name__, assets_folder=ASSETS_PATH)
LOGO_URL = dash_app.get_asset_url('logo.png')

HEATMAP_URL = 'http://0.0.0.0:9999/get?source=noga2&type=energy&start_date=01-01-2024&time=all&format=bin'

HEATMAP_ID = "heatmap-graph"
SOURCES_ID = "sources-checklist"
FREEZE_SCALE_ID = "freeze_scale"
FREEZE_SCALE_VALUE = "Freeze Scale"

PATH_BAR_CHART = '/bar-chart'
PATH_HEATMAP = '/heatmap'

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

def legend(yr, total, total_renewable=None):
    return '{:.0f}: {:.2f} TWh ({:.2f}%)'.format(
            yr, total_renewable, total_renewable / total * 100) if total_renewable \
        else '{:.0f}: {:.2f} TWh'.format(yr, total)


def log_year(yr, renewables, total):
    logging.info("{:.0f}: {:.2f} / {:.2f} ({:.2f}%)"
                 .format(yr, renewables / 1e3, total / 1e3, renewables / total * 100))



def retrieve_data():
    global cached_data, last_call, last_max_year, dfs_zero, sources, dfs


    json_list2 = utils.retrieve_url(HEATMAP_URL)
    e = dict(sorted(json_list2["noga2.energy"].items(), key=lambda d: datetime.strptime(d[0], "%d-%m-%Y")))
    d2 = {}
    for _date, time_dict in e.items():
        date = datetime.strptime(_date, "%d-%m-%Y")
        for time, sources_dict in time_dict.items():
            for source, value in sources_dict.items():
                s = "Diesel" if source == "Solar" else source
                d2.setdefault(s, {}).setdefault(date, {})[time] = value
    dfs = {}
    for source, date_dict in d2.items():
        df = pd.DataFrame(date_dict).fillna(0)
        df.index.name = "Time"
        df.columns.name = "Date"
        df = df.reindex(sorted(df.columns), axis=1).sort_index()
        dfs[source] = df
    dfs_zero = pd.DataFrame(0, index=dfs["Pv"].index, columns=dfs["Pv"].columns)
    sources = [s for s in list(d2.keys()) if s not in ["Actualdemand", "DemandManagement", "Renewables"]]

    return




nav_links = html.Div([
    dcc.Link('דף הבית', href='/'),
    html.Span(' | '),
    dcc.Link('אנרגיות מתחדשות', href=PATH_BAR_CHART),
    html.Span(' | '),
    dcc.Link('תמהיל הייצור', href=PATH_HEATMAP),
    html.Hr()
], style={'padding': '10px', 'textAlign': 'right'})




# --- Heatmap Page Layout ---
def heatmap_layout():
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
            id=SOURCES_ID,
            options=sources,
            value="Pv",
            inline=True,
            style={'textAlign': 'center', 'fontSize': 20, 'marginTop': '0px'}),
    ])


# --- New Top-Level Application Layout ---
def app_layout():
    # This is the single layout structure Dash requires for routing
    return html.Div([
        dcc.Location(id='url', refresh=False),
        html.Div(id='page-content')
    ])


def main():
    logging.info("Starting charts")
    retrieve_data()
    bar_chart.retrieve_data()
    # Use the new top-level layout function for routing
    dash_app.layout = app_layout
    dash_app.run(debug=False, host='0.0.0.0', port=9998)


@dash_app.callback(Output('page-content', 'children'),
                   [Input('url', 'pathname')])
def display_page(pathname):
    if pathname == PATH_BAR_CHART:
        return bar_chart.bar_chart_layout(nav_links)
    elif pathname == PATH_HEATMAP:
        return heatmap_layout()
    else:
        # Default to home page for '/' or any unrecognized path
        return home_layout(nav_links, LOGO_URL)


@dash_app.callback(
    Output(HEATMAP_ID, 'figure'),
    [Input(SOURCES_ID, 'value'),
     Input(FREEZE_SCALE_ID, 'value')]
)
def update_heatmap_output(source, freeze_scale_value):
    global dfs, global_zmin, global_zmax, global_freeze_source

    freeze_checked = FREEZE_SCALE_VALUE in freeze_scale_value
    triggered_id = callback_context.triggered[0]['prop_id'].split('.')[0]
    if triggered_id == FREEZE_SCALE_ID:
        if freeze_checked: # When freezing the scale, no need to update the figure
            global_freeze_source = source # Keep track for which source the scale was frozen
            raise PreventUpdate
        else: # Freeze scale is unchecked
            if source == global_freeze_source: # If source is the same as the one when scale was frozen then no update
                raise PreventUpdate

    logging.info(f"Update heatmap: {source}"
                 f"{'' if FREEZE_SCALE_VALUE not in freeze_scale_value else (' (' + FREEZE_SCALE_VALUE + ')')}")
    dfs_heatmap = dfs[source]
    n_y = len(dfs_heatmap.index) / 4
    fig = make_subplots(rows=2, cols=1, row_heights=[100, 600], vertical_spacing=0.05)
    fig.add_trace(
        go.Scatter(
            x=dfs_heatmap.columns.values,
            y=dfs_heatmap.sum() / 12,
            hovertemplate='<i>%{x} : %{y:,.2f} MWh</i><extra></extra>'
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
            colorbar={'len': 0.8, 'y': 0.4},
            hovertemplate='<i>%{x} %{y}</i><br>%{z:,.2f} MW<extra></extra>'
        ),
        row=2, col=1)
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    fig.update_yaxes(title_text="MWh", col=1, row=1)
    fig.update_yaxes(
        tickvals=[0, n_y - 1, n_y * 2 - 1, n_y * 3 - 1, n_y * 4 - 1],
        ticktext=['00:00', '06:00', '12:00', '18:00', '24:00'],
        row=2, col=1)
    fig.update_layout(height=800,
                      title=go.layout.Title(
                          x=0.5,
                          xanchor='center',
                          font={"family": "Hebrew", "size": 36},
                          text='תמהיל הייצור'
                      ),
    )

    return fig

bar_chart.register_bar_chart_callbacks(dash_app)

if __name__ == "__main__":
    main()
