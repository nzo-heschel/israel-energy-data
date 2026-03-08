from dash import dcc, html, Input, Output, State, callback_context
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
FREEZE_SCALE_VALUE = "Freeze Scale"
VIEW_MODE_ID = "view-mode"
VIEW_STATE_STORE_ID = "view-state-store"

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

def heatmap_layout(nav_links):
    return html.Div([
        nav_links,
        dcc.Store(id=VIEW_STATE_STORE_ID, data={}),
        dcc.Graph(
            id=HEATMAP_ID,
            style={'marginBottom': '0px'}
        ),
        html.Div([
            dcc.RadioItems(
                id=VIEW_MODE_ID,
                options=['Absolute', 'Percent'],
                value='Absolute',
                inline=False,
                style={'marginRight': '20px'}
            ),
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
            value=select_source,
            inline=True,
            style={'textAlign': 'center', 'fontSize': 20, 'marginTop': '0px'}),
    ])

def register_callbacks(app):
    @app.callback(
        Output(VIEW_STATE_STORE_ID, 'data'),
        [Input(HEATMAP_ID, 'relayoutData')],
        [State(VIEW_STATE_STORE_ID, 'data'),
         State(VIEW_MODE_ID, 'value')]
    )
    def update_view_state(relayout_data, current_data, view_mode):
        if not relayout_data:
            raise PreventUpdate

        current_data = current_data or {}
        view_mode_key = view_mode.lower()

        def get_range(axis_prefix):
            if f'{axis_prefix}.range[0]' in relayout_data and f'{axis_prefix}.range[1]' in relayout_data:
                return [relayout_data[f'{axis_prefix}.range[0]'], relayout_data[f'{axis_prefix}.range[1]']]
            elif f'{axis_prefix}.range' in relayout_data:
                return relayout_data[f'{axis_prefix}.range']
            return None

        def is_autorange(axis_prefix):
            return relayout_data.get(f'{axis_prefix}.autorange', False)

        # Update shared axes
        if is_autorange('xaxis'): current_data.pop('xaxis', None)
        else:
            x_range = get_range('xaxis')
            if x_range: current_data['xaxis'] = x_range

        if is_autorange('yaxis2'): current_data.pop('yaxis2', None)
        else:
            y2_range = get_range('yaxis2')
            if y2_range: current_data['yaxis2'] = y2_range

        # Update top Y-axis state for the current view mode
        current_data.setdefault(view_mode_key, {})
        if is_autorange('yaxis'):
            current_data[view_mode_key].pop('yaxis', None)
        else:
            y_top_range = get_range('yaxis')
            if y_top_range:
                current_data[view_mode_key]['yaxis'] = y_top_range

        logging.info(f"Updated view state: {current_data}")
        return current_data

    @app.callback(
        Output(HEATMAP_ID, 'figure'),
        [Input(SOURCES_ID, 'value'),
         Input(FREEZE_SCALE_ID, 'value'),
         Input(VIEW_MODE_ID, 'value')],
        [State(VIEW_STATE_STORE_ID, 'data')]
    )
    def update_heatmap_output(source, freeze_scale_value, view_mode, view_state):
        global dfs, global_zmin, global_zmax
        freeze_checked = FREEZE_SCALE_VALUE in freeze_scale_value
        triggered_id = callback_context.triggered[0]['prop_id'].split('.')[0]

        retrieve_data()
        logging.info(f"Update heatmap: {source} | View: {view_mode} | Frozen: {freeze_checked}")

        if view_mode == 'Percent':
            dfs_heatmap = (dfs[source] / dfs['ActualDemand']) * 100
            top_y = (dfs[source].sum() / dfs['ActualDemand'].sum()) * 100
            y_axis_title = "%"
            hover_template_top = '<i>%{x} : %{y:.2f} %</i><extra></extra>'
            hover_template_heatmap = '<i>%{x} %{y}</i><br>%{z:.2f} %<extra></extra>'
        else:
            dfs_heatmap = dfs[source]
            top_y = dfs_heatmap.sum() / 12
            y_axis_title = "MWh"
            hover_template_top = '<i>%{x} : %{y:,.2f} MWh</i><extra></extra>'
            hover_template_heatmap = '<i>%{x} %{y}</i><br>%{z:,.2f} MW<extra></extra>'

        n_y = len(dfs_heatmap.index) / 4
        fig = make_subplots(rows=2, cols=1, row_heights=[100, 600], vertical_spacing=0.05, shared_xaxes=True)
        fig.add_trace(go.Scatter(x=dfs_heatmap.columns.values, y=top_y, hovertemplate=hover_template_top), row=1, col=1)

        if not freeze_checked or triggered_id == VIEW_MODE_ID:
            global_zmin = dfs_heatmap.min().min()
            global_zmax = dfs_heatmap.max().max()

        fig.add_trace(go.Heatmap(x=dfs_heatmap.columns.values, y=dfs_heatmap.index, z=dfs_heatmap, colorscale=BLUE_RED_COLORSCALE, zmin=global_zmin, zmax=global_zmax, colorbar={'len': 0.8, 'y': 0.4}, hovertemplate=hover_template_heatmap), row=2, col=1)
        fig.update_xaxes(showticklabels=False, row=1, col=1)
        fig.update_yaxes(title_text=y_axis_title, col=1, row=1)

        view_state = view_state or {}
        view_mode_key = view_mode.lower()
        
        # Determine uirevision and Y-axis behavior
        revision_key = ""
        if not freeze_checked:
            # Rule 1 & 4: Not frozen, so always autoscale Y. Use a unique revision to force a reset.
            fig.update_yaxes(autorange=True, row=1, col=1)
            revision_key = f"reset-{datetime.now().timestamp()}"
        else:
            # Rule 2, 3, 5: Frozen. Use a stable key for preservation.
            revision_key = f"frozen-{view_mode}"
            # Rule 5b: Try to apply a stored manual range for the current view mode.
            stored_y_range = view_state.get(view_mode_key, {}).get('yaxis')
            if stored_y_range:
                fig.update_yaxes(range=stored_y_range, row=1, col=1)
            elif triggered_id == VIEW_MODE_ID:
                # Rule 5b (first time): No stored range for this mode, so autoscale it once.
                fig.update_yaxes(autorange=True, row=1, col=1)
            # Rule 2 & 3: If no stored range and not switching modes, do nothing.
            # The stable `revision_key` will preserve the last view.

        # Always preserve shared axes if they are in the state, to counteract the reset key
        if 'xaxis' in view_state: fig.update_xaxes(range=view_state['xaxis'])
        if 'yaxis2' in view_state: fig.update_yaxes(range=view_state['yaxis2'], row=2, col=1)

        fig.update_yaxes(tickvals=[0, n_y - 1, n_y * 2 - 1, n_y * 3 - 1, n_y * 4 - 1], ticktext=['00:00', '06:00', '12:00', '18:00', '24:00'], row=2, col=1)
        fig.update_layout(height=800, uirevision=revision_key, title=go.layout.Title(x=0.5, xanchor='center', font={"family": "Hebrew", "size": 36}, text='תמהיל הייצור'))
        return fig
