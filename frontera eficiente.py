app_code = """
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
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

st.markdown('''
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;600&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stApp { background-color: #f0f2f6; }
    section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e0e0e0; }
    section[data-testid="stSidebar"] * { color: #1a1a2e !important; }
    .main-title { font-family: 'Space Mono', monospace; font-size: 1.9rem; font-weight: 700; color: #1a1a2e; }
    .sub-title { color: #666666; font-size: 0.9rem; margin-top: -8px; margin-bottom: 24px; }
    .weight-bar-wrap { margin: 4px 0; }
    .weight-bar-label { font-size: 0.8rem; color: #444444; font-family: 'Space Mono', monospace; display: flex; justify-content: space-between; }
    .weight-bar-bg { background: #e0e0e0; border-radius: 4px; height: 8px; margin-top: 3px; }
    .weight-bar-fill { height: 8px; border-radius: 4px; background: linear-gradient(90deg, #1a56db, #0ea5e9); }
    div[data-testid="stMetric"] { background: #ffffff; border: 1px solid #e0e0e0; border-radius: 10px; padding: 12px 16px; }
    div[data-testid="stMetric"] label { color: #666666 !important; }
    div[data-testid="stMetric"] div { color: #1a1a2e !important; font-family: 'Space Mono', monospace; }
    .stButton > button { background: linear-gradient(135deg, #1a56db, #0ea5e9); color: white; border: none; border-radius: 8px; font-family: 'Space Mono', monospace; font-size: 0.85rem; padding: 10px 24px; width: 100%; transition: all 0.2s; }
    .section-header { color: #1a56db; font-family: 'Space Mono', monospace; font-size: 0.75rem; letter-spacing: 0.15em; text-transform: uppercase; border-bottom: 1px solid #e0e0e0; padding-bottom: 6px; margin: 18px 0 12px 0; }
    .port-header { font-family: 'Space Mono', monospace; font-size: 1.1rem; font-weight: 700; color: #1a1a2e; margin-bottom: 4px; }
</style>
''', unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def descargar_datos(tickers, años):
    end   = datetime.date.today()
    start = end.replace(year=end.year - años)
    df = yf.download(tickers, start=str(start), end=str(end), auto_adjust=True, progress=False)["Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame(name=tickers[0])
    df.dropna(how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)
    return df


def estadisticas(pesos, ret_med, cov):
    ret = float(np.dot(pesos, ret_med) * 252)
    vol = float(np.sqrt(np.dot(pesos.T, np.dot(cov * 252, pesos))))
    return ret, vol


def optimizar(tipo, n, ret_med, cov, rf, peso_min=0.0, ret_obj=None):
    bounds = tuple((peso_min, 1.0) for _ in range(n))
    cons   = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    if ret_obj is not None:
        cons.append({"type": "eq", "fun": lambda w: estadisticas(w, ret_med, cov)[0] - ret_obj})
    fns = {
        "sharpe": lambda w: -((estadisticas(w, ret_med, cov)[0] - rf) / estadisticas(w, ret_med, cov)[1]),
        "minvol": lambda w:   estadisticas(w, ret_med, cov)[1],
        "maxret": lambda w:  -estadisticas(w, ret_med, cov)[0],
    }
    x0  = np.full(n, 1 / n)
    res = minimize(fns[tipo], x0, method="SLSQP", bounds=bounds, constraints=cons,
                   options={"maxiter": 1000, "ftol": 1e-9})
    return res


def calcular_frontera(ret_med, cov, rf, n, peso_min, n_puntos=50):
    r_min = optimizar("minvol", n, ret_med, cov, rf, peso_min)
    r_max = optimizar("maxret", n, ret_med, cov, rf, peso_min)
    ret_min, _ = estadisticas(r_min.x, ret_med, cov)
    ret_max, _ = estadisticas(r_max.x, ret_med, cov)
    vols, rets = [], []
    for r in np.linspace(ret_min, ret_max, n_puntos):
        res = optimizar("minvol", n, ret_med, cov, rf, peso_min, ret_obj=r)
        if res.success:
            rv, vv = estadisticas(res.x, ret_med, cov)
            rets.append(rv); vols.append(vv)
    return np.array(vols), np.array(rets)


COLORES_ACTIVOS = [
    "#4361EE", "#F72585", "#4CC9F0", "#7209B7", "#3A0CA3",
    "#4895EF", "#560BAD", "#F3722C", "#90BE6D", "#43AA8B",
    "#577590", "#F9C74F", "#F8961E", "#277DA1", "#6D6875",
]

def grafico_barras_composicion(pesos, tickers_ok, titulo, color_titulo):
    idx_sorted = np.argsort(pesos)[::-1]
    tickers_f = [tickers_ok[i] for i in idx_sorted if pesos[i] > 0.0001]
    pesos_f   = [pesos[i] * 100 for i in idx_sorted if pesos[i] > 0.0001]
    colores_f = [COLORES_ACTIVOS[i % len(COLORES_ACTIVOS)] for i in range(len(tickers_f))]

    fig = go.Figure(go.Bar(
        x=pesos_f,
        y=tickers_f,
        orientation="h",
        marker=dict(color=colores_f, line=dict(width=0)),
        text=[f"{p:.1f}%" for p in pesos_f],
        textposition="outside",
        textfont=dict(family="Space Mono", size=11, color="#1a1a2e"),
        hovertemplate="%{y}: %{x:.2f}%<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text=titulo, font=dict(family="Space Mono", size=13, color=color_titulo), x=0),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="DM Sans", color="#1a1a2e"),
        xaxis=dict(
            title="Peso (%)",
            range=[0, max(pesos_f) * 1.25],
            gridcolor="#eeeeee",
            tickfont=dict(size=10),
            color="#666666",
        ),
        yaxis=dict(
            tickfont=dict(family="Space Mono", size=11, color="#1a1a2e"),
            autorange="reversed",
        ),
        height=max(250, len(tickers_f) * 52 + 80),
        margin=dict(l=10, r=60, t=50, b=40),
        bargap=0.35,
    )
    return fig


def mostrar_composicion_tab(portafolios):
    cols = st.columns(len(portafolios))
    for col, p in zip(cols, portafolios):
        with col:
            sr = (p["ret"] - p["rf"]) / p["vol"]
            st.markdown(f'<div class="port-header">{p["label"]}</div>', unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("Retorno", f'{p["ret"]*100:.2f}%')
            c2.metric("Volatilidad", f'{p["vol"]*100:.2f}%')
            c3.metric("Sharpe", f"{sr:.3f}")
            fig = grafico_barras_composicion(p["pesos"], p["tickers_ok"], p["label"], p["color"])
            st.plotly_chart(fig, use_container_width=True)
            df_p = pd.DataFrame({
                "Activo": p["tickers_ok"],
                "Peso (%)": [round(w * 100, 2) for w in p["pesos"]],
            })
            df_p = df_p[df_p["Peso (%)"] > 0.01].sort_values("Peso (%)", ascending=False).reset_index(drop=True)
            st.dataframe(df_p, use_container_width=True, hide_index=True)


# ── SIDEBAR ──
with st.sidebar:
    st.markdown('<div class="main-title">📈 Markowitz</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Optimizador de portafolio</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-header">Activos</div>', unsafe_allow_html=True)
    tickers_raw = st.text_input("Tickers (separados por coma)", value="AAPL, MSFT, GOOGL, AMZN, JPM")
    st.markdown('<div class="section-header">Período</div>', unsafe_allow_html=True)
    años = st.slider("Años de historia", min_value=1, max_value=20, value=5, step=1)
    st.markdown('<div class="section-header">Parámetros</div>', unsafe_allow_html=True)
    rf = st.number_input("Tasa libre de riesgo (%)", min_value=0.0, max_value=20.0, value=3.70, step=0.05, format="%.2f") / 100
    usar_obj = st.checkbox("Usar retorno objetivo", value=True)
    ret_obj  = None
    if usar_obj:
        ret_obj = st.number_input("Retorno objetivo (%)", min_value=1.0, max_value=100.0, value=15.0, step=0.5, format="%.1f") / 100
    peso_min = st.slider("Peso mínimo por activo (%)", 0, 20, 0, step=1) / 100
    n_sim    = st.select_slider("Portafolios a simular", options=[1000, 2000, 5000, 10000], value=5000)
    st.markdown("<br>", unsafe_allow_html=True)
    run = st.button("⚡ OPTIMIZAR")


# ── MAIN ──
st.markdown('<div class="main-title" style="font-size:2.2rem">Optimizador de Portafolio</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Frontera Eficiente · Capital Market Line · Sharpe</div>', unsafe_allow_html=True)

if not run:
    st.info("👈 Configurá los parámetros en el panel izquierdo y presioná **OPTIMIZAR**")
    st.stop()

tickers = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]

with st.spinner("📥 Descargando datos..."):
    try:
        df = descargar_datos(tickers, años)
    except Exception as e:
        st.error(f"Error al descargar datos: {e}")
        st.stop()

tickers_ok = list(df.columns)
if len(tickers_ok) < 2:
    st.error("Se necesitan al menos 2 activos con datos disponibles.")
    st.stop()

no_encontrados = [t for t in tickers if t not in tickers_ok]
if no_encontrados:
    st.warning(f"No se encontraron datos para: {', '.join(no_encontrados)}")

ret_log = np.log(df / df.shift(1)).dropna()
ret_med = ret_log.mean().values
cov     = ret_log.cov().values
n       = len(tickers_ok)

with st.spinner(f"⚙️ Simulando {n_sim:,} portafolios..."):
    rng   = np.random.default_rng(42)
    w_all = rng.dirichlet(np.ones(n), size=n_sim)
    if peso_min > 0:
        w_all = np.clip(w_all, peso_min, 1)
        w_all = w_all / w_all.sum(axis=1, keepdims=True)
    p_rets    = (w_all @ ret_med) * 252
    p_vols    = np.sqrt(np.einsum("ij,jk,ik->i", w_all, cov * 252, w_all))
    p_sharpes = (p_rets - rf) / p_vols

with st.spinner("📐 Calculando frontera eficiente..."):
    fe_vols, fe_rets = calcular_frontera(ret_med, cov, rf, n, peso_min, n_puntos=50)

with st.spinner("⭐ Optimizando portafolios..."):
    res_sharpe = optimizar("sharpe", n, ret_med, cov, rf, peso_min)
    res_minvol = optimizar("minvol", n, ret_med, cov, rf, peso_min)
    ret_s, vol_s   = estadisticas(res_sharpe.x, ret_med, cov)
    ret_mv, vol_mv = estadisticas(res_minvol.x, ret_med, cov)
    sr_s = (ret_s - rf) / vol_s
    ret_o, vol_o, pesos_o = None, None, None
    if usar_obj and ret_obj is not None:
        res_obj = optimizar("minvol", n, ret_med, cov, rf, peso_min, ret_obj=ret_obj)
        if res_obj.success:
            ret_o, vol_o = estadisticas(res_obj.x, ret_med, cov)
            pesos_o = res_obj.x

# ── TABS PRINCIPALES ──
tab_fe, tab_comp, tab_corr = st.tabs(["📊 Frontera Eficiente", "🏦 Composición", "🔗 Correlación"])

# ── TAB 1: FRONTERA EFICIENTE ──
with tab_fe:
    vol_cml = np.linspace(0, max(p_vols) * 1.15, 200)
    ret_cml = rf + sr_s * vol_cml

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=p_vols, y=p_rets, mode="markers",
        marker=dict(color=p_sharpes, colorscale="Viridis", size=6, opacity=0.7,
                    colorbar=dict(title=dict(text="Sharpe", font=dict(color="#444444")), tickfont=dict(color="#444444")), showscale=True),
        name="Portfolios Aleatorios", hovertemplate="Vol: %{x:.2f}<br>Ret: %{y:.2f}<extra></extra>"))
    if len(fe_vols) > 1:
        fig.add_trace(go.Scatter(x=fe_vols, y=fe_rets, mode="lines",
            line=dict(color="#1a56db", width=4), name="Frontera Eficiente"))
    fig.add_trace(go.Scatter(x=vol_cml, y=ret_cml, mode="lines",
        line=dict(color="#e53935", width=2, dash="dash"), name="CML"))
    fig.add_trace(go.Scatter(x=[vol_s], y=[ret_s], mode="markers",
        marker=dict(symbol="star", color="#ffd700", size=22, line=dict(color="#333", width=1)),
        name="Sharpe Optimo"))
    fig.add_trace(go.Scatter(x=[vol_mv], y=[ret_mv], mode="markers",
        marker=dict(symbol="circle", color="#e53935", size=16, line=dict(color="#333", width=1)),
        name="Min Volatilidad"))
    if ret_o is not None:
        fig.add_trace(go.Scatter(x=[vol_o], y=[ret_o], mode="markers",
            marker=dict(symbol="x", color="#2e7d32", size=18, line=dict(color="#333", width=2)),
            name=f"Objetivo {ret_obj*100:.1f}%"))

    fig.update_layout(
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        font=dict(family="DM Sans", color="#1a1a2e"),
        xaxis=dict(title="Volatilidad Anual", tickformat=".2f", gridcolor="#e8e8e8", zerolinecolor="#cccccc", color="#444444"),
        yaxis=dict(title="Retorno Anual", tickformat=".2f", gridcolor="#e8e8e8", zerolinecolor="#cccccc", color="#444444"),
        legend=dict(bgcolor="rgba(255,255,255,0.9)", bordercolor="#cccccc", borderwidth=1,
                    font=dict(size=12, color="#1a1a2e"), orientation="v",
                    x=0.01, y=0.99, xanchor="left", yanchor="top"),
        height=600, margin=dict(l=10, r=10, t=60, b=10), hovermode="closest",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-header">Resultados de Optimización</div>', unsafe_allow_html=True)

    if ret_o is not None:
        tabs_labels = [f"🎯 Objetivo {ret_obj*100:.1f}%", "🔴 Mín. Volatilidad", "⭐ Sharpe Óptimo"]
    else:
        tabs_labels = ["🔴 Mín. Volatilidad", "⭐ Sharpe Óptimo"]
    tab_list = st.tabs(tabs_labels)

    def mostrar_portafolio(tab, pesos, ret, vol, tickers_ok, rf):
        sr = (ret - rf) / vol
        with tab:
            c1, c2, c3 = st.columns(3)
            c1.metric("Retorno Anual", f"{ret*100:.2f}%")
            c2.metric("Volatilidad Anual", f"{vol*100:.2f}%")
            c3.metric("Sharpe Ratio", f"{sr:.3f}")
            st.markdown("**Composición del portafolio**")
            bars_html = ""
            for i in np.argsort(pesos)[::-1]:
                t = tickers_ok[i]; w = pesos[i]
                bars_html += f'<div class="weight-bar-wrap"><div class="weight-bar-label"><span>{t}</span><span>{w*100:.2f}%</span></div><div class="weight-bar-bg"><div class="weight-bar-fill" style="width:{w*100:.1f}%"></div></div></div>'
            st.markdown(bars_html, unsafe_allow_html=True)
            df_p = pd.DataFrame({"Ticker": tickers_ok, "Peso (%)": [f"{w*100:.2f}%" for w in pesos], "_w": pesos}).sort_values("_w", ascending=False).drop(columns="_w")
            st.dataframe(df_p, use_container_width=True, hide_index=True)

    if ret_o is not None:
        mostrar_portafolio(tab_list[0], pesos_o, ret_o, vol_o, tickers_ok, rf)
        mostrar_portafolio(tab_list[1], res_minvol.x, ret_mv, vol_mv, tickers_ok, rf)
        mostrar_portafolio(tab_list[2], res_sharpe.x, ret_s, vol_s, tickers_ok, rf)
    else:
        mostrar_portafolio(tab_list[0], res_minvol.x, ret_mv, vol_mv, tickers_ok, rf)
        mostrar_portafolio(tab_list[1], res_sharpe.x, ret_s, vol_s, tickers_ok, rf)


# ── TAB 2: COMPOSICIÓN ──
with tab_comp:
    st.markdown('<div class="section-header">Composición de Portafolios</div>', unsafe_allow_html=True)

    portafolios_comp = []

    if ret_o is not None:
        portafolios_comp.append({
            "label": f"🎯 Objetivo {ret_obj*100:.1f}%",
            "pesos": pesos_o,
            "ret": ret_o,
            "vol": vol_o,
            "rf": rf,
            "tickers_ok": tickers_ok,
            "color": "#2e7d32",
        })

    portafolios_comp.append({
        "label": "⭐ Sharpe Óptimo",
        "pesos": res_sharpe.x,
        "ret": ret_s,
        "vol": vol_s,
        "rf": rf,
        "tickers_ok": tickers_ok,
        "color": "#b8860b",
    })

    portafolios_comp.append({
        "label": "🔴 Mín. Volatilidad",
        "pesos": res_minvol.x,
        "ret": ret_mv,
        "vol": vol_mv,
        "rf": rf,
        "tickers_ok": tickers_ok,
        "color": "#c62828",
    })

    mostrar_composicion_tab(portafolios_comp)


# ── TAB 3: CORRELACIÓN ──
with tab_corr:
    st.markdown('<div class="section-header">Matriz de Correlación</div>', unsafe_allow_html=True)
    corr = ret_log.corr()
    fig_corr = go.Figure(go.Heatmap(
        z=corr.values, x=corr.columns.tolist(), y=corr.index.tolist(),
        colorscale="RdBu_r", zmin=-1, zmax=1,
        text=np.round(corr.values, 2), texttemplate="%{text}",
        textfont=dict(size=11, color="white"),
    ))
    fig_corr.update_layout(paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        font=dict(color="#1a1a2e"), height=400, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_corr, use_container_width=True)

st.markdown('''<div style="text-align:center; color:#aaaaaa; font-size:0.75rem; margin-top:40px;">
Datos: Yahoo Finance · Optimización: SciPy SLSQP · Teoría: Markowitz (1952)<br>
Este análisis es educativo y no constituye asesoramiento financiero.
</div>''', unsafe_allow_html=True)
"""

with open("markowitz_app.py", "w", encoding="utf-8") as f:
    f.write(app_code)
print("✅ markowitz_app.py escrito correctamente")