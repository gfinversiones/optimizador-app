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
        elif "Close" in raw.columns.get_level_values(1):
            df = raw.xs("Close", axis=1, level=1)
        else:
            for lbl in ["Adj Close", "adj close", "close"]:
                try:
                    df = raw[lbl]; break
                except KeyError:
                    continue
            else:
                df = raw.iloc[:, raw.columns.get_level_values(1) == raw.columns.get_level_values(1)[0]]
    else:
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


def optimizar(tipo, n, ret_med, cov, rf, peso_min=0.0, peso_max=1.0, ret_obj=None):
    bounds = tuple((peso_min, peso_max) for _ in range(n))
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


def calcular_frontera(ret_med, cov, rf, n, peso_min, peso_max, n_puntos=50):
    r_min = optimizar("minvol", n, ret_med, cov, rf, peso_min, peso_max)
    r_max = optimizar("maxret", n, ret_med, cov, rf, peso_min, peso_max)
    ret_min, _ = estadisticas(r_min.x, ret_med, cov)
    ret_max, _ = estadisticas(r_max.x, ret_med, cov)
    vols, rets = [], []
    for r in np.linspace(ret_min, ret_max, n_puntos):
        res = optimizar("minvol", n, ret_med, cov, rf, peso_min, peso_max, ret_obj=r)
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
            range=[0, min(max(pesos_f) + 15, 100)],
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
    peso_max = st.slider("Peso máximo por activo (%)", 10, 100, 100, step=5) / 100

    if peso_max < peso_min:
        st.warning("⚠️ El peso máximo no puede ser menor al mínimo. Se ajustará automáticamente.")
        peso_max = peso_min

    n_sim = st.select_slider("Portafolios a simular", options=[1000, 2000, 5000, 10000], value=5000)

    st.write("")
    run = st.button("⚡ OPTIMIZAR", use_container_width=True, type="primary")


# ── MAIN ──
st.markdown(
    "<p style='font-size:1.1rem; font-weight:600; margin-bottom:0;'>🌐 <a href='https://gfinversiones.com/' target='_blank' style='color:#1a56db; text-decoration:none;'>www.gfinversiones.com</a></p>",
    unsafe_allow_html=True,
)
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

# Validar que peso_max * n >= 1 (factibilidad)
if peso_max * n < 1.0:
    st.error(
        f"⚠️ Con {n} activos y peso máximo de {peso_max*100:.0f}%, "
        f"la suma máxima posible es {peso_max*n*100:.0f}% < 100%. "
        "Aumentá el peso máximo o reducí el número de activos."
    )
    st.stop()

with st.spinner(f"⚙️ Simulando {n_sim:,} portafolios..."):
    rng   = np.random.default_rng(42)
    w_all = rng.dirichlet(np.ones(n), size=n_sim)
    # Aplicar restricciones de min y max
    w_all = np.clip(w_all, peso_min, peso_max)
    w_all = w_all / w_all.sum(axis=1, keepdims=True)
    p_rets    = (w_all @ ret_med) * 252
    p_vols    = np.sqrt(np.einsum("ij,jk,ik->i", w_all, cov * 252, w_all))
    p_sharpes = (p_rets - rf) / p_vols

with st.spinner("📐 Calculando frontera eficiente..."):
    fe_vols, fe_rets = calcular_frontera(ret_med, cov, rf, n, peso_min, peso_max, n_puntos=50)

with st.spinner("⭐ Optimizando portafolios..."):
    res_sharpe = optimizar("sharpe", n, ret_med, cov, rf, peso_min, peso_max)
    res_minvol = optimizar("minvol", n, ret_med, cov, rf, peso_min, peso_max)
    ret_s, vol_s   = estadisticas(res_sharpe.x, ret_med, cov)
    ret_mv, vol_mv = estadisticas(res_minvol.x, ret_med, cov)
    sr_s = (ret_s - rf) / vol_s
    ret_o, vol_o, pesos_o = None, None, None
    if usar_obj and ret_obj is not None:
        res_obj = optimizar("minvol", n, ret_med, cov, rf, peso_min, peso_max, ret_obj=ret_obj)
        if res_obj.success:
            ret_o, vol_o = estadisticas(res_obj.x, ret_med, cov)
            pesos_o = res_obj.x


