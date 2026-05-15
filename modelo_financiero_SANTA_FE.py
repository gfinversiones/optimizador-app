"""
SANTA FE – PARANÁ – Panel de Sensibilidades Financieras
========================================================
Replicación fiel del modelo SANTA_FE_-_PARANA.xlsx.

Instalación:
    pip install streamlit pandas plotly

Ejecución:
    streamlit run modelo_financiero_SANTA_FE.py
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
    neg = np.where(cf < 0, cf, 0.0)
    pos = np.where(cf > 0, cf, 0.0)
    pv_neg = sum(neg[t] / (1 + TASA_FINANCIAMIENTO) ** t for t in range(n))
    fv_pos = sum(pos[t] * (1 + reinvest_rate) ** (n - 1 - t) for t in range(n))
    if pv_neg >= 0 or fv_pos <= 0:
        return float("nan")
    return (fv_pos / (-pv_neg)) ** (1.0 / (n - 1)) - 1.0


# ══════════════════════════════════════════════════════════════
# 1.  DATOS BASE  (extraídos del xlsx SANTA_FE_-_PARANA)
# ══════════════════════════════════════════════════════════════

YEARS = 20

# ── Ingresos de peaje con IVA (FLUJO fila 72) ──────────────────
PEAJE_BASE = np.array([
    0,                       # Y1  (2026)
    17_343_441_788.44,       # Y2  (2027)
    17_863_745_042.10,       # Y3  (2028)
    18_399_657_393.36,       # Y4  (2029)
    18_951_647_115.16,       # Y5  (2030)
    19_520_196_528.61,       # Y6  (2031)
    20_105_802_424.47,       # Y7  (2032)
    20_708_976_497.21,       # Y8  (2033)
    21_330_245_792.12,       # Y9  (2034)
    21_970_153_165.89,       # Y10 (2035)
    22_629_257_760.86,       # Y11 (2036)
    23_308_135_493.69,       # Y12 (2037)
    24_007_379_558.50,       # Y13 (2038)
    24_727_600_945.26,       # Y14 (2039)
    25_469_428_973.61,       # Y15 (2040)
    26_233_511_842.82,       # Y16 (2041)
    27_020_517_198.11,       # Y17 (2042)
    27_831_132_714.05,       # Y18 (2043)
    28_666_066_695.47,       # Y19 (2044)
    29_526_048_696.34,       # Y20 (2045)
], dtype=float)

TARIFA_BASE = 6_000.0
TARIFA_IVA  = TARIFA_BASE * 1.21
UTEQ_ARRANQUE = PEAJE_BASE[1] / TARIFA_IVA   # ≈ 2.39M UTEQs
TRAFICO_CRECIMIENTO_BASE = 0.03

INGRESO_CREDITO = np.zeros(YEARS)
INGRESO_CREDITO[0] = 2_844_943_500.00

# ── OPEX con IVA (FLUJO fila 80) ───────────────────────────────
OPEX_BASE = np.full(YEARS, 5_418_940_000.00)

# ── Garantías (FLUJO fila 99) ──────────────────────────────────
GARANTIAS = np.full(YEARS, 24_000_000.0)

# ── Amortización deuda (FLUJO fila 84 / PRESTAMO) ──────────────
# Préstamo: $2.844.943.500 · TNA 8,5% · 6 cuotas · año de gracia Y1
# Y2: cuota $624.769.746,15 + gastos admin $28.449.435 = $653.219.181,15
AMORT_DEUDA_BASE = np.array([
    0,                    # Y1
    653_219_181.15,       # Y2
    624_769_746.15,       # Y3
    624_769_746.15,       # Y4
    624_769_746.15,       # Y5
    624_769_746.15,       # Y6
    624_769_746.15,       # Y7
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

# ── Impuestos BASE ──────────────────────────────────────────────

IMP_IVA_BASE = np.array([
    0,                      # Y1
    762_436_743.21,         # Y2
    2_322_826_329.56,       # Y3
    1_370_579_053.39,       # Y4
    1_480_245_201.89,       # Y5
    1_593_963_980.22,       # Y6
    583_938_031.79,         # Y7
    627_168_817.16,         # Y8
    734_992_413.80,         # Y9
    2_538_909_660.48,       # Y10
    3_076_514_449.69,       # Y11
    3_124_389_283.49,       # Y12
    3_315_692_612.92,       # Y13
    2_382_652_874.26,       # Y14
    2_511_399_887.44,       # Y15
    2_713_956_232.51,       # Y16
    2_850_543_938.80,       # Y17
    2_003_139_358.92,       # Y18
    2_148_045_256.53,       # Y19
    2_297_298_331.06,       # Y20
], dtype=float)

IMP_GANANCIAS_BASE = np.array([
    0,                      # Y1
    964_017_923.23,         # Y2
    2_997_535_517.38,       # Y3
    2_805_332_362.26,       # Y4
    2_618_623_343.17,       # Y5
    2_528_151_916.48,       # Y6
    1_992_104_636.23,       # Y7
    1_470_581_879.97,       # Y8
    1_289_608_417.22,       # Y9
    1_678_072_433.02,       # Y10
    2_212_913_726.77,       # Y11
    3_105_898_837.23,       # Y12
    4_004_512_764.23,       # Y13
    4_556_245_425.98,       # Y14
    4_549_663_385.14,       # Y15
    4_408_160_525.60,       # Y16
    4_184_823_212.09,       # Y17
    3_233_263_434.91,       # Y18
    2_053_305_461.52,       # Y19
    0,                      # Y20 (quebranto en Y20)
], dtype=float)

IMP_IB_BASE = np.array([
    0,                      # Y1
    358_335_574.14,         # Y2
    369_085_641.37,         # Y3
    380_158_210.61,         # Y4
    391_562_956.92,         # Y5
    403_309_845.63,         # Y6
    415_409_141.00,         # Y7
    427_871_415.23,         # Y8
    440_707_557.69,         # Y9
    453_928_784.42,         # Y10
    467_546_647.95,         # Y11
    481_573_047.39,         # Y12
    496_020_238.81,         # Y13
    510_900_845.98,         # Y14
    526_227_871.36,         # Y15
    542_014_707.50,         # Y16
    558_275_148.72,         # Y17
    575_023_403.18,         # Y18
    592_274_105.28,         # Y19
    610_042_328.44,         # Y20
], dtype=float)

IMP_MUNICIPAL_BASE = np.array([
    0,                      # Y1
    71_667_114.83,          # Y2
    73_817_128.27,          # Y3
    76_031_642.12,          # Y4
    78_312_591.38,          # Y5
    80_661_969.13,          # Y6
    83_081_828.20,          # Y7
    85_574_283.05,          # Y8
    88_141_511.54,          # Y9
    90_785_756.88,          # Y10
    93_509_329.59,          # Y11
    96_314_609.48,          # Y12
    99_204_047.76,          # Y13
    102_180_169.20,         # Y14
    105_245_574.27,         # Y15
    108_402_941.50,         # Y16
    111_655_029.74,         # Y17
    115_004_680.64,         # Y18
    118_454_821.06,         # Y19
    122_008_465.69,         # Y20
], dtype=float)

IMP_SELLOS_BASE = np.array([
    258_630_982.81,         # Y1
    258_630_982.81,         # Y2
    258_630_982.81,         # Y3
    258_630_982.81,         # Y4
    258_630_982.81,         # Y5
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

IMP_DBCR_BASE = np.array([
    34_139_322.00,          # Y1
    208_121_301.46,         # Y2
    214_364_940.51,         # Y3
    220_795_888.72,         # Y4
    227_419_765.38,         # Y5
    234_242_358.34,         # Y6
    241_269_629.09,         # Y7
    248_507_717.97,         # Y8
    255_962_949.51,         # Y9
    263_641_837.99,         # Y10
    271_551_093.13,         # Y11
    279_697_625.92,         # Y12
    288_088_554.70,         # Y13
    296_731_211.34,         # Y14
    305_633_147.68,         # Y15
    314_802_142.11,         # Y16
    324_246_206.38,         # Y17
    333_973_592.57,         # Y18
    343_992_800.35,         # Y19
    354_312_584.36,         # Y20
], dtype=float)

# ── Amortización impositiva (AMORTIZACIONES fila 98 – escenario 20/5) ──
AMORT_IMP_BASE = np.array([
    167_942_355.37,         # Y1
    167_942_355.37,         # Y2
    167_942_355.37,         # Y3
    1_175_596_487.60,       # Y4
    2_183_250_619.83,       # Y5
    3_190_904_752.07,       # Y6
    5_230_004_486.42,       # Y7
    7_245_312_750.89,       # Y8
    8_252_966_883.12,       # Y9
    7_648_374_403.78,       # Y10
    6_640_720_271.55,       # Y11
    4_625_412_007.08,       # Y12
    2_610_103_742.62,       # Y13
    1_602_449_610.39,       # Y14
    2_207_042_089.73,       # Y15
    3_214_696_221.96,       # Y16
    4_474_263_887.25,       # Y17
    7_833_110_994.69,       # Y18
    11_863_727_523.61,      # Y19
    20_932_614_713.70,      # Y20
], dtype=float)

# ── Intereses deducibles (IMPUESTOS fila 60) ───────────────────
INT_DEDUCIBLES_BASE = np.array([
    0,                      # Y1
    241_820_197.50,         # Y2
    209_269_485.86,         # Y3
    173_951_963.74,         # Y4
    135_632_452.24,         # Y5
    94_055_782.25,          # Y6
    48_945_095.32,          # Y7
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

AL_IVA_GASTOS_BASE = 0.11
AL_GANANCIAS_BASE  = 0.35
AL_IB_BASE         = 0.025
AL_MUNICIPAL_BASE  = 0.005
AL_SELLOS_BASE     = 0.012
AL_DBCR_BASE       = 0.012
AL_IVA_BASE        = 0.21
TASA_VAN_BASE      = 0.10


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
    uteq = np.zeros(YEARS)
    uteq[1] = UTEQ_ARRANQUE
    tasa_eff = max(TRAFICO_CRECIMIENTO_BASE + delta_trafico, -0.50)
    for y in range(2, YEARS):
        uteq[y] = uteq[y - 1] * (1 + tasa_eff)

    tarifa_con_iva = tarifa * (1 + al_iva_peaje)
    peaje = np.zeros(YEARS)
    for y in range(1, YEARS):
        peaje[y] = uteq[y] * tarifa_con_iva

    uteq_ref = np.zeros(YEARS)
    for y in range(1, YEARS):
        ub = UTEQ_ARRANQUE * ((1 + TRAFICO_CRECIMIENTO_BASE) ** (y - 1))
        uteq_ref[y] = uteq[y] / ub if ub > 0 else 1.0

    total_ingresos = peaje + INGRESO_CREDITO

    PUESTA_VALOR = np.zeros(YEARS)
    PUESTA_VALOR[0] = 4_064_205_000.00

    OBRAS_OBLIG = np.array([
        0, 0, 0, 0, 0, 0,
        403_027_500.00,     # Y7
        806_055_000.00,     # Y8
        806_055_000.00,     # Y9
        806_055_000.00,     # Y10
        806_055_000.00,     # Y11
        1_209_082_500.00,   # Y12
        806_055_000.00,     # Y13
        806_055_000.00,     # Y14
        806_055_000.00,     # Y15
        403_027_500.00,     # Y16
        403_027_500.00,     # Y17
        0, 0, 0,
    ], dtype=float)

    REPAV = np.array([
        0, 0, 0,
        6_096_307_500.00,   # Y4
        6_096_307_500.00,   # Y5
        6_096_307_500.00,   # Y6
        12_192_615_000.00,  # Y7
        12_192_615_000.00,  # Y8
        12_192_615_000.00,  # Y9
        2_438_523_000.00,   # Y10
        0, 0, 0,
        6_096_307_500.00,   # Y14
        6_096_307_500.00,   # Y15
        6_096_307_500.00,   # Y16
        6_096_307_500.00,   # Y17
        12_192_615_000.00,  # Y18
        12_192_615_000.00,  # Y19
        12_192_615_000.00,  # Y20
    ], dtype=float)

    capex = (PUESTA_VALOR
             + OBRAS_OBLIG * (1 + delta_capex_obras)
             + REPAV       * (1 + delta_capex_repav))
    opex  = OPEX_BASE * (1 + delta_opex)

    factor_tarifa = tarifa / TARIFA_BASE
    factor = uteq_ref * factor_tarifa

    imp_iva       = IMP_IVA_BASE       * factor * ((1 + al_iva_peaje) / (1 + AL_IVA_BASE))
    imp_ib        = IMP_IB_BASE        * factor * (al_ib       / AL_IB_BASE)
    imp_municipal = IMP_MUNICIPAL_BASE * factor * (al_municipal / AL_MUNICIPAL_BASE)
    imp_sellos    = IMP_SELLOS_BASE    * (al_sellos / AL_SELLOS_BASE)
    imp_dbcr      = IMP_DBCR_BASE      * factor * (al_dbcr     / AL_DBCR_BASE)
    imp_dbcr[0]   = IMP_DBCR_BASE[0]  * (al_dbcr / AL_DBCR_BASE)

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
    total_egresos   = capex + opex + AMORT_DEUDA_BASE + total_impuestos + GARANTIAS
    flujo           = total_ingresos - total_egresos

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

_base     = run_model()
MIRR_BASE = _base["mirr"]
VAN_BASE  = _base["van"]
VAFF_BASE = _base["vaff_vae"]


# ══════════════════════════════════════════════════════════════
# 4.  APP STREAMLIT
# ══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Santa Fe – Paraná · Sensibilidades",
    page_icon="🌊",
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

with st.sidebar:
    st.markdown("## 🌊 Santa Fe – Paraná")
    st.markdown("**GESTIÓN – COAC · 2026–2045**")
    st.markdown("---")

    st.markdown('<div class="sh">🚗 Tránsito y Tarifa</div>', unsafe_allow_html=True)
    tarifa_input = st.number_input(
        "Tarifa base (ARS)", min_value=1_000, max_value=50_000,
        value=int(TARIFA_BASE), step=10,
        help=f"Tarifa base: $ {TARIFA_BASE:,.0f}. Se aplica desde el Año 2."
    )
    st.caption(
        "📌 **Regla:**  \n"
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
    al_ganancias = st.slider("Ganancias (%)",         0.0, 55.0, 35.0, 0.1, format="%.1f %%") / 100
    al_ib        = st.slider("Ingresos Brutos (%)",   0.0, 10.0,  2.5, 0.1, format="%.1f %%") / 100
    al_municipal = st.slider("Tasas Municipales (%)", 0.0,  3.0,  0.5, 0.1, format="%.1f %%") / 100
    al_sellos    = st.slider("Impuesto de Sellos (%)",0.0,  5.0,  1.2, 0.1, format="%.1f %%") / 100
    al_dbcr      = st.slider("Débitos y Créditos (%)",0.0,  5.0,  1.2, 0.1, format="%.1f %%") / 100
    al_iva_peaje = st.slider("IVA sobre peaje (%)",   0,   27,   21,   1                    ) / 100

    st.markdown('<div class="sh">📐 Tasa de descuento VAN</div>', unsafe_allow_html=True)
    tasa_van = st.slider("Tasa de descuento (%)", 5.0, 25.0, 10.0, 0.1, format="%.1f %%") / 100

    st.markdown("---")
    if st.button("↺  Resetear todo al base", use_container_width=True):
        st.rerun()

sc = run_model(
    delta_capex_obras=delta_obras, delta_capex_repav=delta_repav,
    delta_opex=delta_opex, delta_trafico=delta_trafico,
    tarifa=float(tarifa_input),
    al_ganancias=al_ganancias, al_ib=al_ib, al_municipal=al_municipal,
    al_sellos=al_sellos, al_dbcr=al_dbcr, al_iva_peaje=al_iva_peaje,
    tasa_van=tasa_van,
)

YEARS_RANGE = list(range(2026, 2046))

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

st.markdown("# 🌊 Santa Fe – Paraná — Análisis de Sensibilidades")
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

c1.markdown(kpi("VAFF / VAE",             vaff_s, sc["vaff_vae"], VAFF_BASE), unsafe_allow_html=True)
c2.markdown(kpi(f"VAN (tasa {tasa_van:.0%})", fmt_ars(sc["van"]), sc["van"], VAN_BASE), unsafe_allow_html=True)
c3.markdown(kpi("TIR Modificada (MIRR)",  mirr_s, sc["mirr"],     MIRR_BASE), unsafe_allow_html=True)
c4.markdown(f"""<div class="kpi">
  <div class="lbl">Payback obras · {inv_s}</div>
  <div class="val">{pb_s}</div>
  <div class="dlt">{delta_html(0,0)}</div>
</div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📊 Flujo de Fondos", "🌪️ Tornado & Spider", "🔥 Mapas de calor"])

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
        line=dict(color=C["neg"], width=2.5), name="Egresos"), row=2, col=2)
    fig.update_layout(**PL, barmode="stack", height=640, showlegend=True,
                      legend=dict(orientation="h", y=-0.07, bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig, use_container_width=True)

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

st.divider()
st.caption(
    "Santa Fe – Paraná (GESTIÓN–COAC) · Modelo de sensibilidades · "
    "Flujos base tomados del xlsx al 1° de marzo 2025 · "
    "Concesión 20 años (2026–2045) · "
    "No incluye recálculo de préstamo ni WACC."
)
