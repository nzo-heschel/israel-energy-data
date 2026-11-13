import os
import logging
import threading
import time
from flask import request, Response
from dash import Dash, dcc, html, ctx, Input, Output, State
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

BURGER_ID = 'nav-burger'
APP_SHELL_ID = 'app-shell'


def _navbar():
    return dmc.AppShellNavbar([
        dmc.Text('ניווט', size='xs', fw=700, c='dimmed', mb='xs', px='sm'),
        *[dmc.NavLink(label=label, href=href, active='exact', leftSection=ui.icon(icon_name),
                      className='nav-link', variant='light')
          for href, label, icon_name in NAV_ITEMS],
        dmc.Box(style={'flex': 1}),
        dmc.Divider(my='sm'),
        dmc.Group([
            ui.icon('bolt', 14),
            dmc.Text('מקור הנתונים: נוגה – ניהול מערכת החשמל', size='xs', c='dimmed'),
        ], gap=6, px='sm', c='dimmed', wrap='nowrap'),
    ], p='md', style={'display': 'flex', 'flexDirection': 'column'})


def _header():
    return dmc.AppShellHeader(
        dmc.Group([
            dmc.Group([
                dmc.Burger(id=BURGER_ID, size='sm', hiddenFrom='sm', opened=False),
                dcc.Link(html.Img(src=LOGO_URL, className='brand-logo', alt='Logo'), href='/'),
                dmc.Divider(orientation='vertical', visibleFrom='xs'),
                dmc.Text('נתוני חשמל בישראל', fw=700, size='lg', visibleFrom='xs'),
            ], gap='md', wrap='nowrap'),
            dmc.Badge('נתונים פתוחים', variant='light', radius='sm', visibleFrom='sm'),
        ], h='100%', px='lg', justify='space-between', wrap='nowrap'),
        className='app-header',
    )


# --- Top-Level Application Layout ---
def app_layout():
    # This is the single layout structure Dash requires for routing
    return dmc.MantineProvider(
        dmc.DirectionProvider(
            dmc.AppShell([
                dcc.Location(id='url', refresh=False),
                _header(),
                _navbar(),
                dmc.AppShellMain(dmc.Container(html.Div(id='page-content'), size='xl', px={'base': 'xs', 'sm': 'md'}, py='md')),
            ],
                id=APP_SHELL_ID,
                header={'height': 64},
                navbar={'width': 248, 'breakpoint': 'sm', 'collapsed': {'mobile': True}},
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


@dash_app.callback(Output(APP_SHELL_ID, 'navbar'),
                   Output(BURGER_ID, 'opened'),
                   Input(BURGER_ID, 'opened'),
                   Input('url', 'pathname'),
                   State(APP_SHELL_ID, 'navbar'))
def toggle_navbar(opened, _pathname, navbar):
    # On mobile the navbar is a drawer: the burger opens it, navigating closes it
    if ctx.triggered_id == 'url':
        opened = False
    navbar['collapsed'] = {'mobile': not opened}
    return navbar, opened


bar_chart.register_callbacks(dash_app)
heatmap.register_callbacks(dash_app)
storage.register_callbacks(dash_app)
co2.register_callbacks(dash_app)

if __name__ == "__main__":
    main()
