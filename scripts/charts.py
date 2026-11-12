import os
import logging
import threading
import time
from flask import request, Response
from dash import Dash, dcc, html, Input, Output
from pages import home, bar_chart, heatmap, storage, co2

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_PATH = os.path.join(ROOT_DIR, 'assets')
dash_app = Dash(
    __name__,
    assets_folder=ASSETS_PATH,
    suppress_callback_exceptions=True,
    title="NZO | נתוני אנרגיה וחשמל בישראל",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
LOGO_URL = dash_app.get_asset_url('logo.png')

data_ready = False

STARTUP_HTML = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="10">
    <title>NZO | טוען נתונים...</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700;800&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Heebo', -apple-system, BlinkMacSystemFont, sans-serif;
            background: radial-gradient(circle at 20% 10%, #e0f2fe 0%, #f1f5f9 50%, #ecfdf5 100%);
            color: #0f172a;
            padding: 24px;
        }}
        .startup-card {{
            background: rgba(255, 255, 255, 0.92);
            backdrop-filter: blur(16px);
            border: 1px solid #e2e8f0;
            border-radius: 24px;
            padding: 48px 44px;
            max-width: 480px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 45px -10px rgba(15, 23, 42, 0.08), 0 4px 12px -2px rgba(15, 23, 42, 0.04);
        }}
        img.logo {{
            height: 72px;
            width: auto;
            display: block;
            margin: 0 auto 24px;
        }}
        .spinner-wrap {{
            position: relative;
            width: 56px;
            height: 56px;
            margin: 28px auto;
        }}
        .spinner {{
            width: 56px;
            height: 56px;
            border: 4px solid #e2e8f0;
            border-top-color: #0284c7;
            border-right-color: #10b981;
            border-radius: 50%;
            animation: spin 0.95s cubic-bezier(0.5, 0.1, 0.5, 0.9) infinite;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        h1 {{
            font-size: 24px;
            font-weight: 800;
            margin: 0 0 8px;
            color: #0f172a;
        }}
        h2 {{
            font-size: 16px;
            font-weight: 500;
            color: #475569;
            margin: 0 0 16px;
            line-height: 1.5;
        }}
        .badge {{
            display: inline-block;
            font-size: 13px;
            font-weight: 600;
            color: #0369a1;
            background: #e0f2fe;
            padding: 6px 16px;
            border-radius: 9999px;
        }}
    </style>
    <script>
        setTimeout(function() {{ window.location.reload(); }}, 10000);
    </script>
</head>
<body>
    <div class="startup-card">
        <img class="logo" src="{LOGO_URL}" alt="NZO Logo">
        <h1>מערכת נתוני האנרגיה של ישראל</h1>
        <div class="spinner-wrap"><div class="spinner"></div></div>
        <h2>השרת עולה ומעבד את נתוני הרשת העדכניים, אנא המתינו...</h2>
        <span class="badge">מתרענן אוטומטית כל 10 שניות</span>
    </div>
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
PATH_CO2 = '/co2'

NAV_ITEMS = [
    ('/', 'דף הבית'),
    (PATH_BAR_CHART, 'אנרגיות מתחדשות'),
    (PATH_HEATMAP, 'תמהיל הייצור'),
    (PATH_STORAGE, 'אגירה'),
    (PATH_CO2, 'פליטות CO₂'),
]


def create_navbar(active_path='/'):
    normalized = active_path if active_path in {p for p, _ in NAV_ITEMS} else '/'
    return html.Header([
        dcc.Link([
            html.Img(src=LOGO_URL, className='nzo-brand-logo', alt='NZO Logo'),
            html.Div([
                html.Span('פלטפורמת נתוני האנרגיה', className='nzo-brand-title'),
                html.Span('משק החשמל בישראל • נתוני נגה', className='nzo-brand-subtitle'),
            ], className='nzo-brand-text'),
        ], href='/', className='nzo-brand'),
        html.Nav([
            dcc.Link(
                label,
                href=href,
                className=f"nzo-nav-link {'active' if normalized == href else ''}"
            )
            for href, label in NAV_ITEMS
        ], className='nzo-nav-links'),
        html.Div([
            html.Span(className='nzo-status-dot'),
            html.Span('נתוני רשת חיים'),
        ], className='nzo-nav-badge'),
    ], className='nzo-navbar')


nav_links = create_navbar('/')


# --- Top-Level Application Layout ---
def app_layout():
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
    dash_app.layout = app_layout
    dash_app.run(debug=False, host='0.0.0.0', port=9998)


@dash_app.callback(Output('page-content', 'children'),
                   [Input('url', 'pathname')])
def display_page(pathname):
    navbar = create_navbar(pathname)
    if pathname == PATH_BAR_CHART:
        return bar_chart.bar_chart_layout(navbar)
    elif pathname == PATH_HEATMAP:
        return heatmap.heatmap_layout(navbar)
    elif pathname == PATH_STORAGE:
        return storage.storage_layout(navbar)
    elif pathname == PATH_CO2:
        return co2.co2_layout(navbar)
    else:
        return home.home_layout(navbar, LOGO_URL)


bar_chart.register_callbacks(dash_app)
heatmap.register_callbacks(dash_app)
storage.register_callbacks(dash_app)
co2.register_callbacks(dash_app)

if __name__ == "__main__":
    main()
