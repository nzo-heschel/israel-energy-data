import json
from datetime import datetime
from urllib.error import HTTPError, URLError

import time
from urllib.request import urlopen
import logging

from dash import Dash, dcc, html, Input, Output
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import calendar
import pandas as pd

from scripts import noga

# import locale
# locale.setlocale(locale.LC_ALL, 'he_IL')
# months_list = calendar.month_name[1:]
months_list = calendar.month_abbr[1:]

dash_app = Dash(__name__)
year_range = None
cached_data = None
last_call = datetime.fromtimestamp(0)  # epoch
last_max_year = 2050

YEAR_URL = "http://0.0.0.0:9999/get?source=noga&type=cost&start_date=01-01-2021&end_date=31-12-2050&time=month"
HEATMAP_URL = 'http://0.0.0.0:9999/get?source=noga2&type=energy&start_date=01-01-2024&time=all'

MAIN_GRAPH_ID = "main-graph"
YEAR_RANGE_SLIDER = "year-range-slider"
HEATMAP_ID = "heatmap-graph"
SOURCES_ID = "sources-checklist"

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

bar_4 = (
    {"conv": "#667788", "ren": "#00a060"},
    {"conv": "#a9a9a9", "ren": "#30d030"},
    {"conv": "#778899", "ren": "#00a020"},
    {"conv": "#808080", "ren": "#008000"},
)

YEAR_FROM: int = 2021
YEAR_TO: int = 2051  # excluding

bar_color = {}
for yr in range(YEAR_FROM, YEAR_TO):
    bar_color[yr] = bar_4[yr % 4]

dfs = {}
dfs_heatmap = None
dfs_zero = None
sources = []


def legend(yr, total, total_renewable=None):
    return '{:.0f}: {:.2f} TWh ({:.2f}%)'.format(
            yr, total_renewable, total_renewable / total * 100) if total_renewable \
        else '{:.0f}: {:.2f} TWh'.format(yr, total)


def log_year(yr, renewables, total):
    logging.info("{:.0f}: {:.2f} / {:.2f} ({:.2f}%)"
                 .format(yr, renewables / 1e3, total / 1e3, renewables / total * 100))


def retrieve_url(url):
    response = None
    retry = 1
    while True:
        retry += 1
        try:
            logging.info("Executing URL call: " + url)
            response = urlopen(url).read().decode('utf-8')
            break
        except (HTTPError, URLError) as ex:
            logging.warning("Exception while trying to get data: " + str(ex))
            logging.warning("Retry #{} in 2 seconds".format(retry))
            time.sleep(2)
    if not response:
        logging.error("Could not get data from server")
        return None
    return json.loads(response)


def retrieve_data():
    global cached_data, last_call, last_max_year, dfs_zero, sources, dfs
    time_since_last_call = datetime.now() - last_call
    if time_since_last_call.total_seconds() < 3600:
        logging.info("Time since last call: {} seconds. No URL call.".format(int(time_since_last_call.total_seconds())))
        return cached_data, last_max_year
    json_list = retrieve_url(YEAR_URL)
    cost_data_all = dict(sorted(json_list["noga.cost"].items(), key=lambda d: datetime.strptime(d[0], "%d-%m-%Y")))
    max_year = int(max(map(lambda date: date[6:], cost_data_all.keys())))
    cached_data = cost_data_all
    last_call = datetime.now()
    last_max_year = max_year

    json_list2 = retrieve_url(HEATMAP_URL)
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

    return cost_data_all, max_year


def bar_chart(cost_data_all, max_year, years_range):
    cost_data, trace_renewable, trace_conventional, year_total, year_total_renewable = {}, {}, {}, {}, {}
    traces = []
    years = years_range or [YEAR_FROM, max_year]
    for yr in range(YEAR_FROM, max_year + 1):
        cost_data[yr] = per_yer_cost_data(cost_data_all, str(yr))
        trace_renewable[yr], trace_conventional[yr], year_total[yr], year_total_renewable[yr] =\
            per_year_stacked_bar(cost_data[yr], yr)
        if years[0] <= yr <= years[1]:
            traces.append(trace_conventional[yr])
            traces.append(trace_renewable[yr])
            log_year(yr, year_total_renewable[yr], year_total[yr])
    fig = go.Figure(data=traces,
                    layout=go.Layout(
                        height=800,  # showlegend=False,
                        xaxis=go.layout.XAxis(title="", fixedrange=True, tickfont={"size": 18}),
                        yaxis=go.layout.YAxis(title='[MWh] ייצור',
                                              fixedrange=True,
                                              tickfont={"size": 18},
                                              titlefont={"size": 18},
                                              tickformat=",.0r"),
                        plot_bgcolor='snow',
                        legend={"font": {"size": 16}},
                        title=go.layout.Title(
                            x=0.5,
                            xanchor='center',
                            font={"family": "Hebrew", "size": 36},
                            text='ייצור חשמל בישראל'
                        )))
    fig.add_annotation(xref="paper", yref="paper", x=0, y=1, showarrow=False, text="מקור : נוגה", font={"size": 16})
    return fig


