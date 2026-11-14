from dash import dcc, html, Input, Output
import dash_mantine_components as dmc
import plotly.graph_objects as go
from datetime import datetime
import calendar
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any

from scripts import utils, noga
from . import heatmap, ui

MAIN_GRAPH_ID = "main-graph"
YEAR_RANGE_SLIDER = "year-range-slider"
YEARLY_SWITCH_ID = "yearly-switch"
TOTAL_SWITCH_ID = "total-switch"
PERCENT_SWITCH_ID = "percent-switch"
PERCENT_WRAPPER_ID = "percent-switch-wrapper"
CONTROL_COLOR = "indigo"
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

# Alternating shades so adjacent years are distinguishable: green family for renewables, grays for the rest
bar_4 = (
    {"conv": "#adb5bd", "ren": "#1baf7a"},
    {"conv": "#ced4da", "ren": "#63d6a8"},
    {"conv": "#868e96", "ren": "#0f8a5f"},
    {"conv": "#dee2e6", "ren": "#38c28f"},
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

    if "ActualDemand" in heatmap.dfs and "RenewableSum" in heatmap.dfs:
        demand_monthly = heatmap.dfs["ActualDemand"].sum().groupby(lambda dt: f"01-{dt.month:02d}-{dt.year}").sum()
        ren_monthly = heatmap.dfs["RenewableSum"].sum().groupby(lambda dt: f"01-{dt.month:02d}-{dt.year}").sum()
        logging.info(f"Computing bar_chart 2024+ data from heatmap.dfs ({len(demand_monthly)} months)")
        for date, demand_val in demand_monthly.items():
            if date in ren_monthly:
                demand = float(demand_val) / 6
                renewable = float(ren_monthly[date]) / 6
                conventional = demand - renewable
                if date not in cost_data_all:
                    cost_data_all[date] = {"00:00": {}}
                cost_data_all[date]["00:00"][noga.COST_REN] = renewable
                cost_data_all[date]["00:00"][noga.COST_CONV] = conventional
    else:
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


def rtl(label: str, value: str) -> str:
    """A right-to-left tooltip line: Hebrew label on the right, then the value with its unit.
    Plotly draws tooltips as left-to-right SVG text, so without explicit embeddings the bidi algorithm
    pushes 'GWh' past the Hebrew label or splits it from its number."""
    return "\u202b" + label + " \u202a" + value + "\u202c\u202c"


def log_year(yr: int, renewables: float, total: float):
    if total == 0:
        logging.info("{:.0f}: No Data".format(yr))
    else:
        logging.info("{:.0f}: {:.2f} / {:.2f} ({:.2f}%)"
                     .format(yr, renewables / 1e3, total / 1e3, renewables / total * 100))

def bar_chart_layout():
    global last_max_year
    controls = dmc.Group([
        dmc.Box([
            ui.control_label('טווח שנים'),
            # The slider runs natively right-to-left (forcing it LTR inside the RTL page breaks dragging),
            # so years are negated to keep the earliest year on the left like the chart's x axis.
            dmc.RangeSlider(
                id=YEAR_RANGE_SLIDER,
                min=-last_max_year, max=-YEAR_FROM, step=1, minRange=0,
                value=[-last_max_year, -YEAR_FROM],
                marks=[{'value': -yr, 'label': str(yr)} for yr in range(YEAR_FROM, last_max_year + 1)],
                # step=1 already snaps to whole years; restrictToMarks would stop both thumbs sharing a year
                label=None,
                color=CONTROL_COLOR,
                mb='lg',
            ),
        ], w={'base': '100%', 'sm': 420}, className='year-slider'),
        # Both sides of each switch are equal choices, so the track keeps one colour in either state
        dmc.Switch(id=YEARLY_SWITCH_ID, label='תצוגה שנתית/חודשית', checked=False, size='md', color=CONTROL_COLOR,
                   className='choice-switch'),
        dmc.Switch(id=TOTAL_SWITCH_ID, label='מתחדשות/סך הכל', checked=True, size='md', color=CONTROL_COLOR,
                   className='choice-switch'),
        # Percentages only make sense for renewables on their own, so this appears when totals are hidden
        html.Div(dmc.Switch(id=PERCENT_SWITCH_ID, label='אנרגיה/אחוזים', checked=False, size='md', color=CONTROL_COLOR,
                            className='choice-switch'),
                 id=PERCENT_WRAPPER_ID, style={'display': 'none'}),
    ], gap='xl', align='center', wrap='wrap')

    return dmc.Stack([
        ui.page_header('ייצור חשמל בישראל', 'ייצור חודשי לפי שנה – מתחדשות מול סך הייצור.', 'sun'),
        dmc.Card(controls),
        ui.chart_card(dcc.Graph(id=MAIN_GRAPH_ID, config=ui.GRAPH_CONFIG),
                      title='ייצור חודשי'),
    ], gap='md')


def bar_chart(cost_data_all: Dict, max_year: int, years_range: List[int], yearly: bool = False,
              show_total: bool = True, percent: bool = False):
    traces = []
    start_year, end_year = years_range if years_range else [YEAR_FROM, max_year]

    # Optimization: Group data by year once (O(N)) instead of filtering in the loop (O(N^2))
    data_by_year = defaultdict(dict)
    for date_str, data in cost_data_all.items():
        # date_str is "dd-mm-yyyy"
        y = int(date_str.split('-')[2])
        data_by_year[y][date_str] = data

    # Yearly view: fewer bars leave more room, so the labels grow as the year range shrinks
    n_years = end_year - start_year + 1
    label_size = max(16, 30 - 2 * (n_years - 1))
    tick_size = max(12, 22 - 2 * (n_years - 1)) if yearly else None

    # Only iterate the years we actually need to display
    for yr in range(start_year, end_year + 1):
        year_data = data_by_year.get(yr, {})
        trace_ren, trace_conv, total, total_ren = per_year_stacked_bar(year_data, yr, yearly=yearly,
                                                                       label_size=label_size,
                                                                       show_total=show_total, percent=percent)
        
        if show_total:
            traces.append(trace_conv)
        traces.append(trace_ren)
        log_year(yr, total_ren, total)

    fig = go.Figure(data=traces,
                    layout=go.Layout(
                        height=640,
                        bargap=0.18,
                        bargroupgap=0.06,
                        xaxis=go.layout.XAxis(title="", fixedrange=True, showline=False, tickfont={"size": tick_size},
                                              type="category" if yearly else None),
                        yaxis=go.layout.YAxis(fixedrange=True,
                                              tickformat=",.0f", rangemode="tozero"),
                        # The legend is informational: hiding the totals is done with the switch above the chart
                        legend={"orientation": "h", "y": -0.12, "x": 0.5, "xanchor": "center",
                                "itemclick": False, "itemdoubleclick": False},
                        margin={"t": 40},
                        hovermode="closest",
                        hoverlabel={"align": "right"},
                        # Many narrow bars: keep the vertical % labels legible instead of shrinking them
                        uniformtext={"minsize": 10, "mode": "show"},
                        ))
    ui.axis_unit(fig, "%" if percent else "GWh")
    return fig

def per_year_stacked_bar(cost_data: Dict, group: int, yearly: bool = False, label_size: int = 18,
                         show_total: bool = True,
                         percent: bool = False):
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

    if yearly:
        x_vals = [str(group)]
        y_ren_vals = [total_renewable]
        y_conv_vals = [total - total_renewable]
        y_text_vals = ["{:.1%}".format(total_renewable / total) if total > 0 else ""]
        offset_grp = "yearly"
    else:
        x_vals = months_list
        y_ren_vals = y_renewable
        y_conv_vals = y_conventional
        y_text_vals = y_text
        offset_grp = group

    # Both segments of a bar share one tooltip: total and renewables for that month/year
    customdata = [(ren, ren + conv, pct) for ren, conv, pct in zip(y_ren_vals, y_conv_vals, y_text_vals)]
    hover_title = '<b>%{x}</b>' if yearly else f'<b>%{{x}} {group}</b>'
    hover = (hover_title
             + '<br><span style="color:black">' + rtl('סך הכל:', '%{customdata[1]:,.0f} GWh') + '</span>'
             + f'<br><span style="color:{bar_4[2]["ren"]}">' + rtl('מתחדשות:', '%{customdata[0]:,.0f} GWh / %{customdata[2]}')
             + '</span><extra></extra>')
    # The renewable share is labelled above the full stack (monthly) or inside the totals segment just above the
    # renewables (yearly); when totals are hidden it goes above the renewables bar
    label = dict(text=y_text_vals, textposition="outside", cliponaxis=False,
                 textangle=0 if yearly else -90,
                 textfont={"size": label_size if yearly else 11, "color": ui.TEXT_PRIMARY if yearly else ui.TEXT_SECONDARY})
    total_label = (dict(label, textposition="inside", insidetextanchor="start") if yearly else label)

    # Percent view: renewables as a share of each month's/year's total (only shown without the totals)
    y_ren_plot = ([ren / (ren + conv) * 100 if ren + conv else 0 for ren, conv in zip(y_ren_vals, y_conv_vals)]
                  if percent and not show_total else y_ren_vals)

    trace_ren = go.Bar(x=x_vals, y=y_ren_plot,
                       offsetgroup=offset_grp,
                       name=legend(group, total / 1e3, total_renewable / 1e3),
                       marker_color=bar_4[group % 4]["ren"],
                       legendgroup="ren",
                       legendgrouptitle={"text": "מתחדשות", "font": {"size": 13}},
                       customdata=customdata,
                       hovertemplate=hover,
                       **({} if show_total else label))
    trace_conv = go.Bar(x=x_vals, y=y_conv_vals,
                        offsetgroup=offset_grp, base=y_ren_vals,
                        name=legend(group, total / 1e3), marker_color=bar_4[group % 4]["conv"],
                        legendgroup="conv",
                        legendgrouptitle={"text": "סך הכל", "font": {"size": 13}},
                        customdata=customdata,
                        hovertemplate=hover,
                        **total_label)
    return trace_ren, trace_conv, total, total_renewable


def register_callbacks(app):
    @app.callback(
        Output(MAIN_GRAPH_ID, 'figure'),
        [Input(YEAR_RANGE_SLIDER, 'value'),
         Input(YEARLY_SWITCH_ID, 'checked'),
         Input(TOTAL_SWITCH_ID, 'checked'),
         Input(PERCENT_SWITCH_ID, 'checked')],
    )
    def update_output(range_from_slider, yearly, show_total, percent):
        response, max_year = retrieve_data()
        # The slider holds negated years (see bar_chart_layout)
        years = sorted(-v for v in range_from_slider) if range_from_slider else None
        return bar_chart(response, max_year, years, yearly=bool(yearly), show_total=bool(show_total),
                         percent=bool(percent) and not show_total)

    @app.callback(
        Output(PERCENT_WRAPPER_ID, 'style'),
        Input(TOTAL_SWITCH_ID, 'checked'),
    )
    def toggle_percent_switch(show_total):
        return {'display': 'none' if show_total else 'block'}
