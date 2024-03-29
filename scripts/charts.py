import json
from datetime import datetime
from urllib.error import HTTPError, URLError

import time
from urllib.request import urlopen
import logging

from dash import Dash, dcc, html, Input, Output
import plotly.graph_objects as go
import calendar

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

MAIN_GRAPH_ID = "main-graph"

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


def legend(yr, total, total_renewable=None):
    return '{:.0f}: {:.2f} TWh ({:.2f}%)'.format(
            yr, total_renewable, total_renewable / total * 100) if total_renewable \
        else '{:.0f}: {:.2f} TWh'.format(yr, total)


def log_year(yr, renewables, total):
    logging.info("{:.0f}: {:.2f} / {:.2f} ({:.2f}%)"
                 .format(yr, renewables / 1e3, total / 1e3, renewables / total * 100))


def retrieve_data():
    global cached_data, last_call, last_max_year
    time_since_last_call = datetime.now() - last_call
    if time_since_last_call.total_seconds() < 3600:
        logging.info("Time since last call: {} seconds. No URL call.".format(int(time_since_last_call.total_seconds())))
        return cached_data, last_max_year
    response = None
    retry = 1
    while True:
        retry += 1
        try:
            logging.info("Executing URL call")
            response = urlopen(YEAR_URL).read().decode('utf-8')
            break
        except (HTTPError, URLError) as ex:
            logging.warning("Exception while trying to get data: " + str(ex))
            logging.warning("Retry #{} in 2 seconds".format(retry))
            time.sleep(2)
    if not response:
        logging.error("Could not get data from server")
        exit(1)
    json_list = json.loads(response)
    cost_data_all = dict(sorted(json_list["noga.cost"].items(), key=lambda d: datetime.strptime(d[0], "%d-%m-%Y")))
    max_year = int(max(map(lambda date: date[6:], cost_data_all.keys())))
    cached_data = cost_data_all
    last_call = datetime.now()
    last_max_year = max_year
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
                id='year-range-slider'),
            ],
            style={'width': '50%', 'padding-left': '15%', 'display': 'inline-block'}),
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
    Input('year-range-slider', 'value'),
)
def update_output(range_from_slider):
    response, max_year = retrieve_data()
    fig = bar_chart(response, max_year, range_from_slider)
    return fig


if __name__ == "__main__":
    main()