def per_yer_cost_data(data, yr):
    return {key: value for key, value in data.items() if yr in key}


def per_year_stacked_bar(cost_data, group):
    total = 0
    total_renewable = 0
    y_renewable = []
    y_conventional = []
    y_text = []
    for date in cost_data:
        renewable = cost_data[date]['00:00'][noga.COST_REN] * 0.5 / 1000
        conventional = cost_data[date]['00:00'][noga.COST_CONV] * 0.5 / 1000
        total = total + renewable + conventional
        total_renewable += renewable
        y_renewable.append(renewable)
        y_conventional.append(conventional)
        y_text.append("{:.1%}".format(renewable / (renewable + conventional)))
    trace_ren = go.Bar(x=months_list, y=y_renewable, text=y_text, textposition="auto", textfont={"size": 48},
                       offsetgroup=group,
                       name=legend(group, total / 1e3, total_renewable / 1e3), marker_color=bar_color[group]["ren"],
                       legendgroup="ren",
                       legendgrouptitle={"text": "  מתחדשות  ", "font": {"size": 20}},
                       hovertemplate='<i>%{x} ' + str(group) + ' Renewable</i>:<br>      %{y:,.0f} MWh')
    trace_conv = go.Bar(x=months_list, y=y_conventional,
                        offsetgroup=group, base=y_renewable,
                        name=legend(group, total / 1e3), marker_color=bar_color[group]["conv"],
                        legendgroup="conv",
                        legendgrouptitle={"text": "   סך הכל   ", "font": {"size": 20}},
                        hovertemplate='<i>%{x} ' + str(group) + ' Total</i>:<br>      %{y:,.0f} MWh')
    return trace_ren, trace_conv, total, total_renewable


def layout():
    global last_max_year
    _layout = html.Div([
        dcc.Graph(id=MAIN_GRAPH_ID, config={'displayModeBar': False}),
        html.Div([
            dcc.RangeSlider(
                YEAR_FROM, last_max_year,
                step=1,
                value=[YEAR_FROM, last_max_year],
                marks={yr: str(yr) for yr in range(YEAR_FROM, last_max_year + 1)},
                id=YEAR_RANGE_SLIDER),
            ],
            style={'width': '50%', 'padding-left': '15%', 'display': 'inline-block'}),
        dcc.Graph(
            id=HEATMAP_ID,
        ),
        dcc.RadioItems(
            id=SOURCES_ID,
            options=sources,
            value="Pv",
            inline=True,
            style={'textAlign': 'center', 'fontSize': 20})
    ])
    return _layout


def main():
    FORMAT = '%(asctime)s : %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    logging.info("Starting")
    retrieve_data()
    # Using a reference to the function (not a function call) makes the graph
    # reload (using fresh data from the server) on page refresh.
    dash_app.layout = layout
    dash_app.run_server(debug=False, host='0.0.0.0', port=9998)


@dash_app.callback(
    Output(MAIN_GRAPH_ID, 'figure'),
    Input(YEAR_RANGE_SLIDER, 'value'),
)
def update_output(range_from_slider):
    response, max_year = retrieve_data()
    fig = bar_chart(response, max_year, range_from_slider)
    return fig


@dash_app.callback(
    Output(HEATMAP_ID, 'figure'),
    Input(SOURCES_ID, 'value')
)
def update_heatmap_output(source):
    # retrieve_data()
    dfs_heatmap = dfs[source]
    n_y = len(dfs_heatmap.index) / 4
    fig = make_subplots(rows=2, cols=1, row_heights=[100, 600], vertical_spacing=0.05)
    fig.add_trace(
        go.Scatter(
            x=dfs_heatmap.columns.values,
            y=dfs_heatmap.sum() / 12,
            hovertemplate='<i>%{x} : %{y:,.2f} MWh</i><extra></extra>'

        ),
        row=1, col=1),
    fig.add_trace(
        go.Heatmap(
            x=dfs_heatmap.columns.values,
            y=dfs_heatmap.index,
            z=dfs_heatmap,
            colorscale=BLUE_RED_COLORSCALE,
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
    fig.update_layout(height=800)
    return fig


if __name__ == "__main__":
    main()
