import os
import logging
from dash import Dash, dcc, html, Input, Output
from pages import home, bar_chart, heatmap

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_PATH = os.path.join(ROOT_DIR, 'assets')
dash_app = Dash(__name__, assets_folder=ASSETS_PATH)
LOGO_URL = dash_app.get_asset_url('logo.png')

PATH_BAR_CHART = '/bar-chart'
PATH_HEATMAP = '/heatmap'

nav_links = html.Div([
    dcc.Link('דף הבית', href='/'),
    html.Span(' | '),
    dcc.Link('אנרגיות מתחדשות', href=PATH_BAR_CHART),
    html.Span(' | '),
    dcc.Link('תמהיל הייצור', href=PATH_HEATMAP),
    html.Hr()
], style={'padding': '10px', 'textAlign': 'right'})



# --- New Top-Level Application Layout ---
def app_layout():
    # This is the single layout structure Dash requires for routing
    return html.Div([
        dcc.Location(id='url', refresh=False),
        html.Div(id='page-content')
    ])


def main():
    logging.info("Starting charts")
    heatmap.retrieve_data()
    bar_chart.retrieve_data()
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
    else:
        # Default to home page for '/' or any unrecognized path
        return home.home_layout(nav_links, LOGO_URL)


bar_chart.register_callbacks(dash_app)
heatmap.register_callbacks(dash_app)

if __name__ == "__main__":
    main()
