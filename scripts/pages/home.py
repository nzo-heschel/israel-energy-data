from dash import html


def home_layout(nav_links, LOGO_URL):
    return html.Div([
        nav_links,
        html.H1("אתר הנתונים של", style={'textAlign': 'center'}),
        html.Img(
            src=LOGO_URL,
            style={
                'height': '80px',
                'width': 'auto',
                'display': 'block', # Ensures the image takes up its own line
                'margin-left': 'auto',
                'margin-right': 'auto',
                'margin-top': '20px',
                'margin-bottom': '20px',
            }
        ),
        html.P("בחרו גרף מהרשימה בראש הדף", style={'textAlign': 'center'})
    ])