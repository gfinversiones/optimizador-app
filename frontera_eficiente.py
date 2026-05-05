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

# FIX 1: CSS compatible con Streamlit 1.28+ — sin selectores de clase inestables
st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.4rem !important; }
[data-testid="stMetricLabel"] { font-size: 0.8rem !important; }
</style>
""", unsafe_allow_html=True)


# FIX 2: yfinance compatible con 0.2.31+ — usar try/except y manejar MultiIndex
@st.cache_data(ttl=3600)
def descargar_datos(tickers, años):
    end   = datetime.date.today()
    start = end.replace(year=end.year - años)
    
    # auto_adjust=True es el nuevo default, no hace falta pasarlo
    raw = yf.download(
        tickers,
        start=str(start),
        end=str(end),
        progress=False,
        group_by="ticker",
    )
    
    # Manejo robusto del resultado según versión de yfinance
    if isinstance(raw.columns, pd.MultiIndex):
        # Versión >= 0.2.x: columnas son (Price, Ticker) o (Ticker, Price)
        if "Close" in raw.columns.get_level_values(0):
            df = raw["Close"]
        elif "Close" in raw.columns.get_level_values(1):
            df = raw.xs("Close", axis=1, level=1)
        else:
            # fallback: tomar el primer nivel que tenga "Adj Close" o "close"
            for lbl in ["Adj Close", "adj close", "close"]:
                try:
                    df = raw[lbl]; break
                except KeyError:
                    continue
            else:
                df = raw.iloc[:, raw.columns.get_level_values(1) == raw.columns.get_level_values(1)[0]]
    else:
        # Serie simple (un solo ticker)
        if isinstance(raw, pd.Series):
            df = raw.to_frame(name=tickers[0] if isinstance(tickers, list) else tickers)
        else:
            if "Close" in raw.columns:
                df = raw[["Close"]].rename(columns={"Close": tickers[0] if len(tickers)==1 else "Close"})
            else:
                df = raw

    if isinstance(df, pd.Series):
        df = df.to_frame()

    df.columns = [str(c).upper() for c in df.columns]
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
        textfont=dict(size=11),
        hovertemplate="%{y}: %{x:.2f}%<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text=titulo, font=dict(size=13, color=color_titulo), x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title="Peso (%)",
            range=[0, max(pesos_f) * 1.25],
            gridcolor="#eeeeee",
            tickfont=dict(size=10),
        ),
        yaxis=dict(autorange="reversed"),
        height=max(250, len(tickers_f) * 52 + 80),
        margin=dict(l=10, r=60, t=50, b=40),
        bargap=0.35,
    )
    return fig


def mostrar_portafolio(pesos, ret, vol, tickers_ok, rf):
    sr = (ret - rf) / vol
    c1, c2, c3 = st.columns(3)
    c1.metric("Retorno Anual", f"{ret*100:.2f}%")
    c2.metric("Volatilidad Anual", f"{vol*100:.2f}%")
    c3.metric("Sharpe Ratio", f"{sr:.3f}")
    st.markdown("**Composición del portafolio**")
    for i in np.argsort(pesos)[::-1]:
        t = tickers_ok[i]; w = pesos[i]
        st.progress(float(w), text=f"{t}: {w*100:.2f}%")
    df_p = (
        pd.DataFrame({"Ticker": tickers_ok, "Peso (%)": [round(w*100, 2) for w in pesos]})
        .sort_values("Peso (%)", ascending=False)
        .reset_index(drop=True)
    )
    st.dataframe(df_p, use_container_width=True, hide_index=True)


# ── SIDEBAR ──
with st.sidebar:
    st.title("📈 Markowitz")
    st.caption("Optimizador de portafolio")

    st.subheader("Activos")
    tickers_raw = st.text_input("Tickers (separados por coma)", value="AAPL, MSFT, GOOGL, AMZN, JPM")

    st.subheader("Período")
    años = st.slider("Años de historia", min_value=1, max_value=20, value=5, step=1)

    st.subheader("Parámetros")
    rf = st.number_input("Tasa libre de riesgo (%)", min_value=0.0, max_value=20.0,
                         value=3.70, step=0.05, format="%.2f") / 100
    usar_obj = st.checkbox("Usar retorno objetivo", value=True)
    ret_obj  = None
    if usar_obj:
        ret_obj = st.number_input("Retorno objetivo (%)", min_value=1.0, max_value=100.0,
                                  value=15.0, step=0.5, format="%.1f") / 100
    peso_min = st.slider("Peso mínimo por activo (%)", 0, 20, 0, step=1) / 100
    n_sim    = st.select_slider("Portafolios a simular", options=[1000, 2000, 5000, 10000], value=5000)

    st.write("")
    run = st.button("⚡ OPTIMIZAR", use_container_width=True, type="primary")


# ── MAIN ──
st.title("Optimizador de Portafolio")
st.caption("Frontera Eficiente · Capital Market Line · Sharpe")

if not run:
    st.info("👈 Configurá los parámetros en el panel izquierdo y presioná **OPTIMIZAR**")
    st.stop()

tickers = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]

with st.spinner("📥 Descargando datos de Yahoo Finance..."):
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


# FIX 3: sin st.tabs() anidados — usar st.tabs() solo en el nivel superior
tab_fe, tab_comp, tab_corr = st.tabs(["📊 Frontera Eficiente", "🏦 Composición", "🔗 Correlación"])


# ── TAB 1: FRONTERA EFICIENTE ──
with tab_fe:
    vol_cml = np.linspace(0, max(p_vols) * 1.15, 200)
    ret_cml = rf + sr_s * vol_cml

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=p_vols, y=p_rets, mode="markers",
        marker=dict(color=p_sharpes, colorscale="Viridis", size=5, opacity=0.6,
                    colorbar=dict(title="Sharpe"), showscale=True),
        name="Portafolios Aleatorios",
        hovertemplate="Vol: %{x:.3f}<br>Ret: %{y:.3f}<extra></extra>",
    ))
    if len(fe_vols) > 1:
        fig.add_trace(go.Scatter(
            x=fe_vols, y=fe_rets, mode="lines",
            line=dict(color="#1a56db", width=4), name="Frontera Eficiente",
        ))
    fig.add_trace(go.Scatter(
        x=vol_cml, y=ret_cml, mode="lines",
        line=dict(color="#e53935", width=2, dash="dash"), name="CML",
    ))
    fig.add_trace(go.Scatter(
        x=[vol_s], y=[ret_s], mode="markers",
        marker=dict(symbol="star", color="#ffd700", size=20, line=dict(color="#333", width=1)),
        name="Sharpe Óptimo",
    ))
    fig.add_trace(go.Scatter(
        x=[vol_mv], y=[ret_mv], mode="markers",
        marker=dict(symbol="circle", color="#e53935", size=14, line=dict(color="#333", width=1)),
        name="Mín. Volatilidad",
    ))
    if ret_o is not None:
        fig.add_trace(go.Scatter(
            x=[vol_o], y=[ret_o], mode="markers",
            marker=dict(symbol="x", color="#2e7d32", size=16, line=dict(color="#333", width=2)),
            name=f"Objetivo {ret_obj*100:.1f}%",
        ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="Volatilidad Anual", tickformat=".2f", gridcolor="rgba(128,128,128,0.2)"),
        yaxis=dict(title="Retorno Anual",     tickformat=".2f", gridcolor="rgba(128,128,128,0.2)"),
        legend=dict(orientation="v", x=0.01, y=0.99, xanchor="left", yanchor="top",
                    bgcolor="rgba(0,0,0,0)"),
        height=550,
        margin=dict(l=10, r=10, t=20, b=10),
        hovermode="closest",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Resultados de Optimización")

    # FIX 3 aplicado: portafolios como columnas en vez de tabs anidados
    portafolios = []
    if ret_o is not None:
        portafolios.append((f"🎯 Objetivo {ret_obj*100:.1f}%", pesos_o, ret_o, vol_o))
    portafolios.append(("🔴 Mín. Volatilidad", res_minvol.x, ret_mv, vol_mv))
    portafolios.append(("⭐ Sharpe Óptimo",    res_sharpe.x, ret_s,  vol_s))

    cols = st.columns(len(portafolios))
    for col, (label, pesos, ret, vol) in zip(cols, portafolios):
        with col:
            sr = (ret - rf) / vol
            st.markdown(f"**{label}**")
            st.metric("Retorno", f"{ret*100:.2f}%")
            st.metric("Volatilidad", f"{vol*100:.2f}%")
            st.metric("Sharpe", f"{sr:.3f}")
            for i in np.argsort(pesos)[::-1]:
                if pesos[i] > 0.001:
                    st.progress(float(pesos[i]), text=f"{tickers_ok[i]}: {pesos[i]*100:.1f}%")


# ── TAB 2: COMPOSICIÓN ──
with tab_comp:
    st.subheader("Composición de Portafolios")

    port_defs = []
    if ret_o is not None:
        port_defs.append({"label": f"🎯 Objetivo {ret_obj*100:.1f}%", "pesos": pesos_o,
                          "ret": ret_o, "vol": vol_o, "color": "#2e7d32"})
    port_defs.append({"label": "⭐ Sharpe Óptimo",   "pesos": res_sharpe.x,
                      "ret": ret_s,  "vol": vol_s,  "color": "#b8860b"})
    port_defs.append({"label": "🔴 Mín. Volatilidad", "pesos": res_minvol.x,
                      "ret": ret_mv, "vol": vol_mv, "color": "#c62828"})

    cols2 = st.columns(len(port_defs))
    for col, p in zip(cols2, port_defs):
        with col:
            sr = (p["ret"] - rf) / p["vol"]
            c1, c2, c3 = col.columns(3)
            c1.metric("Retorno", f'{p["ret"]*100:.2f}%')
            c2.metric("Vol.", f'{p["vol"]*100:.2f}%')
            c3.metric("Sharpe", f"{sr:.3f}")
            fig_b = grafico_barras_composicion(p["pesos"], tickers_ok, p["label"], p["color"])
            st.plotly_chart(fig_b, use_container_width=True)
            df_p = (
                pd.DataFrame({"Activo": tickers_ok, "Peso (%)": [round(w*100, 2) for w in p["pesos"]]})
                .query("`Peso (%)` > 0.01")
                .sort_values("Peso (%)", ascending=False)
                .reset_index(drop=True)
            )
            st.dataframe(df_p, use_container_width=True, hide_index=True)


# ── TAB 3: CORRELACIÓN ──
with tab_corr:
    st.subheader("Matriz de Correlación")
    corr = ret_log.corr()
    fig_corr = go.Figure(go.Heatmap(
        z=corr.values,
        x=corr.columns.tolist(),
        y=corr.index.tolist(),
        colorscale="RdBu_r",
        zmin=-1, zmax=1,
        text=np.round(corr.values, 2),
        texttemplate="%{text}",
        textfont=dict(size=11),
    ))
    fig_corr.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig_corr, use_container_width=True)

st.caption(
    "Datos: Yahoo Finance · Optimización: SciPy SLSQP · Teoría: Markowitz (1952) — "
    "Este análisis es educativo y no constituye asesoramiento financiero."
)