from dash import dcc, html, Input, Output
import plotly.graph_objects as go
from datetime import datetime
import calendar
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any

from scripts import utils, noga

MAIN_GRAPH_ID = "main-graph"
YEAR_RANGE_SLIDER = "year-range-slider"
YEAR_FROM: int = 2021
YEAR_TO: int = 2060  # excluding

YEAR_URL = "http://0.0.0.0:9999/get?source=noga&type=cost&start_date=01-01-2021&end_date=31-12-2023&time=month"
NEW_DATA_DEMAND_URL = "http://0.0.0.0:9999/get?source=noga2&type=energy&tag=ActualDemand&start_date=01-01-2024&time=month"
NEW_DATA_REN_URL = "http://0.0.0.0:9999/get?source=noga2&type=energy&tag=RenewableSum&start_date=01-01-2024&time=month"

months_list = calendar.month_abbr[1:]

year_range = None
cached_data = None
cached_year_data = None
last_call = datetime.fromtimestamp(0)  # epoch
last_max_year = 2050

bar_4 = (
    {"conv": "#667788", "ren": "#00a060"},
    {"conv": "#a9a9a9", "ren": "#30d030"},
    {"conv": "#778899", "ren": "#00a020"},
    {"conv": "#808080", "ren": "#008000"},
)

def retrieve_data() -> Tuple[Dict[str, Any], int]:
    global cached_data, last_call, last_max_year, cached_year_data
    time_since_last_call = datetime.now() - last_call
    if time_since_last_call.total_seconds() < 3600 and cached_data is not None:
        logging.info("Time since last call: {} seconds. No URL call.".format(int(time_since_last_call.total_seconds())))
        return cached_data, last_max_year
    
    cost_data_all = {}
    
    if cached_year_data is None:
        # Old noga data is retrieved only once
        json_list = utils.retrieve_url(YEAR_URL)
        if json_list:
            cached_year_data = json_list["noga.cost"]

    if cached_year_data:
        cost_data_all.update(cached_year_data)

    json_demand = utils.retrieve_url(NEW_DATA_DEMAND_URL)
    json_ren = utils.retrieve_url(NEW_DATA_REN_URL)

    if json_demand and json_ren:
        demand_data = json_demand.get("noga2.energy", {})
        ren_data = json_ren.get("noga2.energy", {})
        logging.info(f"Processing new data. Demand items: {len(demand_data)}, Ren items: {len(ren_data)}")
        
        for date, time_dict in demand_data.items():
            try:
                if date in ren_data:
                    demand_tags = time_dict.get("00:00", {})
                    ren_tags = ren_data[date].get("00:00", {})

                    demand_val = demand_tags.get("ActualDemand")
                    ren_val = ren_tags.get("RenewableSum")
                    
                    if demand_val is not None and ren_val is not None:
                        # Factor adjustment: divide by 6 so that * 0.5 / 1000 results in / 12 / 1000
                        demand = float(demand_val) / 6
                        renewable = float(ren_val) / 6
                        conventional = demand - renewable
                        
                        if date not in cost_data_all:
                            cost_data_all[date] = {"00:00": {}}
                        cost_data_all[date]["00:00"][noga.COST_REN] = renewable
                        cost_data_all[date]["00:00"][noga.COST_CONV] = conventional
                    else:
                        logging.debug(f"Missing data for {date}. Demand: {demand_val}, Ren: {ren_val}")

            except (KeyError, ValueError) as e:
                logging.warning(f"Error processing new data for {date}: {e}")

    if not cost_data_all:
        return cached_data if cached_data is not None else {}, last_max_year

    # Optimization: Sort using string split (faster than strptime) assuming dd-mm-yyyy
    cost_data_all = dict(sorted(cost_data_all.items(), key=lambda d: d[0].split('-')[::-1]))

    # Safety check for empty data
    if cost_data_all:
        max_year = int(max(map(lambda date: date.split('-')[2], cost_data_all.keys())))
    else:
        max_year = last_max_year

    cached_data = cost_data_all
    last_call = datetime.now()
    last_max_year = max_year
    return cost_data_all, max_year

