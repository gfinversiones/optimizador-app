"""
Panel Multi-Proyectos – Análisis de Sensibilidades Financieras
==============================================================
Concesión vial 20 años (2026-2045).
Seleccioná el proyecto con los botones superiores.
Los flujos base se leen de los xlsx; las sensibilidades se aplican en tiempo real.

Instalación:
    pip install streamlit pandas plotly numpy

Ejecución:
    streamlit run modelo_multiproyecto.py
"""

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ══════════════════════════════════════════════════════════════
# 0.  FUNCIONES FINANCIERAS PURAS
# ══════════════════════════════════════════════════════════════

def _npv(rate: float, cf: np.ndarray) -> float:
    t = np.arange(1, len(cf) + 1, dtype=float)
    return float(np.sum(cf / (1.0 + rate) ** t))

TASA_FINANCIAMIENTO = 0.085

def _mirr(cf: np.ndarray, reinvest_rate: float) -> float:
    n = len(cf)
    finance_rate = TASA_FINANCIAMIENTO
    neg = np.where(cf < 0, cf, 0.0)
    pos = np.where(cf > 0, cf, 0.0)
    pv_neg = sum(neg[t] / (1 + finance_rate) ** t       for t in range(n))
    fv_pos = sum(pos[t] * (1 + reinvest_rate) ** (n-1-t) for t in range(n))
    if pv_neg >= 0 or fv_pos <= 0:
        return float("nan")
    return (fv_pos / (-pv_neg)) ** (1.0 / (n - 1)) - 1.0


# ══════════════════════════════════════════════════════════════
# 1.  DATOS BASE POR PROYECTO
# ══════════════════════════════════════════════════════════════
# Todos los arrays tienen 21 elementos: índice 0 = Y0, índices 1..20 = Años concesión 1-20.
# Para CAUCETE, Y0 es la puesta en valor previa (antes de iniciar la concesión).
# Para el resto, la puesta en valor cae en Y1 (primer año de concesión).
#
# IMPORTANTE: se usan los valores del xlsx tal como están en las hojas CAPEX, OPEX y FLUJO.
# NO se analizan las hojas INPUTS, WACC, GRAFICO.

PROYECTOS = {}

# ── CAUCETE ───────────────────────────────────────────────────
PROYECTOS["CAUCETE"] = {
    "label": "CAUCETE",
    "TARIFA_BASE": 6_000.0,
    "TRAFICO_CRECIMIENTO": 0.03,
    "AL_GANANCIAS": 0.35, "AL_IB": 0.025, "AL_MUNICIPAL": 0.005,
    "AL_SELLOS": 0.012, "AL_DBCR": 0.012, "AL_IVA": 0.21,
    "TASA_VAN": 0.10,
    "PEAJE": np.array([
        0, 24_541_041_681.62, 25_277_272_932.07, 26_035_591_120.03,
        26_816_658_853.63, 27_621_158_619.24, 28_449_793_377.82,
        29_303_287_179.15, 30_182_385_794.53, 31_087_857_368.36,
        32_020_493_089.41, 32_981_107_882.10, 33_970_541_118.56,
        34_989_657_352.12, 36_039_347_072.68, 37_120_527_484.86,
        38_234_143_309.40, 39_381_167_608.69, 40_562_602_636.95,
        41_779_480_716.06, 41_779_480_716.06,
    ], dtype=float),
    "PUESTA": np.array([2_890_357_500.0] + [0]*20, dtype=float),
    "OBRAS": np.array([
        0,0,0,0,0,0,
        5_702_850_000, 11_405_700_000, 11_405_700_000, 11_405_700_000,
        11_405_700_000, 17_108_550_000, 11_405_700_000, 11_405_700_000,
        11_405_700_000, 5_702_850_000, 5_702_850_000, 0, 0, 0, 0,
    ], dtype=float),
    "REPAV": np.array([
        0,0,0,
        4_335_536_250, 4_335_536_250, 4_335_536_250,
        8_671_072_500, 8_671_072_500, 8_671_072_500,
        1_734_214_500, 0, 0, 0,
        4_335_536_250, 4_335_536_250, 4_335_536_250,
        4_335_536_250, 8_671_072_500, 8_671_072_500, 8_671_072_500, 8_671_072_500,
    ], dtype=float),
    "OPEX": np.full(21, 3_853_810_000.00),
    "AMORT_DEUDA": np.array([
        0, 464_552_590.09, 444_320_087.59, 444_320_087.59,
        444_320_087.59, 444_320_087.59, 444_320_087.59,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    ], dtype=float),
    "GARANTIAS": np.full(21, 28_000_000.0),
    "CREDITO_LP": np.array([2_023_250_250.0] + [0]*20, dtype=float),
    "IMP_IVA": np.array([
        0, 2_656_972_281.01, 3_832_134_507.98, 3_220_383_801.65,
        3_365_802_350.98, 3_516_125_830.45, 1_929_348_223.21,
        1_093_765_562.35, 1_246_336_396.43, 2_607_401_859.65,
        3_070_243_633.56, 2_247_211_076.91, 3_408_681_721.26,
        2_833_104_693.61, 3_015_282_248.42, 4_192_675_956.32,
        4_385_948_124.22, 4_822_320_843.51, 5_027_363_286.43,
        5_238_557_002.64, 5_238_557_002.64,
    ], dtype=float),
    "IMP_GAN": np.array([
        0, 3_901_238_045.30, 5_527_661_023.34, 5_495_218_647.32,
        5_469_810_984.91, 5_591_266_769.29, 5_212_052_382.37,
        4_958_490_406.28, 4_950_638_227.15, 5_351_380_801.76,
        5_859_957_421.65, 6_627_083_002.42, 7_402_173_381.82,
        7_934_651_357.11, 8_074_273_352.54, 8_122_272_239.79,
        8_116_531_541.40, 7_597_490_588.60, 6_920_749_257.43,
        4_999_722_890.45, 4_999_722_890.45,
    ], dtype=float),
    "IMP_IB": np.array([
        0, 507_046_315.74, 522_257_705.21, 537_925_436.36,
        554_063_199.46, 570_685_095.44, 587_805_648.30, 605_439_817.75,
        623_603_012.28, 642_311_102.65, 661_580_435.73, 681_427_848.80,
        701_870_684.27, 722_926_804.80, 744_614_608.94, 766_953_047.21,
        789_961_638.62, 813_660_487.78, 838_070_302.42, 863_212_411.49,
        863_212_411.49,
    ], dtype=float),
    "IMP_MUN": np.array([
        0, 101_409_263.15, 104_451_541.04, 107_585_087.27,
        110_812_639.89, 114_137_019.09, 117_561_129.66, 121_087_963.55,
        124_720_602.46, 128_462_220.53, 132_316_087.15, 136_285_569.76,
        140_374_136.85, 144_585_360.96, 148_922_921.79, 153_390_609.44,
        157_992_327.72, 162_732_097.56, 167_614_060.48, 172_642_482.30,
        172_642_482.30,
    ], dtype=float),
    "IMP_SEL": np.array([
        398_790_269.26, 398_790_269.26, 398_790_269.26,
        398_790_269.26, 398_790_269.26,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    ], dtype=float),
    "IMP_DBCR": np.array([
        24_279_003.00, 294_492_500.18, 303_327_275.18, 312_427_093.44,
        321_799_906.24, 331_453_903.43, 341_397_520.53, 351_639_446.15,
        362_188_629.53, 373_054_288.42, 384_245_917.07, 395_773_294.59,
        407_646_493.42, 419_875_888.23, 432_472_164.87, 445_446_329.82,
        458_809_719.71, 472_574_011.30, 486_751_231.64, 501_353_768.59,
        501_353_768.59,
    ], dtype=float),
}

