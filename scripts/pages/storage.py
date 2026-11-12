from dash import dcc, html, Input, Output, clientside_callback, callback_context
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging
import math
import numpy as np
from . import heatmap

STORAGE_ID = "storage-graph"
STORAGE_STORE_ID = "storage-graph-store"
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

VALUE_BATTERIES = 'BatteriesNet'
VALUE_PSP = 'PspNet'
VALUE_XY_GRAPH = 'xy'

COLOR_DISCHARGE = '#10b981'
COLOR_CHARGE = '#f43f5e'

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

    return html.Div([
        nav_links,
        dcc.Store(id=STORAGE_STORE_ID),
        html.Main([
            html.Div([
                html.Div([
                    html.H1("אגירת אנרגיה במשק החשמל", className='nzo-page-title'),
                    html.P("פרופיל טעינה ופריקה יומי, מעקב נצילות מחזורית, הספקי שיא ואנרגיה מצטברת", className='nzo-page-subtitle'),
                ]),
                html.Span("מקור הנתונים: נגה", className='nzo-source-pill'),
            ], className='nzo-page-header'),

            # Controls Toolbar Card
            html.Div([
                html.Div([
                    html.Span("טכנולוגיית אגירה:", className='nzo-control-label'),
                    dcc.RadioItems(
                        id=STORAGE_SOURCE_ID,
                        options=[
                            {'label': '🔋 אגירה בסוללות', 'value': VALUE_BATTERIES},
                            {'label': '💧 אגירה שאובה', 'value': VALUE_PSP}
                        ],
                        value=last_source,
                        inline=True,
                        className='nzo-segmented-radio'
                    ),
                ], className='nzo-control-group'),

                html.Div([
                    html.Span("תצוגת פרופיל:", className='nzo-control-label'),
                    dcc.Checklist(
                        id=GRAPH_TYPE_ID,
                        options=[{'label': '📈 גרף מלבני (24 שעות)', 'value': VALUE_XY_GRAPH}],
                        value=[],
                        className='nzo-checklist-pill'
                    ),
                ], className='nzo-control-group'),

                html.Div([
                    html.Span("טווח תאריכים:", className='nzo-control-label'),
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
                        ),
                    ], style={'direction': 'ltr'}),
                    html.Div([
                        html.Button('שבוע אחרון', id=BTN_WEEK_ID, n_clicks=0, className='nzo-btn'),
                        html.Button('חודש אחרון', id=BTN_MONTH_ID, n_clicks=0, className='nzo-btn'),
                        html.Button('שנה אחרונה', id=BTN_YEAR_ID, n_clicks=0, className='nzo-btn'),
                    ], style={'display': 'flex', 'gap': '6px', 'flexWrap': 'wrap'}),
                ], className='nzo-control-group'),
            ], className='nzo-toolbar-card'),

            # KPI Summary Cards Row
            html.Div(id=STORAGE_INFO_ID, className='nzo-kpi-grid'),

            # Main 24-hour Profile Card (Polar or XY)
            html.Div([
                dcc.Graph(
                    id=STORAGE_ID,
                    style={'width': '100%', 'height': '680px'},
                    config={'displayModeBar': False, 'scrollZoom': False, 'responsive': True},
                    clear_on_unhover=True
                ),
            ], className='nzo-card-chart'),

            # Cumulative Energy Card
            html.Div([
                dcc.Graph(
                    id=CUMULATIVE_ID,
                    style={'width': '100%', 'height': '380px'},
                    config={'displayModeBar': False, 'scrollZoom': False, 'responsive': True}
                ),
            ], className='nzo-card-chart'),

            # Side-by-side Daily Max Power & Daily Energy Cards
            html.Div([
                html.Div([
                    dcc.Graph(
                        id=DAILY_ID,
                        style={'width': '100%', 'height': '380px'},
                        config={'displayModeBar': False, 'scrollZoom': False, 'responsive': True}
                    ),
                ], className='nzo-card-chart', style={'marginBottom': '0'}),
                html.Div([
                    dcc.Graph(
                        id=DAILY_ENERGY_ID,
                        style={'width': '100%', 'height': '380px'},
                        config={'displayModeBar': False, 'scrollZoom': False, 'responsive': True}
                    ),
                ], className='nzo-card-chart', style={'marginBottom': '0'}),
            ], className='nzo-charts-grid-2'),
        ], className='nzo-page-container'),
    ])


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

        is_xy = VALUE_XY_GRAPH in (graph_type or [])

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
        time_objs = [datetime.strptime(t, "%H:%M") for t in times]
        diff_seconds = [(time_objs[i + 1] - time_objs[i]).total_seconds() for i in range(len(time_objs) - 1)]
        diff_seconds.append(300.0)  # Assume 5 minutes for the last interval
        diff_hours = np.array(diff_seconds) / 3600.0

        energy_df = df_filtered.mul(diff_hours, axis=0)

        # Global Stats
        total_positive_energy = energy_df[energy_df > 0].sum().sum()
        total_negative_energy = energy_df[energy_df < 0].sum().sum()
        max_power_discharging_total = df_filtered.max().max()
        max_power_charging_total = df_filtered.min().min()

        if max_power_discharging_total < 0:
            max_power_discharging_total = 0
        if max_power_charging_total > 0:
            max_power_charging_total = 0

        # Daily Stats
        daily_max_discharge = df_filtered.max().clip(lower=0)
        daily_max_charge = df_filtered.min().clip(upper=0)

        daily_energy_discharge = energy_df[energy_df > 0].sum()
        daily_energy_charge = energy_df[energy_df < 0].sum()

        # Cumulative Energy
        sorted_cols = sorted(df_filtered.columns)
        df_sorted = df_filtered[sorted_cols]
        energy_sorted = energy_df[sorted_cols]

        flat_energy = energy_sorted.values.flatten(order='F')
        cumulative_y = np.cumsum(flat_energy)

        time_deltas = [timedelta(hours=t.hour, minutes=t.minute) for t in time_objs]
        cumulative_x = []
        for d in sorted_cols:
            cumulative_x.extend([d + t for t in time_deltas])

        # Main Graph Traces
        for i, date_col in enumerate(sorted_cols):
            series = df_sorted[date_col]
            power_values = series.values
            date_str = date_col.strftime('%d-%m-%Y')

            custom_data_for_hover = list(zip(power_values, times, [date_str] * len(times)))

            if is_xy:
                fig_main.add_trace(go.Scattergl(
                    x=dt_times,
                    y=power_values,
                    customdata=custom_data_for_hover,
                    mode='lines',
                    name=date_str,
                    hovertemplate='<b>%{customdata[2]} | %{customdata[1]}</b><br>הספק: %{y:.2f} MW<extra></extra>',
                    showlegend=False,
                    line=dict(width=1.6)
                ))
            else:
                fig_main.add_trace(go.Scatterpolargl(
                    r=power_values,
                    theta=theta,
                    customdata=custom_data_for_hover,
                    mode='markers',
                    marker=dict(size=6),
                    name=date_str,
                    hovertemplate='<b>%{customdata[2]} | %{customdata[1]}</b><br>הספק: %{customdata[0]:.2f} MW<extra></extra>',
                    showlegend=False
                ))

        # Add cumulative energy trace
        fig_cum.add_trace(go.Scatter(
            x=cumulative_x,
            y=cumulative_y,
            mode='lines',
            name='אנרגיה מצטברת',
            line=dict(color='#0284c7', width=2),
            fill='tozeroy',
            fillcolor='rgba(2, 132, 199, 0.08)',
            hovertemplate='<b>%{x}</b><br>אנרגיה: %{y:,.2f} MWh<extra></extra>'
        ))

        # Add daily max charge/discharge traces
        fig_daily.add_trace(go.Scatter(
            x=daily_max_discharge.index,
            y=daily_max_discharge.values,
            mode='lines+markers',
            name='שיא פריקה',
            line=dict(color=COLOR_DISCHARGE, width=2),
            marker=dict(size=6),
            hovertemplate='<b>%{x}</b><br>שיא פריקה: %{y:,.2f} MW<extra></extra>'
        ))

        fig_daily.add_trace(go.Scatter(
            x=daily_max_charge.index,
            y=-daily_max_charge.values,
            mode='lines+markers',
            name='שיא טעינה',
            line=dict(color=COLOR_CHARGE, width=2),
            marker=dict(size=6),
            hovertemplate='<b>%{x}</b><br>שיא טעינה: %{y:,.2f} MW<extra></extra>'
        ))

        # Add daily energy charge/discharge traces
        fig_daily_energy.add_trace(go.Scatter(
            x=daily_energy_discharge.index,
            y=daily_energy_discharge.values,
            mode='lines+markers',
            name='אנרגיית פריקה',
            line=dict(color=COLOR_DISCHARGE, width=2),
            marker=dict(size=6),
            hovertemplate='<b>%{x}</b><br>פריקה יומית: %{y:,.2f} MWh<extra></extra>'
        ))

        fig_daily_energy.add_trace(go.Scatter(
            x=daily_energy_charge.index,
            y=-daily_energy_charge.values,
            mode='lines+markers',
            name='אנרגיית טעינה',
            line=dict(color=COLOR_CHARGE, width=2),
            marker=dict(size=6),
            hovertemplate='<b>%{x}</b><br>טעינה יומית: %{y:,.2f} MWh<extra></extra>'
        ))

        efficiency = total_positive_energy / -total_negative_energy if total_negative_energy != 0 else 0

        info_children = [
            html.Div([
                html.Div("פריקה מקסימלית בטווח", className='nzo-kpi-label'),
                html.Div(f"{max_power_discharging_total:,.1f} MW", className='nzo-kpi-value'),
                html.Div(f"סה״כ נפרק: {total_positive_energy:,.0f} MWh", className='nzo-kpi-sub'),
            ], className='nzo-kpi-card accent-green'),
            html.Div([
                html.Div("טעינה מקסימלית בטווח", className='nzo-kpi-label'),
                html.Div(f"{-max_power_charging_total:,.1f} MW", className='nzo-kpi-value'),
                html.Div(f"סה״כ נטען: {-total_negative_energy:,.0f} MWh", className='nzo-kpi-sub'),
            ], className='nzo-kpi-card accent-rose'),
            html.Div([
                html.Div("נצילות מחזורית", className='nzo-kpi-label'),
                html.Div(f"{efficiency:.1%}", className='nzo-kpi-value'),
                html.Div(f"יחס פריקה מול טעינה ({len(sorted_cols)} ימים)", className='nzo-kpi-sub'),
            ], className='nzo-kpi-card accent-teal'),
        ]

        title_text = 'אגירה בסוללות' if source == VALUE_BATTERIES else 'אגירה שאובה'
        common_font = {"family": "Heebo, Inter, sans-serif", "color": "#0f172a"}
        common_hover = dict(bgcolor="#0f172a", font_size=13, font_family="Heebo, Inter, sans-serif")

        # Main Figure Layout
        if is_xy:
            tickvals = [datetime(1900, 1, 1, h, 0) for h in range(0, 24, 3)]
            tickvals.append(XY_END_TIME)
            ticktext = [f"{h:02d}:00" for h in range(0, 24, 3)] + ["24:00"]

            range_x = [XY_START_TIME - timedelta(minutes=10), XY_END_TIME + timedelta(minutes=10)]

            fig_main.update_layout(
                title=go.layout.Title(
                    x=0.5, xanchor='center', font={"family": "Heebo, Inter, sans-serif", "size": 22, "color": "#0f172a"}, text=title_text
                ),
                font=common_font,
                hoverlabel=common_hover,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='#ffffff',
                dragmode=False,
                xaxis=dict(
                    title="שעה ביממה",
                    gridcolor='#e2e8f0',
                    tickformat="%H:%M",
                    fixedrange=True,
                    tickvals=tickvals,
                    ticktext=ticktext,
                    range=range_x
                ),
                yaxis=dict(
                    title="הספק (MW)",
                    gridcolor='#e2e8f0',
                    fixedrange=True,
                    zeroline=True,
                    zerolinecolor='#94a3b8',
                    zerolinewidth=1.5
                ),
                margin=dict(l=55, r=40, t=60, b=45),
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
                    x=0.5, xanchor='center', font={"family": "Heebo, Inter, sans-serif", "size": 22, "color": "#0f172a"}, text=title_text
                ),
                font=common_font,
                hoverlabel=common_hover,
                paper_bgcolor='rgba(0,0,0,0)',
                dragmode=False,
                margin=dict(l=40, r=40, t=65, b=40),
                polar=dict(
                    bgcolor="#ffffff",
                    radialaxis=dict(
                        visible=True,
                        range=range_vals,
                        tickvals=tickvals,
                        gridcolor='#cbd5e1',
                        tickfont=dict(size=12, color="#475569"),
                    ),
                    angularaxis=dict(
                        direction="clockwise", rotation=90, tickmode='array',
                        tickvals=[0, 45, 90, 135, 180, 225, 270, 315],
                        ticktext=['00:00', '03:00', '06:00', '09:00', '12:00', '15:00', '18:00', '21:00'],
                        gridcolor='#e2e8f0',
                        tickfont=dict(size=14, color="#0f172a"),
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
                line=dict(color='#0f172a', width=2),
                hoverinfo='skip',
                showlegend=False
            ))

        # Cumulative Figure Layout
        fig_cum.update_layout(
            title=go.layout.Title(text="אנרגיה מצטברת (MWh)", x=0.5, xanchor='center', font={"family": "Heebo, Inter, sans-serif", "size": 19, "color": "#0f172a"}),
            font=common_font,
            hoverlabel=common_hover,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='#ffffff',
            dragmode=False,
            xaxis=dict(title="זמן", gridcolor='#e2e8f0', fixedrange=True),
            yaxis=dict(title="אנרגיה (MWh)", gridcolor='#e2e8f0', fixedrange=True, zeroline=True, zerolinecolor='#cbd5e1', zerolinewidth=1),
            margin=dict(l=55, r=35, t=50, b=40),
            showlegend=False
        )

        # Daily Figure Layout
        fig_daily.update_layout(
            title=go.layout.Title(text="הספק מקסימלי יומי (MW)", x=0.5, xanchor='center', font={"family": "Heebo, Inter, sans-serif", "size": 19, "color": "#0f172a"}),
            font=common_font,
            hoverlabel=common_hover,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='#ffffff',
            dragmode=False,
            xaxis=dict(title="תאריך", gridcolor='#e2e8f0', fixedrange=True),
            yaxis=dict(title="הספק (MW)", gridcolor='#e2e8f0', fixedrange=True, rangemode='tozero', zeroline=True, zerolinecolor='#cbd5e1', zerolinewidth=1),
            margin=dict(l=55, r=35, t=50, b=40),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        # Daily Energy Figure Layout
        fig_daily_energy.update_layout(
            title=go.layout.Title(text="אנרגיה יומית: פריקה מול טעינה (MWh)", x=0.5, xanchor='center', font={"family": "Heebo, Inter, sans-serif", "size": 19, "color": "#0f172a"}),
            font=common_font,
            hoverlabel=common_hover,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='#ffffff',
            dragmode=False,
            xaxis=dict(title="תאריך", gridcolor='#e2e8f0', fixedrange=True),
            yaxis=dict(title="אנרגיה (MWh)", gridcolor='#e2e8f0', fixedrange=True, rangemode='tozero', zeroline=True, zerolinecolor='#cbd5e1', zerolinewidth=1),
            margin=dict(l=55, r=35, t=50, b=40),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        return fig_main, fig_cum, fig_daily, fig_daily_energy, info_children, start_date, end_date, min_date_allowed, max_date_allowed
