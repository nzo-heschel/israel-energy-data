import os
import logging
import threading
import time
from flask import request, Response
from dash import Dash, dcc, html, Input, Output
from pages import home, bar_chart, heatmap, storage

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_PATH = os.path.join(ROOT_DIR, 'assets')
dash_app = Dash(__name__, assets_folder=ASSETS_PATH, suppress_callback_exceptions=True)
LOGO_URL = dash_app.get_asset_url('logo.png')

data_ready = False

STARTUP_HTML = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="10">
    <title>טוען נתונים...</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            text-align: center;
            padding-top: 80px;
            background-color: #ffffff;
            color: #333333;
        }}
        img.logo {{
            height: 80px;
            width: auto;
            display: block;
            margin: 20px auto;
        }}
        .spinner {{
            margin: 30px auto;
            width: 48px;
            height: 48px;
            border: 5px solid #e0e0e0;
            border-top-color: #00a060;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
    </style>
    <script>
        setTimeout(function() {{ window.location.reload(); }}, 10000);
    </script>
</head>
<body>
    <h1>אתר הנתונים של</h1>
    <img class="logo" src="{LOGO_URL}" alt="Logo">
    <div class="spinner"></div>
    <h2>השרת עולה וטוען נתונים, אנא המתינו...</h2>
    <p>הדף יתרענן אוטומטית כל 10 שניות</p>
</body>
</html>
"""


@dash_app.server.before_request
def check_startup_ready():
    if not data_ready and not request.path.startswith('/assets/'):
        return Response(STARTUP_HTML, status=200, mimetype='text/html')


PATH_BAR_CHART = '/bar-chart'
PATH_HEATMAP = '/heatmap'
PATH_STORAGE = '/storage'

nav_links = html.Div([
    dcc.Link('דף הבית', href='/'),
    html.Span(' | '),
    dcc.Link('אנרגיות מתחדשות', href=PATH_BAR_CHART),
    html.Span(' | '),
    dcc.Link('תמהיל הייצור', href=PATH_HEATMAP),
    html.Span(' | '),
    dcc.Link('אגירה', href=PATH_STORAGE),
    html.Hr()
], style={'padding': '10px', 'textAlign': 'right'})



# --- New Top-Level Application Layout ---
def app_layout():
    # This is the single layout structure Dash requires for routing
    return html.Div([
        dcc.Location(id='url', refresh=False),
        html.Div(id='page-content')
    ])


def _load_initial_data():
    global data_ready
    time.sleep(1)
    logging.info("Loading initial chart data in background")
    heatmap.retrieve_data()
    bar_chart.retrieve_data()
    data_ready = True
    logging.info("Initial chart data loaded; server is ready")


def main():
    logging.info("Starting charts")
    threading.Thread(target=_load_initial_data, daemon=True).start()
    # Use the new top-level layout function for routing
    dash_app.layout = app_layout
    dash_app.run(debug=False, host='0.0.0.0', port=9998)


@dash_app.callback(Output('page-content', 'children'),
                   [Input('url', 'pathname')])
def display_page(pathname):
    if pathname == PATH_BAR_CHART:
        return bar_chart.bar_chart_layout(nav_links)
    elif pathname == PATH_HEATMAP:
        return heatmap.heatmap_layout(nav_links)
    elif pathname == PATH_STORAGE:
        return storage.storage_layout(nav_links)
    else:
        # Default to home page for '/' or any unrecognized path
        return home.home_layout(nav_links, LOGO_URL)


bar_chart.register_callbacks(dash_app)
heatmap.register_callbacks(dash_app)
storage.register_callbacks(dash_app)

if __name__ == "__main__":
    main()