# ── Helper para cargar proyectos desde los xlsx ───────────────
def _load_project_from_xlsx(fname: str, label: str) -> dict:
    """Lee CAPEX, OPEX y FLUJO del xlsx y devuelve dict de datos del proyecto."""
    import pandas as pd

    def safe_row(df, row_idx, cols):
        row = df.iloc[row_idx]
        vals = []
        for j in cols:
            try:
                v = row[j]
                vals.append(float(v) if pd.notna(v) else 0.0)
            except Exception:
                vals.append(0.0)
        return np.array(vals)

    def last_match(df, lbl, cols):
        found = []
        for _, row in df.iterrows():
            if str(row[1]).strip() == lbl:
                vals = []
                for j in cols:
                    try:
                        v = row[j]
                        vals.append(float(v) if pd.notna(v) else 0.0)
                    except Exception:
                        vals.append(0.0)
                found.append(np.array(vals))
        return found[-1] if found else np.zeros(len(cols))

    # CAPEX: año de concesión 1..20 en cols 3..22 → model Y1..Y20 (prepend 0 for Y0)
    cx = pd.read_excel(fname, sheet_name="CAPEX", header=None)
    cx_cols = list(range(3, 23))
    puesta = np.concatenate([[0.0], safe_row(cx, 16, cx_cols)])
    obras  = np.concatenate([[0.0], safe_row(cx, 17, cx_cols)])
    repav  = np.concatenate([[0.0], safe_row(cx, 18, cx_cols)])

    # OPEX: año 1..20 en cols 4..23
    ox = pd.read_excel(fname, sheet_name="OPEX", header=None)
    ox_cols = list(range(4, 24))
    opex = np.concatenate([[0.0], safe_row(ox, 22, ox_cols)])

    # FLUJO: Y0..Y20 en cols 2..22
    fl = pd.read_excel(fname, sheet_name="FLUJO", header=None)
    fl_cols = list(range(2, 23))

    peaje_e = last_match(fl, "Peajes existentes", fl_cols)
    peaje_n = last_match(fl, "Peajes nuevos",     fl_cols)
    peaje_s = last_match(fl, "Peajes",             fl_cols)
    peaje   = peaje_e + peaje_n if (peaje_e + peaje_n).sum() > 0 else peaje_s

    credito_lp  = last_match(fl, "Ingresos Crédito LP",                fl_cols)
    amort_deuda = last_match(fl, "Amortización de la deuda",            fl_cols)
    garantias   = last_match(fl, "GARANTÍAS",                           fl_cols)
    imp_iva     = last_match(fl, "IVA Saldo a Pagar",                   fl_cols)
    imp_gan     = last_match(fl, "Impuesto a las Ganancias",            fl_cols)
    imp_ib      = last_match(fl, "Impuesto a los Ingresos Brutos",      fl_cols)
    imp_mun     = last_match(fl, "Impuestos Municipales",               fl_cols)
    imp_sel     = last_match(fl, "Impuesto de Sellos",                  fl_cols)
    imp_dbcr    = last_match(fl, "Impuesto a los Débitos y Créditos",   fl_cols)

    # Limpieza: el col22 de FLUJO puede contener un total acumulado → forzar Y20 con extrapolación
    # Si el último elemento parece un total (> 10× el penúltimo), usar el penúltimo
    def fix_total_col(arr):
        if len(arr) == 21 and arr[20] != 0 and arr[19] != 0:
            ratio = abs(arr[20] / arr[19]) if arr[19] != 0 else 0
            if ratio > 5:
                arr = arr.copy()
                arr[20] = arr[19]
        return arr

    amort_deuda = fix_total_col(amort_deuda)
    imp_gan     = fix_total_col(imp_gan)
    imp_ib      = fix_total_col(imp_ib)
    credito_lp  = fix_total_col(credito_lp)

    return {
        "label": label,
        "TARIFA_BASE": 6_000.0,
        "TRAFICO_CRECIMIENTO": 0.03,
        "AL_GANANCIAS": 0.35, "AL_IB": 0.025, "AL_MUNICIPAL": 0.005,
        "AL_SELLOS": 0.012, "AL_DBCR": 0.012, "AL_IVA": 0.21,
        "TASA_VAN": 0.10,
        "PEAJE": peaje, "PUESTA": puesta, "OBRAS": obras, "REPAV": repav,
        "OPEX": opex, "AMORT_DEUDA": amort_deuda, "GARANTIAS": garantias,
        "CREDITO_LP": credito_lp,
        "IMP_IVA": imp_iva, "IMP_GAN": imp_gan, "IMP_IB": imp_ib,
        "IMP_MUN": imp_mun, "IMP_SEL": imp_sel, "IMP_DBCR": imp_dbcr,
    }