def legend(yr: int, total: float, total_renewable: Optional[float] = None) -> str:
    if total_renewable:
        return f'{yr}: {total_renewable:.2f} TWh ({total_renewable / total * 100:.2f}%)'
    return f'{yr}: {total:.2f} TWh'

def log_year(yr: int, renewables: float, total: float):
    if total == 0:
        logging.info("{:.0f}: No Data".format(yr))
    else:
        logging.info("{:.0f}: {:.2f} / {:.2f} ({:.2f}%)"
                     .format(yr, renewables / 1e3, total / 1e3, renewables / total * 100))

def bar_chart_layout(nav_links):
    global last_max_year
    return html.Div([
        nav_links,
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
    ])

def bar_chart(cost_data_all: Dict, max_year: int, years_range: List[int]):
    traces = []
    start_year, end_year = years_range if years_range else [YEAR_FROM, max_year]

    # Optimization: Group data by year once (O(N)) instead of filtering in the loop (O(N^2))
    data_by_year = defaultdict(dict)
    for date_str, data in cost_data_all.items():
        # date_str is "dd-mm-yyyy"
        y = int(date_str.split('-')[2])
        data_by_year[y][date_str] = data

    # Only iterate the years we actually need to display
    for yr in range(start_year, end_year + 1):
        year_data = data_by_year.get(yr, {})
        trace_ren, trace_conv, total, total_ren = per_year_stacked_bar(year_data, yr)
        
        traces.append(trace_conv)
        traces.append(trace_ren)
        log_year(yr, total_ren, total)

    fig = go.Figure(data=traces,
                    layout=go.Layout(
                        height=800,  # showlegend=False,
                        xaxis=go.layout.XAxis(title="", fixedrange=True, tickfont={"size": 18}),
                        yaxis=go.layout.YAxis(title={"text": '[MWh] ייצור', "font":{"size": 18}},
                                              fixedrange=True,
                                              tickfont={"size": 18},
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

def per_year_stacked_bar(cost_data: Dict, group: int):
    total = 0
    total_renewable = 0
    y_renewable = []
    y_conventional = []
    y_text = []
    for date in cost_data:
        renewable = cost_data[date]['00:00'][noga.COST_REN] * 0.5 / 1000
        conventional = cost_data[date]['00:00'][noga.COST_CONV] * 0.5 / 1000
        
        total_month = renewable + conventional
        total = total + total_month
        total_renewable += renewable
        
        y_renewable.append(renewable)
        y_conventional.append(conventional)
        if total_month > 0:
            y_text.append("{:.1%}".format(renewable / total_month))
        else:
            y_text.append("")
    trace_ren = go.Bar(x=months_list, y=y_renewable,
                       text=y_text, textposition="auto", textfont={"size": 48},
                       offsetgroup=group,
                       name=legend(group, total / 1e3, total_renewable / 1e3),
                       marker_color=bar_4[group % 4]["ren"],
                       legendgroup="ren",
                       legendgrouptitle={"text": "  מתחדשות  ", "font": {"size": 20}},
                       hovertemplate='<i>%{x} ' + str(group) + ' Renewable</i>:<br>      %{y:,.0f} MWh')
    trace_conv = go.Bar(x=months_list, y=y_conventional,
                        offsetgroup=group, base=y_renewable,
                        name=legend(group, total / 1e3), marker_color=bar_4[group % 4]["conv"],
                        legendgroup="conv",
                        legendgrouptitle={"text": "   סך הכל   ", "font": {"size": 20}},
                        hovertemplate='<i>%{x} ' + str(group) + ' Total</i>:<br>      %{y:,.0f} MWh')
    return trace_ren, trace_conv, total, total_renewable


def register_callbacks(app):
    @app.callback(
        Output(MAIN_GRAPH_ID, 'figure'),
        Input(YEAR_RANGE_SLIDER, 'value'),
    )
    def update_output(range_from_slider):
        response, max_year = retrieve_data()
        fig = bar_chart(response, max_year, range_from_slider)
        return fig
