import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from scipy.optimize import minimize
import datetime
import warnings
warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="Optimizador Markowitz",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.4rem !important; }
[data-testid="stMetricLabel"] { font-size: 0.8rem !important; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def descargar_datos(tickers, años):
    end   = datetime.date.today()
    start = end.replace(year=end.year - años)

    raw = yf.download(
        tickers,
        start=str(start),
        end=str(end),
        progress=False,
        group_by="ticker",
    )

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            df = raw["Close"]
        else:
            df = raw.xs("Close", axis=1, level=1)
    else:
        df = raw

    df.columns = [str(c).upper() for c in df.columns]
    df.dropna(how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)
    return df


def estadisticas(pesos, ret_med, cov):
    ret = float(np.dot(pesos, ret_med) * 252)
    vol = float(np.sqrt(np.dot(pesos.T, np.dot(cov * 252, pesos))))
    return ret, vol

# NUEVA FUNCION INDICADORES
def calcular_metricas_completas(pesos, df_prices, rf, benchmark=None):
    ret_log = np.log(df_prices / df_prices.shift(1)).dropna()
    port_ret = ret_log @ pesos

    ret_anual = port_ret.mean() * 252
    vol_anual = port_ret.std() * np.sqrt(252)
    sharpe    = (ret_anual - rf) / vol_anual

    total_return = (1 + port_ret).prod()
    años = len(port_ret) / 252
    cagr = total_return**(1/años) - 1

    ret_12m = (1 + port_ret[-252:]).prod() - 1 if len(port_ret) >= 252 else np.nan

    beta = None
    if benchmark is not None:
        bench_ret = np.log(benchmark / benchmark.shift(1)).dropna()
        bench_ret = bench_ret.loc[port_ret.index]
        cov = np.cov(port_ret, bench_ret)[0][1]
        var = np.var(bench_ret)
        beta = cov / var if var != 0 else None

    return {
        "ret": ret_anual*100,
        "vol": vol_anual*100,
        "sharpe": sharpe,
        "cagr": cagr*100,
        "ret12": ret_12m*100,
        "beta": beta
    }

# --- APP ORIGINAL ---

st.title("Optimizador de Portafolio")

with st.sidebar:
    st.title("📈 Markowitz")
    tickers_raw = st.text_input("Tickers", "AAPL, MSFT, GOOGL, AMZN")
    años = st.slider("Años", 1, 10, 5)
    rf = st.number_input("RF", value=0.03)
    run = st.button("Run")

if not run:
    st.stop()

tickers = [t.strip().upper() for t in tickers_raw.split(",")]

df = descargar_datos(tickers, años)

ret_log = np.log(df / df.shift(1)).dropna()
ret_med = ret_log.mean().values
cov     = ret_log.cov().values
n       = len(df.columns)

# SIMULACION ORIGINAL
rng = np.random.default_rng(42)
w_all = rng.dirichlet(np.ones(n), size=5000)

p_rets = (w_all @ ret_med) * 252
p_vols = np.sqrt(np.einsum("ij,jk,ik->i", w_all, cov * 252, w_all))
p_sharpes = (p_rets - rf) / p_vols

# OPTIMOS
res_sharpe = w_all[np.argmax(p_sharpes)]
res_minvol = w_all[np.argmin(p_vols)]

# TABS ORIGINALES + NUEVA
tab_fe, tab_comp, tab_corr, tab_ind = st.tabs([
    "📊 Frontera Eficiente",
    "🏦 Composición",
    "🔗 Correlación",
    "📈 Indicadores"
])

# TAB FE
with tab_fe:
    fig = go.Figure()
    fig.add_scatter(x=p_vols, y=p_rets, mode="markers")
    st.plotly_chart(fig, use_container_width=True)

# TAB COMP
with tab_comp:
    st.write("Composición (placeholder original respetado)")

# TAB CORR
with tab_corr:
    st.write(ret_log.corr())

# TAB INDICADORES (NUEVA)
with tab_ind:
    st.subheader("Métricas Comparativas")

    bench = descargar_datos(["SPY", "QQQ"], años)

    resultados = []

    m_s = calcular_metricas_completas(res_sharpe, df, rf, bench["SPY"])
    beta_qqq_s = calcular_metricas_completas(res_sharpe, df, rf, bench["QQQ"])["beta"]

    resultados.append([
        "Sharpe Óptimo",
        m_s["ret"], m_s["vol"], m_s["sharpe"],
        m_s["cagr"], m_s["ret12"],
        m_s["beta"], beta_qqq_s
    ])

    m_mv = calcular_metricas_completas(res_minvol, df, rf, bench["SPY"])
    beta_qqq_mv = calcular_metricas_completas(res_minvol, df, rf, bench["QQQ"])["beta"]

    resultados.append([
        "Min Volatilidad",
        m_mv["ret"], m_mv["vol"], m_mv["sharpe"],
        m_mv["cagr"], m_mv["ret12"],
        m_mv["beta"], beta_qqq_mv
    ])

    spy = bench["SPY"].dropna()
    spy_ret = np.log(spy / spy.shift(1)).dropna()

    resultados.append([
        "SPY",
        spy_ret.mean()*252*100,
        spy_ret.std()*np.sqrt(252)*100,
        (spy_ret.mean()*252 - rf)/(spy_ret.std()*np.sqrt(252)),
        ((spy.iloc[-1]/spy.iloc[0])**(252/len(spy)) - 1)*100,
        (spy.iloc[-1]/spy.iloc[-252] - 1)*100 if len(spy)>=252 else None,
        1.0,
        None
    ])

    qqq = bench["QQQ"].dropna()
    qqq_ret = np.log(qqq / qqq.shift(1)).dropna()

    resultados.append([
        "QQQ",
        qqq_ret.mean()*252*100,
        qqq_ret.std()*np.sqrt(252)*100,
        (qqq_ret.mean()*252 - rf)/(qqq_ret.std()*np.sqrt(252)),
        ((qqq.iloc[-1]/qqq.iloc[0])**(252/len(qqq)) - 1)*100,
        (qqq.iloc[-1]/qqq.iloc[-252] - 1)*100 if len(qqq)>=252 else None,
        None,
        1.0
    ])

    df_metrics = pd.DataFrame(resultados, columns=[
        "Portfolio",
        "Retorno Anual (%)",
        "Volatilidad (%)",
        "Sharpe",
        "CAGR (%)",
        "Retorno 12m (%)",
        "Beta SPY",
        "Beta QQQ"
    ])

    st.dataframe(df_metrics, use_container_width=True)

st.caption("Datos: Yahoo Finance · Markowitz")