tab_fe, tab_comp, tab_metricas, tab_corr, tab_desemp, tab_riesgo = st.tabs(["📊 Frontera Eficiente", "🏦 Composición", "📐 Indicadores", "🔗 Correlación", "🚀 Desempeño", "⚠️ Riesgo (VaR)"])


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

    def render_portafolio_card(col, p, rf, tickers_ok):
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

    # Portafolio objetivo: fila propia a ancho completo para que nunca se comprima
    if ret_o is not None:
        p_obj = {"label": f"🎯 Objetivo {ret_obj*100:.1f}%", "pesos": pesos_o,
                 "ret": ret_o, "vol": vol_o, "color": "#2e7d32"}
        col_full, _ = st.columns([1, 1])
        render_portafolio_card(col_full, p_obj, rf, tickers_ok)
        st.divider()

    # Sharpe y Mín. Volatilidad siempre lado a lado
    col_s, col_mv = st.columns(2)
    render_portafolio_card(col_s, {"label": "⭐ Sharpe Óptimo", "pesos": res_sharpe.x,
                                   "ret": ret_s, "vol": vol_s, "color": "#b8860b"}, rf, tickers_ok)
    render_portafolio_card(col_mv, {"label": "🔴 Mín. Volatilidad", "pesos": res_minvol.x,
                                    "ret": ret_mv, "vol": vol_mv, "color": "#c62828"}, rf, tickers_ok)


