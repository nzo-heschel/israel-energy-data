from datetime import datetime
from dateutil.relativedelta import relativedelta
from dash import dcc, html
import logging
from scripts import noga
from . import bar_chart, heatmap


def _filter_last_12_months(df):
    """Return a slice of df containing only columns from the last 12 months."""
    if df is None or df.empty:
        return df
    latest_col = max(df.columns)
    cutoff = latest_col - relativedelta(months=12)
    cols = [c for c in df.columns if c >= cutoff]
    return df[cols] if cols else df


def _compute_home_kpis():
    """Safely extract live summary KPIs from loaded in-memory datasets."""
    ren_share_str = "—"
    ren_sub_str = "נתונים רב-שנתיים"
    peak_demand_str = "—"
    demand_sub_str = "שיא ביקוש ב-12 החודשים האחרונים"
    peak_pv_str = "—"
    pv_sub_str = "שיא ייצור סולארי ב-12 החודשים האחרונים"
    peak_bess_str = "—"
    bess_sub_str = "שיא פריקה מסוללות ב-12 החודשים האחרונים"

    try:
        cost_data = bar_chart.cached_data
        max_yr = bar_chart.last_max_year
        if cost_data and max_yr:
            yr_total = 0.0
            yr_ren = 0.0
            for date_str, d in cost_data.items():
                parts = date_str.split('-')
                if len(parts) == 3 and int(parts[2]) == max_yr:
                    slot = d.get('00:00', {})
                    r = float(slot.get(noga.COST_REN, 0.0)) * 0.5 / 1000.0
                    c = float(slot.get(noga.COST_CONV, 0.0)) * 0.5 / 1000.0
                    yr_ren += r
                    yr_total += (r + c)
            if yr_total > 0:
                ren_share_str = f"{(yr_ren / yr_total) * 100:.1f}%"
                ren_sub_str = f"שנת {max_yr} • {yr_ren / 1e3:.2f} מתוך {yr_total / 1e3:.2f} TWh"
    except Exception as ex:
        logging.debug("KPI calc (bar_chart) skipped: %s", ex)

    try:
        dfs = heatmap.dfs or {}
        if "ActualDemand" in dfs and not dfs["ActualDemand"].empty:
            df_dem = _filter_last_12_months(dfs["ActualDemand"])
            daily_peaks = df_dem.max()
            peak_val = float(daily_peaks.max())
            peak_date = daily_peaks.idxmax()
            peak_demand_str = f"{peak_val:,.0f} MW"
            if hasattr(peak_date, "strftime"):
                demand_sub_str = f"ב-12 החודשים האחרונים (נרשם ב-{peak_date.strftime('%d/%m/%Y')})"
            else:
                demand_sub_str = "שיא ביקוש ב-12 החודשים האחרונים"

        if "Pv" in dfs and not dfs["Pv"].empty:
            df_pv = _filter_last_12_months(dfs["Pv"])
            daily_pv_peaks = df_pv.max()
            peak_pv = float(daily_pv_peaks.max())
            peak_pv_date = daily_pv_peaks.idxmax()
            peak_pv_str = f"{peak_pv:,.0f} MW"
            if hasattr(peak_pv_date, "strftime"):
                pv_sub_str = f"ב-12 החודשים האחרונים (נרשם ב-{peak_pv_date.strftime('%d/%m/%Y')})"
            else:
                pv_sub_str = "שיא ייצור פוטו-וולטאי ב-12 החודשים האחרונים"

        if "BatteriesNet" in dfs and not dfs["BatteriesNet"].empty:
            df_bess = _filter_last_12_months(dfs["BatteriesNet"])
            peak_bess = float(df_bess.max().max())
            min_bess = float(df_bess.min().min())
            peak_bess_str = f"{max(0.0, peak_bess):,.0f} MW"
            bess_sub_str = f"ב-12 החודשים האחרונים • שיא טעינה: {abs(min(0.0, min_bess)):,.0f} MW"
    except Exception as ex:
        logging.debug("KPI calc (heatmap) skipped: %s", ex)

    return [
        ("שיעור אנרגיות מתחדשות", ren_share_str, ren_sub_str, "accent-green"),
        ("שיא ביקוש בחשמל", peak_demand_str, demand_sub_str, "accent-teal"),
        ("שיא ייצור סולארי", peak_pv_str, pv_sub_str, "accent-amber"),
        ("שיא הזרמה מאגירה בסוללות", peak_bess_str, bess_sub_str, "accent-rose"),
    ]


