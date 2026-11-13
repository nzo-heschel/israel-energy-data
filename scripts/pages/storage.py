from dash import dcc, html, Input, Output, clientside_callback, callback_context
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging
import math
import numpy as np
from . import heatmap, ui

STORAGE_ID = "storage-graph"
STORAGE_STORE_ID = "storage-graph-store"
CUMULATIVE_ID = "cumulative-graph"
DAILY_ID = "daily-graph"
DAILY_ENERGY_ID = "daily-energy-graph"
STORAGE_SOURCE_ID = "storage-source-radio"
DATE_RANGE_ID = "storage-date-range"
STORAGE_INFO_ID = "storage-info"
GRAPH_TYPE_ID = "graph-type-switch"
STORAGE_TITLE_ID = "storage-title"
BTN_WEEK_ID = "btn-last-week"
BTN_MONTH_ID = "btn-last-month"
BTN_YEAR_ID = "btn-last-year"

# Constants for XY graph time range
XY_START_TIME = datetime(1900, 1, 1, 0, 0)
XY_END_TIME = datetime(1900, 1, 2, 0, 0)

VALUE_BATTERIES = 'BatteriesNet'
VALUE_PSP = 'PspNet'

SOURCE_TITLES = {VALUE_BATTERIES: 'אגירה בסוללות', VALUE_PSP: 'אגירה שאובה'}
SOURCE_ICONS = {VALUE_BATTERIES: '🔋', VALUE_PSP: '💧'}

COLOR_DISCHARGE = ui.COLOR_DISCHARGE
COLOR_CHARGE = ui.COLOR_CHARGE

# Global variables to store state
last_start_date = None
last_end_date = None
last_source = VALUE_BATTERIES

def get_date_range_bounds():
    # Helper to get min/max allowed dates based on data
    if not heatmap.dfs:
        heatmap.retrieve_data()
        
    all_dates = []
    if heatmap.dfs:
        for source_df in heatmap.dfs.values():
            all_dates.extend(source_df.columns)
    
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    if all_dates:
        date_objs = [d.date() if isinstance(d, datetime) else d for d in all_dates]
        min_date = min(date_objs)
        max_data_date = max(date_objs)
        max_date = min(max_data_date, yesterday)
    else:
        min_date = today - timedelta(days=30)
        max_date = yesterday
        
    return min_date, max_date

def storage_layout():
    global last_start_date, last_end_date, last_source
    
    min_date, max_date = get_date_range_bounds()
    
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    # Use stored state if available, otherwise default
    if last_start_date is None:
        start_date = today - timedelta(days=7)
    else:
        start_date = datetime.fromisoformat(last_start_date).date() if isinstance(last_start_date, str) else last_start_date
        
    if last_end_date is None:
        end_date = yesterday
    else:
        end_date = datetime.fromisoformat(last_end_date).date() if isinstance(last_end_date, str) else last_end_date
        
    # Ensure start/end dates are within bounds
    if start_date < min_date:
        start_date = min_date
    if end_date > max_date:
        end_date = max_date
    if start_date > end_date:
        start_date = end_date
    
    controls = dmc.Card(dmc.Stack([
        dmc.Box([
            ui.control_label('סוג אגירה'),
            dmc.SegmentedControl(
                id=STORAGE_SOURCE_ID,
                data=[{'label': html.Span([html.Span(SOURCE_ICONS[value], className='chip-emoji'), title],
                                          className='chip-label'),
                       'value': value} for value, title in SOURCE_TITLES.items()],
                value=last_source,
                fullWidth=True,
            ),
        ]),
        dmc.Box([
            ui.control_label('טווח תאריכים'),
            dmc.DatePickerInput(
                id=DATE_RANGE_ID,
                type='range',
                value=[start_date.isoformat(), end_date.isoformat()],
                minDate=min_date.isoformat(),
                maxDate=max_date.isoformat(),
                valueFormat='DD/MM/YYYY',
                # Israeli week: Sunday to Saturday, with only Saturday marked as the weekend
                firstDayOfWeek=0,
                weekendDays=[6],
                allowSingleDateInRange=True,
                dropdownType='modal',
                # Keep "start – end" in reading order inside the RTL page
                styles={'input': {'direction': 'ltr', 'textAlign': 'right'}},
            ),
            dmc.Group([
                dmc.Button('שבוע אחרון', id=BTN_WEEK_ID, n_clicks=0, variant='light', size='compact-sm'),
                dmc.Button('חודש אחרון', id=BTN_MONTH_ID, n_clicks=0, variant='light', size='compact-sm'),
                dmc.Button('שנה אחרונה', id=BTN_YEAR_ID, n_clicks=0, variant='light', size='compact-sm'),
            ], gap=6, mt='xs'),
        ]),
        dmc.Switch(id=GRAPH_TYPE_ID, label='גרף מלבני', checked=False),
    ], gap='lg'))

    def small_chart(graph_id, title, subtitle):
        return ui.chart_card(dcc.Graph(id=graph_id, style={'height': '340px'}, config=ui.GRAPH_CONFIG),
                             title=title, subtitle=subtitle)

    return dmc.Stack([
        ui.page_header('אגירת אנרגיה', 'פרופיל יומי של טעינה (שלילי) ופריקה (חיובי). ריחוף מעל יום מדגיש אותו.', 'battery'),
        dcc.Store(id=STORAGE_STORE_ID),
        dmc.Grid([
            dmc.GridCol(dmc.Stack([
                controls,
                dmc.Stack(id=STORAGE_INFO_ID, gap='sm'),
            ], gap='md'), span={'base': 12, 'md': 4, 'lg': 3}),
            dmc.GridCol(ui.chart_card(
                dcc.Graph(
                    id=STORAGE_ID,
                    style={'width': '100%', 'height': 'max(520px, 72vh)'},
                    config={**ui.GRAPH_CONFIG, 'scrollZoom': False},
                    clear_on_unhover=True
                ),
                title=dmc.Text(id=STORAGE_TITLE_ID, fw=700, size='lg', span=True),
                subtitle='הספק (MW) לפי שעה ביום – כל קו/נקודה מייצגים יום אחד',
            ), span={'base': 12, 'md': 8, 'lg': 9}),
        ], gutter='md'),
        small_chart(CUMULATIVE_ID, 'אנרגיה מצטברת', 'MWh · סכום מצטבר של טעינה ופריקה לאורך הטווח'),
        dmc.SimpleGrid([
            small_chart(DAILY_ID, 'הספק מקסימלי יומי', 'MW'),
            small_chart(DAILY_ENERGY_ID, 'אנרגיה יומית', 'MWh'),
        ], cols={'base': 1, 'lg': 2}, spacing='md'),
    ], gap='md')