# ── TAB 3: MÉTRICAS COMPARATIVAS ──
with tab_metricas:
    st.subheader("Métricas Comparativas")

    # ── Helpers ──
    def cagr(precio_serie, años_hist):
        """CAGR desde el primer precio disponible al último."""
        serie = precio_serie.dropna()
        if len(serie) < 2:
            return np.nan
        n_years = len(serie) / 252
        return (serie.iloc[-1] / serie.iloc[0]) ** (1 / n_years) - 1

    def retorno_12m(precio_serie):
        """Retorno simple de los últimos 252 días hábiles."""
        serie = precio_serie.dropna()
        if len(serie) < 252:
            return (serie.iloc[-1] / serie.iloc[0]) - 1
        return (serie.iloc[-1] / serie.iloc[-252]) - 1

    def beta_vs(ret_portafolio, ret_benchmark):
        """Beta del portafolio respecto a un benchmark."""
        rets_p = ret_portafolio.dropna()
        rets_b = ret_benchmark.dropna()
        comun  = rets_p.index.intersection(rets_b.index)
        if len(comun) < 20:
            return np.nan
        rp = rets_p.loc[comun].values
        rb = rets_b.loc[comun].values
        cov_pb = np.cov(rp, rb)[0, 1]
        var_b  = np.var(rb)
        return cov_pb / var_b if var_b > 1e-12 else np.nan

    # ── Descargar benchmarks SPY y QQQ ──
    with st.spinner("Descargando benchmarks SPY / QQQ..."):
        bench_tickers = ["SPY", "QQQ"]
        df_bench_raw = descargar_datos(bench_tickers, años)

    spy_prices = df_bench_raw["SPY"] if "SPY" in df_bench_raw.columns else None
    qqq_prices = df_bench_raw["QQQ"] if "QQQ" in df_bench_raw.columns else None
    spy_rets   = np.log(spy_prices / spy_prices.shift(1)).dropna() if spy_prices is not None else None
    qqq_rets   = np.log(qqq_prices / qqq_prices.shift(1)).dropna() if qqq_prices is not None else None

    # ── Función: métricas de un portafolio dado sus pesos ──
    def metricas_portfolio(pesos_w, nombre):
        precio_sim = (df * pesos_w).sum(axis=1)
        ret_log_p  = np.log(precio_sim / precio_sim.shift(1)).dropna()

        ret_anual  = float(np.dot(pesos_w, ret_med) * 252)
        vol_anual  = float(np.sqrt(np.dot(pesos_w.T, np.dot(cov * 252, pesos_w))))
        sharpe_r   = (ret_anual - rf) / vol_anual
        cagr_v     = cagr(precio_sim, años)
        ret12m     = retorno_12m(precio_sim)
        beta_spy   = beta_vs(ret_log_p, spy_rets) if spy_rets is not None else np.nan
        beta_qqq   = beta_vs(ret_log_p, qqq_rets) if qqq_rets is not None else np.nan

        return {
            "Portfolio":        nombre,
            "Retorno Anual (%)": round(ret_anual * 100, 2),
            "Volatilidad (%)":   round(vol_anual * 100, 2),
            "Sharpe":            round(sharpe_r, 2),
            "CAGR (%)":          round(cagr_v   * 100, 2) if not np.isnan(cagr_v)   else None,
            "Retorno 12m (%)":   round(ret12m   * 100, 2) if not np.isnan(ret12m)   else None,
            "Beta SPY":          round(beta_spy,  2)       if not np.isnan(beta_spy)  else None,
            "Beta QQQ":          round(beta_qqq,  2)       if not np.isnan(beta_qqq)  else None,
        }

    # ── Métricas de benchmarks ──
    def metricas_bench(prices, rets, nombre):
        if prices is None:
            return None
        ret_anual = float(rets.mean() * 252)
        vol_anual = float(rets.std()  * np.sqrt(252))
        sharpe_r  = (ret_anual - rf) / vol_anual
        cagr_v    = cagr(prices, años)
        ret12m    = retorno_12m(prices)
        return {
            "Portfolio":        nombre,
            "Retorno Anual (%)": round(ret_anual * 100, 2),
            "Volatilidad (%)":   round(vol_anual * 100, 2),
            "Sharpe":            round(sharpe_r, 2),
            "CAGR (%)":          round(cagr_v * 100, 2) if not np.isnan(cagr_v) else None,
            "Retorno 12m (%)":   round(ret12m  * 100, 2) if not np.isnan(ret12m) else None,
            "Beta SPY":          1.00 if nombre == "SPY" else None,
            "Beta QQQ":          1.00 if nombre == "QQQ" else None,
        }

    # ── Armar tabla ──
    filas = []
    filas.append(metricas_portfolio(res_sharpe.x, "Sharpe Óptimo"))
    filas.append(metricas_portfolio(res_minvol.x, "Min Volatilidad"))
    if ret_o is not None and pesos_o is not None:
        filas.append(metricas_portfolio(pesos_o, f"Objetivo {ret_obj*100:.1f}%"))
    m_spy = metricas_bench(spy_prices, spy_rets, "SPY")
    m_qqq = metricas_bench(qqq_prices, qqq_rets, "QQQ")
    if m_spy: filas.append(m_spy)
    if m_qqq: filas.append(m_qqq)

    df_met = pd.DataFrame(filas).set_index("Portfolio")

    # ── Estilos con heat-map ──
    def colorear(val, col, df_vals):
        if pd.isna(val) or val is None:
            return ""
        serie = df_vals[col].dropna()
        if len(serie) == 0:
            return ""
        vmin, vmax = serie.min(), serie.max()
        rng = vmax - vmin if vmax != vmin else 1

        # Retorno, Sharpe, CAGR, Retorno 12m → verde=alto, rojo=bajo
        if col in ["Retorno Anual (%)", "Sharpe", "CAGR (%)", "Retorno 12m (%)"]:
            t = (val - vmin) / rng
            r = int(220 - t * 140)
            g = int(80  + t * 140)
            b = 80
        # Volatilidad → rojo=alta, verde=baja
        elif col == "Volatilidad (%)":
            t = (val - vmin) / rng
            r = int(80  + t * 140)
            g = int(220 - t * 140)
            b = 80
        # Beta → neutro amarillo cerca de 1
        else:
            dist = abs(val - 1.0)
            t = min(dist / 1.0, 1.0)
            r = int(255 * t)
            g = int(255 * (1 - t * 0.5))
            b = 80
        return f"background-color: rgba({r},{g},{b},0.55); font-weight: bold;"

    def aplicar_estilos(df_s):
        styled = pd.DataFrame("", index=df_s.index, columns=df_s.columns)
        for col in df_s.columns:
            for idx in df_s.index:
                val = df_s.loc[idx, col]
                styled.loc[idx, col] = colorear(val, col, df_s)
        return styled

    # Formateo para display
    df_display = df_met.copy()
    for col in df_display.columns:
        df_display[col] = df_display[col].apply(
            lambda x: f"{x:.2f}" if pd.notna(x) and x is not None else "None"
        )

    st.dataframe(
        df_met.style.apply(lambda _: aplicar_estilos(df_met), axis=None)
                    .format(lambda x: f"{x:.2f}" if isinstance(x, (int, float)) and pd.notna(x) else "—"),
        use_container_width=True,
        height=250,
    )

    st.markdown("""
**Interpretacion:**
- **Retorno Anual**: Rendimiento anualizado del portfolio
- **Volatilidad**: Desviación estándar anualizada (riesgo)
- **Sharpe**: Retorno ajustado por riesgo (mayor es mejor)
- **CAGR**: Tasa de crecimiento anual compuesta
- **Beta**: Sensibilidad respecto al benchmark
""")