def home_layout(nav_links, LOGO_URL):
    kpis = _compute_home_kpis()

    features = [
        {
            "href": "/bar-chart",
            "icon": "☀️",
            "icon_bg": "#d1fae5",
            "title": "אנרגיות מתחדשות מול קונבנציונלי",
            "desc": "ניתוח חודשי ורב-שנתי של ייצור החשמל בישראל, אחוז חדירת אנרגיות מתחדשות ומגמות צמיחה משנת 2021 ועד היום.",
            "cta": "לגרף ייצור ומתחדשות ←",
        },
        {
            "href": "/heatmap",
            "icon": "⚡",
            "icon_bg": "#e0f2fe",
            "title": "תמהיל הייצור המלא",
            "desc": "נתוני ייצור ברזולוציה של 5 דקות ומגמה יומית לכל מקורות הייצור במשק: סולארי, גז טבעי, פחם, רוח, אגירה וביקוש משקי.",
            "cta": "למפת תמהיל הייצור ←",
        },
        {
            "href": "/storage",
            "icon": "🔋",
            "icon_bg": "#fef3c7",
            "title": "אגירה (סוללות ושאובה)",
            "desc": "פרופיל טעינה ופריקה יומי, מעקב נצילות מחזורית, הספקי שיא יומיים ואנרגיה מצטברת.",
            "cta": "לניתוח מערכות אגירה ←",
        },
        {
            "href": "/co2",
            "icon": "🌿",
            "icon_bg": "#ffe4e6",
            "title": "פליטות פחמן ואינטנסיביות CO₂",
            "desc": "מעקב אחר פליטות גזי חממה לפי סוג דלק (גז, פחם, דיזל, מזוט), מקדם פליטות לקוט״ש (tCO₂/MWh) וחיסכון בפליטות בזכות מתחדשות.",
            "cta": "לניתוח פליטות CO₂ ←",
        },
    ]

    return html.Div([
        nav_links,
        html.Main([
            # Hero Section
            html.Section([
                html.Div([
                    html.Div([
                        html.Span("📊 הנגשת מידע לציבור • NZO"),
                    ], className='nzo-hero-eyebrow'),
                    html.H1("אתר הנגשת הנתונים של NZO למשק החשמל והאנרגיה בישראל", className='nzo-hero-title'),
                    html.P(
                        "במטרה לקדם שקיפות ולהנגיש מידע אמין וברור לציבור, לחוקרים ולמקבלי החלטות, "
                        "ריכזנו את נתוני משק החשמל מנגה (ניהול מערכת החשמל) לתצוגות אינטראקטיביות, נוחות ופתוחות לכולם.",
                        className='nzo-hero-desc'
                    ),
                ], className='nzo-hero-content'),
                html.Div([
                    html.Img(src=LOGO_URL, className='nzo-hero-logo', alt='NZO Logo'),
                    html.Span("מקור הנתונים: נגה", style={'fontSize': '13px', 'fontWeight': '600', 'color': '#64748b'}),
                ], className='nzo-hero-logo-box'),
            ], className='nzo-hero'),

            # Live KPI Row
            html.Section([
                html.Div([
                    html.Div(label, className='nzo-kpi-label'),
                    html.Div(val, className='nzo-kpi-value'),
                    html.Div(sub, className='nzo-kpi-sub'),
                ], className=f'nzo-kpi-card {accent}')
                for label, val, sub, accent in kpis
            ], className='nzo-kpi-grid'),

            # Feature Cards Grid
            html.Div([
                html.H2("כלי ניתוח ותצוגות נתונים", className='nzo-page-title', style={'fontSize': '22px', 'marginBottom': '14px'}),
            ], style={'direction': 'rtl'}),
            html.Section([
                dcc.Link([
                    html.Div([
                        html.Div(f["icon"], className='nzo-feature-icon', style={'backgroundColor': f["icon_bg"]}),
                        html.H3(f["title"], className='nzo-feature-title'),
                        html.P(f["desc"], className='nzo-feature-desc'),
                    ]),
                    html.Span(f["cta"], className='nzo-feature-cta'),
                ], href=f["href"], className='nzo-feature-card')
                for f in features
            ], className='nzo-feature-grid'),
        ], className='nzo-page-container'),
    ])