def register_callbacks(app):
    # Client-side callback for highlighting
    clientside_callback(
        """
        function(hoverData, storedFig) {
            if (!storedFig) {
                return window.dash_clientside.no_update;
            }
            
            // If no hover data, return the original figure (reset)
            if (!hoverData || !hoverData.points || hoverData.points.length === 0) {
                return storedFig;
            }
            
            const hoveredCurveIndex = hoverData.points[0].curveNumber;
            
            // Create a shallow copy of the figure structure
            // We avoid deep cloning the large data arrays (x, y, r, theta)
            const newFig = { ...storedFig };
            
            newFig.data = storedFig.data.map((trace, i) => {
                // Shallow copy the trace object
                const newTrace = { ...trace };
                
                // Skip structural traces (like the zero line in polar plot)
                if (newTrace.hoverinfo === 'skip') {
                    return newTrace;
                }

                const isHovered = (i === hoveredCurveIndex);
                
                if (isHovered) {
                    newTrace.opacity = 1.0;
                    // Highlight with increased size/width, keeping original color
                    if (newTrace.type === 'scatter' || newTrace.type === 'scattergl') {
                        newTrace.line = { ...newTrace.line, width: 4 };
                    } else if (newTrace.type === 'scatterpolargl' || newTrace.type === 'scatterpolar') {
                        newTrace.marker = { ...newTrace.marker, size: 8 };
                    }
                } else {
                    // Dim others significantly and make them grey
                    newTrace.opacity = 0.1;
                    if (newTrace.type === 'scatter' || newTrace.type === 'scattergl') {
                        newTrace.line = { ...newTrace.line, width: 1, color: '#808080' };
                    } else if (newTrace.type === 'scatterpolargl' || newTrace.type === 'scatterpolar') {
                        newTrace.marker = { ...newTrace.marker, size: 3, color: '#808080' };
                    }
                }
                return newTrace;
            });
            
            return newFig;
        }
        """,
        Output(STORAGE_ID, 'figure'),
        Input(STORAGE_ID, 'hoverData'),
        Input(STORAGE_STORE_ID, 'data')
    )

    @app.callback(
        [Output(STORAGE_STORE_ID, 'data'),
         Output(CUMULATIVE_ID, 'figure'),
         Output(DAILY_ID, 'figure'),
         Output(DAILY_ENERGY_ID, 'figure'),
         Output(STORAGE_INFO_ID, 'children'),
         Output(STORAGE_TITLE_ID, 'children'),
         Output(DATE_RANGE_ID, 'value'),
         Output(DATE_RANGE_ID, 'minDate'),
         Output(DATE_RANGE_ID, 'maxDate')],
        [Input(DATE_RANGE_ID, 'value'),
         Input(STORAGE_SOURCE_ID, 'value'),
         Input(GRAPH_TYPE_ID, 'checked'),
         Input(BTN_WEEK_ID, 'n_clicks'),
         Input(BTN_MONTH_ID, 'n_clicks'),
         Input(BTN_YEAR_ID, 'n_clicks')]
    )
    def update_storage_graph(date_range, source, is_xy, _btn_week, _btn_month, _btn_year):
        global last_start_date, last_end_date, last_source
        
        ctx = callback_context
        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
        start_date, end_date = (list(date_range or []) + [None, None])[:2]
        # The range picker reports a half-picked range while the user is still choosing the end date
        if triggered_id == DATE_RANGE_ID and not (start_date and end_date):
            raise PreventUpdate
        
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        # Recalculate bounds on every callback to ensure they are up to date
        min_date_allowed, max_date_allowed = (d.isoformat() for d in get_date_range_bounds())

        if triggered_id == BTN_WEEK_ID:
            end_date = yesterday.strftime('%Y-%m-%d')
            start_date = (yesterday - timedelta(days=6)).strftime('%Y-%m-%d')
        elif triggered_id == BTN_MONTH_ID:
            end_date = yesterday.strftime('%Y-%m-%d')
            start_date = (yesterday - timedelta(days=30)).strftime('%Y-%m-%d')
        elif triggered_id == BTN_YEAR_ID:
            end_date = yesterday.strftime('%Y-%m-%d')
            start_date = (yesterday - timedelta(days=365)).strftime('%Y-%m-%d')
            
        # Update global state
        last_start_date = start_date
        last_end_date = end_date
        last_source = source
        
        is_xy = bool(is_xy)
        title_text = SOURCE_TITLES.get(source, source)
        date_value = [start_date, end_date]
        
        # Ensure data is available (refresh if needed, handled by retrieve_data logic)
        heatmap.retrieve_data()
        
        if source not in heatmap.dfs:
            logging.warning(f"Source {source} not found in heatmap.dfs")
            return go.Figure(), go.Figure(), go.Figure(), go.Figure(), [], title_text, date_value, min_date_allowed, max_date_allowed
            
        df = heatmap.dfs[source]
        
        if start_date:
            dt_start = datetime.fromisoformat(start_date).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            dt_start = datetime.min
            
        if end_date:
            dt_end = datetime.fromisoformat(end_date).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            dt_end = datetime.max
            
        # Filter columns by date
        cols = [c for c in df.columns if dt_start <= c <= dt_end]
        df_filtered = df[cols]
        
        if df_filtered.empty:
            return go.Figure(), go.Figure(), go.Figure(), go.Figure(), [], title_text, date_value, min_date_allowed, max_date_allowed

        fig_main = go.Figure()
        fig_cum = go.Figure()
        fig_daily = go.Figure()
        fig_daily_energy = go.Figure()
        
        times = df_filtered.index.tolist()
        dt_times = [datetime.strptime(t, "%H:%M") for t in times]
        theta = [(dt.hour + dt.minute / 60.0) * 360 / 24 for dt in dt_times]
        
        # Vectorized calculations
        # Calculate time difference in hours for each time step
        # Assuming times are sorted and consistent
        time_objs = [datetime.strptime(t, "%H:%M") for t in times]
        diff_seconds = [(time_objs[i+1] - time_objs[i]).total_seconds() for i in range(len(time_objs)-1)]
        diff_seconds.append(300.0) # Assume 5 minutes for the last interval
        diff_hours = np.array(diff_seconds) / 3600.0
        
        # Calculate energy for all points (Power * Time)
        # df_filtered is (Time x Date), diff_hours is (Time,)
        # We multiply each column by diff_hours
        energy_df = df_filtered.mul(diff_hours, axis=0)
        
        # Global Stats
        total_positive_energy = energy_df[energy_df > 0].sum().sum()
        total_negative_energy = energy_df[energy_df < 0].sum().sum()
        max_power_discharging_total = df_filtered.max().max()
        max_power_charging_total = df_filtered.min().min()
        
        # Ensure max stats are bounded by 0 as per original logic (only if they cross 0)
        if max_power_discharging_total < 0: max_power_discharging_total = 0
        if max_power_charging_total > 0: max_power_charging_total = 0

        # Daily Stats
        daily_max_discharge = df_filtered.max().clip(lower=0)
        daily_max_charge = df_filtered.min().clip(upper=0)
        
        daily_energy_discharge = energy_df[energy_df > 0].sum()
        daily_energy_charge = energy_df[energy_df < 0].sum()
        
        # Cumulative Energy
        # Flatten energy values column by column (chronological)
        sorted_cols = sorted(df_filtered.columns)
        df_sorted = df_filtered[sorted_cols]
        energy_sorted = energy_df[sorted_cols]
        
        flat_energy = energy_sorted.values.flatten(order='F')
        cumulative_y = np.cumsum(flat_energy)
        
        # Construct cumulative x-axis
        # This creates a full datetime for every point
        time_deltas = [timedelta(hours=t.hour, minutes=t.minute) for t in time_objs]
        cumulative_x = []
        for d in sorted_cols:
            cumulative_x.extend([d + t for t in time_deltas])

        # Main Graph Traces
        # We still iterate to add traces per day to allow for individual hover info and potential future interactivity
        for i, date_col in enumerate(sorted_cols):
            series = df_sorted[date_col]
            power_values = series.values
            date_str = date_col.strftime('%d-%m-%Y')
            
            # Create customdata for hover (Power, Time, Date)
            # We can construct this efficiently
            # But zip is fast enough for per-day slices
            custom_data_for_hover = list(zip(power_values, times, [date_str]*len(times)))
            
            if is_xy:
                fig_main.add_trace(go.Scattergl(
                    x=dt_times,
                    y=power_values,
                    customdata=custom_data_for_hover,
                    mode='lines',
                    name=date_str,
                    hovertemplate='Date: %{customdata[2]}<br>Time: %{customdata[1]}<br>Power: %{y:.2f} MW<extra></extra>',
                    showlegend=False,
                    line=dict(width=1.5)
                ))
            else:
                fig_main.add_trace(go.Scatterpolargl(
                    r=power_values,
                    theta=theta,
                    customdata=custom_data_for_hover,
                    mode='markers',
                    marker=dict(
                        size=6
                    ),
                    name=date_str,
                    hovertemplate='Date: %{customdata[2]}<br>Time: %{customdata[1]}<br>Power: %{customdata[0]:.2f} MW<extra></extra>',
                    showlegend=False
                ))

        # Add cumulative energy trace
        fig_cum.add_trace(go.Scatter(
            x=cumulative_x,
            y=cumulative_y,
            mode='lines',
            name='Cumulative Energy',
            line=dict(color=ui.COLOR_LINE),
            fill='tozeroy',
            fillcolor='rgba(42, 120, 214, 0.08)',
            hovertemplate='%{x}<br>Energy: %{y:,.2f} MWh<extra></extra>'
        ))
        
        # Add daily max charge/discharge traces
        fig_daily.add_trace(go.Scatter(
            x=daily_max_discharge.index,
            y=daily_max_discharge.values,
            mode='lines+markers',
            name='Max Discharge',
            line=dict(color=COLOR_DISCHARGE),
            hovertemplate='Date: %{x}<br>Max Discharge: %{y:,.2f} MW<extra></extra>'
        ))
        
        fig_daily.add_trace(go.Scatter(
            x=daily_max_charge.index,
            y=-daily_max_charge.values, # Negate to show as positive
            mode='lines+markers',
            name='Max Charge',
            line=dict(color=COLOR_CHARGE),
            hovertemplate='Date: %{x}<br>Max Charge: %{y:,.2f} MW<extra></extra>'
        ))
        
        # Add daily energy charge/discharge traces
        fig_daily_energy.add_trace(go.Scatter(
            x=daily_energy_discharge.index,
            y=daily_energy_discharge.values,
            mode='lines+markers',
            name='Energy Discharge',
            line=dict(color=COLOR_DISCHARGE),
            hovertemplate='Date: %{x}<br>Energy Discharge: %{y:,.2f} MWh<extra></extra>'
        ))
        
        fig_daily_energy.add_trace(go.Scatter(
            x=daily_energy_charge.index,
            y=-daily_energy_charge.values, # Negate to show as positive
            mode='lines+markers',
            name='Energy Charge',
            line=dict(color=COLOR_CHARGE),
            hovertemplate='Date: %{x}<br>Energy Charge: %{y:,.2f} MWh<extra></extra>'
        ))

        efficiency = total_positive_energy / -total_negative_energy if total_negative_energy != 0 else 0

        info_children = [
            ui.stat_card('פריקה מקסימלית', f'{max_power_discharging_total:,.2f} MW', 'arrow-up', color='teal',
                         center_value=True),
            ui.stat_card('טעינה מקסימלית', f'{-max_power_charging_total:,.2f} MW', 'arrow-down', color='orange',
                         center_value=True),
            ui.stat_card('נצילות', f'{efficiency:.1%}', 'gauge', color='blue', hint='אנרגיה שנפרקה / אנרגיה שנטענה',
                         center_value=True),
        ]

        # Main Figure Layout
        if is_xy:
            tickvals = [datetime(1900, 1, 1, h, 0) for h in range(0, 24, 3)]
            tickvals.append(XY_END_TIME)
            ticktext = [f"{h:02d}:00" for h in range(0, 24, 3)] + ["24:00"]
            
            # Ensure the range covers 24:00 with a small padding
            range_x = [XY_START_TIME - timedelta(minutes=10), XY_END_TIME + timedelta(minutes=10)]
            
            ui.axis_unit(fig_main, "MW")
            fig_main.update_layout(
                dragmode=False,
                xaxis=dict(
                    tickformat="%H:%M", 
                    fixedrange=True,
                    tickvals=tickvals,
                    ticktext=ticktext,
                    range=range_x # Explicitly set range to include 24:00 with padding
                ),
                yaxis=dict(fixedrange=True, zeroline=True, zerolinecolor=ui.TEXT_MUTED, zerolinewidth=1),
                margin=dict(l=56, r=24, t=36, b=48),
                showlegend=False
            )
            
        else:
            # Polar Layout
            all_power_values_flat = df_sorted.values.flatten()
            if len(all_power_values_flat) > 0:
                min_p, max_p = min(all_power_values_flat), max(all_power_values_flat)
                span = max_p - min_p if max_p != min_p else 1.0
                
                target_step = span / 6
                magnitude = 10 ** math.floor(math.log10(target_step)) if target_step > 0 else 1
                rescaled_step = target_step / magnitude
                
                nice_options = [1, 2, 2.5, 5, 10]
                closest_nice_step = min(nice_options, key=lambda x: abs(x - rescaled_step))
                nice_step = closest_nice_step * magnitude
                
                r_min = math.floor(min_p / nice_step) * nice_step
                r_max = math.ceil(max_p / nice_step) * nice_step
                
                # Extend r_min by one step
                r_min -= nice_step
                
                tickvals = []
                curr = r_min
                while curr <= r_max + (nice_step / 1000):
                    tickvals.append(curr)
                    curr += nice_step
            else:
                r_min, r_max = -1, 1
                tickvals = [-1, 0, 1]
                nice_step = 1
            
            range_vals = [r_min, r_max + (nice_step / 10) if len(all_power_values_flat) > 0 else 1]

            fig_main.update_layout(
                dragmode=False,
                margin=dict(l=40, r=40, t=32, b=32),
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=range_vals,
                        tickvals=tickvals,
                        tickfont=dict(size=11, color=ui.TEXT_MUTED),
                    ),
                    angularaxis=dict(
                        direction="clockwise", rotation=90, tickmode='array',
                        tickvals=[0, 45, 90, 135, 180, 225, 270, 315],
                        ticktext=['00:00', '03:00', '06:00', '09:00', '12:00', '15:00', '18:00', '21:00'],
                    )
                ),
                showlegend=False
            )
            
            # Add a thicker zero line for polar plot
            zero_line_theta = [i for i in range(0, 361)]
            zero_line_r = [0] * len(zero_line_theta)
            
            fig_main.add_trace(go.Scatterpolar(
                r=zero_line_r,
                theta=zero_line_theta,
                mode='lines',
                line=dict(color=ui.TEXT_SECONDARY, width=1.5),
                hoverinfo='skip',
                showlegend=False
            ))

        # Secondary figures share one layout: titles live in the surrounding cards
        for fig, unit in [(fig_cum, "MWh"), (fig_daily, "MW"), (fig_daily_energy, "MWh")]:
            ui.axis_unit(fig, unit)
            fig.update_layout(
                dragmode=False,
                xaxis=dict(fixedrange=True),
                yaxis=dict(fixedrange=True, zeroline=True, zerolinecolor=ui.AXIS_LINE, zerolinewidth=1,
                           rangemode='normal' if fig is fig_cum else 'tozero'),
                margin=dict(l=64, r=16, t=36, b=48),
                hovermode='x unified',
                showlegend=fig is not fig_cum,
                legend=dict(orientation='h', x=1, xanchor='right', y=1.12),
            )

        return fig_main, fig_cum, fig_daily, fig_daily_energy, info_children, title_text, date_value, min_date_allowed, max_date_allowed
