from dash import dcc, html, Input, Output, callback_context
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging
import math
import numpy as np
from . import heatmap

STORAGE_ID = "storage-graph"
CUMULATIVE_ID = "cumulative-graph"
DAILY_ID = "daily-graph"
DAILY_ENERGY_ID = "daily-energy-graph"
STORAGE_SOURCE_ID = "storage-source-radio"
DATE_RANGE_ID = "storage-date-range"
STORAGE_INFO_ID = "storage-info"
GRAPH_TYPE_ID = "graph-type-checklist"
BTN_WEEK_ID = "btn-last-week"
BTN_MONTH_ID = "btn-last-month"
BTN_YEAR_ID = "btn-last-year"

# Constants for XY graph time range
XY_START_TIME = datetime(1900, 1, 1, 0, 0)
XY_END_TIME = datetime(1900, 1, 2, 0, 0)

# Global variables to store state
last_start_date = None
last_end_date = None
last_source = 'BatteriesNet'

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

def storage_layout(nav_links):
    global last_start_date, last_end_date, last_source
    
    min_date, max_date = get_date_range_bounds()
    
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    # Use stored state if available, otherwise default
    if last_start_date is None:
        start_date = today - timedelta(days=7)
    else:
        start_date = datetime.strptime(last_start_date, '%Y-%m-%d').date() if isinstance(last_start_date, str) else last_start_date
        
    if last_end_date is None:
        end_date = yesterday
    else:
        end_date = datetime.strptime(last_end_date, '%Y-%m-%d').date() if isinstance(last_end_date, str) else last_end_date
        
    # Ensure start/end dates are within bounds
    if start_date < min_date:
        start_date = min_date
    if end_date > max_date:
        end_date = max_date
    if start_date > end_date:
        start_date = end_date
    
    button_style = {
        'marginRight': '5px', 
        'marginTop': '10px', 
        'padding': '5px 10px', 
        'fontSize': '14px',
        'cursor': 'pointer'
    }

    return html.Div([
        nav_links,
        html.Div([
            html.Div([
                dcc.DatePickerRange(
                    id=DATE_RANGE_ID,
                    min_date_allowed=min_date,
                    max_date_allowed=max_date,
                    initial_visible_month=end_date,
                    start_date=start_date,
                    end_date=end_date,
                    display_format='DD/MM/YYYY',
                    with_portal=True,
                    style={'fontSize': '10px', 'transform': 'scale(0.8)', 'transformOrigin': 'top left'}
                ),
                html.Div([
                    html.Button('שבוע אחרון', id=BTN_WEEK_ID, n_clicks=0, style=button_style),
                    html.Button('חודש אחרון', id=BTN_MONTH_ID, n_clicks=0, style=button_style),
                    html.Button('שנה אחרונה', id=BTN_YEAR_ID, n_clicks=0, style=button_style),
                ], style={'display': 'flex', 'flexWrap': 'wrap'}),
                dcc.RadioItems(
                    id=STORAGE_SOURCE_ID,
                    options=[
                        {'label': 'אגירה בסוללות', 'value': 'BatteriesNet'},
                        {'label': 'אגירה שאובה', 'value': 'PspNet'}
                    ],
                    value=last_source,
                    style={'marginTop': '20px', 'fontSize': 20}
                ),
                dcc.Checklist(
                    id=GRAPH_TYPE_ID,
                    options=[{'label': 'גרף מלבני', 'value': 'xy'}],
                    value=[],
                    style={'marginTop': '20px', 'fontSize': 18}
                )
            ], style={'flex': '1', 'padding': '20px', 'boxSizing': 'border-box'}),
            
            html.Div([
                dcc.Graph(
                    id=STORAGE_ID, 
                    style={'width': '100%', 'height': '80vh'},
                    config={'displayModeBar': False, 'scrollZoom': False, 'responsive': True}
                )
            ], style={'flex': '6', 'overflow': 'hidden'}),
            
            html.Div(id=STORAGE_INFO_ID, style={'flex': '1', 'padding': '20px', 'textAlign': 'right', 'direction': 'rtl', 'boxSizing': 'border-box'})
            
        ], style={'display': 'flex', 'flexDirection': 'row', 'width': '100%', 'alignItems': 'flex-start'}),
        
        dcc.Graph(
            id=CUMULATIVE_ID, 
            style={'width': '100%', 'height': '40vh'},
            config={'displayModeBar': False, 'scrollZoom': False, 'responsive': True}
        ),
        dcc.Graph(
            id=DAILY_ID, 
            style={'width': '100%', 'height': '40vh'},
            config={'displayModeBar': False, 'scrollZoom': False, 'responsive': True}
        ),
        dcc.Graph(
            id=DAILY_ENERGY_ID, 
            style={'width': '100%', 'height': '40vh'},
            config={'displayModeBar': False, 'scrollZoom': False, 'responsive': True}
        )
    ])

