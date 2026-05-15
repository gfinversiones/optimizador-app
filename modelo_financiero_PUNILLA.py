"""
PUNILLA – Panel de Sensibilidades Financieras
==============================================
Replicación fiel del modelo PUNILLA.xlsx.

El modelo NO recalcula el préstamo ni usa WACC.
Los flujos base se toman directamente del xlsx y se
escalan con los factores de sensibilidad ingresados.

Instalación:
    pip install streamlit pandas plotly

Ejecución:
    streamlit run modelo_financiero_PUNILLA.py
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

# Tasa de financiamiento (PRESTAMO!D3 = 8.5%)
TASA_FINANCIAMIENTO = 0.085

def _mirr(cf: np.ndarray, reinvest_rate: float) -> float:
    n = len(cf)
    neg = np.where(cf < 0, cf, 0.0)
    pos = np.where(cf > 0, cf, 0.0)
    pv_neg = sum(neg[t] / (1 + TASA_FINANCIAMIENTO) ** t for t in range(n))
    fv_pos = sum(pos[t] * (1 + reinvest_rate) ** (n - 1 - t) for t in range(n))
    if pv_neg >= 0 or fv_pos <= 0:
        return float("nan")
    return (fv_pos / (-pv_neg)) ** (1.0 / (n - 1)) - 1.0


# ══════════════════════════════════════════════════════════════
# 1.  DATOS BASE  (extraídos del xlsx PUNILLA)
# ══════════════════════════════════════════════════════════════
#
# Concesión: 20 años (2026–2045).
# Índice 0 = Año 1 (2026). Arrays de 20 elementos [0..19].

YEARS = 20

# ── Ingresos de peaje con IVA (FLUJO fila 72) ──────────────────
# Y1 (2026) = 0 (puesta en valor); Y2+ crecen al 3% constante
PEAJE_BASE = np.array([
    0,                       # Y1  (2026)
    20_472_602_107.93,       # Y2  (2027)
    21_086_780_171.17,       # Y3  (2028)
    21_719_383_576.31,       # Y4  (2029)
    22_370_965_083.60,       # Y5  (2030)
    23_042_094_036.10,       # Y6  (2031)
    23_733_356_857.19,       # Y7  (2032)
    24_445_357_562.90,       # Y8  (2033)
    25_178_718_289.79,       # Y9  (2034)
    25_934_079_838.48,       # Y10 (2035)
    26_712_102_233.64,       # Y11 (2036)
    27_513_465_300.65,       # Y12 (2037)
    28_338_869_259.67,       # Y13 (2038)
    29_189_035_337.46,       # Y14 (2039)
    30_064_706_397.58,       # Y15 (2040)
    30_966_647_589.51,       # Y16 (2041)
    31_895_647_017.19,       # Y17 (2042)
    32_852_516_427.71,       # Y18 (2043)
    33_838_091_920.54,       # Y19 (2044)
    34_853_234_678.15,       # Y20 (2045)
], dtype=float)

# ── Tarifa y tránsito ───────────────────────────────────────────
# Tarifa base sin IVA: $6.000/UTEQ (CONTROL!C24)
TARIFA_BASE = 6_000.0
TARIFA_IVA  = TARIFA_BASE * 1.21
UTEQ_ARRANQUE = PEAJE_BASE[1] / TARIFA_IVA   # ≈ 2.82M UTEQs (año 2)
TRAFICO_CRECIMIENTO_BASE = 0.03               # 3% constante desde Y2

# ── Ingreso crédito LP: solo Y1 (FLUJO fila 76) ────────────────
INGRESO_CREDITO = np.zeros(YEARS)
INGRESO_CREDITO[0] = 3_801_378_000.00

# ── OPEX con IVA – Conservación y Mantenimiento (FLUJO fila 80) ─
# Constante $7.240.720.000/año
OPEX_BASE = np.full(YEARS, 7_240_720_000.00)

# ── Garantías anuales (FLUJO fila 99) ──────────────────────────
GARANTIAS = np.full(YEARS, 31_000_000.0)

# ── Amortización deuda (FLUJO fila 84 / PRESTAMO) ──────────────
# Préstamo: $3.801.378.000 · TNA 8,5% · 6 cuotas · año de gracia Y1
# Y2: cuota $834.809.537,72 + gastos admin $38.013.780 = $872.823.317,72
# Y3–Y7: cuota anual $834.809.537,72
AMORT_DEUDA_BASE = np.array([
    0,                    # Y1  (gracia)
    872_823_317.72,       # Y2  (cuota + gastos admin)
    834_809_537.72,       # Y3
    834_809_537.72,       # Y4
    834_809_537.72,       # Y5
    834_809_537.72,       # Y6
    834_809_537.72,       # Y7
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

# ── CAPEX con IVA (FLUJO filas 94/95/96) ───────────────────────
# Puesta en Valor (fila 94) + Obras Obligatorias (fila 95) + Repavimentación (fila 96)
# (constantes en run_model, se sensibilizan por separado)

# ── Impuestos BASE por componente (IMPUESTOS y FLUJO) ───────────

IMP_IVA_BASE = np.array([
    0,                      # Y1
    550_275_993.01,         # Y2
    2_620_998_041.93,       # Y3
    1_334_129_546.89,       # Y4
    1_465_741_890.25,       # Y5
    1_602_321_641.12,       # Y6
    282_183_582.48,         # Y7
    368_919_098.23,         # Y8
    496_196_579.76,         # Y9
    2_889_269_377.47,       # Y10
    3_589_792_305.55,       # Y11
    3_680_686_608.50,       # Y12
    3_872_123_772.88,       # Y13
    2_605_937_637.62,       # Y14
    2_757_913_606.73,       # Y15
    2_962_634_092.52,       # Y16
    3_123_865_398.15,       # Y17
    1_924_383_260.72,       # Y18
    2_095_433_552.86,       # Y19
    2_271_615_353.77,       # Y20
], dtype=float)

IMP_GANANCIAS_BASE = np.array([
    0,                      # Y1
    549_467_647.50,         # Y2
    3_240_233_346.14,       # Y3
    2_960_342_918.88,       # Y4
    2_687_101_558.52,       # Y5
    2_538_116_617.84,       # Y6
    1_802_036_774.89,       # Y7
    1_079_217_996.47,       # Y8
    810_657_936.61,         # Y9
    1_302_170_761.72,       # Y10
    1_988_444_640.52,       # Y11
    3_152_414_586.09,       # Y12
    4_323_028_917.63,       # Y13
    5_029_241_760.12,       # Y14
    4_988_511_301.09,       # Y15
    4_766_543_259.38,       # Y16
    4_434_242_230.95,       # Y17
    3_127_883_019.82,       # Y18
    1_515_294_081.94,       # Y19
    0,                      # Y20 (quebranto en Y20)
], dtype=float)

IMP_IB_BASE = np.array([
    0,                      # Y1
    422_987_646.86,         # Y2
    435_677_276.26,         # Y3
    448_747_594.55,         # Y4
    462_210_022.39,         # Y5
    476_076_323.06,         # Y6
    490_358_612.75,         # Y7
    505_069_371.13,         # Y8
    520_221_452.27,         # Y9
    535_828_095.84,         # Y10
    551_902_938.71,         # Y11
    568_460_026.87,         # Y12
    585_513_827.68,         # Y13
    603_079_242.51,         # Y14
    621_171_619.78,         # Y15
    639_806_768.38,         # Y16
    659_000_971.43,         # Y17
    678_771_000.57,         # Y18
    699_134_130.59,         # Y19
    720_108_154.51,         # Y20
], dtype=float)

IMP_MUNICIPAL_BASE = np.array([
    0,                      # Y1
    84_597_529.37,          # Y2
    87_135_455.25,          # Y3
    89_749_518.91,          # Y4
    92_442_004.48,          # Y5
    95_215_264.61,          # Y6
    98_071_722.55,          # Y7
    101_013_874.23,         # Y8
    104_044_290.45,         # Y9
    107_165_619.17,         # Y10
    110_380_587.74,         # Y11
    113_692_005.37,         # Y12
    117_102_765.54,         # Y13
    120_615_848.50,         # Y14
    124_234_323.96,         # Y15
    127_961_353.68,         # Y16
    131_800_194.29,         # Y17
    135_754_200.11,         # Y18
    139_826_826.12,         # Y19
    144_021_630.90,         # Y20
], dtype=float)

# Impuesto de Sellos: primeros 5 años (IMPUESTOS fila 20)
IMP_SELLOS_BASE = np.array([
    335_230_470.74,         # Y1
    335_230_470.74,         # Y2
    335_230_470.74,         # Y3
    335_230_470.74,         # Y4
    335_230_470.74,         # Y5
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

IMP_DBCR_BASE = np.array([
    45_616_536.00,          # Y1  (sobre crédito LP)
    245_671_225.30,         # Y2
    253_041_362.05,         # Y3
    260_632_602.92,         # Y4
    268_451_581.00,         # Y5
    276_505_128.43,         # Y6
    284_800_282.29,         # Y7
    293_344_290.75,         # Y8
    302_144_619.48,         # Y9
    311_208_958.06,         # Y10
    320_545_226.80,         # Y11
    330_161_583.61,         # Y12
    340_066_431.12,         # Y13
    350_268_424.05,         # Y14
    360_776_476.77,         # Y15
    371_599_771.07,         # Y16
    382_747_764.21,         # Y17
    394_230_197.13,         # Y18
    406_057_103.05,         # Y19
    418_238_816.14,         # Y20
], dtype=float)

# ── Amortización impositiva (AMORTIZACIONES fila 98 – escenario 20/5) ──
# = TOTAL AMORTIZACIÓN OBRAS (fila 68) + TOTAL AMORTIZACIÓN REPAV (fila 95)
AMORT_IMP_BASE = np.array([
    224_402_479.34,         # Y1
    224_402_479.34,         # Y2
    224_402_479.34,         # Y3
    1_570_817_355.37,       # Y4
    2_917_232_231.40,       # Y5
    4_263_647_107.44,       # Y6
    6_972_866_396.10,       # Y7
    9_665_696_148.17,       # Y8
    11_012_111_024.20,      # Y9
    10_204_262_098.58,      # Y10
    8_857_847_222.55,       # Y11
    6_165_017_470.48,       # Y12
    3_472_187_718.42,       # Y13
    2_125_772_842.38,       # Y14
    2_933_621_768.00,       # Y15
    4_280_036_644.04,       # Y16
    5_963_055_239.08,       # Y17
    10_451_104_825.86,      # Y18
    15_836_764_329.99,      # Y19
    27_954_498_214.29,      # Y20
], dtype=float)

# ── Intereses deducibles del préstamo (IMPUESTOS fila 60) ──────
INT_DEDUCIBLES_BASE = np.array([
    0,                      # Y1
    323_117_130.00,         # Y2
    279_623_275.34,         # Y3
    232_432_443.04,         # Y4
    181_230_389.99,         # Y5
    125_676_162.44,         # Y6
    65_399_825.54,          # Y7
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

# Parámetros de alícuotas base
AL_IVA_GASTOS_BASE = 0.11
AL_GANANCIAS_BASE  = 0.35
AL_IB_BASE         = 0.025
AL_MUNICIPAL_BASE  = 0.005
AL_SELLOS_BASE     = 0.012
AL_DBCR_BASE       = 0.012
AL_IVA_BASE        = 0.21

# Tasa de descuento VAN (CONTROL!G21 = 10%)
TASA_VAN_BASE = 0.10


# ══════════════════════════════════════════════════════════════
# 2.  MODELO DE SENSIBILIDAD
# ══════════════════════════════════════════════════════════════

def run_model(
    delta_capex_obras   = 0.0,
    delta_capex_repav   = 0.0,
    delta_opex          = 0.0,
    delta_trafico       = 0.0,
    tarifa              = TARIFA_BASE,
    al_ganancias        = AL_GANANCIAS_BASE,
    al_ib               = AL_IB_BASE,
    al_municipal        = AL_MUNICIPAL_BASE,
    al_sellos           = AL_SELLOS_BASE,
    al_dbcr             = AL_DBCR_BASE,
    al_iva_peaje        = AL_IVA_BASE,
    tasa_van            = TASA_VAN_BASE,
):
    # ── Tráfico ────────────────────────────────────────────────
    # Y1: 0 (puesta en valor); Y2+: 3% + delta constante
    uteq = np.zeros(YEARS)
    uteq[1] = UTEQ_ARRANQUE
    tasa_eff = max(TRAFICO_CRECIMIENTO_BASE + delta_trafico, -0.50)
    for y in range(2, YEARS):
        uteq[y] = uteq[y - 1] * (1 + tasa_eff)

    # ── Ingresos de peaje con IVA ──────────────────────────────
    tarifa_con_iva = tarifa * (1 + al_iva_peaje)
    peaje = np.zeros(YEARS)
    for y in range(1, YEARS):
        peaje[y] = uteq[y] * tarifa_con_iva

    # Factor de tráfico para escalar impuestos proporcionales
    uteq_ref = np.zeros(YEARS)
    for y in range(1, YEARS):
        ub = UTEQ_ARRANQUE * ((1 + TRAFICO_CRECIMIENTO_BASE) ** (y - 1))
        uteq_ref[y] = uteq[y] / ub if ub > 0 else 1.0

    total_ingresos = peaje + INGRESO_CREDITO

    # ── CAPEX escalado ─────────────────────────────────────────
    PUESTA_VALOR = np.zeros(YEARS)
    PUESTA_VALOR[0] = 5_430_540_000.00

    OBRAS_OBLIG = np.array([
        0, 0, 0, 0, 0, 0,
        277_638_750.00,     # Y7
        555_277_500.00,     # Y8
        555_277_500.00,     # Y9
        555_277_500.00,     # Y10
        555_277_500.00,     # Y11
        832_916_250.00,     # Y12
        555_277_500.00,     # Y13
        555_277_500.00,     # Y14
        555_277_500.00,     # Y15
        277_638_750.00,     # Y16
        277_638_750.00,     # Y17
        0, 0, 0,
    ], dtype=float)

    REPAV = np.array([
        0, 0, 0,
        8_145_810_000.00,   # Y4
        8_145_810_000.00,   # Y5
        8_145_810_000.00,   # Y6
        16_291_620_000.00,  # Y7
        16_291_620_000.00,  # Y8
        16_291_620_000.00,  # Y9
        3_258_324_000.00,   # Y10
        0, 0, 0,
        8_145_810_000.00,   # Y14
        8_145_810_000.00,   # Y15
        8_145_810_000.00,   # Y16
        8_145_810_000.00,   # Y17
        16_291_620_000.00,  # Y18
        16_291_620_000.00,  # Y19
        16_291_620_000.00,  # Y20
    ], dtype=float)

    capex = (PUESTA_VALOR
             + OBRAS_OBLIG * (1 + delta_capex_obras)
             + REPAV       * (1 + delta_capex_repav))

    # ── OPEX escalado ──────────────────────────────────────────
    opex = OPEX_BASE * (1 + delta_opex)

    # ── Impuestos escalados ────────────────────────────────────
    factor_tarifa = tarifa / TARIFA_BASE
    factor = uteq_ref * factor_tarifa

    imp_iva       = IMP_IVA_BASE       * factor * ((1 + al_iva_peaje) / (1 + AL_IVA_BASE))
    imp_ib        = IMP_IB_BASE        * factor * (al_ib       / AL_IB_BASE)
    imp_municipal = IMP_MUNICIPAL_BASE * factor * (al_municipal / AL_MUNICIPAL_BASE)
    imp_sellos    = IMP_SELLOS_BASE    * (al_sellos / AL_SELLOS_BASE)
    imp_dbcr      = IMP_DBCR_BASE      * factor * (al_dbcr     / AL_DBCR_BASE)
    imp_dbcr[0]   = IMP_DBCR_BASE[0]  * (al_dbcr / AL_DBCR_BASE)  # Y1: sobre crédito LP

    # ── Impuesto a las Ganancias ───────────────────────────────
    # BI[y] = peaje[y]/(1+IVA) - gastos[y] - imp_ded[y] - AMORT_IMP[y] - INT_DED[y]
    # El quebranto de Y1 (sin peaje) es real y reduce la BI de Y2.
    gastos_gan  = opex / (1 + AL_IVA_GASTOS_BASE) + GARANTIAS
    imp_ded_gan = imp_ib + imp_municipal + imp_dbcr + imp_sellos
    bi_bruta    = (peaje / (1 + al_iva_peaje)
                   - gastos_gan - imp_ded_gan - AMORT_IMP_BASE - INT_DEDUCIBLES_BASE)

    quebranto     = np.zeros(YEARS)
    imp_ganancias = np.zeros(YEARS)
    for y in range(YEARS):
        base_y = bi_bruta[y] + (quebranto[y - 1] if y > 0 else 0)
        if base_y <= 0:
            quebranto[y]     = base_y
            imp_ganancias[y] = 0.0
        else:
            quebranto[y]     = 0.0
            imp_ganancias[y] = base_y * al_ganancias

    total_impuestos = imp_iva + imp_ganancias + imp_ib + imp_municipal + imp_sellos + imp_dbcr

    # ── Egresos y flujo ────────────────────────────────────────
    total_egresos = capex + opex + AMORT_DEUDA_BASE + total_impuestos + GARANTIAS
    flujo         = total_ingresos - total_egresos

    # ── Métricas ───────────────────────────────────────────────
    van      = _npv(tasa_van, flujo)
    van_egr  = _npv(tasa_van, total_egresos)
    van_ing  = _npv(tasa_van, total_ingresos)
    vaff_vae = van / van_egr if van_egr != 0 else float("nan")
    mirr_val = _mirr(flujo, tasa_van)
    acum     = np.cumsum(flujo)

    inversion_obras = float(np.sum(PUESTA_VALOR) + np.sum(OBRAS_OBLIG * (1 + delta_capex_obras)))
    payback = next((y + 1 for y, v in enumerate(acum) if v >= inversion_obras), None)

    return dict(
        flujo=flujo, total_ing=total_ingresos, total_egr=total_egresos,
        peaje=peaje, capex=capex, opex=opex, amort_deuda=AMORT_DEUDA_BASE.copy(),
        imp_iva=imp_iva, imp_ganancias=imp_ganancias, imp_ib=imp_ib,
        imp_municipal=imp_municipal, imp_sellos=imp_sellos, imp_dbcr=imp_dbcr,
        total_imp=total_impuestos, acum=acum,
        van=van, van_ing=van_ing, van_egr=van_egr,
        vaff_vae=vaff_vae, mirr=mirr_val, payback=payback,
        inversion_obras=inversion_obras, uteq=uteq,
    )


# ══════════════════════════════════════════════════════════════
# 3.  CONSTANTES BASE
# ══════════════════════════════════════════════════════════════

_base      = run_model()
MIRR_BASE  = _base["mirr"]
VAN_BASE   = _base["van"]
VAFF_BASE  = _base["vaff_vae"]


# ══════════════════════════════════════════════════════════════
# 4.  APP STREAMLIT
# ══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="PUNILLA – Sensibilidades",
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.main { background: #0e1117; }
.block-container { padding-top: 1.2rem; padding-bottom: 1rem; }
.kpi {
  background: linear-gradient(135deg, #1c2230, #222a3c);
  border: 1px solid #2d3650; border-radius: 12px;
  padding: 16px 20px; text-align: center; margin-bottom: 6px;
}
.kpi .lbl { color: #7a869a; font-size: .72rem; text-transform: uppercase;
            letter-spacing: .09em; margin-bottom: 3px; }
.kpi .val { color: #dce4f0; font-size: 1.55rem; font-weight: 700; }
.kpi .dlt { font-size: .76rem; margin-top: 2px; }
.kpi .pos { color: #3ecf8e; }
.kpi .neg { color: #f76e6e; }
.kpi .neu { color: #7a869a; }
.sh {
  color: #6c7fe8; font-size: .76rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: .1em;
  margin: 12px 0 4px; padding-bottom: 3px; border-bottom: 1px solid #2d3650;
}
div[data-testid="stSidebar"] { background: #131720; }
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏔️ PUNILLA")
    st.markdown("**GESTIÓN – COAC · 2026–2045**")
    st.markdown("---")

    st.markdown('<div class="sh">🚗 Tránsito y Tarifa</div>', unsafe_allow_html=True)
    tarifa_input = st.number_input(
        "Tarifa base (ARS)", min_value=1_000, max_value=50_000,
        value=int(TARIFA_BASE), step=10,
        help=f"Tarifa base del xlsx: $ {TARIFA_BASE:,.0f}. Se aplica desde el Año 2."
    )
    st.caption(
        "📌 **Regla de ingresos:**  \n"
        "**Año 1** → puesta en valor, sin peaje.  \n"
        "**Año 2** → tránsito arranque.  \n"
        "**Año 3+** → crece 3% + Δ."
    )
    delta_trafico_pp = st.slider(
        "Δ tasa crecimiento Año 3+ (±pp sobre base 3%)",
        min_value=-3.0, max_value=5.0, value=0.0, step=0.01, format="%.2f pp"
    )
    delta_trafico = delta_trafico_pp / 100

    st.markdown('<div class="sh">🏗️ CAPEX – sensibilidades</div>', unsafe_allow_html=True)
    delta_obras = st.slider("Obras obligatorias (%)", -40, 100, 0, 1) / 100
    delta_repav = st.slider("Repavimentación (%)",    -40, 100, 0, 1) / 100

    st.markdown('<div class="sh">⚙️ OPEX – Conservación y Mantenimiento</div>', unsafe_allow_html=True)
    delta_opex = st.slider("Variación OPEX (%)", -40, 100, 0, 1) / 100

    st.markdown('<div class="sh">💰 Alícuotas impositivas</div>', unsafe_allow_html=True)
    al_ganancias = st.slider("Ganancias (%)",               0.0, 55.0, 35.0, 0.1, format="%.1f %%") / 100
    al_ib        = st.slider("Ingresos Brutos (%)",         0.0, 10.0,  2.5, 0.1, format="%.1f %%") / 100
    al_municipal = st.slider("Tasas Municipales (%)",       0.0,  3.0,  0.5, 0.1, format="%.1f %%") / 100
    al_sellos    = st.slider("Impuesto de Sellos (%)",      0.0,  5.0,  1.2, 0.1, format="%.1f %%") / 100
    al_dbcr      = st.slider("Débitos y Créditos (%)",      0.0,  5.0,  1.2, 0.1, format="%.1f %%") / 100
    al_iva_peaje = st.slider("IVA sobre peaje (%)",         0,   27,   21,   1                    ) / 100

    st.markdown('<div class="sh">📐 Tasa de descuento VAN</div>', unsafe_allow_html=True)
    tasa_van = st.slider("Tasa de descuento (%)", 5.0, 25.0, 10.0, 0.1, format="%.1f %%") / 100

    st.markdown("---")
    if st.button("↺  Resetear todo al base", use_container_width=True):
        st.rerun()

# ── EJECUTAR MODELO ────────────────────────────────────────────
sc = run_model(
    delta_capex_obras=delta_obras, delta_capex_repav=delta_repav,
    delta_opex=delta_opex, delta_trafico=delta_trafico,
    tarifa=float(tarifa_input),
    al_ganancias=al_ganancias, al_ib=al_ib, al_municipal=al_municipal,
    al_sellos=al_sellos, al_dbcr=al_dbcr, al_iva_peaje=al_iva_peaje,
    tasa_van=tasa_van,
)

YEARS_RANGE = list(range(2026, 2046))

# ── HELPERS ────────────────────────────────────────────────────
def fmt_ars(v):
    if abs(v) >= 1e12: return f"$ {v/1e12:.2f} B"
    if abs(v) >= 1e9:  return f"$ {v/1e9:.2f} MM"
    return f"$ {v:,.0f}"

def delta_html(new, base, flip=False):
    if base == 0 or (isinstance(new, float) and np.isnan(new)):
        return '<span class="neu">—</span>'
    d = (new - base) / abs(base)
    good = (d >= 0) if not flip else (d <= 0)
    cls = "pos" if good else "neg"
    sgn = "+" if d > 0 else ""
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
C = dict(pos="#3ecf8e", neg="#f76e6e", acc="#6c7fe8",
         warn="#f0a742", pur="#a855f7", gry="#64748b")

# ══════════════════════════════════════════════════════════════
# 4.  ENCABEZADO Y KPIs
# ══════════════════════════════════════════════════════════════
st.markdown("# 🏔️ PUNILLA — Análisis de Sensibilidades")
st.markdown(
    "Concesión vial 20 años · 2026–2045 &nbsp;|&nbsp; "
    "Modificá los parámetros en el panel ← para ver el impacto en tiempo real"
)
st.divider()

c1, c2, c3, c4 = st.columns(4)
mirr_s = f"{sc['mirr']:.2%}"    if not np.isnan(sc["mirr"])     else "n/d"
vaff_s = f"{sc['vaff_vae']:.2%}" if not np.isnan(sc["vaff_vae"]) else "n/d"
pb_año = sc["payback"]
pb_s   = f"Año {pb_año}  ({2025 + pb_año})" if pb_año is not None else "No recupera"
inv_s  = fmt_ars(sc["inversion_obras"])

c1.markdown(kpi("VAFF / VAE",            vaff_s, sc["vaff_vae"], VAFF_BASE), unsafe_allow_html=True)
c2.markdown(kpi(f"VAN (tasa {tasa_van:.0%})", fmt_ars(sc["van"]), sc["van"], VAN_BASE), unsafe_allow_html=True)
c3.markdown(kpi("TIR Modificada (MIRR)", mirr_s, sc["mirr"],     MIRR_BASE), unsafe_allow_html=True)
c4.markdown(f"""<div class="kpi">
  <div class="lbl">Payback obras · {inv_s}</div>
  <div class="val">{pb_s}</div>
  <div class="dlt">{delta_html(0,0)}</div>