# ── Registrar proyectos desde xlsx ───────────────────────────
_XLSX_PROJECTS = [
    ("COMODORO",        "COMODORO_-_RADA_-_TILLI.xlsx",  "COMODORO RADA TILLI"),
    ("CORDOBA_NORTE",   "CORDOBA_NORTE.xlsx",             "CÓRDOBA NORTE"),
    ("EJE_RN_22",       "EJE_RN_Nª_22.xlsx",             "EJE RN N° 22"),
    ("JUJUY_NORTE",     "JUJUY_NORTE_9.xlsx",             "JUJUY NORTE 9"),
    ("LA_PAMPA",        "LA_PAMPA_SANTA_ROSA.xlsx",       "LA PAMPA SANTA ROSA"),
    ("NORTE_34",        "NORTE_34.xlsx",                  "NORTE 34"),
    ("PUNILLA",         "PUNILLA.xlsx",                   "PUNILLA"),
    ("RAWSON",          "RAWSON_TRELEW_GAIMAN.xlsx",      "RAWSON TRELEW GAIMAN"),
    ("SANTA_FE",        "SANTA_FE_-_PARANA.xlsx",         "SANTA FE PARANÁ"),
    ("SANTIAGO_SUR",    "SANTIAGO_SUR.xlsx",              "SANTIAGO SUR"),
    ("TUNUYAN",         "TUNUYAN.xlsx",                   "TUNUYÁN"),
]

@st.cache_data(show_spinner=False)
def _load_all_xlsx():
    import os
    data = {}
    for key, fname, label in _XLSX_PROJECTS:
        path = fname  # assumes same directory; adjust if needed
        if os.path.exists(path):
            try:
                data[key] = _load_project_from_xlsx(path, label)
            except Exception as e:
                st.warning(f"No se pudo cargar {label}: {e}")
    return data

_loaded = _load_all_xlsx()
for key, d in _loaded.items():
    PROYECTOS[key] = d

PROJECT_KEYS   = list(PROYECTOS.keys())
PROJECT_LABELS = [PROYECTOS[k]["label"] for k in PROJECT_KEYS]


# ══════════════════════════════════════════════════════════════
# 2.  MODELO DE SENSIBILIDAD (genérico, recibe datos del proyecto)
# ══════════════════════════════════════════════════════════════

YEARS = 20
AL_IVA_GASTOS_BASE = 0.11