def register_callbacks(app):
    @app.callback(
        [Output(STORAGE_ID, 'figure'),
         Output(CUMULATIVE_ID, 'figure'),
         Output(DAILY_ID, 'figure'),
         Output(DAILY_ENERGY_ID, 'figure'),
         Output(STORAGE_INFO_ID, 'children'),
         Output(DATE_RANGE_ID, 'start_date'),
         Output(DATE_RANGE_ID, 'end_date'),
         Output(DATE_RANGE_ID, 'min_date_allowed'),
         Output(DATE_RANGE_ID, 'max_date_allowed')],
        [Input(DATE_RANGE_ID, 'start_date'),
         Input(DATE_RANGE_ID, 'end_date'),
         Input(STORAGE_SOURCE_ID, 'value'),
         Input(GRAPH_TYPE_ID, 'value'),
         Input(BTN_WEEK_ID, 'n_clicks'),
         Input(BTN_MONTH_ID, 'n_clicks'),
         Input(BTN_YEAR_ID, 'n_clicks')]
    )
    def update_storage_graph(start_date, end_date, source, graph_type, _btn_week, _btn_month, _btn_year):
        global last_start_date, last_end_date, last_source
        
        ctx = callback_context
        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
        
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        # Recalculate bounds on every callback to ensure they are up to date
        min_date_allowed, max_date_allowed = get_date_range_bounds()

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
        
        is_xy = 'xy' in (graph_type or [])
        
        # Ensure data is available (refresh if needed, handled by retrieve_data logic)
        heatmap.retrieve_data()
        
        if source not in heatmap.dfs:
            logging.warning(f"Source {source} not found in heatmap.dfs")
            return go.Figure(), go.Figure(), go.Figure(), go.Figure(), [], start_date, end_date, min_date_allowed, max_date_allowed
            
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
            return go.Figure(), go.Figure(), go.Figure(), go.Figure(), [], start_date, end_date, min_date_allowed, max_date_allowed

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
        for date_col in sorted_cols:
            series = df_sorted[date_col]
            power_values = series.values
            date_str = date_col.strftime('%d-%m-%Y')
            
            # Create customdata for hover (Power, Time, Date)
            # We can construct this efficiently
            # But zip is fast enough for per-day slices
            custom_data_for_hover = list(zip(power_values, times, [date_str]*len(times)))
            
            if is_xy:
                fig_main.add_trace(go.Scatter(
                    x=dt_times,
                    y=power_values,
                    customdata=custom_data_for_hover,
                    mode='lines',
                    name=date_str,
                    hovertemplate='Date: %{customdata[2]}<br>Time: %{customdata[1]}<br>Power: %{y:.2f} MW<extra></extra>',
                    showlegend=False
                ))
            else:
                fig_main.add_trace(go.Scatterpolar(
                    r=power_values,
                    theta=theta,
                    customdata=custom_data_for_hover,
                    mode='markers',
                    marker=dict(size=6),
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
            line=dict(color='blue'),
            hovertemplate='%{x}<br>Energy: %{y:,.2f} MWh<extra></extra>'
        ))
        
        # Add daily max charge/discharge traces
        fig_daily.add_trace(go.Scatter(
            x=daily_max_discharge.index,
            y=daily_max_discharge.values,
            mode='lines+markers',
            name='Max Discharge',
            line=dict(color='green'),
            hovertemplate='Date: %{x}<br>Max Discharge: %{y:,.2f} MW<extra></extra>'
        ))
        
        fig_daily.add_trace(go.Scatter(
            x=daily_max_charge.index,
            y=-daily_max_charge.values, # Negate to show as positive
            mode='lines+markers',
            name='Max Charge',
            line=dict(color='red'),
            hovertemplate='Date: %{x}<br>Max Charge: %{y:,.2f} MW<extra></extra>'
        ))
        
        # Add daily energy charge/discharge traces
        fig_daily_energy.add_trace(go.Scatter(
            x=daily_energy_discharge.index,
            y=daily_energy_discharge.values,
            mode='lines+markers',
            name='Energy Discharge',
            line=dict(color='green'),
            hovertemplate='Date: %{x}<br>Energy Discharge: %{y:,.2f} MWh<extra></extra>'
        ))
        
        fig_daily_energy.add_trace(go.Scatter(
            x=daily_energy_charge.index,
            y=-daily_energy_charge.values, # Negate to show as positive
            mode='lines+markers',
            name='Energy Charge',
            line=dict(color='red'),
            hovertemplate='Date: %{x}<br>Energy Charge: %{y:,.2f} MWh<extra></extra>'
        ))

        efficiency = total_positive_energy / -total_negative_energy if total_negative_energy != 0 else 0

        info_children = html.Div([
            html.P(f'פריקה מקסימלית: {max_power_discharging_total:,.2f} MW', style={'fontSize': '20px'}),
            html.P(f'טעינה מקסימלית: {-max_power_charging_total:,.2f} MW', style={'fontSize': '20px'}),
            html.P(f'נצילות: {efficiency:.2%}', style={'fontSize': '20px'})
        ])

        title_text = 'אגירה בסוללות' if source == 'BatteriesNet' else 'אגירה שאובה'

        # Main Figure Layout
        if is_xy:
            tickvals = [datetime(1900, 1, 1, h, 0) for h in range(0, 24, 3)]
            tickvals.append(XY_END_TIME)
            ticktext = [f"{h:02d}:00" for h in range(0, 24, 3)] + ["24:00"]
            
            # Ensure the range covers 24:00 with a small padding
            range_x = [XY_START_TIME - timedelta(minutes=10), XY_END_TIME + timedelta(minutes=10)]
            
            fig_main.update_layout(
                title=go.layout.Title(
                    x=0.5, xanchor='center', font={"family": "Hebrew", "size": 36}, text=title_text
                ),
                paper_bgcolor='white',
                plot_bgcolor='white',
                dragmode=False,
                xaxis=dict(
                    title="זמן", 
                    gridcolor='lightgrey', 
                    tickformat="%H:%M", 
                    fixedrange=True,
                    tickvals=tickvals,
                    ticktext=ticktext,
                    range=range_x # Explicitly set range to include 24:00 with padding
                ),
                yaxis=dict(title="הספק (MW)", gridcolor='lightgrey', fixedrange=True, zeroline=True, zerolinecolor='lightgrey', zerolinewidth=1),
                margin=dict(l=40, r=40, t=60, b=40),
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
                title=go.layout.Title(
                    x=0.5, xanchor='center', font={"family": "Hebrew", "size": 36}, text=title_text
                ),
                paper_bgcolor='white',
                dragmode=False,
                margin=dict(l=40, r=40, t=60, b=40),
                polar=dict(
                    bgcolor="white",
                    radialaxis=dict(
                        visible=True,
                        range=range_vals,
                        tickvals=tickvals,
                        gridcolor='darkgrey'
                    ),
                    angularaxis=dict(
                        direction="clockwise", rotation=90, tickmode='array',
                        tickvals=[0, 45, 90, 135, 180, 225, 270, 315],
                        ticktext=['00:00', '03:00', '06:00', '09:00', '12:00', '15:00', '18:00', '21:00'],
                        gridcolor='darkgrey'
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
                line=dict(color='black', width=2),
                hoverinfo='skip',
                showlegend=False
            ))

        # Cumulative Figure Layout
        fig_cum.update_layout(
            title=go.layout.Title(text="אנרגיה מצטברת (MWh)", x=0.5, xanchor='center', font={"family": "Hebrew", "size": 24}),
            paper_bgcolor='white',
            plot_bgcolor='white',
            dragmode=False,
            xaxis=dict(title="זמן", gridcolor='lightgrey', fixedrange=True),
            yaxis=dict(title="אנרגיה (MWh)", gridcolor='lightgrey', fixedrange=True, zeroline=True, zerolinecolor='lightgrey', zerolinewidth=1),
            margin=dict(l=40, r=40, t=40, b=40),
            showlegend=False
        )

        # Daily Figure Layout
        fig_daily.update_layout(
            title=go.layout.Title(text="הספק מקסימלי יומי (MW)", x=0.5, xanchor='center', font={"family": "Hebrew", "size": 24}),
            paper_bgcolor='white',
            plot_bgcolor='white',
            dragmode=False,
            xaxis=dict(title="תאריך", gridcolor='lightgrey', fixedrange=True),
            yaxis=dict(title="הספק (MW)", gridcolor='lightgrey', fixedrange=True, rangemode='tozero', zeroline=True, zerolinecolor='lightgrey', zerolinewidth=1),
            margin=dict(l=40, r=40, t=40, b=40),
            showlegend=False
        )
        
        # Daily Energy Figure Layout
        fig_daily_energy.update_layout(
            title=go.layout.Title(text="אנרגיה יומית (MWh)", x=0.5, xanchor='center', font={"family": "Hebrew", "size": 24}),
            paper_bgcolor='white',
            plot_bgcolor='white',
            dragmode=False,
            xaxis=dict(title="תאריך", gridcolor='lightgrey', fixedrange=True),
            yaxis=dict(title="אנרגיה (MWh)", gridcolor='lightgrey', fixedrange=True, rangemode='tozero', zeroline=True, zerolinecolor='lightgrey', zerolinewidth=1),
            margin=dict(l=40, r=40, t=40, b=40),
            showlegend=False
        )
        
        return fig_main, fig_cum, fig_daily, fig_daily_energy, info_children, start_date, end_date, min_date_allowed, max_date_allowed
