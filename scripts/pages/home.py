import logging
from datetime import datetime
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


def _kpis():
    """Headline numbers from the latest loaded day. Returns None if data isn't available yet."""
    dfs = heatmap.dfs
    if "ActualDemand" not in dfs or "RenewableSum" not in dfs:
        return None
    try:
        demand = dfs["ActualDemand"]
        renewables = dfs["RenewableSum"]
        # Today's column is still filling up during the day, so report the last complete day
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        last_day = demand.columns[demand.columns < today].max()
        day_demand = demand[last_day]
        day_share = renewables[last_day].sum() / day_demand.sum()

        year_cols = [c for c in demand.columns if c.year == last_day.year]
        year_share = renewables[year_cols].sum().sum() / demand[year_cols].sum().sum()
        return [
            ui.stat_card('מתחדשות – היום האחרון', f'{day_share:.1%}', 'sun', hint=last_day.strftime('%d/%m/%Y')),
            ui.stat_card(f'מתחדשות – {last_day.year}', f'{year_share:.1%}', 'leaf', hint='מתחילת השנה'),
            ui.stat_card('שיא ביקוש יומי', f'{day_demand.max():,.0f} MW', 'gauge', color='blue',
                         hint=f'בשעה {day_demand.idxmax()}'),
            ui.stat_card('צריכה יומית', f'{day_demand.sum() / 12 / 1000:,.1f} GWh', 'bolt', color='orange',
                         hint=last_day.strftime('%d/%m/%Y')),
        ]
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
    return dmc.Stack([
        dmc.Paper(
            dmc.Group([
                dmc.Stack([
                    dmc.Badge('NOGA · נתונים פתוחים', variant='light', size='lg', radius='sm'),
                    dmc.Title('משק החשמל בישראל, בנתונים', order=1, fw=800, style={'fontSize': 'clamp(28px, 4vw, 42px)'}),
                    dmc.Text('ייצור, ביקוש, אגירה ופליטות – מתעדכן אוטומטית מנתוני נוגה, ניהול מערכת החשמל.',
                             c='dimmed', size='lg', maw=560),
                ], gap='sm'),
                html.Img(src=LOGO_URL, className='hero-logo', alt='Logo'),
            ], justify='space-between', align='center', wrap='wrap', gap='xl'),
            className='hero', p={'base': 'lg', 'sm': 40}, radius='lg', withBorder=True,
        ),
        dmc.SimpleGrid(kpis, cols={'base': 1, 'xs': 2, 'md': 4}, spacing='md') if kpis else None,
        dmc.Title('גרפים', order=3, mt='sm'),
        dmc.SimpleGrid([_feature_card(*f) for f in FEATURES], cols={'base': 1, 'sm': 2, 'lg': 4}, spacing='md'),
    ], gap='lg')