def run_model(
    P: dict,                    # datos del proyecto activo
    delta_capex_obras = 0.0,
    delta_capex_repav = 0.0,
    delta_opex        = 0.0,
    delta_trafico     = 0.0,
    tarifa            = None,
    al_ganancias      = 0.35,
    al_ib             = 0.025,
    al_municipal      = 0.005,
    al_sellos         = 0.012,
    al_dbcr           = 0.012,
    al_iva_peaje      = 0.21,
    tasa_van          = 0.10,
):
    if tarifa is None:
        tarifa = P["TARIFA_BASE"]

    TARIFA_BASE          = P["TARIFA_BASE"]
    TRAFICO_BASE         = P["TRAFICO_CRECIMIENTO"]
    PEAJE_BASE           = P["PEAJE"]
    PUESTA_VALOR         = P["PUESTA"]
    OBRAS_OBLIG          = P["OBRAS"]
    REPAV                = P["REPAV"]
    OPEX_BASE            = P["OPEX"]
    AMORT_DEUDA_BASE     = P["AMORT_DEUDA"]
    GARANTIAS            = P["GARANTIAS"]
    CREDITO_LP           = P["CREDITO_LP"]
    IMP_IVA_BASE         = P["IMP_IVA"]
    IMP_GANANCIAS_BASE   = P["IMP_GAN"]
    IMP_IB_BASE          = P["IMP_IB"]
    IMP_MUNICIPAL_BASE   = P["IMP_MUN"]
    IMP_SELLOS_BASE      = P["IMP_SEL"]
    IMP_DBCR_BASE        = P["IMP_DBCR"]
    AL_GANANCIAS_BASE    = P["AL_GANANCIAS"]
    AL_IB_BASE           = P["AL_IB"]
    AL_MUNICIPAL_BASE    = P["AL_MUNICIPAL"]
    AL_SELLOS_BASE       = P["AL_SELLOS"]
    AL_DBCR_BASE         = P["AL_DBCR"]
    AL_IVA_BASE          = P["AL_IVA"]

    # ── Tráfico ────────────────────────────────────────────────
    tarifa_iva = TARIFA_BASE * (1 + AL_IVA_BASE)
    UTEQ_ARRANQUE = PEAJE_BASE[1] / tarifa_iva if tarifa_iva > 0 else 0.0

    uteq = np.zeros(YEARS + 1)
    tasa_eff = max(TRAFICO_BASE + delta_trafico, -0.50)
    uteq[1] = UTEQ_ARRANQUE
    for y in range(2, YEARS + 1):
        uteq[y] = uteq[y - 1] * (1 + tasa_eff)

    tarifa_con_iva = tarifa * (1 + al_iva_peaje)
    peaje = np.zeros(YEARS + 1)
    for y in range(1, YEARS + 1):
        peaje[y] = uteq[y] * tarifa_con_iva

    # Factor tráfico para escalar impuestos
    uteq_ref = np.zeros(YEARS + 1)
    for y in range(1, YEARS + 1):
        uteq_base_y = UTEQ_ARRANQUE * ((1 + TRAFICO_BASE) ** (y - 1))
        uteq_ref[y] = uteq[y] / uteq_base_y if uteq_base_y > 0 else 1.0

    total_ingresos = peaje + CREDITO_LP

    # ── CAPEX ──────────────────────────────────────────────────
    capex = (PUESTA_VALOR
             + OBRAS_OBLIG * (1 + delta_capex_obras)
             + REPAV       * (1 + delta_capex_repav))

    # ── OPEX ───────────────────────────────────────────────────
    opex = OPEX_BASE * (1 + delta_opex)

    # ── Impuestos ──────────────────────────────────────────────
    factor_tarifa      = tarifa / TARIFA_BASE
    factor_trafico_avg = uteq_ref * factor_tarifa

    imp_iva       = IMP_IVA_BASE      * factor_trafico_avg * ((1 + al_iva_peaje) / (1 + AL_IVA_BASE))
    imp_ib        = IMP_IB_BASE       * factor_trafico_avg * (al_ib       / AL_IB_BASE       if AL_IB_BASE       > 0 else 1)
    imp_municipal = IMP_MUNICIPAL_BASE* factor_trafico_avg * (al_municipal / AL_MUNICIPAL_BASE if AL_MUNICIPAL_BASE > 0 else 1)
    imp_sellos    = IMP_SELLOS_BASE   * (al_sellos / AL_SELLOS_BASE if AL_SELLOS_BASE > 0 else 1)
    imp_dbcr      = IMP_DBCR_BASE     * factor_trafico_avg * (al_dbcr     / AL_DBCR_BASE     if AL_DBCR_BASE     > 0 else 1)
    imp_dbcr[0]   = IMP_DBCR_BASE[0] * (al_dbcr / AL_DBCR_BASE if AL_DBCR_BASE > 0 else 1)

    # ── Ganancias ──────────────────────────────────────────────
    bi_base = np.where(AL_GANANCIAS_BASE > 0, IMP_GANANCIAS_BASE / AL_GANANCIAS_BASE, 0.0)
    gastos_base_gan = OPEX_BASE / (1 + AL_IVA_GASTOS_BASE) + GARANTIAS
    bi_ingr_base    = bi_base + gastos_base_gan
    bi_ingr_sen     = bi_ingr_base * factor_trafico_avg
    gastos_sen      = opex / (1 + AL_IVA_GASTOS_BASE) + GARANTIAS
    base_imponible  = bi_ingr_sen - gastos_sen

    quebranto_acum = np.zeros(YEARS + 1)
    imp_ganancias  = np.zeros(YEARS + 1)
    for y in range(1, YEARS + 1):
        base_y = base_imponible[y] + quebranto_acum[y - 1]
        if base_y <= 0:
            quebranto_acum[y] = base_y
            imp_ganancias[y]  = 0.0
        else:
            quebranto_acum[y] = 0.0
            imp_ganancias[y]  = base_y * al_ganancias

    total_impuestos = imp_iva + imp_ganancias + imp_ib + imp_municipal + imp_sellos + imp_dbcr
    total_egresos   = capex + opex + AMORT_DEUDA_BASE + total_impuestos + GARANTIAS
    flujo           = total_ingresos - total_egresos

    flujo_20    = flujo[:20]
    egresos_20  = total_egresos[:20]
    ingresos_20 = total_ingresos[:20]
    van         = _npv(tasa_van, flujo_20)
    van_egr     = _npv(tasa_van, egresos_20)
    van_ing     = _npv(tasa_van, ingresos_20)
    vaff_vae    = van / van_egr if van_egr != 0 else float("nan")
    mirr_val    = _mirr(flujo_20, tasa_van)
    acum        = np.cumsum(flujo)

    inversion_obras = float(np.sum(PUESTA_VALOR) + np.sum(OBRAS_OBLIG * (1 + delta_capex_obras)))
    payback = next((y + 1 for y, v in enumerate(acum) if v >= inversion_obras), None)

    return dict(
        flujo=flujo, total_ing=total_ingresos, total_egr=total_egresos,
        peaje=peaje, capex=capex, opex=opex, amort_deuda=AMORT_DEUDA_BASE.copy(),
        imp_iva=imp_iva, imp_ganancias=imp_ganancias, imp_ib=imp_ib,
        imp_municipal=imp_municipal, imp_sellos=imp_sellos, imp_dbcr=imp_dbcr,
        total_imp=total_impuestos, acum=acum, van=van, van_ing=van_ing,
        van_egr=van_egr, vaff_vae=vaff_vae, mirr=mirr_val,
        payback=payback, inversion_obras=inversion_obras, uteq=uteq,
    )


# ══════════════════════════════════════════════════════════════
# 3.  APP STREAMLIT
# ══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Panel Multi-Proyectos – Sensibilidades",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.main { background: #0e1117; }
.block-container { padding-top: 1.2rem; padding-bottom: 1rem; }

