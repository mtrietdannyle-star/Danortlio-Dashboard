import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta, timezone
import json
import re

# Eastern timezone (UTC-4 EDT / UTC-5 EST)
ET_OFFSET = timedelta(hours=-4)  # EDT
def now_eastern():
    return datetime.now(timezone.utc) + ET_OFFSET

# ════════════════════════════════════════════════════
# PAGE CONFIG
# ════════════════════════════════════════════════════
st.set_page_config(
    page_title="Portfolio Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Bloomberg-style dark theme
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    .stApp { background-color: #000000; }
    header[data-testid="stHeader"] { background-color: #1a1a1a; border-bottom: 1px solid #cc7000; }
    .block-container { padding: 1rem 1.5rem; max-width: 1600px; }
    h1, h2, h3, h4 { color: #ff8c00 !important; font-family: 'Helvetica Neue', Helvetica, sans-serif !important; letter-spacing: 0.05em; }
    p, span, label, .stMarkdown { color: #e8e8e8 !important; font-family: 'Helvetica Neue', Helvetica, sans-serif !important; }
    .stMetric label { color: #555 !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: 0.08em; }
    .stMetric [data-testid="stMetricValue"] { font-size: 22px !important; font-weight: 700 !important; }
    div[data-testid="stMetricDelta"] { font-size: 12px !important; }
    .stDataFrame { border: 1px solid #222 !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 0; background-color: #1a1a1a; border-bottom: 1px solid #333; }
    .stTabs [data-baseweb="tab"] { color: #555; font-weight: 700; text-transform: uppercase; font-size: 11px; letter-spacing: 0.06em; padding: 8px 16px; }
    .stTabs [aria-selected="true"] { color: #ff8c00 !important; border-bottom: 2px solid #ff8c00; }
    .stFileUploader { border: 2px dashed #333 !important; background: #0a0a0a !important; }
    .stFileUploader:hover { border-color: #ff8c00 !important; }
    .stButton > button { background-color: #1a1a1a !important; color: #999 !important; border: 1px solid #333 !important; font-weight: 700 !important; text-transform: uppercase; letter-spacing: 0.06em; font-size: 11px !important; }
    .stButton > button:hover { background-color: #333 !important; color: #ff8c00 !important; border-color: #cc7000 !important; }
    .stSelectbox, .stMultiSelect { background-color: #111 !important; }
    div[data-testid="stExpander"] { border: 1px solid #222 !important; background: #111 !important; }
    div[data-testid="stExpander"] summary { color: #ff8c00 !important; }
    .green { color: #00d26a; } .red { color: #ff3b3b; }
    .metric-card { background: #111; border: 1px solid #222; padding: 12px 14px; border-radius: 0; }
    .metric-card .label { font-size: 9px; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px; }
    .metric-card .value { font-size: 20px; font-weight: 700; }
    .metric-card .sub { font-size: 11px; margin-top: 2px; }
    .topbar { background: #1a1a1a; border-bottom: 1px solid #cc7000; padding: 6px 0; margin-bottom: 8px; }
    .topbar-title { font-size: 14px; font-weight: 700; color: #ff8c00; letter-spacing: 0.1em; }
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════
# PERSISTENT STORAGE — survives page refresh
# ════════════════════════════════════════════════════
import os
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'portfolio_data.json')

def save_to_disk():
    """Save current state to JSON file"""
    try:
        export = {
            'positions': st.session_state.positions.to_dict('records') if isinstance(st.session_state.positions, pd.DataFrame) and len(st.session_state.positions) > 0 else [],
            'rebalances': st.session_state.rebalances.to_dict('records') if isinstance(st.session_state.rebalances, pd.DataFrame) and len(st.session_state.rebalances) > 0 else [],
            'benchmark': st.session_state.benchmark_components,
            'inception': st.session_state.inception_date,
            'account_data': st.session_state.get('account_data', {}),
            'target_weights': st.session_state.get('target_weights', {}),
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(export, f, default=str)
    except Exception as e:
        pass  # Silent fail on write errors

def load_from_disk():
    """Load saved state from JSON file"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            return data
    except:
        pass
    return None

# Initialize session state — try loading from disk first
saved = load_from_disk()
if 'positions' not in st.session_state:
    if saved and saved.get('positions'):
        st.session_state.positions = pd.DataFrame(saved['positions'])
    else:
        st.session_state.positions = pd.DataFrame(columns=['ticker','name','sleeve','shares','avgCost'])
if 'rebalances' not in st.session_state:
    if saved and saved.get('rebalances'):
        st.session_state.rebalances = pd.DataFrame(saved['rebalances'])
    else:
        st.session_state.rebalances = pd.DataFrame(columns=['date','action','ticker','shares','price','notes'])
if 'benchmark_components' not in st.session_state:
    if saved and saved.get('benchmark'):
        st.session_state.benchmark_components = saved['benchmark']
    else:
        st.session_state.benchmark_components = [{'ticker': 'SPY', 'weight': 60}, {'ticker': 'ACWI', 'weight': 40}]
if 'inception_date' not in st.session_state:
    if saved and saved.get('inception'):
        st.session_state.inception_date = saved['inception']
    else:
        st.session_state.inception_date = '2026-02-02'
if 'account_data' not in st.session_state:
    if saved and saved.get('account_data'):
        st.session_state.account_data = saved['account_data']
    else:
        st.session_state.account_data = {'realized_pnl': 0, 'total_deposits': 0, 'total_dividends': 0}
if 'target_weights' not in st.session_state:
    if saved and saved.get('target_weights'):
        st.session_state.target_weights = saved['target_weights']
    else:
        st.session_state.target_weights = {}

# ════════════════════════════════════════════════════
# SECURITY CLASSIFICATION (runtime, via yfinance)
# ════════════════════════════════════════════════════
# No hard-coded ticker lists: sleeve (etf vs stock) is derived from yfinance
# quoteType at import time and cached for a day. If yfinance can't classify
# (network failure / unknown ticker) we default to 'stock'; the
# "FIX SLEEVE CLASSIFICATION" toggle below the holdings table corrects any miss.
@st.cache_data(ttl=86400, show_spinner=False)
def _quote_type(ticker):
    """Raw quoteType from yfinance ('ETF', 'EQUITY', 'MUTUALFUND', ...)."""
    qt = yf.Ticker(ticker).info.get('quoteType', '')
    return str(qt).upper()

def classify_security(ticker):
    """Return 'etf' or 'stock' for sleeve assignment. Degrades to 'stock' on failure."""
    try:
        qt = _quote_type(ticker)
        if qt in ('ETF', 'MUTUALFUND', 'INDEX'):
            return 'etf'
    except Exception:
        pass
    return 'stock'

# ════════════════════════════════════════════════════
# SCHWAB CSV PARSER
# ════════════════════════════════════════════════════
def parse_schwab_csv(file):
    df = pd.read_csv(file, dtype=str)
    df.columns = df.columns.str.strip().str.replace('"', '')
    # Clean fields
    df['Date'] = df['Date'].str.split(' as of ').str[0]
    df['Quantity'] = pd.to_numeric(df['Quantity'].str.replace(r'[$,"]', '', regex=True), errors='coerce').fillna(0)
    df['Price'] = pd.to_numeric(df['Price'].str.replace(r'[$,"]', '', regex=True), errors='coerce').fillna(0)
    df['Amount'] = pd.to_numeric(df['Amount'].str.replace(r'[$,"]', '', regex=True), errors='coerce').fillna(0)
    df['Symbol'] = df['Symbol'].str.strip().str.replace('"', '')

    trades = df[df['Action'].isin(['Buy', 'Sell', 'Reinvest Shares', 'Cash In Lieu'])].copy()

    # CRITICAL: Sort chronologically — CSV is newest-first but we must process oldest-first
    trades['_parsed_date'] = pd.to_datetime(trades['Date'], format='%m/%d/%Y', errors='coerce')
    trades = trades.sort_values('_parsed_date', ascending=True).reset_index(drop=True)

    # Calculate positions using average cost method + track realized P&L
    positions = {}
    total_realized_pnl = 0.0

    for _, row in trades.iterrows():
        sym = row['Symbol']
        if not sym or pd.isna(sym):
            continue
        if sym not in positions:
            positions[sym] = {'shares': 0.0, 'cost': 0.0, 'desc': row.get('Description', sym), 'realized': 0.0}
        p = positions[sym]
        if row['Action'] in ['Buy', 'Reinvest Shares']:
            p['shares'] += row['Quantity']
            p['cost'] += row['Quantity'] * row['Price']
        elif row['Action'] == 'Sell':
            if p['shares'] > 0:
                avg = p['cost'] / p['shares']
                realized = (row['Price'] - avg) * row['Quantity']
                p['realized'] += realized
                total_realized_pnl += realized
                p['cost'] -= row['Quantity'] * avg
            p['shares'] -= row['Quantity']
        elif row['Action'] == 'Cash In Lieu':
            # Cash In Lieu = proceeds from fractional shares during stock split/corporate action
            # Treated as a partial sale: reduces cost basis proportionally
            cash_received = row['Amount']  # positive dollar amount
            if p['shares'] > 0 and p['cost'] > 0:
                # What fraction of the position was cashed out?
                # cash_received / (cash_received + remaining_value) approximation
                # Simpler: reduce cost basis by the cash received (cost recovery method)
                cost_reduction = min(cash_received, p['cost'])
                realized = cash_received - cost_reduction
                p['cost'] -= cost_reduction
                p['realized'] += realized
                total_realized_pnl += realized

    # Calculate total deposits (MoneyLink Transfers)
    transfers = df[df['Action'].str.contains('MoneyLink Transfer', na=False)]
    total_deposits = transfers['Amount'].sum()

    # Dividends: only actual cash dividends and reinvest dividends, NOT Cash In Lieu
    divs = df[df['Action'].str.contains('Cash Dividend|Reinvest Dividend', na=False, regex=True)]
    total_dividends = divs['Amount'].sum()

    rows = []
    for sym, p in positions.items():
        if p['shares'] > 0.0001:
            avg_cost = p['cost'] / p['shares'] if p['shares'] > 0 else 0
            sleeve = classify_security(sym)  # runtime lookup (yfinance quoteType), cached
            rows.append({'ticker': sym, 'name': str(p['desc'])[:40], 'sleeve': sleeve,
                        'shares': round(p['shares'], 4), 'avgCost': round(avg_cost, 2)})

    # Build rebalance log
    rebal_rows = []
    for _, row in trades.iterrows():
        sym = row['Symbol']
        if not sym or pd.isna(sym):
            continue
        action = 'SELL' if row['Action'] == 'Sell' else ('ADD' if row['Action'] == 'Reinvest Shares' else 'BUY')
        rebal_rows.append({'date': row['Date'], 'action': action, 'ticker': sym,
                          'shares': row['Quantity'], 'price': row['Price'], 'notes': 'Schwab CSV'})

    # Account-level data
    account_data = {
        'realized_pnl': round(total_realized_pnl, 2),
        'total_deposits': round(total_deposits, 2),
        'total_dividends': round(total_dividends, 2),
    }

    return pd.DataFrame(rows), pd.DataFrame(rebal_rows), trades, account_data

# ════════════════════════════════════════════════════
# YFINANCE DATA
# ════════════════════════════════════════════════════
@st.cache_data(ttl=60)
def fetch_quotes(tickers):
    """Fetch current prices for all tickers"""
    if not tickers:
        return {}
    data = {}
    try:
        tickers_str = ' '.join(tickers)
        quotes = yf.Tickers(tickers_str)
        for t in tickers:
            try:
                info = quotes.tickers[t].fast_info
                price = info.get('lastPrice', 0) or info.get('last_price', 0)
                prev = info.get('previousClose', 0) or info.get('previous_close', 0)
                if price and price > 0:
                    data[t] = {
                        'price': price,
                        'prevClose': prev,
                        'change': price - prev if prev else 0,
                        'changePct': ((price - prev) / prev * 100) if prev else 0,
                    }
            except:
                pass
    except:
        pass
    return data

@st.cache_data(ttl=300)
def fetch_history(tickers, start_date, end_date=None):
    """Fetch historical daily closes for multiple tickers"""
    if not tickers:
        return pd.DataFrame()
    try:
        df = yf.download(tickers, start=start_date, end=end_date or now_eastern().strftime('%Y-%m-%d'),
                        auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            return df['Close']
        else:
            return df[['Close']].rename(columns={'Close': tickers[0]}) if len(tickers) == 1 else df
    except:
        return pd.DataFrame()

# ════════════════════════════════════════════════════
# LIVE RISK-FREE RATE (3-month T-bill via ^IRX)
# ════════════════════════════════════════════════════
@st.cache_data(ttl=3600, show_spinner=False)
def _last_close(symbol):
    """Most recent non-NaN close for a symbol, or None. Cached 1h."""
    df = yf.Ticker(symbol).history(period='10d')
    if df is None or df.empty or 'Close' not in df.columns:
        return None
    s = df['Close'].dropna()
    return float(s.iloc[-1]) if len(s) > 0 else None

def fetch_risk_free_rate():
    """
    Live annualized risk-free rate as a decimal, from the 3-month US T-bill (^IRX).
    ^IRX is quoted in percent (4.32 means 4.32%), so annual decimal = close / 100.
    Fallback: ^FVX (5-yr yield) as a clearly-labeled proxy. If both fail, returns
    (None, 'unavailable') — metrics that need rf are then suppressed rather than
    silently computed off a magic number.
    """
    try:
        v = _last_close('^IRX')
    except Exception:
        v = None
    if v is not None and v > 0:
        return v / 100.0, '3M T-bill (^IRX)'
    try:
        v = _last_close('^FVX')
    except Exception:
        v = None
    if v is not None and v > 0:
        return v / 100.0, '5Y Treasury (^FVX) — proxy; ^IRX unavailable'
    return None, 'unavailable'

@st.cache_data(ttl=86400, show_spinner=False)
def _ticker_has_data(ticker):
    """True if yfinance returns any recent price history for the ticker."""
    h = yf.Ticker(ticker).history(period='5d')
    return h is not None and len(h) > 0

def validate_ticker(ticker):
    """True (resolves), False (no data), or None (couldn't check — network failure)."""
    try:
        return bool(_ticker_has_data(ticker))
    except Exception:
        return None

# ════════════════════════════════════════════════════
# TIME-WEIGHTED RETURN ENGINE (single source of truth)
# ════════════════════════════════════════════════════
def _apply_trades(trade_rows, shares):
    """Apply BUY/ADD/SELL/TRIM rows to a {ticker: shares} dict (in place)."""
    for _, tr in trade_rows.iterrows():
        tk = str(tr['ticker']).upper().strip()
        if not tk:
            continue
        try:
            q = float(tr.get('shares', 0) or 0)
        except (TypeError, ValueError):
            q = 0.0
        a = str(tr.get('action', 'BUY')).upper()
        if tk not in shares:
            shares[tk] = 0.0
        if a in ('BUY', 'ADD'):
            shares[tk] += q
        elif a in ('SELL', 'TRIM'):
            shares[tk] -= q
    return shares

def parse_trade_log(rebal_df):
    """Parse + chronologically sort the rebalance log. Tolerates mixed date formats."""
    if rebal_df is None or len(rebal_df) == 0:
        return pd.DataFrame()
    trades = rebal_df.copy()
    trades['parsed_date'] = pd.to_datetime(trades['date'], format='%m/%d/%Y', errors='coerce')
    nat = trades['parsed_date'].isna()
    if nat.any():  # tolerate ISO or other formats that may sit in saved JSON
        trades.loc[nat, 'parsed_date'] = pd.to_datetime(trades.loc[nat, 'date'], errors='coerce')
    return trades.dropna(subset=['parsed_date']).sort_values('parsed_date').reset_index(drop=True)

def build_twr_engine(price_df, rebal_df):
    """
    Rebuild the portfolio's daily time-weighted return series from the trade log,
    plus per-ticker daily contributions and beginning-of-day weights.

    Method (same convention as the original engine, now with correct opening
    positions for windows that start mid-life):
      - Opening shares = replay of all trades dated strictly BEFORE the first
        price date (the original engine started every window from zero shares,
        which broke YTD/1M/7D whenever trades existed inside the window).
      - Trades execute at the close of their trade date (end-of-day flows), so
        cash flows never contaminate that day's return — this is what makes the
        series time-weighted.
      - Daily return on t:  r_t = Σ_i sh_i,(t-1) · P_i,t  /  Σ_i sh_i,(t-1) · P_i,(t-1)  −  1
      - Per-ticker contribution on t:  c_i,t = w_i,t · r_i,t
        where w_i,t = sh_i,(t-1)·P_i,(t-1) / V_(t-1)  (beginning-of-day weight)
        and r_i,t is ticker i's price return; Σ_i c_i,t = r_t exactly.
      - Prices are forward-filled so a single missing print doesn't drop a
        position out of the valuation for a day (robustness fix).

    Returns (port_daily Series, contrib_df [date × ticker], weight_df [date × ticker]).
    """
    empty = (pd.Series(dtype=float), pd.DataFrame(), pd.DataFrame())
    if price_df is None or price_df.empty:
        return empty
    px_now = price_df.ffill()
    px_prev = px_now.shift(1)

    trades = parse_trade_log(rebal_df)
    dates = px_now.index
    first_date = dates[0]

    shares = {}
    if len(trades) > 0:
        opening = trades[trades['parsed_date'].dt.date < first_date.date()]
        shares = _apply_trades(opening, shares)

    rets, contribs, weights, kept = [], [], [], []
    for d in dates:
        v_prev, v_now = 0.0, 0.0
        live = []
        for tk, sh in shares.items():
            if sh > 1e-4 and tk in px_now.columns:
                p1, p0 = px_now.loc[d, tk], px_prev.loc[d, tk]
                if pd.notna(p1) and pd.notna(p0) and p0 > 0:
                    v_prev += sh * p0
                    v_now += sh * p1
                    live.append((tk, sh, p0, p1))
        if v_prev > 0:
            rets.append(v_now / v_prev - 1)
            kept.append(d)
            c_row, w_row = {}, {}
            for tk, sh, p0, p1 in live:
                w_row[tk] = sh * p0 / v_prev
                c_row[tk] = sh * (p1 - p0) / v_prev          # = w_i,t × r_i,t
            contribs.append(c_row)
            weights.append(w_row)
        # apply today's trades at the close (end-of-day flow assumption)
        if len(trades) > 0:
            todays = trades[trades['parsed_date'].dt.date == d.date()]
            if len(todays) > 0:
                shares = _apply_trades(todays, shares)

    if not kept:
        return empty
    idx = pd.DatetimeIndex(kept)
    return (pd.Series(rets, index=idx),
            pd.DataFrame(contribs, index=idx).fillna(0.0),
            pd.DataFrame(weights, index=idx).fillna(0.0))

def build_benchmark_daily(price_df, components):
    """
    Blended benchmark daily return series: r_B,t = Σ_j w_j · r_j,t with weights
    normalized to sum to 1 (a daily-rebalanced blend — the standard composite
    convention). This one series drives the chart, beta, alpha, TE, and IR.
    """
    if price_df is None or price_df.empty or not components:
        return pd.Series(dtype=float)
    rets = price_df.ffill().pct_change()
    total_w = sum(float(c.get('weight', 0) or 0) for c in components)
    if total_w <= 0:
        return pd.Series(dtype=float)
    bm = pd.Series(0.0, index=rets.index)
    got_any = False
    for c in components:
        t, w = c['ticker'], float(c.get('weight', 0) or 0) / total_w
        if t in rets.columns and w > 0:
            bm = bm.add(w * rets[t].fillna(0.0), fill_value=0.0)
            got_any = True
    return bm.iloc[1:] if got_any else pd.Series(dtype=float)

# ── Period statistics helpers ──────────────────────
TRADING_DAYS = 252  # the one accepted constant

def annualized_return(cum_ret, n_days):
    """Geometric annualization: (1 + total)^(252/n) − 1."""
    if n_days <= 0 or cum_ret is None or (1 + cum_ret) <= 0:
        return None
    return (1.0 + cum_ret) ** (TRADING_DAYS / n_days) - 1.0

def max_drawdown(daily):
    """Max drawdown of the cumulative return path: min(cum/cummax − 1)."""
    if daily is None or len(daily) < 2:
        return None
    cum = (1 + daily).cumprod()
    return float((cum / cum.cummax() - 1.0).min())

# ════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════
def color_val(val, fmt_str='{:+.2f}%'):
    if pd.isna(val) or val == 0:
        return '<span style="color:#555">\u2014</span>'
    color = '#00d26a' if val >= 0 else '#ff3b3b'
    return f'<span style="color:{color};font-weight:700">{fmt_str.format(val)}</span>'

def color_dollar(val):
    if pd.isna(val) or val == 0:
        return '<span style="color:#555">\u2014</span>'
    color = '#00d26a' if val >= 0 else '#ff3b3b'
    sign = '+' if val >= 0 else '-'
    return f'<span style="color:{color};font-weight:700">{sign}${abs(val):,.2f}</span>'

def metric_card(label, value, delta=None, delta_color=None):
    delta_html = ''
    if delta is not None:
        dc = delta_color or ('#00d26a' if delta >= 0 else '#ff3b3b')
        delta_html = f'<div class="sub" style="color:{dc}">{delta:+.2f}%</div>'
    return f'<div class="metric-card"><div class="label">{label}</div><div class="value" style="color:{delta_color or "#e8e8e8"}">{value}</div>{delta_html}</div>'

# ════════════════════════════════════════════════════
# MAIN APP
# ════════════════════════════════════════════════════
now_et = now_eastern()
pos_df = st.session_state.positions
has_positions = len(pos_df) > 0 and pos_df['shares'].sum() > 0

# Fetch live prices
all_tickers = []
if has_positions:
    all_tickers = pos_df[pos_df['shares'] > 0]['ticker'].tolist()
bm_tickers = [c['ticker'] for c in st.session_state.benchmark_components]
all_tickers = list(set(all_tickers + bm_tickers))

quotes = fetch_quotes(all_tickers) if all_tickers else {}

# ─── Top Bar ────────────────────────────────────────
bm_label = ' / '.join([f"{c['weight']}% {c['ticker']}" for c in st.session_state.benchmark_components])

cols_top = st.columns([4, 1, 1, 1, 1])
with cols_top[0]:
    st.markdown(f'<div class="topbar-title">PORTFOLIO MONITOR</div>', unsafe_allow_html=True)
    st.caption(f"BM: {bm_label} | {len(pos_df[pos_df['shares']>0]) if has_positions else 0} positions | {now_et.strftime('%b %d, %I:%M %p')}")

# ─── Sidebar: Import & Config ──────────────────────
with st.sidebar:
    st.markdown("### IMPORT SCHWAB CSV")
    uploaded = st.file_uploader("Drop Schwab transaction CSV", type=['csv'], label_visibility='collapsed')
    if uploaded:
        # Only process if this is a new file (avoid infinite rerun loop)
        file_key = uploaded.name + str(uploaded.size)
        if st.session_state.get('_last_import') != file_key:
            pos_new, rebal_new, trades, acct_data = parse_schwab_csv(uploaded)
            if len(pos_new) > 0:
                st.session_state.positions = pos_new
                st.session_state.rebalances = rebal_new
                st.session_state.account_data = acct_data
                st.session_state._last_import = file_key
                save_to_disk()
                st.rerun()
        else:
            st.success(f"Imported {len(st.session_state.positions)} positions, {len(st.session_state.rebalances)} trades")

    st.markdown("---")
    st.markdown("### BLENDED BENCHMARK")
    st.caption("Add/remove rows. Weights auto-normalize to 100%.")
    bm_seed = pd.DataFrame(st.session_state.benchmark_components)
    if bm_seed.empty:
        bm_seed = pd.DataFrame([{'ticker': '', 'weight': 0.0}])
    bm_seed = bm_seed[['ticker', 'weight']]
    bm_edited = st.data_editor(
        bm_seed,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        key='bm_editor',
        column_config={
            'ticker': st.column_config.TextColumn("Ticker", required=True),
            'weight': st.column_config.NumberColumn("Weight", min_value=0.0, step=1.0),
        },
    )
    # Preview of normalized weights (what the calculations actually use)
    _preview = []
    for _, r in bm_edited.iterrows():
        t = str(r.get('ticker') or '').upper().strip()
        try:
            w = float(r.get('weight') or 0)
        except (TypeError, ValueError):
            w = 0.0
        if t and w > 0:
            _preview.append((t, w))
    _wsum = sum(w for _, w in _preview)
    if _wsum > 0:
        st.caption("Normalized: " + " / ".join(f"{t} {w / _wsum * 100:.1f}%" for t, w in _preview))

    if st.button("APPLY BENCHMARK"):
        comps, invalid, unverified = [], [], []
        for t, w in _preview:
            ok = validate_ticker(t)
            if ok is True:
                comps.append({'ticker': t, 'weight': w})
            elif ok is None:
                # yfinance unreachable — accept but flag, don't block configuration
                comps.append({'ticker': t, 'weight': w})
                unverified.append(t)
            else:
                invalid.append(t)
        if invalid:
            st.warning(f"Not found on yfinance (dropped): {', '.join(invalid)}")
        if unverified:
            st.info(f"Could not verify (yfinance unreachable), kept anyway: {', '.join(unverified)}")
        if comps:
            st.session_state.benchmark_components = comps
            save_to_disk()
            st.rerun()
        else:
            st.error("Benchmark needs at least one valid ticker with weight > 0 — keeping previous benchmark.")

    st.markdown("---")
    st.markdown("### INCEPTION DATE")
    inc = st.date_input("Portfolio start", value=datetime.strptime(st.session_state.inception_date, '%Y-%m-%d'))
    st.session_state.inception_date = inc.strftime('%Y-%m-%d')
    save_to_disk()

    st.markdown("---")
    st.markdown("### DATA EXPORT")
    if st.button("EXPORT JSON"):
        export = {
            'positions': pos_df.to_dict('records') if has_positions else [],
            'rebalances': st.session_state.rebalances.to_dict('records') if len(st.session_state.rebalances) > 0 else [],
            'benchmark': st.session_state.benchmark_components,
            'inception': st.session_state.inception_date,
        }
        st.download_button("DOWNLOAD", json.dumps(export, indent=2, default=str), "portfolio.json", "application/json")

if not has_positions:
    st.markdown("## Welcome")
    st.markdown("Open the **sidebar** (arrow top-left) and **import your Schwab CSV** to get started.")
    st.stop()

# ════════════════════════════════════════════════════
# CALCULATIONS
# ════════════════════════════════════════════════════
active = pos_df[pos_df['shares'] > 0].copy()
active['price'] = active['ticker'].map(lambda t: quotes.get(t, {}).get('price', 0))
active['prevClose'] = active['ticker'].map(lambda t: quotes.get(t, {}).get('prevClose', 0))
active['mv'] = active['shares'] * active['price']
active['cost'] = active['shares'] * active['avgCost']
active['pnl'] = active['mv'] - active['cost']
active['totalRet'] = np.where(active['cost'] > 0, (active['pnl'] / active['cost']) * 100, 0)
active['dayChg'] = np.where(active['prevClose'] > 0, ((active['price'] - active['prevClose']) / active['prevClose']) * 100, 0)
active['dayPnl'] = active['shares'] * (active['price'] - active['prevClose'])

total_mv = active['mv'].sum()
total_cost = active['cost'].sum()
unrealized_pnl = total_mv - total_cost
unrealized_ret = (unrealized_pnl / total_cost * 100) if total_cost > 0 else 0
total_daily_pnl = active['dayPnl'].sum()
daily_ret = (total_daily_pnl / (total_mv - total_daily_pnl) * 100) if (total_mv - total_daily_pnl) > 0 else 0

# Realized P&L from closed positions
acct = st.session_state.account_data
realized_pnl = acct.get('realized_pnl', 0)
total_deposits = acct.get('total_deposits', 0)
total_dividends = acct.get('total_dividends', 0)

# Total P&L = Realized + Unrealized (true portfolio performance)
total_pnl = realized_pnl + unrealized_pnl
# Total return based on deposits (money-weighted)
total_ret = (total_pnl / total_deposits * 100) if total_deposits > 0 else 0

active['weight'] = np.where(total_mv > 0, (active['mv'] / total_mv) * 100, 0)
# NOTE: the old single-day `attrib` (weight × dayChg / 100) was removed —
# replaced by the proper period attribution section further down.

# ── CTR: Contribution to Risk ──────────────────────
# CTR_i = w_i × MCTR_i, where MCTR_i = β_i × σ_P
# PCR_i = CTR_i / σ_P = w_i × β_i (percent contribution to risk)
# Uses 30-day daily returns
active['beta'] = 0.0
active['mctr'] = 0.0
active['ctr_risk'] = 0.0
active['pcr'] = 0.0
port_vol = 0.0

try:
    ctr_tickers = active['ticker'].tolist()
    if len(ctr_tickers) >= 2:
        ctr_start = (now_et - timedelta(days=45)).strftime('%Y-%m-%d')
        ctr_hist = fetch_history(ctr_tickers, ctr_start)
        if not ctr_hist.empty and len(ctr_hist) >= 10:
            # Daily returns
            ctr_returns = ctr_hist.pct_change().dropna()
            # Portfolio weights as array (decimal, not percent)
            weights = active.set_index('ticker')['weight'].reindex(ctr_returns.columns).fillna(0).values / 100
            # Portfolio daily return series
            port_returns = (ctr_returns * weights).sum(axis=1)
            # Portfolio volatility (annualized)
            port_vol = port_returns.std() * np.sqrt(252)
            # Per-asset beta to portfolio
            for idx, row in active.iterrows():
                t = row['ticker']
                if t in ctr_returns.columns:
                    cov_ip = ctr_returns[t].cov(port_returns)
                    var_p = port_returns.var()
                    beta_i = cov_ip / var_p if var_p > 0 else 0
                    w_i = row['weight'] / 100
                    mctr_i = beta_i * port_vol
                    ctr_i = w_i * mctr_i
                    pcr_i = (ctr_i / port_vol * 100) if port_vol > 0 else 0
                    active.at[idx, 'beta'] = round(beta_i, 3)
                    active.at[idx, 'mctr'] = round(mctr_i * 100, 3)  # as percent
                    active.at[idx, 'ctr_risk'] = round(ctr_i * 100, 3)  # as percent
                    active.at[idx, 'pcr'] = round(pcr_i, 1)  # percent contribution to risk
except Exception as e:
    pass  # Silently fall back to zeros if history unavailable

# Blended benchmark — day change (weights normalized; supports any number of components)
bm_comps = st.session_state.benchmark_components
total_bm_weight = sum(c['weight'] for c in bm_comps)
blended_chg = sum((c['weight'] / total_bm_weight) * quotes.get(c['ticker'], {}).get('changePct', 0) for c in bm_comps) if total_bm_weight > 0 else 0

# Live risk-free rate (feeds Sharpe, Sortino, Jensen's alpha below)
rf_rate, rf_source = fetch_risk_free_rate()

# Sleeves
etf = active[active['sleeve'] == 'etf']
stock = active[active['sleeve'] == 'stock']
etf_mv = etf['mv'].sum()
stock_mv = stock['mv'].sum()
etf_w = (etf_mv / total_mv * 100) if total_mv > 0 else 0
stock_w = (stock_mv / total_mv * 100) if total_mv > 0 else 0
etf_daily = (etf['dayPnl'].sum() / (etf_mv - etf['dayPnl'].sum()) * 100) if (etf_mv - etf['dayPnl'].sum()) > 0 else 0
stock_daily = (stock['dayPnl'].sum() / (stock_mv - stock['dayPnl'].sum()) * 100) if (stock_mv - stock['dayPnl'].sum()) > 0 else 0
etf_ret = ((etf_mv - etf['cost'].sum()) / etf['cost'].sum() * 100) if etf['cost'].sum() > 0 else 0
stock_ret = ((stock_mv - stock['cost'].sum()) / stock['cost'].sum() * 100) if stock['cost'].sum() > 0 else 0

# ════════════════════════════════════════════════════
# SUMMARY STRIP
# ════════════════════════════════════════════════════
# Row 1: Portfolio-level P&L
r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns(5)
with r1c1:
    st.metric("NET EQUITY", f"${total_mv:,.2f}", f"Cost: ${total_cost:,.2f}")
with r1c2:
    st.metric("DAY P&L", f"{'+'if total_daily_pnl>=0 else ''}{total_daily_pnl:,.2f}", f"{daily_ret:+.2f}% today",
              delta_color="normal" if total_daily_pnl >= 0 else "inverse")
with r1c3:
    st.metric("UNREALIZED P&L", f"{'+'if unrealized_pnl>=0 else ''}{unrealized_pnl:,.2f}", f"{unrealized_ret:+.2f}% vs cost",
              delta_color="normal" if unrealized_pnl >= 0 else "inverse")
with r1c4:
    st.metric("REALIZED P&L", f"{'+'if realized_pnl>=0 else ''}{realized_pnl:,.2f}", f"Divs: ${total_dividends:,.2f}",
              delta_color="normal" if realized_pnl >= 0 else "inverse")
with r1c5:
    st.metric("TOTAL P&L", f"{'+'if total_pnl>=0 else ''}{total_pnl:,.2f}", f"{total_ret:+.2f}% on ${total_deposits:,.0f} deposited",
              delta_color="normal" if total_pnl >= 0 else "inverse")

# Row 2: Benchmark, Alpha, Sleeves, Vol
r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns(5)
with r2c1:
    bm_parts = ' / '.join([f"{c['ticker']} {quotes.get(c['ticker'],{}).get('changePct',0):+.2f}%" for c in bm_comps])
    st.metric("BM DAY CHG", f"{blended_chg:+.2f}%", bm_parts)
with r2c2:
    # Excess return = portfolio daily return - benchmark daily return (NOT Jensen's alpha)
    excess = daily_ret - blended_chg
    st.metric("EXCESS RTN (DAY)", f"{excess:+.2f}%", "Port day - BM day",
              delta_color="normal" if excess >= 0 else "inverse")
with r2c3:
    st.metric("ETF SLEEVE (DAY)", f"{etf_daily:+.2f}%", f"{etf_w:.1f}% of port \u00b7 {len(etf)} pos \u00b7 {etf_ret:+.1f}% total")
with r2c4:
    st.metric("STOCK SLEEVE (DAY)", f"{stock_daily:+.2f}%", f"{stock_w:.1f}% of port \u00b7 {len(stock)} pos \u00b7 {stock_ret:+.1f}% total")
with r2c5:
    st.metric("PORT VOL (30D)", f"{port_vol*100:.1f}%" if port_vol > 0 else "\u2014", "30d daily returns \u00d7 \u221a252" if port_vol > 0 else "Need 10+ days data")

# ════════════════════════════════════════════════════
# PERFORMANCE, RISK & ATTRIBUTION (period-driven)
# ════════════════════════════════════════════════════
# One engine run powers everything below: the chart, the risk/return strip,
# the tracking metrics, and the attribution — all for the selected period.
st.markdown("#### PORTFOLIO VS BLENDED BENCHMARK")

periods = {'INCEP': st.session_state.inception_date, 'YTD': f'{now_et.year}-01-01',
           '1M': (now_et - timedelta(days=30)).strftime('%Y-%m-%d'),
           '7D': (now_et - timedelta(days=7)).strftime('%Y-%m-%d')}

if 'chart_period' not in st.session_state:
    st.session_state.chart_period = 'INCEP'

period_cols = st.columns([1, 1, 1, 1, 6])
for i, label in enumerate(periods):
    with period_cols[i]:
        if st.button(label, key=f'period_{label}', use_container_width=True):
            st.session_state.chart_period = label

sel_period = st.session_state.chart_period
start_date = periods[sel_period]

# ── Fetch with a warm-up buffer ─────────────────────
# We fetch ~2 extra weeks BEFORE the window so (a) the first day of the window
# has a prior close to compute a return against and (b) trades executed before
# the window establish the correct opening positions (the old engine started
# every window from zero shares, which broke YTD/1M/7D attribution).
window_start = pd.Timestamp(start_date)
fetch_start = (window_start - timedelta(days=14)).strftime('%Y-%m-%d')

# Universe must include SOLD tickers from the trade log — they contributed
# returns inside the window even if no longer held (old code omitted them).
log_tickers = []
if len(st.session_state.rebalances) > 0:
    log_tickers = [str(t).upper().strip() for t in st.session_state.rebalances['ticker'].dropna().unique()]
hist_universe = sorted(set(active['ticker'].tolist()) | set(bm_tickers) | set(log_tickers))
hist = fetch_history(hist_universe, fetch_start)

# Defensive: normalize index tz so date comparisons never crash
if not hist.empty and getattr(hist.index, 'tz', None) is not None:
    hist.index = hist.index.tz_localize(None)

# Flag tickers with no usable history (degrade visibly, never crash)
missing_px = [t for t in hist_universe
              if hist.empty or t not in hist.columns or hist[t].dropna().empty]

# ── Run the engine over the buffered range, slice to the window ──
port_w = pd.Series(dtype=float)   # portfolio daily TWR within window
bm_w = pd.Series(dtype=float)     # blended benchmark daily within window
contrib_w = pd.DataFrame()        # per-ticker daily contributions
weight_w = pd.DataFrame()         # per-ticker beginning-of-day weights

if not hist.empty and len(hist) >= 2:
    port_all, contrib_all, weight_all = build_twr_engine(hist, st.session_state.rebalances)
    bm_all = build_benchmark_daily(hist, bm_comps)
    if len(port_all) > 0 and len(bm_all) > 0:
        common = port_all.index.intersection(bm_all.index)
        common = common[common >= window_start]
        port_w = port_all.loc[common]
        bm_w = bm_all.loc[common]
        contrib_w = contrib_all.loc[common] if not contrib_all.empty else pd.DataFrame()
        weight_w = weight_all.loc[common] if not weight_all.empty else pd.DataFrame()

have_series = len(port_w) >= 2

# ── Chart (same visual style as before) ─────────────
if have_series:
    port_line = ((1 + port_w).cumprod() - 1) * 100
    bm_line = ((1 + bm_w).cumprod() - 1) * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=port_line.index, y=port_line.values, name='Portfolio',
                            line=dict(color='#ff8c00', width=2), fill='tozeroy',
                            fillcolor='rgba(255,140,0,0.04)'))
    fig.add_trace(go.Scatter(x=bm_line.index, y=bm_line.values, name=bm_label,
                            line=dict(color='#555', width=1.5, dash='dash')))
    fig.update_layout(
        template='plotly_dark', paper_bgcolor='#111', plot_bgcolor='#111',
        margin=dict(l=50, r=20, t=30, b=40), height=320,
        xaxis=dict(gridcolor='#222', showgrid=True), yaxis=dict(gridcolor='#222', showgrid=True, tickformat='+.1f', ticksuffix='%'),
        legend=dict(orientation='h', yanchor='top', y=1.02, xanchor='right', x=1, font=dict(size=10)),
        hovermode='x unified',
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Since {start_date} ({sel_period}) \u00b7 Port: {port_line.iloc[-1]:+.2f}% vs BM: {bm_line.iloc[-1]:+.2f}% \u00b7 "
               f"BM = daily-rebalanced blend of component returns")
else:
    st.info("Historical data unavailable for this window — metrics below are suppressed rather than guessed.")

if missing_px:
    st.caption(f"\u26a0 No price data from yfinance for: {', '.join(missing_px)} — excluded from history-based calcs.")

# ── Period statistics ───────────────────────────────
MIN_OBS = 3  # minimum daily observations before showing risk stats

def _fmt(v, fmt='{:+.2f}%', scale=100.0):
    """Format a stat or show an em-dash when it can't be computed."""
    if v is None or (isinstance(v, float) and (pd.isna(v) or np.isinf(v))):
        return '\u2014'
    return fmt.format(v * scale)

stats = {}
if have_series:
    n_days = len(port_w)
    stats['n'] = n_days
    stats['cum_p'] = float((1 + port_w).prod() - 1)
    stats['cum_b'] = float((1 + bm_w).prod() - 1)
    stats['active_cum'] = stats['cum_p'] - stats['cum_b']
    stats['ann_p'] = annualized_return(stats['cum_p'], n_days)
    stats['ann_b'] = annualized_return(stats['cum_b'], n_days)
    stats['mdd_p'] = max_drawdown(port_w)
    stats['mdd_b'] = max_drawdown(bm_w)

    if n_days >= MIN_OBS:
        vol_p_d = float(port_w.std())
        vol_b_d = float(bm_w.std())
        stats['vol_p'] = vol_p_d * np.sqrt(TRADING_DAYS) if vol_p_d > 0 else None
        stats['vol_b'] = vol_b_d * np.sqrt(TRADING_DAYS) if vol_b_d > 0 else None

        var_b = float(bm_w.var())
        stats['beta'] = float(port_w.cov(bm_w)) / var_b if var_b > 0 else None

        active_d = port_w - bm_w
        te_d = float(active_d.std())
        stats['te'] = te_d * np.sqrt(TRADING_DAYS) if te_d > 0 else None
        # IR = annualized active return / tracking error (arithmetic, consistent units)
        stats['ir'] = (float(active_d.mean()) * TRADING_DAYS) / stats['te'] if stats.get('te') else None

        if rf_rate is not None:
            rf_daily = rf_rate / TRADING_DAYS
            ex_p = port_w - rf_daily
            ex_b = bm_w - rf_daily
            # Sharpe = mean(daily excess) × √252 / σ(daily)
            stats['sharpe_p'] = float(ex_p.mean()) * np.sqrt(TRADING_DAYS) / vol_p_d if vol_p_d > 0 else None
            stats['sharpe_b'] = float(ex_b.mean()) * np.sqrt(TRADING_DAYS) / vol_b_d if vol_b_d > 0 else None
            # Downside deviation = σ of NEGATIVE daily excess returns only (subset convention)
            neg = ex_p[ex_p < 0]
            dd_d = float(neg.std()) if len(neg) >= 2 else None
            stats['downside_dev'] = dd_d * np.sqrt(TRADING_DAYS) if dd_d else None
            # Sortino = same numerator as Sharpe / annualized downside deviation
            stats['sortino_p'] = float(ex_p.mean()) * np.sqrt(TRADING_DAYS) / dd_d if dd_d else None
            # Jensen's alpha (annualized) = 252 × [ mean(Rp−Rf) − β·mean(Rm−Rf) ]
            if stats.get('beta') is not None:
                stats['alpha_ann'] = TRADING_DAYS * (float(ex_p.mean()) - stats['beta'] * float(ex_b.mean()))

# ── Metrics strip: risk & return, portfolio vs benchmark ──
st.markdown(f"##### RISK & RETURN \u2014 {sel_period}")
m1, m2, m3, m4, m5, m6 = st.columns(6)
with m1:
    st.metric("CUM RETURN", _fmt(stats.get('cum_p')),
              f"BM: {_fmt(stats.get('cum_b'))}", delta_color="off")
with m2:
    st.metric("ANN RETURN", _fmt(stats.get('ann_p')),
              f"BM: {_fmt(stats.get('ann_b'))} \u00b7 (1+r)^(252/n)\u22121", delta_color="off")
with m3:
    st.metric("ANN VOLATILITY", _fmt(stats.get('vol_p'), '{:.2f}%'),
              f"BM: {_fmt(stats.get('vol_b'), '{:.2f}%')} \u00b7 \u03c3(daily)\u00d7\u221a252", delta_color="off")
with m4:
    st.metric("SHARPE", _fmt(stats.get('sharpe_p'), '{:.2f}', 1),
              f"BM: {_fmt(stats.get('sharpe_b'), '{:.2f}', 1)}", delta_color="off")
with m5:
    st.metric("SORTINO", _fmt(stats.get('sortino_p'), '{:.2f}', 1),
              f"Downside dev: {_fmt(stats.get('downside_dev'), '{:.2f}%')}", delta_color="off")
with m6:
    st.metric("MAX DRAWDOWN", _fmt(stats.get('mdd_p'), '{:.2f}%'),
              f"BM: {_fmt(stats.get('mdd_b'), '{:.2f}%')}", delta_color="off")

# ── Metrics strip: tracking vs the blended benchmark ──
st.markdown(f"##### VS BENCHMARK \u2014 {sel_period}")
t1, t2, t3, t4, t5, t6 = st.columns(6)
with t1:
    st.metric("BETA TO BM", _fmt(stats.get('beta'), '{:.2f}', 1), "Cov(Rp,Rm)/Var(Rm)")
with t2:
    av = stats.get('alpha_ann')
    st.metric("JENSEN'S \u03b1 (ANN)", _fmt(av), "Rp\u2212[Rf+\u03b2(Rm\u2212Rf)]",
              delta_color=("normal" if av is not None and av >= 0 else "inverse") if av is not None else "off")
with t3:
    st.metric("TRACKING ERROR", _fmt(stats.get('te'), '{:.2f}%'), "\u03c3(Rp\u2212Rm)\u00d7\u221a252")
with t4:
    st.metric("INFO RATIO", _fmt(stats.get('ir'), '{:.2f}', 1), "Ann active rtn / TE")
with t5:
    ae = stats.get('active_cum')
    st.metric("ACTIVE RTN (CUM)", _fmt(ae), "Port \u2212 BM cumulative",
              delta_color=("normal" if ae is not None and ae >= 0 else "inverse") if ae is not None else "off")
with t6:
    if rf_rate is not None:
        st.metric("RISK-FREE (LIVE)", f"{rf_rate*100:.2f}%", rf_source)
    else:
        st.metric("RISK-FREE (LIVE)", "\u2014", "Unavailable \u2014 Sharpe/Sortino/\u03b1 suppressed")

if rf_rate is None and have_series:
    st.caption("\u26a0 Could not fetch a live risk-free rate (^IRX and ^FVX both failed). "
               "Sharpe, Sortino and Jensen's \u03b1 are hidden instead of using a stale constant.")

# ════════════════════════════════════════════════════
# PERIOD ATTRIBUTION — contribution to return by holding
# ════════════════════════════════════════════════════
st.markdown(f"#### ATTRIBUTION \u2014 {sel_period}")

if have_series and not contrib_w.empty:
    # Growth-factor linking: each day's contribution w_i,t·r_i,t is scaled by the
    # portfolio's cumulative growth through the PRIOR day, G_(t-1) = Π_(s<t)(1+r_p,s).
    # This makes contributions sum EXACTLY to the geometric period TWR:
    #   Σ_i Σ_t w_i,t·r_i,t·G_(t-1) = Σ_t r_p,t·G_(t-1) = Π(1+r_p,t) − 1   (telescoping)
    growth_prev = (1 + port_w).cumprod().shift(1).fillna(1.0)
    linked_contrib = contrib_w.multiply(growth_prev, axis=0).sum()

    # Per-holding period return while held: chain-linked over days with weight > 0
    daily_ret_by_ticker = contrib_w / weight_w.replace(0, np.nan)
    ret_while_held = (1 + daily_ret_by_ticker.fillna(0)).prod() - 1
    avg_weight = weight_w.mean()  # average of beginning-of-day weights over the window

    attr_df = pd.DataFrame({
        'Ticker': linked_contrib.index,
        'Avg Wt %': avg_weight.reindex(linked_contrib.index).values * 100,
        'Period Rtn %': ret_while_held.reindex(linked_contrib.index).values * 100,
        'Contribution %': linked_contrib.values * 100,
    })
    attr_df = attr_df[attr_df['Avg Wt %'].abs() > 1e-9].sort_values('Contribution %', ascending=False)

    ac1, ac2 = st.columns([1, 1])
    with ac1:
        st.dataframe(
            attr_df.style.format({
                'Avg Wt %': '{:.1f}%', 'Period Rtn %': '{:+.2f}%', 'Contribution %': '{:+.2f}%',
            }).map(lambda v: 'color: #00d26a' if isinstance(v, (int, float)) and v > 0 else ('color: #ff3b3b' if isinstance(v, (int, float)) and v < 0 else ''),
                       subset=['Period Rtn %', 'Contribution %']),
            use_container_width=True, height=min(400, 40 + len(attr_df) * 35)
        )
        st.caption(f"\u03a3 contributions = {attr_df['Contribution %'].sum():+.2f}% "
                   f"(= period TWR {stats['cum_p']*100:+.2f}%) \u00b7 "
                   "Contribution_i = \u03a3\u209c w\u1d62,\u209c\u00b7r\u1d62,\u209c\u00b7G\u209c\u208b\u2081 \u00b7 "
                   "'Period Rtn' is the holding's chained return on days it was held")
    with ac2:
        attr_sorted = attr_df.sort_values('Contribution %')
        fig_attr = go.Figure()
        fig_attr.add_trace(go.Bar(
            y=attr_sorted['Ticker'], x=attr_sorted['Contribution %'], orientation='h',
            marker_color=[('#00d26a' if v >= 0 else '#ff3b3b') for v in attr_sorted['Contribution %']],
            text=[f"{v:+.2f}%" for v in attr_sorted['Contribution %']],
            textposition='outside', textfont=dict(size=10, color='#e8e8e8'),
        ))
        fig_attr.add_vline(x=0, line_color='#555', line_width=1)
        fig_attr.update_layout(
            template='plotly_dark', paper_bgcolor='#111', plot_bgcolor='#111',
            margin=dict(l=60, r=50, t=5, b=5), height=max(220, len(attr_sorted) * 26),
            xaxis=dict(title='Contribution to return %', gridcolor='#222', zeroline=False),
            yaxis=dict(gridcolor='#222'),
        )
        st.plotly_chart(fig_attr, use_container_width=True)

    # ── Sleeve attribution vs benchmark (Brinson-style, honest version) ──
    # A full Brinson (Allocation/Selection/Interaction) needs benchmark sleeve
    # weights. Our benchmark is a single ETF composite with no ETF-vs-Stock
    # structure, so allocation/interaction effects are UNDEFINED against it —
    # decomposing them would be fabrication. Instead, per the spec fallback, we
    # show each sleeve's contribution to ACTIVE return using the sleeve's own
    # return vs the TOTAL benchmark (a selection-style effect):
    #   Active_s = Σ_t W_s,t · (r_s,t − r_B,t) · G_(t-1)
    # Sleeve effects sum to total active return up to a small geometric-linking
    # residual (shown), since Σ_s W_s,t = 1 and Σ_s W_s,t·r_s,t = r_p,t.
    with st.expander("SLEEVE ATTRIBUTION VS BENCHMARK", expanded=False):
        sleeve_lookup = dict(zip(pos_df['ticker'], pos_df['sleeve']))
        rows_sl = []
        total_active_effect = 0.0
        for sleeve_name in ('etf', 'stock'):
            cols_s = [t for t in contrib_w.columns
                      if (sleeve_lookup.get(t) or classify_security(t)) == sleeve_name]
            if not cols_s:
                continue
            W_s = weight_w[cols_s].sum(axis=1)
            c_s = contrib_w[cols_s].sum(axis=1)              # = W_s,t · r_s,t
            r_s = c_s / W_s.replace(0, np.nan)               # sleeve daily return
            sleeve_period_ret = float((1 + r_s.fillna(0)).prod() - 1)
            effect = float(((c_s - W_s * bm_w) * growth_prev).sum())
            total_active_effect += effect
            rows_sl.append({
                'Sleeve': sleeve_name.upper(),
                'Avg Wt %': float(W_s.mean()) * 100,
                'Sleeve Rtn %': sleeve_period_ret * 100,
                'BM Rtn %': stats['cum_b'] * 100,
                'Active Effect %': effect * 100,
            })
        if rows_sl:
            sl_df = pd.DataFrame(rows_sl)
            st.dataframe(
                sl_df.style.format({
                    'Avg Wt %': '{:.1f}%', 'Sleeve Rtn %': '{:+.2f}%',
                    'BM Rtn %': '{:+.2f}%', 'Active Effect %': '{:+.2f}%',
                }).map(lambda v: 'color: #00d26a' if isinstance(v, (int, float)) and v > 0 else ('color: #ff3b3b' if isinstance(v, (int, float)) and v < 0 else ''),
                           subset=['Sleeve Rtn %', 'Active Effect %']),
                use_container_width=True, height=40 + len(sl_df) * 38
            )
            resid = stats['active_cum'] * 100 - sl_df['Active Effect %'].sum()
            st.caption(
                f"\u03a3 sleeve effects = {sl_df['Active Effect %'].sum():+.2f}% vs total active {stats['active_cum']*100:+.2f}% "
                f"(geometric-linking residual {resid:+.2f}%). "
                "Assumptions: benchmark is a single composite, so sleeve-level Allocation/Interaction "
                "effects are undefined and NOT shown; 'Active Effect' = W\u209b\u00b7(r\u209b\u2212r_BM) per day, growth-linked."
            )
        else:
            st.info("No sleeve data in this window.")
else:
    st.info("Attribution needs at least 2 days of history in the selected window.")

# ════════════════════════════════════════════════════
# ALLOCATION PIE CHARTS
# ════════════════════════════════════════════════════
pie_col1, pie_col2 = st.columns(2)

with pie_col1:
    st.markdown("#### POSITION ALLOCATION")
    if total_mv > 0:
        alloc = active[['ticker', 'weight']].sort_values('weight', ascending=False)
        fig_pie = go.Figure(data=[go.Pie(
            labels=alloc['ticker'], values=alloc['weight'],
            hole=0.5, textinfo='label+percent', textposition='auto',
            textfont=dict(size=10, color='white', family='Helvetica'),
            marker=dict(colors=px.colors.qualitative.Set2),
        )])
        fig_pie.update_layout(template='plotly_dark', paper_bgcolor='#111', plot_bgcolor='#111',
                             margin=dict(l=10, r=10, t=10, b=10), height=280, showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)

with pie_col2:
    st.markdown("#### SLEEVE ALLOCATION")
    if total_mv > 0:
        sleeve_data = pd.DataFrame([
            {'Sleeve': 'ETF', 'Weight': etf_w},
            {'Sleeve': 'Stock', 'Weight': stock_w},
        ])
        fig_sleeve = go.Figure(data=[go.Pie(
            labels=sleeve_data['Sleeve'], values=sleeve_data['Weight'],
            hole=0.5, textinfo='label+percent', textposition='auto',
            textfont=dict(size=12, color='white', family='Helvetica'),
            marker=dict(colors=['#00bfff', '#ffd700']),
        )])
        fig_sleeve.update_layout(template='plotly_dark', paper_bgcolor='#111', plot_bgcolor='#111',
                                margin=dict(l=10, r=10, t=10, b=10), height=280, showlegend=False)
        st.plotly_chart(fig_sleeve, use_container_width=True)

# ════════════════════════════════════════════════════
# HOLDINGS TABLE
# ════════════════════════════════════════════════════
# Cash calculation: Deposits + Realized P&L + Dividends - Current Cost Basis
cash_balance = total_deposits + realized_pnl + total_dividends - total_cost
net_liq = total_mv + cash_balance

st.markdown("#### HOLDINGS")
cash_col1, cash_col2, cash_col3 = st.columns(3)
with cash_col1:
    st.metric("NET LIQUIDATION", f"${net_liq:,.2f}")
with cash_col2:
    st.metric("CASH AVAILABLE", f"${cash_balance:,.2f}", f"{(cash_balance/net_liq*100) if net_liq>0 else 0:.1f}% of net liq")
with cash_col3:
    st.metric("INVESTED", f"${total_mv:,.2f}", f"{(total_mv/net_liq*100) if net_liq>0 else 0:.1f}% of net liq")

tab_all, tab_etf, tab_stock = st.tabs(["ALL", "ETF", "STOCK"])

def show_holdings(df, relative_mv=None):
    """Show holdings table. relative_mv = denominator for weight column (total portfolio or sleeve MV)."""
    if len(df) == 0:
        st.info("No positions")
        return
    display = df.copy()
    denom = relative_mv if relative_mv and relative_mv > 0 else total_mv
    display['rel_weight'] = np.where(denom > 0, (display['mv'] / denom) * 100, 0)
    display = display[['ticker', 'sleeve', 'shares', 'avgCost', 'price', 'mv', 'rel_weight', 'dayChg', 'dayPnl', 'totalRet', 'pnl', 'beta', 'ctr_risk', 'pcr']].copy()
    display.columns = ['Ticker', 'Sleeve', 'Shares', 'Avg Cost', 'Price', 'Mkt Value', 'Weight %', 'Day Chg %', 'Day P&L', 'Total Rtn %', 'Total P&L', 'Beta', 'CTR %', 'PCR %']
    display = display.sort_values('Mkt Value', ascending=False)

    st.dataframe(
        display.style.format({
            'Shares': '{:.4f}', 'Avg Cost': '${:.2f}', 'Price': '${:.2f}',
            'Mkt Value': '${:,.2f}', 'Weight %': '{:.1f}%', 'Day Chg %': '{:+.2f}%',
            'Day P&L': '${:+,.2f}', 'Total Rtn %': '{:+.2f}%', 'Total P&L': '${:+,.2f}',
            'Beta': '{:.2f}', 'CTR %': '{:+.3f}%', 'PCR %': '{:.1f}%',
        }).map(lambda v: 'color: #00d26a' if isinstance(v, (int, float)) and v > 0 else ('color: #ff3b3b' if isinstance(v, (int, float)) and v < 0 else ''),
                   subset=['Day Chg %', 'Day P&L', 'Total Rtn %', 'Total P&L']),
        use_container_width=True, height=min(400, 40 + len(display) * 35)
    )

with tab_all:
    show_holdings(active, total_mv)  # weight relative to total portfolio
with tab_etf:
    st.caption(f"Weights relative to ETF sleeve (${etf_mv:,.2f})")
    show_holdings(etf, etf_mv)  # weight relative to ETF sleeve only
with tab_stock:
    st.caption(f"Weights relative to Stock sleeve (${stock_mv:,.2f})")
    show_holdings(stock, stock_mv)  # weight relative to Stock sleeve only

# Sleeve toggle
with st.expander("FIX SLEEVE CLASSIFICATION", expanded=False):
    st.caption("Toggle any ticker between ETF and Stock sleeve.")
    pos = st.session_state.positions
    if len(pos) > 0:
        toggle_cols = st.columns(min(6, len(pos)))
        changed = False
        for i, (idx, row) in enumerate(pos.iterrows()):
            with toggle_cols[i % min(6, len(pos))]:
                current = row.get('sleeve', 'etf')
                label = f"{row['ticker']} ({current.upper()})"
                if st.button(label, key=f'sleeve_toggle_{row["ticker"]}'):
                    new_sleeve = 'stock' if current == 'etf' else 'etf'
                    st.session_state.positions.at[idx, 'sleeve'] = new_sleeve
                    changed = True
        if changed:
            save_to_disk()
            st.rerun()

# ════════════════════════════════════════════════════
# SLEEVE BREAKDOWN
# ════════════════════════════════════════════════════
sl1, sl2 = st.columns(2)

with sl1:
    st.markdown("#### ETF SLEEVE")
    e1, e2, e3 = st.columns(3)
    with e1: st.metric("MKT VALUE", f"${etf_mv:,.2f}")
    with e2: st.metric("WEIGHT", f"{etf_w:.1f}%")
    with e3: st.metric("TOTAL RTN", f"{etf_ret:+.2f}%", delta_color="normal" if etf_ret >= 0 else "inverse")

with sl2:
    st.markdown("#### STOCK SLEEVE")
    s1, s2, s3 = st.columns(3)
    with s1: st.metric("MKT VALUE", f"${stock_mv:,.2f}")
    with s2: st.metric("WEIGHT", f"{stock_w:.1f}%")
    with s3: st.metric("TOTAL RTN", f"{stock_ret:+.2f}%", delta_color="normal" if stock_ret >= 0 else "inverse")

# ════════════════════════════════════════════════════
# LIVE PRICES PANEL
# ════════════════════════════════════════════════════
with st.expander("LIVE PRICES", expanded=False):
    price_rows = []
    for c in bm_comps:
        q = quotes.get(c['ticker'], {})
        price_rows.append({'Ticker': c['ticker'], 'Type': f"BM {c['weight']}%",
                          'Price': q.get('price', 0), 'Chg %': q.get('changePct', 0)})
    # Blended
    price_rows.append({'Ticker': 'BLEND', 'Type': bm_label, 'Price': 0, 'Chg %': blended_chg})
    for _, row in active.iterrows():
        q = quotes.get(row['ticker'], {})
        price_rows.append({'Ticker': row['ticker'], 'Type': row['sleeve'].upper(),
                          'Price': q.get('price', 0), 'Chg %': q.get('changePct', 0)})
    pdf = pd.DataFrame(price_rows)
    st.dataframe(pdf.style.format({'Price': '${:.2f}', 'Chg %': '{:+.2f}%'}).map(
        lambda v: 'color: #00d26a' if isinstance(v, (int, float)) and v > 0 else ('color: #ff3b3b' if isinstance(v, (int, float)) and v < 0 else ''),
        subset=['Chg %']), use_container_width=True)

# ════════════════════════════════════════════════════
# TARGET ALLOCATION & DRIFT BY SLEEVE
# ════════════════════════════════════════════════════
st.markdown("#### TARGET ALLOCATION & DRIFT")

# Helper: build drift analysis for a sleeve
def render_sleeve_drift(sleeve_name, sleeve_df, sleeve_targets, sleeve_mv, color_accent):
    """Render target editor, pie charts, drift table, and bar chart for one sleeve"""
    tickers_in_sleeve = sleeve_df['ticker'].tolist()
    st_targets = sleeve_targets.copy()

    # Auto-populate missing tickers with 0
    for t in tickers_in_sleeve:
        if t not in st_targets:
            st_targets[t] = 0.0

    has_targets = any(v > 0 for v in st_targets.values())

    # Editor — paste from Excel or type manually
    with st.expander(f"EDIT {sleeve_name.upper()} TARGETS", expanded=False):
        st.caption("Paste from Excel: two columns (Ticker, Weight %). Tab, comma, or space separated. One row per ticker.")

        # Show current targets
        current_str = '\n'.join([f"{t}\t{w}" for t, w in sorted(st_targets.items()) if w > 0])
        if not current_str:
            current_str = '\n'.join([f"{t}\t0" for t in sorted(tickers_in_sleeve)])

        paste_text = st.text_area(
            "Paste targets (Ticker  Weight)",
            value=current_str,
            height=min(200, 30 + len(st_targets) * 22),
            key=f'tw_paste_{sleeve_name}',
            placeholder="RSPT\t15\nPAVE\t12\nSPYM\t10"
        )

        # Parse
        parsed_targets = {}
        if paste_text:
            for line in paste_text.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                # Split by tab, comma, or multiple spaces (re imported at top of file)
                parts = re.split(r'[\t,]+|\s{2,}', line)
                if len(parts) < 2:
                    parts = line.split()
                if len(parts) >= 2:
                    ticker = parts[0].strip().upper()
                    try:
                        weight = float(parts[1].strip().replace('%', ''))
                        parsed_targets[ticker] = weight
                    except:
                        pass

        tw_sum = sum(parsed_targets.values())
        cash_alloc = max(0, 100 - tw_sum)
        st.caption(f"Sum: {tw_sum:.1f}% | Unallocated: {cash_alloc:.1f}%")

        if st.button(f"SAVE {sleeve_name.upper()} TARGETS", key=f'save_tw_{sleeve_name}'):
            tw_all = st.session_state.target_weights.copy()
            tw_all[sleeve_name] = parsed_targets
            st.session_state.target_weights = tw_all
            save_to_disk()
            st.success(f"{sleeve_name} targets saved")
            st.rerun()

    if not has_targets or sleeve_mv <= 0:
        st.info(f"Set {sleeve_name} target weights above to see drift analysis.")
        return None  # No drift summary available for this sleeve

    # Build drift data (weights within the sleeve, not total portfolio)
    drift_rows = []
    for _, row in sleeve_df.iterrows():
        t = row['ticker']
        actual_w = (row['mv'] / sleeve_mv * 100) if sleeve_mv > 0 else 0
        target = st_targets.get(t, 0)
        drift = actual_w - target
        status = 'OW' if drift > 0.5 else ('UW' if drift < -0.5 else 'ON TARGET')
        target_mv_val = sleeve_mv * target / 100
        rebal = target_mv_val - row['mv']
        drift_rows.append({
            'Ticker': t, 'Actual %': actual_w, 'Target %': target, 'Drift %': drift,
            'Status': status, 'Actual $': row['mv'], 'Target $': target_mv_val, 'Rebal $': rebal,
        })

    # Tickers in targets but not held
    for t, tw_val in st_targets.items():
        if tw_val > 0 and t not in sleeve_df['ticker'].values:
            target_mv_val = sleeve_mv * tw_val / 100
            drift_rows.append({
                'Ticker': t, 'Actual %': 0, 'Target %': tw_val, 'Drift %': -tw_val,
                'Status': 'UW', 'Actual $': 0, 'Target $': target_mv_val, 'Rebal $': target_mv_val,
            })

    drift_df = pd.DataFrame(drift_rows).sort_values('Drift %', key=abs, ascending=False)

    # Pie charts side by side
    pc1, pc2 = st.columns(2)
    with pc1:
        st.markdown(f"###### ACTUAL ({sleeve_name.upper()})")
        if len(sleeve_df) > 0:
            fig_a = go.Figure(data=[go.Pie(
                labels=sleeve_df['ticker'], values=sleeve_df['mv'],
                hole=0.5, textinfo='label+percent', textposition='auto',
                textfont=dict(size=10, color='white', family='Helvetica'),
                marker=dict(colors=px.colors.qualitative.Set2),
            )])
            fig_a.update_layout(template='plotly_dark', paper_bgcolor='#111', plot_bgcolor='#111',
                               margin=dict(l=5, r=5, t=5, b=5), height=220, showlegend=False)
            st.plotly_chart(fig_a, use_container_width=True)

    with pc2:
        st.markdown(f"###### TARGET ({sleeve_name.upper()})")
        tgt_data = pd.DataFrame([{'t': t, 'w': w} for t, w in st_targets.items() if w > 0])
        if len(tgt_data) > 0:
            if cash_alloc > 0.5:
                tgt_data = pd.concat([tgt_data, pd.DataFrame([{'t': 'UNALLOC', 'w': cash_alloc}])], ignore_index=True)
            fig_t = go.Figure(data=[go.Pie(
                labels=tgt_data['t'], values=tgt_data['w'],
                hole=0.5, textinfo='label+percent', textposition='auto',
                textfont=dict(size=10, color='white', family='Helvetica'),
                marker=dict(colors=px.colors.qualitative.Set2),
            )])
            fig_t.update_layout(template='plotly_dark', paper_bgcolor='#111', plot_bgcolor='#111',
                               margin=dict(l=5, r=5, t=5, b=5), height=220, showlegend=False)
            st.plotly_chart(fig_t, use_container_width=True)

    # Summary metrics
    total_abs_drift = drift_df['Drift %'].abs().sum()
    total_rebal_dollars = drift_df['Rebal $'].abs().sum()
    max_ow_row = drift_df.loc[drift_df['Drift %'].idxmax()] if len(drift_df) > 0 else None
    max_uw_row = drift_df.loc[drift_df['Drift %'].idxmin()] if len(drift_df) > 0 else None

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        st.metric("ABS DRIFT", f"{total_abs_drift:.1f}%")
    with mc2:
        st.metric("REBAL $", f"${total_rebal_dollars:,.0f}")
    with mc3:
        if max_ow_row is not None and max_ow_row['Drift %'] > 0:
            st.metric("TOP OW", f"{max_ow_row['Ticker']} +{max_ow_row['Drift %']:.1f}%")
        else:
            st.metric("TOP OW", "\u2014")
    with mc4:
        if max_uw_row is not None and max_uw_row['Drift %'] < 0:
            st.metric("TOP UW", f"{max_uw_row['Ticker']} {max_uw_row['Drift %']:.1f}%")
        else:
            st.metric("TOP UW", "\u2014")

    # Drift table
    st.dataframe(
        drift_df.style.format({
            'Actual %': '{:.1f}%', 'Target %': '{:.1f}%', 'Drift %': '{:+.1f}%',
            'Actual $': '${:,.2f}', 'Target $': '${:,.2f}', 'Rebal $': '${:+,.2f}',
        }).map(
            lambda v: 'color: #00d26a; font-weight: 700' if v == 'OW' else ('color: #ff3b3b; font-weight: 700' if v == 'UW' else 'color: #555'),
            subset=['Status']
        ).map(
            lambda v: 'color: #00d26a' if isinstance(v, (int, float)) and v > 0.5 else ('color: #ff3b3b' if isinstance(v, (int, float)) and v < -0.5 else ''),
            subset=['Drift %']
        ).map(
            lambda v: 'color: #00d26a' if isinstance(v, (int, float)) and v > 0 else ('color: #ff3b3b' if isinstance(v, (int, float)) and v < 0 else ''),
            subset=['Rebal $']
        ),
        use_container_width=True, height=min(300, 40 + len(drift_df) * 35)
    )

    # Horizontal bar chart
    ds = drift_df.sort_values('Drift %')
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        y=ds['Ticker'], x=ds['Drift %'], orientation='h',
        marker_color=[('#00d26a' if d > 0 else '#ff3b3b') for d in ds['Drift %']],
        text=[f"{d:+.1f}%" for d in ds['Drift %']], textposition='outside',
        textfont=dict(size=10, color='#e8e8e8'),
    ))
    fig_bar.add_vline(x=0, line_color='#555', line_width=1)
    fig_bar.update_layout(
        template='plotly_dark', paper_bgcolor='#111', plot_bgcolor='#111',
        margin=dict(l=60, r=40, t=5, b=5), height=max(150, len(ds) * 28),
        xaxis=dict(title='Drift %', gridcolor='#222', zeroline=False),
        yaxis=dict(gridcolor='#222'),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # Return sleeve-level summary so the portfolio-level rollup can aggregate
    return {'abs_drift': total_abs_drift, 'rebal_dollars': total_rebal_dollars, 'sleeve_mv': sleeve_mv}

# ─── Render both sleeves ──────────────────────────
tw_all = st.session_state.target_weights

sleeve_tab_etf, sleeve_tab_stock = st.tabs(["ETF SLEEVE", "STOCK SLEEVE"])

with sleeve_tab_etf:
    etf_targets = tw_all.get('etf', {})
    etf_drift_summary = render_sleeve_drift('etf', etf, etf_targets, etf_mv, '#00bfff')

with sleeve_tab_stock:
    stock_targets = tw_all.get('stock', {})
    stock_drift_summary = render_sleeve_drift('stock', stock, stock_targets, stock_mv, '#ffd700')

# ─── Portfolio-level rebalance summary ────────────
# Aggregates across both sleeves. Only shown if at least one sleeve has targets set.
_sleeve_summaries = [s for s in (etf_drift_summary, stock_drift_summary) if s is not None]
if _sleeve_summaries and total_mv > 0:
    st.markdown("##### PORTFOLIO REBALANCE SUMMARY")

    # Total trade dollars = sum of |Rebal $| across all holdings in all sleeves.
    # Every rebalance trade is counted at its absolute value (buys + sells).
    total_trade_dollars = sum(s['rebal_dollars'] for s in _sleeve_summaries)

    # One-way turnover = total trade $ / 2 (each $1 sold funds $1 bought,
    # so half the gross trade value is the standard one-way turnover figure).
    one_way_turnover = total_trade_dollars / 2.0

    # Turnover % = one-way turnover / total portfolio market value × 100
    turnover_pct = (one_way_turnover / total_mv * 100) if total_mv > 0 else 0.0

    # Portfolio-weighted absolute drift = Σ_sleeves (sleeve_mv / total_mv) × sleeve_abs_drift.
    # Each sleeve's intra-sleeve drift is scaled by the sleeve's share of the portfolio,
    # so a 10% drift inside a sleeve that is 20% of the book counts as 2% at portfolio level.
    port_wtd_abs_drift = sum((s['sleeve_mv'] / total_mv) * s['abs_drift'] for s in _sleeve_summaries)

    rs1, rs2, rs3, rs4 = st.columns(4)
    with rs1:
        st.metric("TOTAL TRADE $", f"${total_trade_dollars:,.0f}")
        st.caption("Σ |Rebal $| across both sleeves (gross buys + sells)")
    with rs2:
        st.metric("ONE-WAY TURNOVER $", f"${one_way_turnover:,.0f}")
        st.caption("Total trade $ ÷ 2")
    with rs3:
        st.metric("TURNOVER %", f"{turnover_pct:.1f}%")
        st.caption("One-way turnover ÷ portfolio MV × 100")
    with rs4:
        st.metric("PORT-WTD ABS DRIFT", f"{port_wtd_abs_drift:.1f}%")
        st.caption("Σ (sleeve MV ÷ total MV) × sleeve abs drift")
    if len(_sleeve_summaries) < 2:
        st.caption("Note: only one sleeve has targets set — summary reflects that sleeve only.")


# ════════════════════════════════════════════════════
# REBALANCE LOG
# ════════════════════════════════════════════════════
st.markdown("#### REBALANCE LOG")

with st.expander("ADD ENTRY", expanded=False):
    rc = st.columns([2, 1, 1, 1, 1, 3])
    with rc[0]: rb_date = st.date_input("Date", value=now_et, key='rb_date')
    with rc[1]: rb_action = st.selectbox("Action", ['BUY', 'SELL', 'TRIM', 'ADD', 'ROTATE'], key='rb_action')
    with rc[2]: rb_ticker = st.text_input("Ticker", key='rb_ticker')
    with rc[3]: rb_shares = st.number_input("Shares", value=0.0, step=0.01, key='rb_shares')
    with rc[4]: rb_price = st.number_input("Price", value=0.0, step=0.01, key='rb_price')
    with rc[5]: rb_notes = st.text_input("Notes", key='rb_notes')
    if st.button("LOG REBALANCE"):
        ticker_up = rb_ticker.upper().strip()
        if not ticker_up or rb_shares <= 0 or rb_price <= 0:
            st.error("Enter valid ticker, shares, and price")
        else:
            # 1. Log to rebalance journal
            new_row = pd.DataFrame([{
                'date': rb_date.strftime('%m/%d/%Y'), 'action': rb_action,
                'ticker': ticker_up, 'shares': rb_shares, 'price': rb_price, 'notes': rb_notes
            }])
            st.session_state.rebalances = pd.concat([new_row, st.session_state.rebalances], ignore_index=True)

            # 2. Update positions
            pos = st.session_state.positions
            existing = pos[pos['ticker'] == ticker_up]
            sleeve = classify_security(ticker_up)  # runtime lookup (yfinance quoteType), cached

            if rb_action in ['BUY', 'ADD']:
                if len(existing) > 0:
                    idx = existing.index[0]
                    old_shares = pos.at[idx, 'shares']
                    old_cost = old_shares * pos.at[idx, 'avgCost']
                    new_shares = old_shares + rb_shares
                    new_cost = old_cost + (rb_shares * rb_price)
                    pos.at[idx, 'shares'] = round(new_shares, 4)
                    pos.at[idx, 'avgCost'] = round(new_cost / new_shares, 2) if new_shares > 0 else 0
                else:
                    new_pos = pd.DataFrame([{'ticker': ticker_up, 'name': ticker_up, 'sleeve': sleeve,
                                            'shares': round(rb_shares, 4), 'avgCost': round(rb_price, 2)}])
                    st.session_state.positions = pd.concat([pos, new_pos], ignore_index=True)

            elif rb_action in ['SELL', 'TRIM']:
                if len(existing) > 0:
                    idx = existing.index[0]
                    old_shares = pos.at[idx, 'shares']
                    old_avg = pos.at[idx, 'avgCost']
                    sell_qty = min(rb_shares, old_shares)  # Can't sell more than you own

                    # Track realized P&L
                    realized_from_sell = (rb_price - old_avg) * sell_qty
                    acct = st.session_state.account_data
                    acct['realized_pnl'] = acct.get('realized_pnl', 0) + round(realized_from_sell, 2)
                    st.session_state.account_data = acct

                    # Reduce shares (avg cost stays the same)
                    new_shares = old_shares - sell_qty
                    if new_shares < 0.0001:
                        st.session_state.positions = pos.drop(idx).reset_index(drop=True)
                    else:
                        pos.at[idx, 'shares'] = round(new_shares, 4)
                else:
                    st.warning(f"No position in {ticker_up} to sell")

            elif rb_action == 'ROTATE':
                # ROTATE = sell old + buy new. Notes should specify "FROM:XTN TO:PPI" etc.
                # Just log it — user handles the buy/sell separately
                pass

            save_to_disk()
            st.rerun()

if len(st.session_state.rebalances) > 0:
    rebal = st.session_state.rebalances.copy()
    rebal['notional'] = rebal['shares'] * rebal['price']
    st.dataframe(
        rebal[['date', 'action', 'ticker', 'shares', 'price', 'notional', 'notes']].style.format({
            'shares': '{:.4f}', 'price': '${:.2f}', 'notional': '${:,.2f}'
        }).map(lambda v: 'color: #00d26a' if v in ['BUY', 'ADD'] else ('color: #ff3b3b' if v in ['SELL', 'TRIM'] else ''),
                   subset=['action']),
        use_container_width=True, height=min(300, 40 + len(rebal) * 35)
    )
else:
    st.info("No rebalances logged")

# ─── Auto-refresh ───────────────────────────────────
st.markdown("---")
st.caption(f"Last updated: {now_et.strftime('%I:%M:%S %p ET')} \u00b7 Refresh page to update prices")
