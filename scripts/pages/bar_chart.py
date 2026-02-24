from dash import dcc, html, Input, Output
import plotly.graph_objects as go
from datetime import datetime
import calendar
import logging

from scripts import utils, noga

MAIN_GRAPH_ID = "main-graph"
YEAR_RANGE_SLIDER = "year-range-slider"
YEAR_FROM: int = 2021
YEAR_TO: int = 2060  # excluding

YEAR_URL = "http://0.0.0.0:9999/get?source=noga&type=cost&start_date=01-01-2021&end_date=31-12-2050&time=month"
NEW_DATA_DEMAND_URL = "http://0.0.0.0:9999/get?source=noga2&type=energy&tag=ActualDemand&start_date=01-01-2024&time=month"
NEW_DATA_REN_URL = "http://0.0.0.0:9999/get?source=noga2&type=energy&tag=RenewableSum&start_date=01-01-2024&time=month"

months_list = calendar.month_abbr[1:]

year_range = None
cached_data = None
last_call = datetime.fromtimestamp(0)  # epoch
last_max_year = 2050

bar_4 = (
    {"conv": "#667788", "ren": "#00a060"},
    {"conv": "#a9a9a9", "ren": "#30d030"},
    {"conv": "#778899", "ren": "#00a020"},
    {"conv": "#808080", "ren": "#008000"},
)

def retrieve_data():
    global cached_data, last_call, last_max_year
    time_since_last_call = datetime.now() - last_call
    if time_since_last_call.total_seconds() < 3600 and cached_data is not None:
        logging.info("Time since last call: {} seconds. No URL call.".format(int(time_since_last_call.total_seconds())))
        return cached_data, last_max_year
    
    cost_data_all = {}
    
    json_list = utils.retrieve_url(YEAR_URL)
    if json_list:
        cost_data_all.update(json_list["noga.cost"])

    json_demand = utils.retrieve_url(NEW_DATA_DEMAND_URL)
    json_ren = utils.retrieve_url(NEW_DATA_REN_URL)

    if json_demand and json_ren:
        demand_data = json_demand.get("noga2.energy", {})
        ren_data = json_ren.get("noga2.energy", {})
        logging.info(f"Processing new data. Demand items: {len(demand_data)}, Ren items: {len(ren_data)}")
        
        for date, time_dict in demand_data.items():
            if date in ren_data:
                try:
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
                        logging.info(f"Missing data for {date}. Demand: {demand_val}, Ren: {ren_val}")

                except (KeyError, ValueError) as e:
                    logging.warning(f"Error processing new data for {date}: {e}")

    if not cost_data_all:
        return cached_data if cached_data is not None else {}, last_max_year

    cost_data_all = dict(sorted(cost_data_all.items(), key=lambda d: datetime.strptime(d[0], "%d-%m-%Y")))

    max_year = int(max(map(lambda date: date[6:], cost_data_all.keys())))
    cached_data = cost_data_all
    last_call = datetime.now()
    last_max_year = max_year
    return cost_data_all, max_year

def legend(yr, total, total_renewable=None):
    return '{:.0f}: {:.2f} TWh ({:.2f}%)'.format(
        yr, total_renewable, total_renewable / total * 100) if total_renewable \
        else '{:.0f}: {:.2f} TWh'.format(yr, total)

def log_year(yr, renewables, total):
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

def bar_chart(cost_data_all, max_year, years_range):
    cost_data, trace_renewable, trace_conventional, year_total, year_total_renewable = {}, {}, {}, {}, {}
    traces = []
    years = years_range or [YEAR_FROM, max_year]
    for yr in range(YEAR_FROM, max_year + 1):
        cost_data[yr] = per_yer_cost_data(cost_data_all, str(yr))
        trace_renewable[yr], trace_conventional[yr], year_total[yr], year_total_renewable[yr] = \
            per_year_stacked_bar(cost_data[yr], yr)
        if years[0] <= yr <= years[1]:
            traces.append(trace_conventional[yr])
            traces.append(trace_renewable[yr])
            log_year(yr, year_total_renewable[yr], year_total[yr])
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
