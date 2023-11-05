import json
from datetime import datetime
from urllib.error import HTTPError

import time
from urllib.request import urlopen
import logging

from dash import Dash, dcc, html
import plotly.graph_objects as go
import calendar

from scripts import noga

# import locale
# locale.setlocale(locale.LC_ALL, 'he_IL')
# months_list = calendar.month_name[1:]
months_list = calendar.month_abbr[1:]

dash_app = Dash(__name__)

YEAR_URL = "http://0.0.0.0:9999/get?source=noga&type=cost&start_date=01-01-2021&end_date=31-12-2023&time=month"
bar_color = {2021: {"conv": "Gray", "ren": "Green"},
             2022: {"conv": "lightslategrey", "ren": "Teal"},
             2023: {"conv": "darkgrey", "ren": "limegreen"}}


def legend(year, total, total_renewable=None):
    return '{:.0f}: {:.2f} TWh ({:.2f}%)'.format(
            year, total_renewable, total_renewable / total * 100) if total_renewable \
        else '{:.0f}: {:.2f} TWh'.format(year, total)


def print_year(renewables, total):
    logging.info("2021: {:.2f} / {:.2f} ({:.2f}%)".format(renewables / 1e3, total / 1e3, renewables / total * 100))


def retrieve_data():
    response = None
    for retry in range(5):
        try:
            logging.info("Executing URL call")
            response = urlopen(YEAR_URL)
            break
        except HTTPError as ex:
            logging.warning("Exception while trying to get data: " + str(ex))
            logging.warning("Retry #{} in 2 seconds".format(retry + 1))
            time.sleep(2)
    if not response:
        logging.error("Could not get data from server")
        exit(1)
    return response


def bar_chart(response):
    string = response.read().decode('utf-8')
    json_list = json.loads(string)
    cost_data_all = dict(sorted(json_list["noga.cost"].items(), key=lambda d: datetime.strptime(d[0], "%d-%m-%Y")))
    cost_data_2021 = per_yer_cost_data(cost_data_all, "2021")
    cost_data_2022 = per_yer_cost_data(cost_data_all, "2022")
    cost_data_2023 = per_yer_cost_data(cost_data_all, "2023")
    trace_ren_2021, trace_conv_2021, total_2021, total_renewable_2021 = per_year_stacked_bar(cost_data_2021, 2021)
    trace_ren_2022, trace_conv_2022, total_2022, total_renewable_2022 = per_year_stacked_bar(cost_data_2022, 2022)
    trace_ren_2023, trace_conv_2023, total_2023, total_renewable_2023 = per_year_stacked_bar(cost_data_2023, 2023)
    print_year(total_renewable_2021, total_2021)
    print_year(total_renewable_2022, total_2022)
    print_year(total_renewable_2023, total_2023)
    fig = go.Figure(data=[trace_conv_2021, trace_ren_2021,
                          trace_conv_2022, trace_ren_2022,
                          trace_conv_2023, trace_ren_2023],
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


def per_yer_cost_data(data, year):
    return {key: value for key, value in data.items() if year in key}


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
    response = retrieve_data()
    fig = bar_chart(response)
    _layout = html.Div([
        dcc.Graph(id="graph", config={'displayModeBar': False}, figure=fig),
    ])
    return _layout


def main():
    FORMAT = '%(asctime)s : %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    logging.info("Starting")
    # Using a reference to the function (not a function call) makes the graph
    # reload (using fresh data from the server) on page refresh.
    dash_app.layout = layout
    dash_app.run_server(debug=False, host='0.0.0.0', port=9998)


if __name__ == "__main__":
    main()