# ── TAB 4: CORRELACIÓN ──
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

# ── TAB 5: DESEMPEÑO ──
with tab_desemp:
    st.subheader("Rendimientos Acumulados")

    # ── Precio base 100 para cada portafolio ──
    def precio_simulado(pesos_w):
        return (df * pesos_w).sum(axis=1)

    port_series = {
        "Sharpe Óptimo":   precio_simulado(res_sharpe.x),
        "Min Volatilidad": precio_simulado(res_minvol.x),
    }
    if ret_o is not None and pesos_o is not None:
        port_series[f"Objetivo {ret_obj*100:.1f}%"] = precio_simulado(pesos_o)

    # Benchmarks
    bench_series = {}
    with st.spinner("Cargando benchmarks..."):
        df_b = descargar_datos(["SPY", "QQQ"], años)
    if "SPY" in df_b.columns:
        bench_series["SPY"] = df_b["SPY"]
    if "QQQ" in df_b.columns:
        bench_series["QQQ"] = df_b["QQQ"]

    # ── GRÁFICO 1: Rendimientos Acumulados ──
    fig_acum = go.Figure()

    colores_port  = ["#1a56db", "#e53935", "#2e7d32", "#7209B7", "#F72585"]
    colores_bench = {"SPY": "#b8860b", "QQQ": "#e65c00"}

    for i, (nombre, serie) in enumerate(port_series.items()):
        base = serie.iloc[0]
        acum = (serie / base - 1) * 100
        fig_acum.add_trace(go.Scatter(
            x=acum.index, y=acum.values,
            mode="lines", name=nombre,
            line=dict(color=colores_port[i % len(colores_port)], width=2),
        ))

    for nombre, serie in bench_series.items():
        base = serie.iloc[0]
        acum = (serie / base - 1) * 100
        fig_acum.add_trace(go.Scatter(
            x=acum.index, y=acum.values,
            mode="lines", name=nombre,
            line=dict(color=colores_bench.get(nombre, "#999"), width=1.5, dash="dash"),
        ))

    fig_acum.update_layout(
        title="Rendimientos Acumulados: Portfolios vs Benchmarks",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="Fecha", gridcolor="rgba(128,128,128,0.15)"),
        yaxis=dict(title="Crecimiento Acumulado (%)", gridcolor="rgba(128,128,128,0.15)"),
        legend=dict(orientation="v", x=0.01, y=0.99, xanchor="left", yanchor="top",
                    bgcolor="rgba(0,0,0,0)"),
        height=480,
        margin=dict(l=10, r=10, t=50, b=40),
        hovermode="x unified",
    )
    st.plotly_chart(fig_acum, use_container_width=True)

    st.subheader("Comparativa CAGR")

    # ── GRÁFICO 2: CAGR por activo + portfolios + benchmarks ──
    def calc_cagr(serie):
        s = serie.dropna()
        if len(s) < 2:
            return np.nan
        n_y = len(s) / 252
        return ((s.iloc[-1] / s.iloc[0]) ** (1 / n_y) - 1) * 100

    nombres_bar, cagr_bar, colores_bar, tipos_bar = [], [], [], []

    # Activos individuales
    for t in tickers_ok:
        nombres_bar.append(t)
        cagr_bar.append(calc_cagr(df[t]))
        colores_bar.append("#1a56db")
        tipos_bar.append("Activo")

    # Portafolios
    color_port_bar = {"Sharpe Óptimo": "#F3722C", "Min Volatilidad": "#F3722C"}
    for nombre, serie in port_series.items():
        nombres_bar.append(nombre)
        cagr_bar.append(calc_cagr(serie))
        colores_bar.append("#F3722C")
        tipos_bar.append("Portfolio")

    # Benchmarks
    for nombre, serie in bench_series.items():
        nombres_bar.append(nombre)
        cagr_bar.append(calc_cagr(serie))
        colores_bar.append("#2e7d32")
        tipos_bar.append("Benchmark")

    df_cagr = pd.DataFrame({"Nombre": nombres_bar, "CAGR": cagr_bar, "Tipo": tipos_bar})

    color_map = {"Activo": "#1a56db", "Portfolio": "#F3722C", "Benchmark": "#2e7d32"}

    fig_cagr = go.Figure()
    for tipo, color in color_map.items():
        mask = df_cagr["Tipo"] == tipo
        fig_cagr.add_trace(go.Bar(
            x=df_cagr.loc[mask, "Nombre"],
            y=df_cagr.loc[mask, "CAGR"],
            name=tipo,
            marker_color=color,
            text=[f"{v:.1f}%" for v in df_cagr.loc[mask, "CAGR"]],
            textposition="outside",
            textfont=dict(size=10),
        ))

    fig_cagr.update_layout(
        title="Comparativa CAGR Anual",
        barmode="group",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="rgba(128,128,128,0.15)", tickangle=-30),
        yaxis=dict(title="CAGR Anual (%)", gridcolor="rgba(128,128,128,0.15)"),
        legend=dict(title="Tipo", orientation="v", x=0.99, y=0.99,
                    xanchor="right", yanchor="top", bgcolor="rgba(0,0,0,0)"),
        height=460,
        margin=dict(l=10, r=10, t=50, b=80),
    )
    st.plotly_chart(fig_cagr, use_container_width=True)