.kpi {
  background: linear-gradient(135deg, #1c2230, #222a3c);
  border: 1px solid #2d3650;
  border-radius: 12px;
  padding: 16px 20px;
  text-align: center;
  margin-bottom: 6px;
}
.kpi .lbl  { color: #7a869a; font-size: .72rem; text-transform: uppercase;
             letter-spacing: .09em; margin-bottom: 3px; }
.kpi .val  { color: #dce4f0; font-size: 1.55rem; font-weight: 700; }
.kpi .dlt  { font-size: .76rem; margin-top: 2px; }
.kpi .pos  { color: #3ecf8e; }
.kpi .neg  { color: #f76e6e; }
.kpi .neu  { color: #7a869a; }

.sh {
  color: #6c7fe8; font-size: .76rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: .1em;
  margin: 12px 0 4px;
  padding-bottom: 3px;
  border-bottom: 1px solid #2d3650;
}

/* Project selector buttons */
.stButton > button {
  border-radius: 8px !important;
  font-size: 0.78rem !important;
  padding: 4px 10px !important;
  white-space: nowrap !important;
}

div[data-testid="stSidebar"] { background: #131720; }
</style>
""", unsafe_allow_html=True)


# ── SELECTOR DE PROYECTO (estado persistente) ──────────────────
if "proyecto_idx" not in st.session_state:
    st.session_state.proyecto_idx = 0

# ── SIDEBAR ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛣️ Panel de Proyectos")
    st.markdown("**Concesión vial 20 años · 2026–2045**")
    st.markdown("---")

    st.markdown('<div class="sh">📂 Seleccionar Proyecto</div>', unsafe_allow_html=True)

    # Botones de selección de proyecto en columnas de 2
    n_cols = 2
    rows_btns = [PROJECT_KEYS[i:i+n_cols] for i in range(0, len(PROJECT_KEYS), n_cols)]
    for row_keys in rows_btns:
        cols_btn = st.columns(len(row_keys))
        for col, key in zip(cols_btn, row_keys):
            idx = PROJECT_KEYS.index(key)
            label = PROYECTOS[key]["label"]
            # Highlight active project
            is_active = (st.session_state.proyecto_idx == idx)
            btn_label = f"✅ {label}" if is_active else label
            if col.button(btn_label, key=f"btn_{key}", use_container_width=True):
                st.session_state.proyecto_idx = idx
                st.rerun()

    st.markdown("---")

    # Obtener proyecto activo
    pkey  = PROJECT_KEYS[st.session_state.proyecto_idx]
    P     = PROYECTOS[pkey]
    TB    = P["TARIFA_BASE"]
    TC    = P["TRAFICO_CRECIMIENTO"]

    st.markdown(f'<div class="sh">🚗 Tránsito y Tarifa — {P["label"]}</div>', unsafe_allow_html=True)

    tarifa_input = st.number_input(
        "Tarifa base (ARS)",
        min_value=1_000, max_value=200_000,
        value=int(TB), step=10,
        key=f"tarifa_{pkey}",
        help=f"Tarifa base del xlsx: $ {TB:,.0f}. Se aplica desde el Año 1."
    )

    st.caption(
        "📌 **Regla de ingresos:**  \n"
        "**Año 1** → tránsito arranque (UTEQs base × 1.05), genera ingresos.  \n"
        "**Año 2+** → crece a tasa base 3% + Δ abajo."
    )

    delta_trafico_pp = st.slider(
        "Δ tasa crecimiento anual Año 2+ (±pp sobre base 3%)",
        min_value=-3.0, max_value=5.0, value=0.0, step=0.01,
        format="%.2f pp", key=f"trafico_{pkey}",
    )
    delta_trafico = delta_trafico_pp / 100

    st.markdown('<div class="sh">🏗️ CAPEX – sensibilidades</div>', unsafe_allow_html=True)
    delta_obras = st.slider(
        "Obras obligatorias (%)", -40, 100, 0, 1, key=f"obras_{pkey}",
        help="Variación % sobre monto base de obras obligatorias"
    ) / 100
    delta_repav = st.slider(
        "Repavimentación (%)", -40, 100, 0, 1, key=f"repav_{pkey}",
        help="Variación % sobre monto base de repavimentaciones"
    ) / 100

    st.markdown('<div class="sh">⚙️ OPEX – Conservación y Mantenimiento</div>', unsafe_allow_html=True)
    delta_opex = st.slider(
        "Variación OPEX (%)", -40, 100, 0, 1, key=f"opex_{pkey}"
    ) / 100

    st.markdown('<div class="sh">💰 Alícuotas impositivas</div>', unsafe_allow_html=True)
    al_ganancias = st.slider("Ganancias (%)", 0.0, 55.0, float(P["AL_GANANCIAS"]*100), 0.1,
                              format="%.1f %%", key=f"gan_{pkey}") / 100
    al_ib        = st.slider("Ingresos Brutos (%)", 0.0, 10.0, float(P["AL_IB"]*100), 0.1,
                              format="%.1f %%", key=f"ib_{pkey}") / 100
    al_municipal = st.slider("Tasas Municipales (%)", 0.0, 3.0, float(P["AL_MUNICIPAL"]*100), 0.1,
                              format="%.1f %%", key=f"mun_{pkey}") / 100
    al_sellos    = st.slider("Impuesto de Sellos (%)", 0.0, 5.0, float(P["AL_SELLOS"]*100), 0.1,
                              format="%.1f %%", key=f"sel_{pkey}") / 100
    al_dbcr      = st.slider("Débitos y Créditos Bancarios (%)", 0.0, 5.0, float(P["AL_DBCR"]*100), 0.1,
                              format="%.1f %%", key=f"dbcr_{pkey}") / 100
    al_iva_peaje = st.slider("IVA sobre peaje (%)", 0, 27, int(P["AL_IVA"]*100), 1,
                              key=f"iva_{pkey}") / 100

    st.markdown('<div class="sh">📐 Tasa de descuento VAN</div>', unsafe_allow_html=True)
    tasa_van = st.slider("Tasa de descuento (%)", 5.0, 25.0, float(P["TASA_VAN"]*100), 0.1,
                          format="%.1f %%", key=f"tasa_{pkey}") / 100

    st.markdown("---")
    if st.button("↺  Resetear todo al base", use_container_width=True):
        st.rerun()


# ── EJECUTAR MODELO ───────────────────────────────────────────
sc = run_model(
    P             = P,
    delta_capex_obras = delta_obras,
    delta_capex_repav = delta_repav,
    delta_opex        = delta_opex,
    delta_trafico     = delta_trafico,
    tarifa            = float(tarifa_input),
    al_ganancias      = al_ganancias,
    al_ib             = al_ib,
    al_municipal      = al_municipal,
    al_sellos         = al_sellos,
    al_dbcr           = al_dbcr,
    al_iva_peaje      = al_iva_peaje,
    tasa_van          = tasa_van,
)

# Base sin sensibilidades (para deltas)
_base = run_model(P=P, tasa_van=tasa_van,
                  al_ganancias=P["AL_GANANCIAS"], al_ib=P["AL_IB"],
                  al_municipal=P["AL_MUNICIPAL"], al_sellos=P["AL_SELLOS"],
                  al_dbcr=P["AL_DBCR"], al_iva_peaje=P["AL_IVA"])
MIRR_BASE     = _base["mirr"]
VAN_BASE      = _base["van"]
VAFF_VAE_BASE = _base["vaff_vae"]

YEARS_RANGE = list(range(2025, 2025 + YEARS + 1))


# ── HELPERS ───────────────────────────────────────────────────
def fmt_ars(v):
    if abs(v) >= 1e12: return f"$ {v/1e12:.2f} B"
    if abs(v) >= 1e9:  return f"$ {v/1e9:.2f} MM"
    return f"$ {v:,.0f}"

def delta_html(new, base, flip=False):
    if base == 0 or (isinstance(new, float) and np.isnan(new)):
        return '<span class="neu">—</span>'
    d = (new - base) / abs(base)
    good = (d >= 0) if not flip else (d <= 0)
    cls  = "pos" if good else "neg"
    sgn  = "+" if d > 0 else ""
    return f'<span class="{cls}">{sgn}{d:.1%} vs base</span>'

def kpi(label, value_str, new, base, flip=False):
    return f"""<div class="kpi">
  <div class="lbl">{label}</div>
  <div class="val">{value_str}</div>
  <div class="dlt">{delta_html(new, base, flip)}</div>
</div>"""

PL = dict(
    plot_bgcolor="#181e2d", paper_bgcolor="#181e2d",
    font=dict(color="#c5cdd8", size=12),
    xaxis=dict(gridcolor="#252f45", zeroline=False),
    yaxis=dict(gridcolor="#252f45", zeroline=False),
)
C = dict(
    pos="#3ecf8e", neg="#f76e6e",
    acc="#6c7fe8", warn="#f0a742",
    pur="#a855f7", gry="#64748b",
)


# ══════════════════════════════════════════════════════════════
# 4.  ENCABEZADO, SELECTOR VISUAL Y KPIs
# ══════════════════════════════════════════════════════════════
st.markdown(f"# 🛣️ {P['label']} — Análisis de Sensibilidades")
st.markdown(
    "Concesión vial 20 años · 2026–2045 &nbsp;|&nbsp; "
    "Modificá los parámetros en el panel ← para ver el impacto en tiempo real"
)

# Selector visual de proyectos (en la página principal)
st.markdown("**Seleccionar proyecto:**")
btn_cols = st.columns(len(PROJECT_KEYS))
for i, (col, key) in enumerate(zip(btn_cols, PROJECT_KEYS)):
    lbl = PROYECTOS[key]["label"]
    is_active = (st.session_state.proyecto_idx == i)
    btn_txt = f"✅ {lbl}" if is_active else lbl
    if col.button(btn_txt, key=f"top_btn_{key}", use_container_width=True):
        st.session_state.proyecto_idx = i
        st.rerun()

st.divider()

# KPIs
c1, c2, c3, c4 = st.columns(4)
mirr_s   = f"{sc['mirr']:.2%}"     if not np.isnan(sc["mirr"])     else "n/d"
vaff_s   = f"{sc['vaff_vae']:.2%}" if not np.isnan(sc["vaff_vae"]) else "n/d"
pb_año   = sc["payback"]
pb_s     = f"Año {pb_año}  ({2025 + pb_año})" if pb_año is not None else "No recupera"
inv_obras_s = fmt_ars(sc["inversion_obras"])

c1.markdown(kpi("VAFF / VAE", vaff_s, sc["vaff_vae"], VAFF_VAE_BASE), unsafe_allow_html=True)
c2.markdown(kpi(f"VAN  (tasa {tasa_van:.0%})", fmt_ars(sc["van"]), sc["van"], VAN_BASE), unsafe_allow_html=True)
c3.markdown(kpi("TIR Modificada (MIRR)", mirr_s, sc["mirr"], MIRR_BASE), unsafe_allow_html=True)
c4.markdown(kpi(f"Payback obras · {inv_obras_s}", pb_s, 0, 0), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# 5.  TABS
# ══════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs([
    "📊 Flujo de Fondos",
    "🌪️ Tornado & Spider",
    "🔥 Mapas de calor",
])


# ─────────────────────────────────────────────────────────────
# TAB 1 – FLUJO DE FONDOS
# ─────────────────────────────────────────────────────────────
with tab1:
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "Flujo Neto Anual  ($ MM ARS)",
            "Flujo Acumulado  ($ MM ARS)",
            "Composición de Egresos por año  ($ MM ARS)",
            "Ingresos vs Egresos  ($ MM ARS)",
        ],
        vertical_spacing=0.16, horizontal_spacing=0.10,
    )

    bc = [C["pos"] if v >= 0 else C["neg"] for v in sc["flujo"]]
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["flujo"]/1e9, marker_color=bc, name="Flujo Neto"), row=1, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="#888", row=1, col=1)

    fig.add_trace(go.Scatter(
        x=YEARS_RANGE, y=sc["acum"]/1e9, mode="lines+markers",
        line=dict(color=C["acc"], width=2.5), marker=dict(size=5),
        fill="tozeroy", fillcolor="rgba(108,127,232,.12)", name="Acumulado"),
        row=1, col=2)
    fig.add_hline(y=0, line_dash="dot", line_color="#888", row=1, col=2)

    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["capex"]/1e9, name="CAPEX", marker_color=C["neg"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["opex"]/1e9, name="OPEX", marker_color=C["warn"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["total_imp"]/1e9, name="Impuestos", marker_color=C["pur"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["amort_deuda"]/1e9, name="Deuda LP", marker_color=C["gry"]), row=2, col=1)

    fig.add_trace(go.Scatter(x=YEARS_RANGE, y=sc["total_ing"]/1e9, mode="lines",
                              line=dict(color=C["pos"], width=2.5), name="Ingresos"), row=2, col=2)
    fig.add_trace(go.Scatter(x=YEARS_RANGE, y=sc["total_egr"]/1e9, mode="lines",
                              line=dict(color=C["neg"], width=2.5), name="Egresos"), row=2, col=2)

    fig.update_layout(**PL, barmode="stack", height=640, showlegend=True,
                      legend=dict(orientation="h", y=-0.07, bgcolor="rgba(0,0,0,0)"))
    for ax in ["xaxis","xaxis2","xaxis3","xaxis4","yaxis","yaxis2","yaxis3","yaxis4"]:
        fig.update_layout(**{ax: dict(gridcolor="#252f45", zeroline=False)})

    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# TAB 2 – TORNADO + SPIDER
# ─────────────────────────────────────────────────────────────
with tab2:
    st.markdown("#### Gráfico Tornado — impacto individual sobre el VAN")
    st.caption("Cada barra aplica un shock de ±20% a UNA sola variable, manteniendo el resto en el valor del panel.")

    BASE_KW = dict(
        P=P,
        delta_capex_obras=delta_obras, delta_capex_repav=delta_repav,
        delta_opex=delta_opex, delta_trafico=delta_trafico,
        tarifa=float(tarifa_input),
        al_ganancias=al_ganancias, al_ib=al_ib,
        al_municipal=al_municipal, al_sellos=al_sellos,
        al_dbcr=al_dbcr, al_iva_peaje=al_iva_peaje, tasa_van=tasa_van,
    )

    shocks = {
        "Obras +20%":          dict(delta_capex_obras=delta_obras+0.20),
        "Obras –20%":          dict(delta_capex_obras=delta_obras-0.20),
        "Repavim. +20%":       dict(delta_capex_repav=delta_repav+0.20),
        "Repavim. –20%":       dict(delta_capex_repav=delta_repav-0.20),
        "OPEX +20%":           dict(delta_opex=delta_opex+0.20),
        "OPEX –20%":           dict(delta_opex=delta_opex-0.20),
        "Tránsito +1pp":       dict(delta_trafico=delta_trafico+0.01),
        "Tránsito –1pp":       dict(delta_trafico=delta_trafico-0.01),
        "Tarifa +20%":         dict(tarifa=float(tarifa_input)*1.20),
        "Tarifa –20%":         dict(tarifa=float(tarifa_input)*0.80),
        "Ganancias +10pp":     dict(al_ganancias=min(0.60, al_ganancias+0.10)),
        "Ganancias –10pp":     dict(al_ganancias=max(0.00, al_ganancias-0.10)),
        "IB +2pp":             dict(al_ib=al_ib+0.02),
        "IB –2pp":             dict(al_ib=max(0, al_ib-0.02)),
        "IVA peaje +3pp":      dict(al_iva_peaje=al_iva_peaje+0.03),
        "IVA peaje –3pp":      dict(al_iva_peaje=max(0, al_iva_peaje-0.03)),
        "Db/Cr +1pp":          dict(al_dbcr=al_dbcr+0.01),
        "Db/Cr –1pp":          dict(al_dbcr=max(0, al_dbcr-0.01)),
        "Tasa descuento +2pp": dict(tasa_van=tasa_van+0.02),
        "Tasa descuento –2pp": dict(tasa_van=max(0.01, tasa_van-0.02)),
    }

    base_van = sc["van"]
    t_rows = []
    for label, ov in shocks.items():
        r = run_model(**{**BASE_KW, **ov})
        t_rows.append({"Variable": label, "ΔVAN": (r["van"] - base_van) / 1e9})
    df_t = pd.DataFrame(t_rows).sort_values("ΔVAN")

    fig2 = go.Figure(go.Bar(
        x=df_t["ΔVAN"], y=df_t["Variable"], orientation="h",
        marker_color=["#3ecf8e" if v >= 0 else "#f76e6e" for v in df_t["ΔVAN"]],
        text=[f"$ {v:+.1f} MM" for v in df_t["ΔVAN"]],
        textposition="outside",
    ))
    fig2.add_vline(x=0, line_color="#999", line_dash="dot")
    fig2.update_layout(**PL, height=540, margin=dict(l=180, r=130, t=40, b=50))
    fig2.update_xaxes(title_text="Δ VAN ($ ARS MM)")
    st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.markdown("#### Spider — MIRR según variación de cada variable (±40%)")

    rang = np.arange(-40, 45, 10)
    variables = {
        "CAPEX Obras":     lambda p: dict(delta_capex_obras=delta_obras + p/100),
        "CAPEX Repavim.":  lambda p: dict(delta_capex_repav=delta_repav + p/100),
        "OPEX":            lambda p: dict(delta_opex=delta_opex + p/100),
        "Tránsito (+pp)":  lambda p: dict(delta_trafico=delta_trafico + p/100),
        "Tarifa (+%)":     lambda p: dict(tarifa=float(tarifa_input) * (1 + p/100)),
        "Ganancias (+pp)": lambda p: dict(al_ganancias=max(0, al_ganancias + p/100)),
    }
    cols_spider = [C["neg"], C["warn"], C["pur"], C["pos"], C["acc"], "#f59e0b"]

    fig3 = go.Figure()
    for (vname, fn), col in zip(variables.items(), cols_spider):
        mirrs = []
        for p in rang:
            r = run_model(**{**BASE_KW, **fn(p)})
            mirrs.append(r["mirr"]*100 if not np.isnan(r["mirr"]) else None)
        fig3.add_trace(go.Scatter(x=list(rang), y=mirrs, name=vname,
                                   mode="lines+markers",
                                   line=dict(color=col, width=2.5),
                                   marker=dict(size=5)))

    fig3.add_hline(y=MIRR_BASE*100 if not np.isnan(MIRR_BASE) else 0,
                   line_dash="dash", line_color="#aaa",
                   annotation_text=f"Base {MIRR_BASE*100:.1f}%" if not np.isnan(MIRR_BASE) else "Base",
                   annotation_position="bottom right")
    fig3.update_layout(**PL, height=400, margin=dict(t=40, b=50, l=60, r=20),
                       legend=dict(bgcolor="rgba(0,0,0,0)"))
    fig3.update_xaxes(title_text="Variación (%)")
    fig3.update_yaxes(title_text="MIRR (%)")
    st.plotly_chart(fig3, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# TAB 3 – MAPAS DE CALOR
# ─────────────────────────────────────────────────────────────
with tab3:
    trafico_rng = np.arange(-2.0, 3.5, 0.5)
    capex_rng   = np.arange(-30, 55, 10)
    opex_rng    = np.arange(-30, 55, 10)
    gan_rng     = np.arange(15, 55, 5)
    tasa_rng    = np.arange(6, 20, 2)

    def heat(**ov):
        return run_model(**{**BASE_KW, **ov})

    st.markdown("#### MIRR (%) — Δ Tránsito (pp) × Obras CAPEX (%)")
    mat1 = np.zeros((len(trafico_rng), len(capex_rng)))
    for i, tr in enumerate(trafico_rng):
        for j, cp in enumerate(capex_rng):
            r = heat(delta_trafico=delta_trafico+tr/100, delta_capex_obras=delta_obras+cp/100)
            mat1[i, j] = r["mirr"]*100 if not np.isnan(r["mirr"]) else 0

    fig4 = go.Figure(go.Heatmap(
        z=mat1.round(1), x=[f"{c:+d}%" for c in capex_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng],
        colorscale="RdYlGn", text=mat1.round(1), texttemplate="%{text:.1f}%",
        colorbar=dict(title="MIRR (%)", tickfont=dict(color="#c5cdd8")),
    ))
    fig4.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=100,r=20))
    fig4.update_xaxes(title_text="Variación obras CAPEX")
    fig4.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig4, use_container_width=True)

    st.markdown("#### VAN ($ MM) — Δ Tránsito × OPEX (%)")
    mat2 = np.zeros((len(trafico_rng), len(opex_rng)))
    for i, tr in enumerate(trafico_rng):
        for j, op in enumerate(opex_rng):
            r = heat(delta_trafico=delta_trafico+tr/100, delta_opex=delta_opex+op/100)
            mat2[i, j] = r["van"] / 1e9

    fig5 = go.Figure(go.Heatmap(
        z=mat2.round(1), x=[f"{o:+d}%" for o in opex_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng],
        colorscale="RdYlGn", text=mat2.round(1), texttemplate="%{text:.0f}",
        colorbar=dict(title="VAN (MM$)", tickfont=dict(color="#c5cdd8")),
    ))
    fig5.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=100,r=20))
    fig5.update_xaxes(title_text="Variación OPEX")
    fig5.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig5, use_container_width=True)

    st.markdown("#### VAN ($ MM) — Tasa de descuento × Obras CAPEX (%)")
    mat3 = np.zeros((len(tasa_rng), len(capex_rng)))
    for i, td in enumerate(tasa_rng):
        for j, cp in enumerate(capex_rng):
            r = heat(tasa_van=td/100, delta_capex_obras=delta_obras+cp/100)
            mat3[i, j] = r["van"] / 1e9

    fig6 = go.Figure(go.Heatmap(
        z=mat3.round(1), x=[f"{c:+d}%" for c in capex_rng],
        y=[f"{t}%" for t in tasa_rng],
        colorscale="RdYlGn", text=mat3.round(1), texttemplate="%{text:.0f}",
        colorbar=dict(title="VAN (MM$)", tickfont=dict(color="#c5cdd8")),
    ))
    fig6.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=80,r=20))
    fig6.update_xaxes(title_text="Variación obras CAPEX")
    fig6.update_yaxes(title_text="Tasa de descuento")
    st.plotly_chart(fig6, use_container_width=True)

    st.markdown("#### VAFF/VAE — Δ Tránsito × Alícuota Ganancias (%)")
    mat4 = np.zeros((len(trafico_rng), len(gan_rng)))
    for i, tr in enumerate(trafico_rng):
        for j, ga in enumerate(gan_rng):
            r = heat(delta_trafico=delta_trafico+tr/100, al_ganancias=ga/100)
            mat4[i, j] = r["vaff_vae"] if not np.isnan(r["vaff_vae"]) else 0

    fig7 = go.Figure(go.Heatmap(
        z=mat4.round(4), x=[f"{g}%" for g in gan_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng],
        colorscale="RdYlGn", text=mat4.round(3), texttemplate="%{text:.3f}",
        colorbar=dict(title="VAFF/VAE", tickfont=dict(color="#c5cdd8")),
    ))
    fig7.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=100,r=20))
    fig7.update_xaxes(title_text="Alícuota Ganancias")
    fig7.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig7, use_container_width=True)


# ── FOOTER ────────────────────────────────────────────────────
st.divider()
st.caption(
    f"{P['label']} · Modelo de sensibilidades · "
    "Flujos base tomados de los xlsx al 1° de marzo 2025 · "
    "Concesión 20 años (2026–2045) · "
    "No incluye recálculo de préstamo ni WACC."
)
