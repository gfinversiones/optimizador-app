"""
RAWSON – TRELEW – GAIMAN – Panel de Sensibilidades Financieras
==============================================================
Replicación fiel del modelo RAWSON_TRELEW_GAIMAN.xlsx.

Instalación:
    pip install streamlit pandas plotly

Ejecución:
    streamlit run modelo_financiero_RAWSON.py
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
# 1.  DATOS BASE  (extraídos del xlsx RAWSON_TRELEW_GAIMAN)
# ══════════════════════════════════════════════════════════════
#
# Concesión: 20 años (2026–2045). Índice 0 = Año 1 (2026).

YEARS = 20

# ── Ingresos de peaje con IVA (FLUJO fila 72) ──────────────────
PEAJE_BASE = np.array([
    0,                       # Y1  (2026) – puesta en valor
    19_977_880_929.57,       # Y2  (2027)
    20_577_217_357.46,       # Y3  (2028)
    21_194_533_878.18,       # Y4  (2029)
    21_830_369_894.53,       # Y5  (2030)
    22_485_280_991.36,       # Y6  (2031)
    23_159_839_421.10,       # Y7  (2032)
    23_854_634_603.73,       # Y8  (2033)
    24_570_273_641.85,       # Y9  (2034)
    25_307_381_851.10,       # Y10 (2035)
    26_066_603_306.64,       # Y11 (2036)
    26_848_601_405.83,       # Y12 (2037)
    27_654_059_448.01,       # Y13 (2038)
    28_483_681_231.45,       # Y14 (2039)
    29_338_191_668.39,       # Y15 (2040)
    30_218_337_418.44,       # Y16 (2041)
    31_124_887_540.998,      # Y17 (2042)
    32_058_634_167.23,       # Y18 (2043)
    33_020_393_192.25,       # Y19 (2044)
    34_011_004_988.01,       # Y20 (2045)
], dtype=float)

# Tarifa y tránsito
TARIFA_BASE = 6_000.0
TARIFA_IVA  = TARIFA_BASE * 1.21
UTEQ_ARRANQUE = PEAJE_BASE[1] / TARIFA_IVA   # ≈ 2.75M UTEQs
TRAFICO_CRECIMIENTO_BASE = 0.03

# ── Ingreso crédito LP: solo Y1 (FLUJO fila 76) ────────────────
INGRESO_CREDITO = np.zeros(YEARS)
INGRESO_CREDITO[0] = 2_614_437_000.00

# ── OPEX con IVA – Conservación y Mantenimiento (FLUJO fila 80) ─
OPEX_BASE = np.full(YEARS, 4_979_880_000.00)

# ── Garantías anuales (FLUJO fila 99) ──────────────────────────
GARANTIAS = np.full(YEARS, 30_000_000.0)

# ── Amortización deuda (FLUJO fila 84 / PRESTAMO) ──────────────
# Préstamo: $2.614.437.000 · TNA 8,5% · 6 cuotas · año de gracia Y1
# Y2: cuota $574.148.885,85 + gastos admin $26.144.370 = $600.293.255,85
AMORT_DEUDA_BASE = np.array([
    0,                    # Y1  (gracia)
    600_293_255.85,       # Y2  (cuota + gastos admin)
    574_148_885.85,       # Y3
    574_148_885.85,       # Y4
    574_148_885.85,       # Y5
    574_148_885.85,       # Y6
    574_148_885.85,       # Y7
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

# ── Impuestos BASE por componente (IMPUESTOS y FLUJO) ───────────

IMP_IVA_BASE = np.array([
    0,                      # Y1
    1_399_002_189.35,       # Y2
    2_855_375_729.53,       # Y3
    2_001_946_532.27,       # Y4
    2_125_041_026.33,       # Y5
    2_252_529_208.59,       # Y6
    624_095_447.77,         # Y7
    0,                      # Y8  (IVA acumulado negativo → pago 0)
    52_782_507.23,          # Y9
    1_772_118_082.49,       # Y10
    2_292_808_302.05,       # Y11
    1_640_331_246.95,       # Y12
    2_568_317_219.15,       # Y13
    1_739_989_884.04,       # Y14
    1_888_293_348.31,       # Y15
    2_829_241_649.97,       # Y16
    2_986_576_795.20,       # Y17
    2_964_516_447.28,       # Y18
    3_131_433_302.86,       # Y19
    3_303_357_664.11,       # Y20
], dtype=float)

IMP_GANANCIAS_BASE = np.array([
    0,                      # Y1
    1_880_997_736.03,       # Y2
    3_843_941_323.57,       # Y3
    3_701_810_178.81,       # Y4
    3_565_762_990.18,       # Y5
    3_577_135_226.63,       # Y6
    3_036_037_821.63,       # Y7
    2_595_599_551.998,      # Y8
    2_469_283_044.43,       # Y9
    2_867_466_170.98,       # Y10
    3_401_402_427.77,       # Y11
    4_265_737_419.79,       # Y12
    5_136_556_235.94,       # Y13
    5_689_949_630.63,       # Y14
    5_731_655_697.82,       # Y15
    5_650_805_310.59,       # Y16
    5_496_226_584.46,       # Y17
    4_673_948_220.20,       # Y18
    3_643_342_707.50,       # Y19
    1_000_192_678.998,      # Y20
], dtype=float)

IMP_IB_BASE = np.array([
    0,                      # Y1
    412_766_134.91,         # Y2
    425_149_118.96,         # Y3
    437_903_592.52,         # Y4
    451_040_700.30,         # Y5
    464_571_921.31,         # Y6
    478_509_078.95,         # Y7
    492_864_351.32,         # Y8
    507_650_281.86,         # Y9
    522_879_790.31,         # Y10
    538_566_184.02,         # Y11
    554_723_169.54,         # Y12
    571_364_864.63,         # Y13
    588_505_810.57,         # Y14
    606_160_984.88,         # Y15
    624_345_814.43,         # Y16
    643_076_188.86,         # Y17
    662_368_474.53,         # Y18
    682_239_528.77,         # Y19
    702_706_714.63,         # Y20
], dtype=float)

IMP_MUNICIPAL_BASE = np.array([
    0,                      # Y1
    82_553_226.98,          # Y2
    85_029_823.79,          # Y3
    87_580_718.50,          # Y4
    90_208_140.06,          # Y5
    92_914_384.26,          # Y6
    95_701_815.79,          # Y7
    98_572_870.26,          # Y8
    101_530_056.37,         # Y9
    104_575_958.06,         # Y10
    107_713_236.80,         # Y11
    110_944_633.91,         # Y12
    114_272_972.93,         # Y13
    117_701_162.11,         # Y14
    121_232_196.98,         # Y15
    124_869_162.89,         # Y16
    128_615_237.77,         # Y17
    132_473_694.91,         # Y18
    136_447_905.75,         # Y19
    140_541_342.93,         # Y20
], dtype=float)

IMP_SELLOS_BASE = np.array([
    403_142_411.90,         # Y1
    403_142_411.90,         # Y2
    403_142_411.90,         # Y3
    403_142_411.90,         # Y4
    403_142_411.90,         # Y5
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

IMP_DBCR_BASE = np.array([
    31_373_244.00,          # Y1  (sobre crédito LP)
    239_734_571.15,         # Y2
    246_926_608.29,         # Y3
    254_334_406.54,         # Y4
    261_964_438.73,         # Y5
    269_823_371.90,         # Y6
    277_918_073.05,         # Y7
    286_255_615.24,         # Y8
    294_843_283.70,         # Y9
    303_688_582.21,         # Y10
    312_799_239.68,         # Y11
    322_183_216.87,         # Y12
    331_848_713.38,         # Y13
    341_804_174.78,         # Y14
    352_058_300.02,         # Y15
    362_620_049.02,         # Y16
    373_498_650.49,         # Y17
    384_703_610.01,         # Y18
    396_244_718.31,         # Y19
    408_132_059.86,         # Y20
], dtype=float)

# ── Amortización impositiva (AMORTIZACIONES fila 98 – escenario 20/5) ──
AMORT_IMP_BASE = np.array([
    154_335_123.97,         # Y1
    154_335_123.97,         # Y2
    154_335_123.97,         # Y3
    1_080_345_867.77,       # Y4
    2_006_356_611.57,       # Y5
    2_932_367_355.37,       # Y6
    5_052_482_629.87,       # Y7
    6_904_504_117.47,       # Y8
    7_830_514_861.28,       # Y9
    7_274_908_414.99,       # Y10
    6_348_897_671.19,       # Y11
    4_496_876_183.59,       # Y12
    2_644_854_695.99,       # Y13
    1_718_843_952.18,       # Y14
    2_274_450_398.47,       # Y15
    3_200_461_142.27,       # Y16
    4_357_974_572.02,       # Y17
    7_444_677_051.36,       # Y18
    11_148_720_026.56,      # Y19
    19_482_816_720.78,      # Y20
], dtype=float)

# ── Intereses deducibles del préstamo (IMPUESTOS fila 60) ──────
INT_DEDUCIBLES_BASE = np.array([
    0,                      # Y1
    222_227_145.00,         # Y2
    192_313_797.03,         # Y3
    159_857_814.48,         # Y4
    124_643_073.41,         # Y5
    86_435_079.36,          # Y6
    44_979_405.80,          # Y7
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

# Alícuotas base
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
    # ── Tráfico ────────────────────────────────────────────────
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

    # ── CAPEX ──────────────────────────────────────────────────
    PUESTA_VALOR = np.zeros(YEARS)
    PUESTA_VALOR[0] = 3_734_910_000.00

    OBRAS_OBLIG = np.array([
        0, 0, 0, 0, 0, 0,
        4_541_508_750.00,   # Y7
        9_083_017_500.00,   # Y8
        9_083_017_500.00,   # Y9
        9_083_017_500.00,   # Y10
        9_083_017_500.00,   # Y11
        13_624_526_250.00,  # Y12
        9_083_017_500.00,   # Y13
        9_083_017_500.00,   # Y14
        9_083_017_500.00,   # Y15
        4_541_508_750.00,   # Y16
        4_541_508_750.00,   # Y17
        0, 0, 0,
    ], dtype=float)

    REPAV = np.array([
        0, 0, 0,
        5_602_365_000.00,   # Y4
        5_602_365_000.00,   # Y5
        5_602_365_000.00,   # Y6
        11_204_730_000.00,  # Y7
        11_204_730_000.00,  # Y8
        11_204_730_000.00,  # Y9
        2_240_946_000.00,   # Y10
        0, 0, 0,
        5_602_365_000.00,   # Y14
        5_602_365_000.00,   # Y15
        5_602_365_000.00,   # Y16
        5_602_365_000.00,   # Y17
        11_204_730_000.00,  # Y18
        11_204_730_000.00,  # Y19
        11_204_730_000.00,  # Y20
    ], dtype=float)

    capex = (PUESTA_VALOR
             + OBRAS_OBLIG * (1 + delta_capex_obras)
             + REPAV       * (1 + delta_capex_repav))

    opex = OPEX_BASE * (1 + delta_opex)

    # ── Impuestos ──────────────────────────────────────────────
    factor_tarifa = tarifa / TARIFA_BASE
    factor = uteq_ref * factor_tarifa

    imp_iva       = IMP_IVA_BASE       * factor * ((1 + al_iva_peaje) / (1 + AL_IVA_BASE))
    imp_ib        = IMP_IB_BASE        * factor * (al_ib       / AL_IB_BASE)
    imp_municipal = IMP_MUNICIPAL_BASE * factor * (al_municipal / AL_MUNICIPAL_BASE)
    imp_sellos    = IMP_SELLOS_BASE    * (al_sellos / AL_SELLOS_BASE)
    imp_dbcr      = IMP_DBCR_BASE      * factor * (al_dbcr     / AL_DBCR_BASE)
    imp_dbcr[0]   = IMP_DBCR_BASE[0]  * (al_dbcr / AL_DBCR_BASE)

    # ── Ganancias – fórmula directa bi_bruta ───────────────────
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
    page_title="Rawson-Trelew-Gaiman – Sensibilidades",
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

# ── SIDEBAR ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌊 Rawson · Trelew · Gaiman")
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
# ENCABEZADO Y KPIs
# ══════════════════════════════════════════════════════════════
st.markdown("# 🌊 Rawson · Trelew · Gaiman — Análisis de Sensibilidades")
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

# ══════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════
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
    "Rawson · Trelew · Gaiman (GESTIÓN–COAC) · Modelo de sensibilidades · "
    "Flujos base tomados del xlsx al 1° de marzo 2025 · "
    "Concesión 20 años (2026–2045) · "
    "No incluye recálculo de préstamo ni WACC."
)
