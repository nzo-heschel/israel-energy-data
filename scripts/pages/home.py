import logging
from datetime import datetime
import pandas as pd
from dash import dcc, html
import dash_mantine_components as dmc

from . import heatmap, ui

FEATURES = [
    ('/bar-chart', 'sun', 'אנרגיות מתחדשות',
     'ייצור חודשי ושנתי לפי שנים, וחלקן של האנרגיות המתחדשות בסך הייצור.'),
    ('/heatmap', 'layers', 'תמהיל הייצור',
     'מפת חום לכל מקור ייצור – לפי שעה ביום ולאורך השנים, בערכים מוחלטים או באחוזים.'),
    ('/storage', 'battery', 'אגירה',
     'פרופיל הטעינה והפריקה של סוללות ואגירה שאובה, הספקים מקסימליים ונצילות.'),
    ('/co2', 'cloud', 'פליטות',
     'פליטות CO2 לפי סוג דלק, יחס פליטות לקוט"ש, וחיסכון מאנרגיות מתחדשות.'),
]


def _peak(df, cols):
    """Highest reading in the given day columns, as (value, timestamp)."""
    day = df[cols].max().idxmax()
    time = df[day].idxmax()
    return df.at[time, day], day.strftime('%d/%m/%Y') + ' · ' + time


# Home page KPIs use a larger number than the default stat card
VALUE_SIZE = 28


def _format_mw(value):
    return f'{value:,.0f} MW' if value >= 100 else f'{value:,.1f} MW'


def _kpis():
    """Headline numbers from the loaded data, as (renewables cards, peak cards). None if data isn't available yet."""
    dfs = heatmap.dfs
    if any(s not in dfs for s in ('ActualDemand', 'RenewableSum', 'Pv', 'BatteriesNet', 'PvWithStorage')):
        return None
    try:
        demand = dfs["ActualDemand"]
        renewables = dfs["RenewableSum"]
        # Today's column is still filling up during the day, so count up to the last complete day
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        last_day = demand.columns[demand.columns < today].max()

        def share(cols):
            return renewables[cols].sum().sum() / demand[cols].sum().sum()

        year_cols = demand.columns[(demand.columns.year == last_day.year) & (demand.columns <= last_day)]
        past_12m_cols = demand.columns[(demand.columns > last_day - pd.DateOffset(years=1)) & (demand.columns <= last_day)]
        renewable_cards = [
            ui.stat_card('מתחדשות – מתחילת השנה', f'{share(year_cols):.1%}', 'leaf',
                         hint=f'עד {last_day:%d/%m/%Y}', value_size=VALUE_SIZE),
            ui.stat_card('מתחדשות – 12 חודשים', f'{share(past_12m_cols):.1%}', 'leaf',
                         hint=f'עד {last_day:%d/%m/%Y}', value_size=VALUE_SIZE),
        ]

        peak_cards = []
        for source, label, icon_name, color in [
            ('ActualDemand', 'שיא ביקוש – 12 חודשים', 'gauge', 'red'),
            ('Pv', 'שיא ייצור סולארי – 12 חודשים', 'sun', 'yellow'),
            ('BatteriesNet', 'שיא פריקת סוללות – 12 חודשים', 'battery', 'teal'),
            ('PvWithStorage', 'שיא PV משולב אגירה – 12 חודשים', 'sun', 'lime'),
        ]:
            value, when = _peak(dfs[source], past_12m_cols)
            peak_cards.append(ui.stat_card(label, _format_mw(value), icon_name, color=color, hint=when,
                                           value_size=VALUE_SIZE))
        return renewable_cards, peak_cards
    except (KeyError, ValueError, ZeroDivisionError, AttributeError) as e:
        logging.warning(f"Could not compute home KPIs: {e}")
        return None


def _feature_card(href, icon_name, title, description):
    return dcc.Link(
        dmc.Card([
            dmc.ThemeIcon(ui.icon(icon_name, 24), size=48, radius='md', variant='light', mb='md'),
            dmc.Text(title, fw=700, size='lg', mb=6),
            dmc.Text(description, c='dimmed', size='sm', mb='md'),
            dmc.Group([
                dmc.Text('לגרף', size='sm', fw=600, c='teal'),
                html.Span(ui.icon('chevron', 16), className='feature-arrow', style={'color': 'var(--mantine-color-teal-6)', 'display': 'flex'}),
            ], gap=4),
        ], h='100%'),
        href=href, className='feature-card',
    )


def home_layout(LOGO_URL):
    kpis = _kpis()
    renewable_cards, peak_cards = kpis if kpis else ([], [])
    return dmc.Stack([
        dmc.Paper(
            dmc.Group([
                dmc.Stack([
                    dmc.Badge('הנגשת מידע לציבור - NZO', leftSection=ui.icon('chart', 14), variant='light', size='lg',
                              radius='sm'),
                    dmc.Title('אתר הנגשת הנתונים של NZO למשק החשמל והאנרגיה בישראל', order=1, fw=800,
                              style={'fontSize': 'clamp(26px, 3vw, 34px)'}, maw=620),
                ], gap='sm', style={'flex': '1 1 360px'}),
                dmc.Group([html.Div(card, className='hero-stat') for card in renewable_cards], gap='md'),
                # Last in the RTL row, so the logo sits on the left
                dmc.Paper(html.Img(src=LOGO_URL, className='hero-logo', alt='NZO'),
                          className='hero-logo-box', radius='lg', shadow='sm', withBorder=True),
            ], justify='space-between', align='center', gap='xl'),
            className='hero', p={'base': 'lg', 'sm': 40}, radius='lg', withBorder=True,
        ),
        dmc.SimpleGrid(peak_cards, cols={'base': 1, 'xs': 2, 'md': 4}, spacing='md') if peak_cards else None,
        dmc.Title('גרפים', order=3, mt='sm'),
        dmc.SimpleGrid([_feature_card(*f) for f in FEATURES], cols={'base': 1, 'sm': 2, 'lg': 4}, spacing='md'),
    ], gap='lg')
