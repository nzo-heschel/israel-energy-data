from dash import dcc, html, Input, Output
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging
import math
from . import heatmap

STORAGE_ID = "storage-graph"
STORAGE_SOURCE_ID = "storage-source-radio"
DATE_RANGE_ID = "storage-date-range"
STORAGE_INFO_ID = "storage-info"

# Global variables to store state
last_start_date = None
last_end_date = None
last_source = 'BatteriesNet'

def storage_layout(nav_links):
    global last_start_date, last_end_date, last_source
    
    # Only retrieve data if it hasn't been retrieved yet
    if not heatmap.dfs:
        heatmap.retrieve_data()
        
    all_dates = []
    if heatmap.dfs:
        for source_df in heatmap.dfs.values():
            all_dates.extend(source_df.columns)
    
    if all_dates:
        min_date = min(all_dates)
        max_date = max(all_dates)
    else:
        min_date = datetime(2020, 1, 1)
        max_date = datetime.today()
    
    today = datetime.today()
    
    # Use stored state if available, otherwise default
    if last_start_date is None:
        start_date = today - timedelta(days=7)
    else:
        start_date = last_start_date
        
    if last_end_date is None:
        end_date = today
    else:
        end_date = last_end_date
    
    return html.Div([
        nav_links,
        html.Div([
            html.Div([
                dcc.DatePickerRange(
                    id=DATE_RANGE_ID,
                    min_date_allowed=min_date,
                    max_date_allowed=max_date,
                    start_date=start_date,
                    end_date=end_date,
                    display_format='DD/MM/YYYY'
                ),
                dcc.RadioItems(
                    id=STORAGE_SOURCE_ID,
                    options=[
                        {'label': 'סוללות', 'value': 'BatteriesNet'},
                        {'label': 'אגירה שאובה', 'value': 'PspNet'}
                    ],
                    value=last_source,
                    style={'marginTop': '20px', 'fontSize': 20}
                )
            ], style={'flex': '1', 'padding': '20px', 'boxSizing': 'border-box'}),
            
            html.Div([
                dcc.Graph(
                    id=STORAGE_ID, 
                    style={'width': '100%', 'height': '85vh'},
                    config={'displayModeBar': False, 'scrollZoom': False, 'responsive': True}
                )
            ], style={'flex': '5', 'overflow': 'hidden'}),
            
            html.Div(id=STORAGE_INFO_ID, style={'flex': '1', 'padding': '20px', 'textAlign': 'right', 'direction': 'rtl', 'boxSizing': 'border-box'})
            
        ], style={'display': 'flex', 'flexDirection': 'row', 'width': '100%', 'alignItems': 'flex-start'})
    ])

def register_callbacks(app):
    @app.callback(
        [Output(STORAGE_ID, 'figure'),
         Output(STORAGE_INFO_ID, 'children')],
        [Input(DATE_RANGE_ID, 'start_date'),
         Input(DATE_RANGE_ID, 'end_date'),
         Input(STORAGE_SOURCE_ID, 'value')]
    )
    def update_storage_graph(start_date, end_date, source):
        global last_start_date, last_end_date, last_source
        
        # Update global state
        last_start_date = start_date
        last_end_date = end_date
        last_source = source
        
        # Ensure data is available (refresh if needed, handled by retrieve_data logic)
        heatmap.retrieve_data()
        
        if source not in heatmap.dfs:
            logging.warning(f"Source {source} not found in heatmap.dfs")
            return go.Figure(), []
            
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
            return go.Figure(), []

        fig = go.Figure()
        
        times = df_filtered.index.tolist()
        dt_times = [datetime.strptime(t, "%H:%M") for t in times]
        theta = [(dt.hour + dt.minute / 60.0) * 360 / 24 for dt in dt_times]
        
        all_power_values = []
        total_positive_energy = 0
        total_negative_energy = 0
        max_power_charging = 0
        max_power_discharging = 0

        for date_col in df_filtered.columns:
            series = df_filtered[date_col]
            power_values = series.values
            
            for i in range(len(times)):
                val = power_values[i] # Power in MW
                
                if i < len(times) - 1:
                    diff_hours = (dt_times[i+1] - dt_times[i]).total_seconds() / 3600.0
                else:
                    diff_hours = 5.0 / 60.0
                
                energy = val * diff_hours # MWh
                
                if energy > 0:
                    total_positive_energy += energy
                elif energy < 0:
                    total_negative_energy += energy
                
                if val > max_power_discharging:
                    max_power_discharging = val
                if val < max_power_charging:
                    max_power_charging = val
            
            all_power_values.extend(power_values)
            
            date_str = date_col.strftime('%d-%m-%Y')
            custom_data_for_hover = list(zip(power_values, times, [date_str]*len(times)))
            fig.add_trace(go.Scatterpolar(
                r=power_values,
                theta=theta,
                customdata=custom_data_for_hover,
                mode='markers',
                marker=dict(size=6),
                name=date_str,
                hovertemplate='Date: %{customdata[2]}<br>Time: %{customdata[1]}<br>Power: %{customdata[0]:.2f} MW<extra></extra>',
                showlegend=False
            ))

        if all_power_values:
            min_p, max_p = min(all_power_values), max(all_power_values)
            
            # Calculate a nice step size
            span = max_p - min_p if max_p != min_p else 1.0
            
            # Aim for roughly 5-8 steps
            target_step = span / 6
            magnitude = 10 ** math.floor(math.log10(target_step)) if target_step > 0 else 1
            rescaled_step = target_step / magnitude
            
            # Pick the closest nice step
            nice_options = [1, 2, 2.5, 5, 10]
            closest_nice_step = min(nice_options, key=lambda x: abs(x - rescaled_step))
            nice_step = closest_nice_step * magnitude
            
            # Calculate min and max based on the nice step
            r_min = math.floor(min_p / nice_step) * nice_step
            r_max = math.ceil(max_p / nice_step) * nice_step
            
            # Generate tick values
            tickvals = []
            curr = r_min
            while curr <= r_max + (nice_step / 1000): # Add epsilon for float precision
                tickvals.append(curr)
                curr += nice_step
        else:
            r_min, r_max = -1, 1
            tickvals = [-1, 0, 1]
            nice_step = 1

        efficiency = total_positive_energy / -total_negative_energy if total_negative_energy != 0 else 0

        info_children = html.Div([
            html.H4(f'פריקה מקסימלית: {max_power_discharging:,.2f} MW', style={'fontSize': '20px'}),
            html.H4(f'טעינה מקסימלית: {-max_power_charging:,.2f} MW', style={'fontSize': '20px'}),
            html.H4(f'נצילות: {efficiency:.2%}', style={'fontSize': '20px'})
        ])

        fig.update_layout(
            title=go.layout.Title(
                x=0.5, xanchor='center', font={"family": "Hebrew", "size": 36}, text='אגירה'
            ),
            paper_bgcolor='white',
            dragmode=False,
            margin=dict(l=40, r=40, t=60, b=40),
            polar=dict(
                bgcolor="white",
                radialaxis=dict(
                    visible=True,
                    range=[r_min, r_max + (nice_step / 10) if all_power_values else 1], # Increased padding
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
        
        # Add a thicker zero line
        zero_line_theta = [i for i in range(0, 361)]
        zero_line_r = [0] * len(zero_line_theta)
        
        fig.add_trace(go.Scatterpolar(
            r=zero_line_r,
            theta=zero_line_theta,
            mode='lines',
            line=dict(color='black', width=2),
            hoverinfo='skip',
            showlegend=False
        ))

        return fig, info_children
