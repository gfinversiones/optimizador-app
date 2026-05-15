"""
TUNUYÁN – Panel de Sensibilidades Financieras
=============================================
Replicación fiel del modelo TUNUYAN.xlsx.

Instalación:
    pip install streamlit pandas plotly

Ejecución:
    streamlit run modelo_financiero_TUNUYAN.py
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
# 1.  DATOS BASE  (extraídos del xlsx TUNUYAN)
# ══════════════════════════════════════════════════════════════

YEARS = 20

# ── Ingresos de peaje con IVA (FLUJO fila 72) ──────────────────
PEAJE_BASE = np.array([
    0,                       # Y1  (2026)
    16_638_942_680.07,       # Y2  (2027)
    17_138_110_960.47,       # Y3  (2028)
    17_652_254_289.28,       # Y4  (2029)
    18_181_821_917.96,       # Y5  (2030)
    18_727_276_575.50,       # Y6  (2031)
    19_289_094_872.76,       # Y7  (2032)
    19_867_767_718.95,       # Y8  (2033)
    20_463_800_750.51,       # Y9  (2034)
    21_077_714_773.03,       # Y10 (2035)
    21_710_046_216.22,       # Y11 (2036)
    22_361_347_602.71,       # Y12 (2037)
    23_032_188_030.79,       # Y13 (2038)
    23_723_153_671.71,       # Y14 (2039)
    24_434_848_281.86,       # Y15 (2040)
    25_167_893_730.32,       # Y16 (2041)
    25_922_930_542.23,       # Y17 (2042)
    26_700_618_458.50,       # Y18 (2043)
    27_501_637_012.25,       # Y19 (2044)
    28_326_686_122.62,       # Y20 (2045)
], dtype=float)

TARIFA_BASE = 6_000.0
TARIFA_IVA  = TARIFA_BASE * 1.21
UTEQ_ARRANQUE = PEAJE_BASE[1] / TARIFA_IVA   # ≈ 2.30M UTEQs
TRAFICO_CRECIMIENTO_BASE = 0.03

INGRESO_CREDITO = np.zeros(YEARS)
INGRESO_CREDITO[0] = 1_772_875_125.00

# ── OPEX con IVA (FLUJO fila 80) ───────────────────────────────
OPEX_BASE = np.full(YEARS, 3_376_905_000.00)

# ── Garantías (FLUJO fila 99) ──────────────────────────────────
GARANTIAS = np.full(YEARS, 15_000_000.0)

# ── Amortización deuda (FLUJO fila 84 / PRESTAMO) ──────────────
# Préstamo: $1.772.875.125 · TNA 8,5% · 6 cuotas · año de gracia Y1
# Y2: cuota $389.335.936,48 + gastos admin $17.728.751,25 = $407.064.687,73
AMORT_DEUDA_BASE = np.array([
    0,                    # Y1
    407_064_687.73,       # Y2
    389_335_936.48,       # Y3
    389_335_936.48,       # Y4
    389_335_936.48,       # Y5
    389_335_936.48,       # Y6
    389_335_936.48,       # Y7
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

# ── Impuestos BASE ──────────────────────────────────────────────

IMP_IVA_BASE = np.array([
    0,                      # Y1
    1_487_115_958.43,       # Y2
    2_489_867_183.06,       # Y3
    1_927_729_009.14,       # Y4
    2_028_278_449.38,       # Y5
    2_132_319_628.32,       # Y6
    1_542_595_179.33,       # Y7
    1_610_250_769.67,       # Y8
    1_713_694_518.95,       # Y9
    2_875_175_539.39,       # Y10
    3_248_652_502.67,       # Y11
    3_323_619_489.17,       # Y12
    3_478_115_131.65,       # Y13
    2_938_701_064.16,       # Y14
    3_062_218_310.55,       # Y15
    3_227_509_865.66,       # Y16
    3_358_549_312.35,       # Y17
    2_872_255_009.60,       # Y18
    3_011_274_758.59,       # Y19
    3_154_465_100.06,       # Y20
], dtype=float)

IMP_GANANCIAS_BASE = np.array([
    0,                      # Y1
    2_213_182_035.73,       # Y2
    3_528_324_623.94,       # Y3
    3_458_347_935.22,       # Y4
    3_393_288_950.88,       # Y5
    3_389_299_237.38,       # Y6
    3_110_324_950.76,       # Y7
    2_841_377_215.23,       # Y8
    2_786_330_029.77,       # Y9
    3_087_869_418.89,       # Y10
    3_482_410_150.56,       # Y11
    4_101_971_674.99,       # Y12
    4_726_933_370.68,       # Y13
    5_137_679_334.69,       # Y14
    5_202_509_687.49,       # Y15
    5_185_329_789.995,      # Y16
    5_119_283_355.80,       # Y17
    4_601_626_558.35,       # Y18
    3_943_899_242.41,       # Y19
    2_193_923_915.67,       # Y20
], dtype=float)

IMP_IB_BASE = np.array([
    0,                      # Y1
    343_779_807.44,         # Y2
    354_093_201.66,         # Y3
    364_715_997.71,         # Y4
    375_657_477.64,         # Y5
    386_927_201.97,         # Y6
    398_535_018.03,         # Y7
    410_491_068.57,         # Y8
    422_805_800.63,         # Y9
    435_489_974.65,         # Y10
    448_554_673.89,         # Y11
    462_011_314.11,         # Y12
    475_871_653.53,         # Y13
    490_147_803.13,         # Y14
    504_852_237.23,         # Y15
    519_997_804.35,         # Y16
    535_597_738.48,         # Y17
    551_665_670.63,         # Y18
    568_215_640.75,         # Y19
    585_262_109.97,         # Y20
], dtype=float)

IMP_MUNICIPAL_BASE = np.array([
    0,                      # Y1
    68_755_961.49,          # Y2
    70_818_640.33,          # Y3
    72_943_199.54,          # Y4
    75_131_495.53,          # Y5
    77_385_440.39,          # Y6
    79_707_003.61,          # Y7
    82_098_213.71,          # Y8
    84_561_160.13,          # Y9
    87_097_994.93,          # Y10
    89_710_934.78,          # Y11
    92_402_262.82,          # Y12
    95_174_330.71,          # Y13
    98_029_560.63,          # Y14
    100_970_447.45,         # Y15
    103_999_560.87,         # Y16
    107_119_547.70,         # Y17
    110_333_134.13,         # Y18
    113_643_128.15,         # Y19
    117_052_421.99,         # Y20
], dtype=float)

IMP_SELLOS_BASE = np.array([
    159_908_638.76,         # Y1
    159_908_638.76,         # Y2
    159_908_638.76,         # Y3
    159_908_638.76,         # Y4
    159_908_638.76,         # Y5
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

IMP_DBCR_BASE = np.array([
    21_274_501.50,          # Y1
    199_667_312.16,         # Y2
    205_657_331.53,         # Y3
    211_827_051.47,         # Y4
    218_181_863.02,         # Y5
    224_727_318.91,         # Y6
    231_469_138.47,         # Y7
    238_413_212.63,         # Y8
    245_565_609.01,         # Y9
    252_932_577.28,         # Y10
    260_520_554.59,         # Y11
    268_336_171.23,         # Y12
    276_386_256.37,         # Y13
    284_677_844.06,         # Y14
    293_218_179.38,         # Y15
    302_014_724.76,         # Y16
    311_075_166.51,         # Y17
    320_407_421.50,         # Y18
    330_019_644.15,         # Y19
    339_920_233.47,         # Y20
], dtype=float)

# ── Amortización impositiva (AMORTIZACIONES fila 98 – escenario 20/5) ──
AMORT_IMP_BASE = np.array([
    104_656_146.69,         # Y1
    104_656_146.69,         # Y2
    104_656_146.69,         # Y3
    732_593_026.86,         # Y4
    1_360_529_907.02,       # Y5
    1_988_466_787.19,       # Y6
    3_257_289_115.997,      # Y7
    4_513_162_876.33,       # Y8
    5_141_099_756.49,       # Y9
    4_764_337_628.39,       # Y10
    4_136_400_748.23,       # Y11
    2_880_526_987.90,       # Y12
    1_624_653_227.57,       # Y13
    996_716_347.40,         # Y14
    1_373_478_475.50,       # Y15
    2_001_415_355.67,       # Y16
    2_786_336_455.87,       # Y17
    4_879_459_389.76,       # Y18
    7_391_206_910.42,       # Y19
    13_042_638_831.91,      # Y20
], dtype=float)

# ── Intereses deducibles (IMPUESTOS fila 60) ───────────────────
INT_DEDUCIBLES_BASE = np.array([
    0,                      # Y1
    150_694_385.63,         # Y2
    130_409_853.80,         # Y3
    108_401_136.77,         # Y4
    84_521_678.80,          # Y5
    58_612_466.90,          # Y6
    30_500_971.98,          # Y7
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
    PUESTA_VALOR[0] = 2_532_678_750.00

    OBRAS_OBLIG = np.array([
        0, 0, 0, 0, 0, 0,
        219_348_750.00,     # Y7
        438_697_500.00,     # Y8
        438_697_500.00,     # Y9
        438_697_500.00,     # Y10
        438_697_500.00,     # Y11
        658_046_250.00,     # Y12
        438_697_500.00,     # Y13
        438_697_500.00,     # Y14
        438_697_500.00,     # Y15
        219_348_750.00,     # Y16
        219_348_750.00,     # Y17
        0, 0, 0,
    ], dtype=float)

    REPAV = np.array([
        0, 0, 0,
        3_799_018_125.00,   # Y4
        3_799_018_125.00,   # Y5
        3_799_018_125.00,   # Y6
        7_598_036_250.00,   # Y7
        7_598_036_250.00,   # Y8
        7_598_036_250.00,   # Y9
        1_519_607_250.00,   # Y10
        0, 0, 0,
        3_799_018_125.00,   # Y14
        3_799_018_125.00,   # Y15
        3_799_018_125.00,   # Y16
        3_799_018_125.00,   # Y17
        7_598_036_250.00,   # Y18
        7_598_036_250.00,   # Y19
        7_598_036_250.00,   # Y20
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
    page_title="Tunuyán · Sensibilidades",
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

with st.sidebar:
    st.markdown("## 🏔️ Tunuyán")
    st.markdown("**GESTIÓN – COAC · 2026–2045**")
    st.markdown("---")

    st.markdown('<div class="sh">🚗 Tránsito y Tarifa</div>', unsafe_allow_html=True)
    tarifa_input = st.number_input(
        "Tarifa base (ARS)", min_value=1_000, max_value=50_000,
        value=int(TARIFA_BASE), step=10,
        help=f"Tarifa base: $ {TARIFA_BASE:,.0f}. Se aplica desde el Año 2."
    )
    st.caption("📌 **Año 1** → puesta en valor.  \n**Año 2** → arranque.  \n**Año 3+** → 3% + Δ.")
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

st.markdown("# 🏔️ Tunuyán — Análisis de Sensibilidades")
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
    "Tunuyán (GESTIÓN–COAC) · Modelo de sensibilidades · "
    "Flujos base tomados del xlsx al 1° de marzo 2025 · "
    "Concesión 20 años (2026–2045) · "
    "No incluye recálculo de préstamo ni WACC."
)
