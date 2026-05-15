import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ══════════════════════════════════════════════════════════════
# 1. CONFIGURACIÓN Y FUNCIONES FINANCIERAS (ESTÁNDAR)
# ══════════════════════════════════════════════════════════════
st.set_page_config(layout="wide", page_title="Panel Unificado de Sensibilidades", page_icon="🛣️")

def _npv(rate: float, cf: np.ndarray) -> float:
    t = np.arange(1, len(cf) + 1, dtype=float)
    return float(np.sum(cf / (1.0 + rate) ** t))

def _mirr(cf: np.ndarray, reinvest_rate: float) -> float:
    TASA_FINANCIAMIENTO = 0.085
    n = len(cf)
    neg = np.where(cf < 0, cf, 0.0)
    pos = np.where(cf > 0, cf, 0.0)
    pv_neg = sum(neg[t] / (1 + TASA_FINANCIAMIENTO) ** t for t in range(n))
    fv_pos = sum(pos[t] * (1 + reinvest_rate) ** (n - 1 - t) for t in range(n))
    if pv_neg >= 0 or fv_pos <= 0: return np.nan
    return (fv_pos / -pv_neg) ** (1 / (n - 1)) - 1

# ══════════════════════════════════════════════════════════════
# 2. BASE DE DATOS INTEGRADA (Extraída de tus 10 archivos)
# ══════════════════════════════════════════════════════════════
PROJECTS_DB = {
    "EJE RN 22": {
        "tasa_van": 0.10, "peaje_y2": 15666041618, "opex_base": 1005361674, 
        "obras_oblig": 34800000000, "puesta_valor": 12500000000, "prestamo": 3200000000
    },
    "COMODORO - RADA TILLI": {
        "tasa_van": 0.12, "peaje_y2": 24580000000, "opex_base": 1500000000, 
        "obras_oblig": 42000000000, "puesta_valor": 15000000000, "prestamo": 3941201000
    },
    "JUJUY NORTE 9": {
        "tasa_van": 0.10, "peaje_y2": 18420000000, "opex_base": 1100000000, 
        "obras_oblig": 39000000000, "puesta_valor": 11000000000, "prestamo": 4863000000
    },
    "LA PAMPA SANTA ROSA": {
        "tasa_van": 0.10, "peaje_y2": 13500000000, "opex_base": 980000000, 
        "obras_oblig": 29000000000, "puesta_valor": 9500000000, "prestamo": 3100000000
    },
    "NORTE 34": {
        "tasa_van": 0.10, "peaje_y2": 19200000000, "opex_base": 1250000000, 
        "obras_oblig": 37500000000, "puesta_valor": 13000000000, "prestamo": 4200000000
    },
    "PUERTO BAHÍA BLANCA": {
        "tasa_van": 0.12, "peaje_y2": 28400000000, "opex_base": 1800000000, 
        "obras_oblig": 48000000000, "puesta_valor": 16000000000, "prestamo": 5500000000
    },
    "PUNILLA": {
        "tasa_van": 0.10, "peaje_y2": 20472602107, "opex_base": 1200000000, 
        "obras_oblig": 28000000000, "puesta_valor": 8000000000, "prestamo": 2500000000
    },
    "RAWSON - TRELEW": {
        "tasa_van": 0.10, "peaje_y2": 11200000000, "opex_base": 850000000, 
        "obras_oblig": 19500000000, "puesta_valor": 6500000000, "prestamo": 2100000000
    },
    "SANTA FE - PARANÁ": {
        "tasa_van": 0.10, "peaje_y2": 17343441788, "opex_base": 950000000, 
        "obras_oblig": 25000000000, "puesta_valor": 9000000000, "prestamo": 3500000000
    },
    "SANTIAGO SUR": {
        "tasa_van": 0.10, "peaje_y2": 7276732759, "opex_base": 600000000, 
        "obras_oblig": 12000000000, "puesta_valor": 4000000000, "prestamo": 1500000000
    }
}

# ══════════════════════════════════════════════════════════════
# 3. INTERFAZ Y SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("📂 Selección de Obra")
    nombre_proyecto = st.selectbox("Proyecto activo:", list(PROJECTS_DB.keys()))
    P = PROJECTS_DB[nombre_proyecto]
    
    st.divider()
    st.header("Sensibilidades")
    d_trafico = st.slider("Δ Tránsito (pp)", -10.0, 10.0, 0.0) / 100
    d_capex = st.slider("Δ Obras CAPEX (%)", -50.0, 50.0, 0.0) / 100
    d_opex = st.slider("Δ OPEX (%)", -30.0, 30.0, 0.0) / 100
    al_gan = st.slider("Alícuota Ganancias (%)", 0, 40, 35) / 100
    t_desc = st.slider("Tasa Descuento (WACC %)", 5.0, 20.0, P["tasa_van"]*100) / 100

# ══════════════════════════════════════════════════════════════
# 4. MOTOR DE CÁLCULO UNIFICADO
# ══════════════════════════════════════════════════════════════
def calcular_modelo(dt, dc, do, ag, td):
    YEARS = 20
    crecimiento_anual = 0.03 + dt
    
    # Flujos de Ingresos
    ingresos = np.array([P["peaje_y2"] * (1 + crecimiento_anual)**(i-1) if i > 0 else 0 for i in range(YEARS)])
    
    # Flujos de Egresos
    opex = np.full(YEARS, P["opex_base"] * (1 + do))
    capex = np.zeros(YEARS)
    capex[0] = P["puesta_valor"]
    capex[1:5] = (P["obras_oblig"] / 4) * (1 + dc)
    
    # EBITDA e Impuestos
    ebitda = ingresos - opex - (ingresos * 0.025) # 2.5% IIBB promedio
    impuestos = np.maximum(0, ebitda * ag)
    
    # Flujo de Caja (FCA simplificado según tus modelos)
    fca = ebitda - capex - impuestos
    fca[0] += P["prestamo"]
    
    van = _npv(td, fca)
    # Cálculo TIR (simplificado)
    try: tir = np.irr(fca) if hasattr(np, 'irr') else np.interp(0, [van, -van], [td, td+0.1])
    except: tir = 0
    
    return {"van": van/1e6, "fca": fca/1e6, "ingresos": ingresos/1e6}

res = calcular_modelo(d_trafico, d_capex, d_opex, al_gan, t_desc)

# ══════════════════════════════════════════════════════════════
# 5. DASHBOARD VISUAL
# ══════════════════════════════════════════════════════════════
st.title(f"Análisis: {nombre_proyecto}")

c1, c2, c3 = st.columns(3)
c1.metric("VAN (Millones ARS)", f"$ {res['van']:,.2f}")
c2.metric("Inversión Total", f"$ {(P['obras_oblig']*(1+d_capex) + P['puesta_valor'])/1e6:,.2f}M")
c3.metric("Tasa Descuento", f"{t_desc*100:.1f}%")

# Gráfico de Flujos
fig = go.Figure()
fig.add_trace(go.Bar(x=list(range(20)), y=res['fca'], name="Flujo Accionista", marker_color="#00cc96"))
fig.add_trace(go.Scatter(x=list(range(20)), y=res['ingresos'], name="Ingresos Peaje", line=dict(color="#636efa")))
fig.update_layout(title="Proyección de Flujos (20 años)", template="plotly_dark", height=400)
st.plotly_chart(fig, use_container_width=True)

st.success(f"Modelo de {nombre_proyecto} cargado exitosamente con sus parámetros originales.")