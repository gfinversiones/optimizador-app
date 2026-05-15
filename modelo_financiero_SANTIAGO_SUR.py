"""
SANTIAGO SUR – Panel de Sensibilidades Financieras
===================================================
Replicación fiel del modelo SANTIAGO_SUR.xlsx.

Instalación:
    pip install streamlit pandas plotly

Ejecución:
    streamlit run modelo_financiero_SANTIAGO_SUR.py
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
# 1.  DATOS BASE  (extraídos del xlsx SANTIAGO_SUR)
# ══════════════════════════════════════════════════════════════

YEARS = 20

# ── Ingresos de peaje con IVA (FLUJO fila 72) ──────────────────
PEAJE_BASE = np.array([
    0,                       # Y1  (2026)
    7_276_732_759.22,        # Y2  (2027)
    7_495_034_741.99,        # Y3  (2028)
    7_719_885_784.25,        # Y4  (2029)
    7_951_482_357.78,        # Y5  (2030)
    8_190_026_828.51,        # Y6  (2031)
    8_435_727_633.37,        # Y7  (2032)
    8_688_799_462.37,        # Y8  (2033)
    8_949_463_446.24,        # Y9  (2034)
    9_217_947_349.63,        # Y10 (2035)
    9_494_485_770.12,        # Y11 (2036)
    9_779_320_343.22,        # Y12 (2037)
    10_072_699_953.52,       # Y13 (2038)
    10_374_880_952.12,       # Y14 (2039)
    10_686_127_380.69,       # Y15 (2040)
    11_006_711_202.11,       # Y16 (2041)
    11_336_912_538.17,       # Y17 (2042)
    11_677_019_914.32,       # Y18 (2043)
    12_027_330_511.75,       # Y19 (2044)
    12_388_150_427.10,       # Y20 (2045)
], dtype=float)

TARIFA_BASE = 6_000.0
TARIFA_IVA  = TARIFA_BASE * 1.21
UTEQ_ARRANQUE = PEAJE_BASE[1] / TARIFA_IVA   # ≈ 1.002M UTEQs
TRAFICO_CRECIMIENTO_BASE = 0.03

INGRESO_CREDITO = np.zeros(YEARS)
INGRESO_CREDITO[0] = 966_483_000.00

# ── OPEX con IVA (FLUJO fila 80) ───────────────────────────────
OPEX_BASE = np.full(YEARS, 1_840_920_000.00)

# ── Garantías (FLUJO fila 99) ──────────────────────────────────
GARANTIAS = np.full(YEARS, 12_000_000.0)

# ── Amortización deuda (FLUJO fila 84 / PRESTAMO) ──────────────
# Préstamo: $966.483.000 · TNA 8,5% · 6 cuotas · año de gracia Y1
# Y2: cuota $212.246.513,36 + gastos admin $9.664.830 = $221.911.343,36
AMORT_DEUDA_BASE = np.array([
    0,                    # Y1
    221_911_343.36,       # Y2
    212_246_513.36,       # Y3
    212_246_513.36,       # Y4
    212_246_513.36,       # Y5
    212_246_513.36,       # Y6
    212_246_513.36,       # Y7
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

# ── Impuestos BASE ──────────────────────────────────────────────

IMP_IVA_BASE = np.array([
    0,                      # Y1
    498_021_172.49,         # Y2
    1_035_993_927.15,       # Y3
    719_923_445.05,         # Y4
    764_828_538.27,         # Y5
    811_339_869.84,         # Y6
    147_148_640.93,         # Y7
    0,                      # Y8  (acumulado negativo → pago 0)
    0,                      # Y9  (ídem)
    382_359_148.56,         # Y10
    699_714_307.21,         # Y11
    396_205_224.86,         # Y12
    800_065_529.12,         # Y13
    493_074_338.80,         # Y14
    547_092_314.00,         # Y15
    955_674_010.28,         # Y16
    1_012_981_680.18,       # Y17
    1_065_515_935.54,       # Y18
    1_126_313_642.53,       # Y19
    1_188_935_280.74,       # Y20
], dtype=float)

IMP_GANANCIAS_BASE = np.array([
    0,                      # Y1
    654_870_282.23,         # Y2
    1_384_858_925.48,       # Y3
    1_331_390_298.68,       # Y4
    1_280_142_933.87,       # Y5
    1_288_289_270.94,       # Y6
    1_079_918_508.34,       # Y7
    916_057_902.13,         # Y8
    868_287_884.08,         # Y9
    1_014_378_231.19,       # Y10
    1_210_619_450.62,       # Y11
    1_528_965_490.51,       # Y12
    1_849_673_195.06,       # Y13
    2_053_001_472.08,       # Y14
    2_067_136_131.71,       # Y15
    2_035_926_669.22,       # Y16
    1_977_422_295.59,       # Y17
    1_672_047_525.77,       # Y18
    1_289_618_078.97,       # Y19
    311_033_471.08,         # Y20
], dtype=float)

IMP_IB_BASE = np.array([
    0,                      # Y1
    150_345_718.17,         # Y2
    154_856_089.71,         # Y3
    159_501_772.40,         # Y4
    164_286_825.57,         # Y5
    169_215_430.34,         # Y6
    174_291_893.25,         # Y7
    179_520_650.05,         # Y8
    184_906_269.55,         # Y9
    190_453_457.64,         # Y10
    196_167_061.37,         # Y11
    202_052_073.21,         # Y12
    208_113_635.40,         # Y13
    214_357_044.47,         # Y14
    220_787_755.80,         # Y15
    227_411_388.47,         # Y16
    234_233_730.13,         # Y17
    241_260_742.03,         # Y18
    248_498_564.29,         # Y19
    255_953_521.22,         # Y20
], dtype=float)

IMP_MUNICIPAL_BASE = np.array([
    0,                      # Y1
    30_069_143.63,          # Y2
    30_971_217.94,          # Y3
    31_900_354.48,          # Y4
    32_857_365.11,          # Y5
    33_843_086.07,          # Y6
    34_858_378.65,          # Y7
    35_904_130.01,          # Y8
    36_981_253.91,          # Y9
    38_090_691.53,          # Y10
    39_233_412.27,          # Y11
    40_410_414.64,          # Y12
    41_622_727.08,          # Y13
    42_871_408.89,          # Y14
    44_157_551.16,          # Y15
    45_482_277.69,          # Y16
    46_846_746.03,          # Y17
    48_252_148.41,          # Y18
    49_699_712.86,          # Y19
    51_190_704.24,          # Y20
], dtype=float)

IMP_SELLOS_BASE = np.array([
    163_103_343.47,         # Y1
    163_103_343.47,         # Y2
    163_103_343.47,         # Y3
    163_103_343.47,         # Y4
    163_103_343.47,         # Y5
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

IMP_DBCR_BASE = np.array([
    11_597_796.00,          # Y1
    87_320_793.11,          # Y2
    89_940_416.90,          # Y3
    92_638_629.41,          # Y4
    95_417_788.29,          # Y5
    98_280_321.94,          # Y6
    101_228_731.60,         # Y7
    104_265_593.55,         # Y8
    107_393_561.35,         # Y9
    110_615_368.20,         # Y10
    113_933_829.24,         # Y11
    117_351_844.12,         # Y12
    120_872_399.44,         # Y13
    124_498_571.43,         # Y14
    128_233_528.57,         # Y15
    132_080_534.43,         # Y16
    136_042_950.46,         # Y17
    140_124_238.97,         # Y18
    144_327_966.14,         # Y19
    148_657_805.13,         # Y20
], dtype=float)

# ── Amortización impositiva (AMORTIZACIONES fila 98 – escenario 20/5) ──
AMORT_IMP_BASE = np.array([
    57_053_305.79,          # Y1
    57_053_305.79,          # Y2
    57_053_305.79,          # Y3
    399_373_140.50,         # Y4
    741_692_975.21,         # Y5
    1_084_012_809.92,       # Y6
    1_888_701_180.64,       # Y7
    2_573_340_850.06,       # Y8
    2_915_660_684.77,       # Y9
    2_710_268_783.94,       # Y10
    2_367_948_949.23,       # Y11
    1_683_309_279.81,       # Y12
    998_669_610.39,         # Y13
    656_349_775.68,         # Y14
    861_741_676.51,         # Y15
    1_204_061_511.22,       # Y16
    1_631_961_304.60,       # Y17
    2_773_027_420.31,       # Y18
    4_142_306_759.15,       # Y19
    7_223_185_271.55,       # Y20
], dtype=float)

# ── Intereses deducibles (IMPUESTOS fila 60) ───────────────────
INT_DEDUCIBLES_BASE = np.array([
    0,                      # Y1
    82_151_055.00,          # Y2
    71_092_941.04,          # Y3
    59_094_887.39,          # Y4
    46_076_999.19,          # Y5
    31_952_590.48,          # Y6
    16_627_607.04,          # Y7
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
    PUESTA_VALOR[0] = 1_380_690_000.00

    OBRAS_OBLIG = np.array([
        0, 0, 0, 0, 0, 0,
        2_033_625_000.00,   # Y7
        4_067_250_000.00,   # Y8
        4_067_250_000.00,   # Y9
        4_067_250_000.00,   # Y10
        4_067_250_000.00,   # Y11
        6_100_875_000.00,   # Y12
        4_067_250_000.00,   # Y13
        4_067_250_000.00,   # Y14
        4_067_250_000.00,   # Y15
        2_033_625_000.00,   # Y16
        2_033_625_000.00,   # Y17
        0, 0, 0,
    ], dtype=float)

    REPAV = np.array([
        0, 0, 0,
        2_071_035_000.00,   # Y4
        2_071_035_000.00,   # Y5
        2_071_035_000.00,   # Y6
        4_142_070_000.00,   # Y7
        4_142_070_000.00,   # Y8
        4_142_070_000.00,   # Y9
        828_414_000.00,     # Y10
        0, 0, 0,
        2_071_035_000.00,   # Y14
        2_071_035_000.00,   # Y15
        2_071_035_000.00,   # Y16
        2_071_035_000.00,   # Y17
        4_142_070_000.00,   # Y18
        4_142_070_000.00,   # Y19
        4_142_070_000.00,   # Y20
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
    page_title="Santiago Sur · Sensibilidades",
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
    st.markdown("## 🛣️ Santiago Sur")
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

st.markdown("# 🛣️ Santiago Sur — Análisis de Sensibilidades")
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
    "Santiago Sur (GESTIÓN–COAC) · Modelo de sensibilidades · "
    "Flujos base tomados del xlsx al 1° de marzo 2025 · "
    "Concesión 20 años (2026–2045) · "
    "No incluye recálculo de préstamo ni WACC."
)