</div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# 5.  TABS
# ══════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs(["📊 Flujo de Fondos", "🌪️ Tornado & Spider", "🔥 Mapas de calor"])

# ── TAB 1 ──────────────────────────────────────────────────────
with tab1:
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=["Flujo Neto Anual ($ MM ARS)", "Flujo Acumulado ($ MM ARS)",
                        "Composición de Egresos ($ MM ARS)", "Ingresos vs Egresos ($ MM ARS)"],
        vertical_spacing=0.16, horizontal_spacing=0.10,
    )
    bc = [C["pos"] if v >= 0 else C["neg"] for v in sc["flujo"]]
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["flujo"]/1e9, marker_color=bc, name="Flujo Neto"), row=1, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="#888", row=1, col=1)
    fig.add_trace(go.Scatter(x=YEARS_RANGE, y=sc["acum"]/1e9, mode="lines+markers",
        line=dict(color=C["acc"], width=2.5), marker=dict(size=5),
        fill="tozeroy", fillcolor="rgba(108,127,232,.12)", name="Acumulado"), row=1, col=2)
    fig.add_hline(y=0, line_dash="dot", line_color="#888", row=1, col=2)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["capex"]/1e9,      name="CAPEX",    marker_color=C["neg"]),  row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["opex"]/1e9,       name="OPEX",     marker_color=C["warn"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["total_imp"]/1e9,  name="Impuestos",marker_color=C["pur"]),  row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["amort_deuda"]/1e9,name="Deuda LP", marker_color=C["gry"]),  row=2, col=1)
    fig.add_trace(go.Scatter(x=YEARS_RANGE, y=sc["total_ing"]/1e9, mode="lines",
        line=dict(color=C["pos"], width=2.5), name="Ingresos"), row=2, col=2)
    fig.add_trace(go.Scatter(x=YEARS_RANGE, y=sc["total_egr"]/1e9, mode="lines",
        line=dict(color=C["neg"], width=2.5), name="Egresos"),  row=2, col=2)
    fig.update_layout(**PL, barmode="stack", height=640, showlegend=True,
                      legend=dict(orientation="h", y=-0.07, bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig, use_container_width=True)

# ── TAB 2 ──────────────────────────────────────────────────────
with tab2:
    st.markdown("#### Gráfico Tornado — impacto individual sobre el VAN")
    st.caption("Cada barra aplica un shock de ±20% a UNA variable, manteniendo el resto en el valor del panel.")
    BASE_KW = dict(
        delta_capex_obras=delta_obras, delta_capex_repav=delta_repav,
        delta_opex=delta_opex, delta_trafico=delta_trafico,
        tarifa=float(tarifa_input), al_ganancias=al_ganancias, al_ib=al_ib,
        al_municipal=al_municipal, al_sellos=al_sellos, al_dbcr=al_dbcr,
        al_iva_peaje=al_iva_peaje, tasa_van=tasa_van,
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
    rows = [{"Variable": lbl, "ΔVAN": (run_model(**{**BASE_KW, **ov})["van"] - base_van) / 1e9}
            for lbl, ov in shocks.items()]
    df_t = pd.DataFrame(rows).sort_values("ΔVAN")
    fig2 = go.Figure(go.Bar(
        x=df_t["ΔVAN"], y=df_t["Variable"], orientation="h",
        marker_color=["#3ecf8e" if v >= 0 else "#f76e6e" for v in df_t["ΔVAN"]],
        text=[f"$ {v:+.2f} MM" for v in df_t["ΔVAN"]], textposition="outside",
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
    cols_s = [C["neg"], C["warn"], C["pur"], C["pos"], C["acc"], "#f59e0b"]
    fig3 = go.Figure()
    for (vname, fn), col in zip(variables.items(), cols_s):
        mirrs = [run_model(**{**BASE_KW, **fn(p)})["mirr"]*100
                 if not np.isnan(run_model(**{**BASE_KW, **fn(p)})["mirr"]) else None
                 for p in rang]
        fig3.add_trace(go.Scatter(x=list(rang), y=mirrs, name=vname,
                                  mode="lines+markers",
                                  line=dict(color=col, width=2.5), marker=dict(size=5)))
    fig3.add_hline(y=MIRR_BASE*100, line_dash="dash", line_color="#aaa",
                   annotation_text=f"Base {MIRR_BASE*100:.1f}%",
                   annotation_position="bottom right")
    fig3.update_layout(**PL, height=400, margin=dict(t=40, b=50, l=60, r=20),
                       legend=dict(bgcolor="rgba(0,0,0,0)"))
    fig3.update_xaxes(title_text="Variación (%)"); fig3.update_yaxes(title_text="MIRR (%)")
    st.plotly_chart(fig3, use_container_width=True)

# ── TAB 3 ──────────────────────────────────────────────────────
with tab3:
    trafico_rng = np.arange(-2.0, 3.5, 0.5)
    capex_rng   = np.arange(-30, 55, 10)
    opex_rng    = np.arange(-30, 55, 10)
    gan_rng     = np.arange(15, 55, 5)
    tasa_rng    = np.arange(6, 20, 2)

    def heat(**ov): return run_model(**{**BASE_KW, **ov})

    st.markdown("#### MIRR (%) — Δ Tránsito (pp) × Obras CAPEX (%)")
    mat1 = np.array([[heat(delta_trafico=delta_trafico+tr/100, delta_capex_obras=delta_obras+cp/100)["mirr"]*100
                      for cp in capex_rng] for tr in trafico_rng])
    fig4 = go.Figure(go.Heatmap(z=mat1.round(1), x=[f"{c:+d}%" for c in capex_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng], colorscale="RdYlGn",
        text=mat1.round(1), texttemplate="%{text:.1f}%",
        colorbar=dict(title="MIRR (%)", tickfont=dict(color="#c5cdd8"))))
    fig4.update_layout(**PL, height=370, margin=dict(t=30, b=60, l=100, r=20))
    fig4.update_xaxes(title_text="Variación obras CAPEX")
    fig4.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig4, use_container_width=True)

    st.markdown("#### VAN ($ MM) — Δ Tránsito × OPEX (%)")
    mat2 = np.array([[heat(delta_trafico=delta_trafico+tr/100, delta_opex=delta_opex+op/100)["van"]/1e9
                      for op in opex_rng] for tr in trafico_rng])
    fig5 = go.Figure(go.Heatmap(z=mat2.round(1), x=[f"{o:+d}%" for o in opex_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng], colorscale="RdYlGn",
        text=mat2.round(1), texttemplate="%{text:.0f}",
        colorbar=dict(title="VAN (MM$)", tickfont=dict(color="#c5cdd8"))))
    fig5.update_layout(**PL, height=370, margin=dict(t=30, b=60, l=100, r=20))
    fig5.update_xaxes(title_text="Variación OPEX")
    fig5.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig5, use_container_width=True)

    st.markdown("#### VAN ($ MM) — Tasa de descuento × Obras CAPEX (%)")
    mat3 = np.array([[heat(tasa_van=td/100, delta_capex_obras=delta_obras+cp/100)["van"]/1e9
                      for cp in capex_rng] for td in tasa_rng])
    fig6 = go.Figure(go.Heatmap(z=mat3.round(1), x=[f"{c:+d}%" for c in capex_rng],
        y=[f"{t}%" for t in tasa_rng], colorscale="RdYlGn",
        text=mat3.round(1), texttemplate="%{text:.0f}",
        colorbar=dict(title="VAN (MM$)", tickfont=dict(color="#c5cdd8"))))
    fig6.update_layout(**PL, height=370, margin=dict(t=30, b=60, l=80, r=20))
    fig6.update_xaxes(title_text="Variación obras CAPEX")
    fig6.update_yaxes(title_text="Tasa de descuento")
    st.plotly_chart(fig6, use_container_width=True)

    st.markdown("#### VAFF/VAE — Δ Tránsito × Alícuota Ganancias (%)")
    mat4 = np.array([[heat(delta_trafico=delta_trafico+tr/100, al_ganancias=ga/100)["vaff_vae"]
                      for ga in gan_rng] for tr in trafico_rng])
    fig7 = go.Figure(go.Heatmap(z=mat4.round(4), x=[f"{g}%" for g in gan_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng], colorscale="RdYlGn",
        text=mat4.round(3), texttemplate="%{text:.3f}",
        colorbar=dict(title="VAFF/VAE", tickfont=dict(color="#c5cdd8"))))
    fig7.update_layout(**PL, height=370, margin=dict(t=30, b=60, l=100, r=20))
    fig7.update_xaxes(title_text="Alícuota Ganancias")
    fig7.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig7, use_container_width=True)

# ── FOOTER ─────────────────────────────────────────────────────
st.divider()
st.caption(
    "PUNILLA (GESTIÓN–COAC) · Modelo de sensibilidades · "
    "Flujos base tomados del xlsx al 1° de marzo 2025 · "
    "Concesión 20 años (2026–2045) · "
    "No incluye recálculo de préstamo ni WACC."
)