# ── TAB 6: RIESGO (VaR) ──
with tab_riesgo:
    from scipy.stats import norm as sp_norm

    st.subheader("Value at Risk (VaR) - 95% Confianza")

    CONFIANZA = 0.95
    Z = sp_norm.ppf(1 - CONFIANZA)   # -1.6449

    # ── Series de retornos diarios de cada portafolio ──
    def ret_diarios_port(pesos_w):
        precio = (df * pesos_w).sum(axis=1)
        return np.log(precio / precio.shift(1)).dropna()

    # Benchmarks (ya descargados en tab Desempeño, pero los recalculamos dentro del tab
    # para no depender del scope)
    with st.spinner("Calculando VaR..."):
        df_b2 = descargar_datos(["SPY", "QQQ"], años)

    spy_ret_d = np.log(df_b2["SPY"] / df_b2["SPY"].shift(1)).dropna() if "SPY" in df_b2.columns else None
    qqq_ret_d = np.log(df_b2["QQQ"] / df_b2["QQQ"].shift(1)).dropna() if "QQQ" in df_b2.columns else None

    # ── Armar lista de portfolios para la tabla ──
    portafolios_var = [
        ("Sharpe Óptimo",   ret_diarios_port(res_sharpe.x)),
        ("Min Volatilidad", ret_diarios_port(res_minvol.x)),
    ]
    if ret_o is not None and pesos_o is not None:
        portafolios_var.append((f"Objetivo {ret_obj*100:.1f}%", ret_diarios_port(pesos_o)))
    if spy_ret_d is not None:
        portafolios_var.append(("SPY", spy_ret_d))
    if qqq_ret_d is not None:
        portafolios_var.append(("QQQ", qqq_ret_d))

    def var_historico(rets, confianza=0.95):
        return -np.percentile(rets.values, (1 - confianza) * 100)

    # ── Tabla VaR ──
    filas_var = []
    for nombre, rets in portafolios_var:
        var1  = var_historico(rets) * 100
        var10 = var1 * np.sqrt(10)
        filas_var.append({"Portfolio": nombre,
                          "VaR 1 día (%)": round(var1, 2),
                          "VaR 10 días (%)": round(var10, 2)})

    df_var = pd.DataFrame(filas_var).set_index("Portfolio")

    def color_var(val, col, df_v):
        serie = df_v[col].dropna()
        if len(serie) == 0:
            return ""
        vmin, vmax = serie.min(), serie.max()
        rng = vmax - vmin if vmax != vmin else 1
        t = (val - vmin) / rng           # 0 = menor riesgo, 1 = mayor riesgo
        r = int(180 + t * 75)
        g = int(220 - t * 190)
        b = int(220 - t * 190)
        return f"background-color: rgba({r},{g},{b},0.75); font-weight: bold; text-align: center;"

    def estilo_var(df_s):
        out = pd.DataFrame("", index=df_s.index, columns=df_s.columns)
        for col in df_s.columns:
            for idx in df_s.index:
                out.loc[idx, col] = color_var(df_s.loc[idx, col], col, df_s)
        return out

    st.dataframe(
        df_var.style.apply(lambda _: estilo_var(df_var), axis=None)
                    .format("{:.2f}"),
        use_container_width=True,
        height=220,
    )

    # ── Histogramas por portafolio ──
    st.markdown("### Distribución de Retornos Diarios & VaR")

    colores_hist = {
        "Sharpe Óptimo":   "#1a56db",
        "Min Volatilidad": "#e53935",
        "SPY":             "#e6a817",
        "QQQ":             "#9c27b0",
    }
    if ret_o is not None and pesos_o is not None:
        colores_hist[f"Objetivo {ret_obj*100:.1f}%"] = "#2e7d32"

    # Mostrar histogramas en pares (2 por fila)
    items = portafolios_var
    for i in range(0, len(items), 2):
        cols_h = st.columns(2)
        for j, (nombre, rets) in enumerate(items[i:i+2]):
            var1 = var_historico(rets) * 100
            color = colores_hist.get(nombre, "#4CC9F0")

            rets_pct = rets.values * 100
            hist_vals, bin_edges = np.histogram(rets_pct, bins=60, density=True)
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

            # KDE suavizado
            from scipy.stats import gaussian_kde
            kde = gaussian_kde(rets_pct)
            x_kde = np.linspace(rets_pct.min(), rets_pct.max(), 300)
            y_kde = kde(x_kde)

            fig_h = go.Figure()
            fig_h.add_trace(go.Bar(
                x=bin_centers, y=hist_vals,
                marker_color=color, opacity=0.55,
                name="Frecuencia", showlegend=False,
                hovertemplate="Retorno: %{x:.2f}%<br>Densidad: %{y:.4f}<extra></extra>",
            ))
            fig_h.add_trace(go.Scatter(
                x=x_kde, y=y_kde, mode="lines",
                line=dict(color=color, width=2),
                name="KDE", showlegend=False,
            ))
            # Línea VaR
            fig_h.add_vline(
                x=-var1,
                line=dict(color=color, width=2, dash="dash"),
                annotation_text=f"VaR<br>{var1:.2f}%",
                annotation_position="top left",
                annotation_font=dict(color=color, size=11),
            )

            fig_h.update_layout(
                title=f"Retornos Diarios & VaR: {nombre}",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(title="Retorno Diario (%)", gridcolor="rgba(128,128,128,0.15)"),
                yaxis=dict(title="Densidad", gridcolor="rgba(128,128,128,0.15)"),
                height=320,
                margin=dict(l=10, r=10, t=45, b=40),
            )
            with cols_h[j]:
                st.plotly_chart(fig_h, use_container_width=True)

    # ── Interpretación ──
    st.info("""
**Cómo interpretar cada gráfico:**
- Cada histograma muestra la frecuencia de retornos diarios del portfolio.
- La línea discontinua marca el **Value at Risk (VaR)** al 95%.
- Hay solo un 5% de chances de que la pérdida diaria sea peor que ese valor.
- Ejemplo: si el VaR es 2.5%, con 95% de confianza NO se espera perder más de 2.5% en un solo día.
""")


st.caption(
    "Datos: Yahoo Finance · Optimización: SciPy SLSQP · Teoría: Markowitz (1952) — "
    "Este análisis es educativo y no constituye asesoramiento financiero."
)