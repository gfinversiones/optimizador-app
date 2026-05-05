import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from scipy.optimize import minimize
import datetime
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Portfolio Terminal",
    page_icon="📊",
    layout="wide"
)

# ─────────────────────────────────────────────────────────────
# BLOOMBERG STYLE CSS (PRO LEVEL)
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
body {
    background-color: #0b0f14;
    color: #e6e6e6;
}

/* TITLES */
.title {
    font-size: 26px;
    font-weight: 600;
    letter-spacing: 0.5px;
}

.section {
    font-size: 12px;
    color: #8aa0b6;
    letter-spacing: 1.5px;
    margin-top: 25px;
    margin-bottom: 10px;
}

/* CARDS */
.metric-card {
    background: #11161c;
    border: 1px solid #1f2a36;
    border-radius: 6px;
    padding: 10px;
    text-align: center;
}

.metric-label {
    font-size: 11px;
    color: #7f8c99;
    letter-spacing: 1px;
}

.metric-value {
    font-size: 20px;
    font-weight: 600;
    color: #ffffff;
}

/* PORTFOLIO BLOCK */
.port-box {
    background: #0f141a;
    border: 1px solid #1c2630;
    padding: 12px;
    border-radius: 6px;
}

.port-title {
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 8px;
}

/* SIDEBAR */
section[data-testid="stSidebar"] {
    background-color: #0f141a;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# FUNCTIONS
# ─────────────────────────────────────────────────────────────
@st.cache_data
def get_data(tickers, years):
    end = datetime.date.today()
    start = end.replace(year=end.year - years)
    df = yf.download(tickers, start=start, end=end)["Close"]
    return df.dropna()

def stats(w, ret, cov):
    r = np.dot(w, ret) * 252
    v = np.sqrt(w.T @ (cov * 252) @ w)
    return r, v

def optimize(n, ret, cov, rf, mode):
    cons = ({'type':'eq','fun': lambda x: np.sum(x)-1})
    bounds = [(0,1)] * n
    init = np.ones(n)/n

    if mode=="sharpe":
        func = lambda w: -(stats(w, ret, cov)[0]-rf)/stats(w, ret, cov)[1]
    elif mode=="minvol":
        func = lambda w: stats(w, ret, cov)[1]

    return minimize(func, init, bounds=bounds, constraints=cons)

# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ SETTINGS")

    tickers = st.text_input("Tickers", "AAPL,MSFT,GOOGL,AMZN").split(",")
    years = st.slider("Years", 1, 10, 5)
    rf = st.number_input("Risk Free %", value=3.0)/100
    run = st.button("RUN")

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
st.markdown('<div class="title">PORTFOLIO OPTIMIZATION TERMINAL</div>', unsafe_allow_html=True)

if not run:
    st.stop()

df = get_data(tickers, years)
ret = np.log(df/df.shift(1)).dropna()
ret_m = ret.mean().values
cov = ret.cov().values

n = len(df.columns)

res_s = optimize(n, ret_m, cov, rf, "sharpe")
res_m = optimize(n, ret_m, cov, rf, "minvol")

r_s, v_s = stats(res_s.x, ret_m, cov)
r_m, v_m = stats(res_m.x, ret_m, cov)

# ─────────────────────────────────────────────────────────────
# PORTFOLIO DISPLAY
# ─────────────────────────────────────────────────────────────
st.markdown('<div class="section">PORTFOLIOS</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

def draw_portfolio(col, title, r, v, w):
    with col:
        st.markdown(f'<div class="port-box">', unsafe_allow_html=True)
        st.markdown(f'<div class="port-title">{title}</div>', unsafe_allow_html=True)

        c1,c2,c3 = st.columns(3)
        c1.markdown(f'<div class="metric-card"><div class="metric-label">RETURN</div><div class="metric-value">{r*100:.2f}%</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-card"><div class="metric-label">VOL</div><div class="metric-value">{v*100:.2f}%</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-card"><div class="metric-label">SHARPE</div><div class="metric-value">{(r-rf)/v:.2f}</div></div>', unsafe_allow_html=True)

        fig = go.Figure(go.Bar(
            x=w,
            y=df.columns,
            orientation='h'
        ))

        fig.update_layout(
            height=250,
            margin=dict(l=0,r=0,t=10,b=0),
            paper_bgcolor="#0f141a",
            plot_bgcolor="#0f141a",
            font=dict(color="white")
        )

        st.plotly_chart(fig, use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

draw_portfolio(col1, "⭐ MAX SHARPE", r_s, v_s, res_s.x)
draw_portfolio(col2, "🔻 MIN VOL", r_m, v_m, res_m.x)

# ─────────────────────────────────────────────────────────────
# FRONTIER
# ─────────────────────────────────────────────────────────────
st.markdown('<div class="section">EFFICIENT FRONTIER</div>', unsafe_allow_html=True)

w_rand = np.random.dirichlet(np.ones(n), 2000)
rets = w_rand @ ret_m * 252
vols = np.sqrt(np.einsum('ij,jk,ik->i', w_rand, cov*252, w_rand))

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=vols, y=rets,
    mode='markers',
    marker=dict(size=5, color=rets/vols),
    name="Portfolios"
))

fig.add_trace(go.Scatter(
    x=[v_s], y=[r_s],
    mode='markers',
    marker=dict(size=14, color='gold'),
    name="Sharpe"
))

fig.update_layout(
    paper_bgcolor="#0b0f14",
    plot_bgcolor="#0b0f14",
    font=dict(color="white"),
    height=500
)

st.plotly_chart(fig, use_container_width=True)