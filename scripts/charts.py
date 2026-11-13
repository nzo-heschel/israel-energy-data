import os
import logging
import threading
import time
from flask import request, Response
from dash import Dash, dcc, html, Input, Output
import dash_mantine_components as dmc
from pages import home, bar_chart, heatmap, storage, co2, ui

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_PATH = os.path.join(ROOT_DIR, 'assets')
dash_app = Dash(__name__, assets_folder=ASSETS_PATH, suppress_callback_exceptions=True,
                external_stylesheets=[ui.FONT_URL], title='נתוני חשמל בישראל')
LOGO_URL = dash_app.get_asset_url('logo.png')

data_ready = False

STARTUP_HTML = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="10">
    <title>טוען נתונים...</title>
    <link rel="stylesheet" href="{ui.FONT_URL}">
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: {ui.FONT_FAMILY};
            color: #212529;
            background:
                radial-gradient(circle at 15% 20%, rgba(32, 201, 151, 0.18), transparent 45%),
                radial-gradient(circle at 85% 80%, rgba(42, 120, 214, 0.14), transparent 50%),
                #f6f8fa;
        }}
        .card {{
            background: #ffffff;
            border: 1px solid #e9ecef;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(16, 24, 40, 0.08);
            padding: 48px 40px;
            max-width: 440px;
            width: calc(100% - 32px);
            text-align: center;
        }}
        img.logo {{ height: 64px; width: auto; display: block; margin: 0 auto 24px; }}
        h1 {{ font-size: 22px; font-weight: 700; margin: 0 0 8px; }}
        p {{ color: #868e96; font-size: 14px; margin: 0; }}
        .progress {{
            height: 6px;
            border-radius: 3px;
            background: #e6fcf5;
            overflow: hidden;
            margin: 28px 0 20px;
        }}
        .progress::after {{
            content: "";
            display: block;
            height: 100%;
            width: 40%;
            border-radius: 3px;
            background: linear-gradient(90deg, #20c997, #0ca678);
            animation: slide 1.4s ease-in-out infinite;
        }}
        @keyframes slide {{
            from {{ transform: translateX(150%); }}
            to {{ transform: translateX(-250%); }}
        }}
    </style>
    <script>
        setTimeout(function() {{ window.location.reload(); }}, 10000);
    </script>
</head>
<body>
    <div class="card">
        <img class="logo" src="{LOGO_URL}" alt="Logo">
        <h1>השרת עולה וטוען נתונים</h1>
        <p>אנא המתינו, הדף יתרענן אוטומטית כל 10 שניות</p>
        <div class="progress"></div>
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
    ('/', 'דף הבית', 'home'),
    (PATH_BAR_CHART, 'אנרגיות מתחדשות', 'sun'),
    (PATH_HEATMAP, 'תמהיל הייצור', 'layers'),
    (PATH_STORAGE, 'אגירה', 'battery'),
    (PATH_CO2, 'פליטות', 'cloud'),
]

def _nav_links():
    return dmc.Group([
        dmc.NavLink(label=label, href=href, active='exact', leftSection=ui.icon(icon_name, 16),
                    className='nav-link', variant='light', w='auto', noWrap=True)
        for href, label, icon_name in NAV_ITEMS
    ], gap=4, wrap='nowrap', visibleFrom='md')


def _nav_menu():
    # Below the md breakpoint the links don't fit in the header, so they collapse into a menu
    return dmc.Box(dmc.Menu([
        dmc.MenuTarget(dmc.ActionIcon(ui.icon('menu', 20), variant='subtle', color='gray', size='lg',
                                      **{'aria-label': 'ניווט'})),
        dmc.MenuDropdown([
            dmc.MenuItem(label, href=href, leftSection=ui.icon(icon_name, 16))
            for href, label, icon_name in NAV_ITEMS
        ]),
    ], position='bottom-end', width=220, shadow='md'), hiddenFrom='md')


def _header():
    return dmc.AppShellHeader(
        dmc.Group([
            dmc.Group([
                dcc.Link(html.Img(src=LOGO_URL, className='brand-logo', alt='Logo'), href='/'),
                dmc.Divider(orientation='vertical', visibleFrom='lg'),
                dmc.Text('נתוני חשמל בישראל', fw=700, size='lg', visibleFrom='lg'),
            ], gap='md', wrap='nowrap'),
            _nav_links(),
            _nav_menu(),
        ], h='100%', px='lg', justify='space-between', wrap='nowrap'),
        className='app-header',
    )


def _footer():
    return dmc.Group([
        ui.icon('bolt', 14),
        dmc.Text('מקור הנתונים: נוגה – ניהול מערכת החשמל', size='xs'),
    ], gap=6, c='dimmed', justify='center', mt='xl', pb='md')


# --- Top-Level Application Layout ---
def app_layout():
    # This is the single layout structure Dash requires for routing
    return dmc.MantineProvider(
        dmc.DirectionProvider(
            dmc.AppShell([
                dcc.Location(id='url', refresh=False),
                _header(),
                dmc.AppShellMain(dmc.Container([
                    html.Div(id='page-content'),
                    _footer(),
                ], size='xl', px={'base': 'xs', 'sm': 'md'}, py='md')),
            ],
                header={'height': 64},
                padding='md',
            ),
            direction='rtl',
        ),
        theme=ui.MANTINE_THEME,
        forceColorScheme='light',
    )


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
        return bar_chart.bar_chart_layout()
    elif pathname == PATH_HEATMAP:
        return heatmap.heatmap_layout()
    elif pathname == PATH_STORAGE:
        return storage.storage_layout()
    elif pathname == PATH_CO2:
        return co2.co2_layout()
    else:
        # Default to home page for '/' or any unrecognized path
        return home.home_layout(LOGO_URL)


bar_chart.register_callbacks(dash_app)
heatmap.register_callbacks(dash_app)
storage.register_callbacks(dash_app)
co2.register_callbacks(dash_app)

if __name__ == "__main__":
    main()
