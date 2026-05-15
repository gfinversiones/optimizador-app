"""
PUERTO BAHÍA BLANCA – Panel de Sensibilidades Financieras
==========================================================
Replicación fiel del modelo PEF_PUERTO_BAHÍA_BLANCA.xlsx.

El modelo NO recalcula el préstamo ni usa WACC.
Los flujos base se toman directamente del xlsx y se
escalan con los factores de sensibilidad ingresados.

Instalación:
    pip install streamlit pandas plotly

Ejecución:
    streamlit run modelo_financiero_PBB.py
"""

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ══════════════════════════════════════════════════════════════
# 0.  FUNCIONES FINANCIERAS PURAS (sin librerías externas)
# ══════════════════════════════════════════════════════════════

def _npv(rate: float, cf: np.ndarray) -> float:
    """VAN con convención Excel: todos los flujos se descuentan a partir de t=1."""
    t = np.arange(1, len(cf) + 1, dtype=float)
    return float(np.sum(cf / (1.0 + rate) ** t))


# Tasa de financiamiento para MIRR (PRESTAMO!D3 = 8.5%)
TASA_FINANCIAMIENTO = 0.085


def _mirr(cf: np.ndarray, reinvest_rate: float) -> float:
    """
    MIRR replicando exactamente =MIRR(flujos, finance_rate=8.5%, reinvest_rate) del xlsx.
    Convención Excel:
      - PV de negativos: descontados con finance_rate desde t=0
      - FV de positivos: acumulados con reinvest_rate hasta t=n-1
      - Exponente: 1/(n-1) donde n = número de períodos
    """
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
# 1.  DATOS BASE  (extraídos del xlsx PEF_PUERTO_BAHÍA_BLANCA)
# ══════════════════════════════════════════════════════════════
#
# Concesión: 20 años (2026–2045).
# Índice 0 = Año 1 de concesión (2026).
# Los arrays tienen 20 elementos [0..19] → Y1..Y20.

YEARS = 20

# ── Ingresos de peaje con IVA (FLUJO fila 72) ──────────────────
# Y1 (2026) = 0 (puesta en valor, sin peaje)
# Y2 (2027) en adelante: peajes existentes + nuevos
PEAJE_BASE = np.array([
    0,                        # Y1  (2026) – puesta en valor
    75_001_166_289.00,        # Y2  (2027)
    77_251_201_277.67,        # Y3  (2028)
    79_568_737_316.00,        # Y4  (2029)
    81_955_799_435.48,        # Y5  (2030)
    84_414_473_418.54,        # Y6  (2031)
    86_946_907_621.10,        # Y7  (2032)
    89_555_314_849.73,        # Y8  (2033)
    92_241_974_295.23,        # Y9  (2034)
    95_009_233_524.08,        # Y10 (2035)
    97_859_510_529.81,        # Y11 (2036)
    100_795_295_845.70,       # Y12 (2037)
    103_819_154_721.07,       # Y13 (2038)
    106_933_729_362.70,       # Y14 (2039)
    110_141_741_243.58,       # Y15 (2040)
    113_445_993_480.89,       # Y16 (2041)
    116_849_373_285.32,       # Y17 (2042)
    120_354_854_483.88,       # Y18 (2043)
    123_965_500_118.39,       # Y19 (2044)
    127_684_465_121.95,       # Y20 (2045)
], dtype=float)

# ── Tarifa base y tránsito ──────────────────────────────────────
# Tarifa base sin IVA: $6.000 por UTEQ (CONTROL!C24 = 6000)
TARIFA_BASE = 6_000.0          # ARS por UTEQ, sin IVA
TARIFA_IVA  = TARIFA_BASE * 1.21

# UTEQs de arranque (año con primer cobro = Y2)
# UTEQ_ARRANQUE = PEAJE_BASE[1] / (TARIFA_BASE * 1.21)
UTEQ_ARRANQUE = PEAJE_BASE[1] / TARIFA_IVA   # ≈ 10.34 M UTEQs

# Crecimiento base de tránsito: 3% constante desde Y2 en adelante.
# (El 5% de FLUJO fila 16 col D es el incremento del tránsito base 2023
# al arranque de la concesión, no un salto entre años consecutivos.)
TRAFICO_CRECIMIENTO_BASE = 0.03

# ── CAPEX con IVA (FLUJO filas 36, 37, 38) ─────────────────────
# Puesta en Valor (fila 36) + Obras Obligatorias (fila 37) + Repavimentación (fila 38)
CAPEX_BASE = np.array([
    11_673_007_500.00,    # Y1  – Puesta en Valor
    0,                    # Y2
    0,                    # Y3
    17_509_511_250.00,    # Y4  – Repavimentación
    17_509_511_250.00,    # Y5
    17_509_511_250.00,    # Y6
    51_024_086_250.00,    # Y7  – Obras Oblig. + Repav.
    67_029_150_000.00,    # Y8
    67_029_150_000.00,    # Y9
    39_013_932_000.00,    # Y10
    32_010_127_500.00,    # Y11
    48_015_191_250.00,    # Y12
    32_010_127_500.00,    # Y13
    49_519_638_750.00,    # Y14
    49_519_638_750.00,    # Y15
    33_514_575_000.00,    # Y16
    33_514_575_000.00,    # Y17
    35_019_022_500.00,    # Y18
    35_019_022_500.00,    # Y19
    35_019_022_500.00,    # Y20
], dtype=float)

# ── OPEX con IVA – Conservación y Mantenimiento (FLUJO fila 25) ─
# Constante: $15.564.010.000 por año (sin IVA × 1.21)
OPEX_BASE = np.full(YEARS, 15_564_010_000.00)

# ── Amortización deuda (FLUJO fila 84 / PRESTAMO) ──────────────
# Préstamo: $8.171.105.250 · TNA 8.5% · 6 cuotas anuales (francés)
# Y1: cuota + gastos administrativos (1% del préstamo)
# Y2–Y6: cuota anual fija $1.794.432.596.93
AMORT_DEUDA_BASE = np.array([
    0,                        # Y1  (puesta en valor, gracia)
    1_876_143_649.43,         # Y2  (cuota $1.794.432.596,93 + gastos admin $81.711.052,50)
    1_794_432_596.93,         # Y3
    1_794_432_596.93,         # Y4
    1_794_432_596.93,         # Y5
    1_794_432_596.93,         # Y6
    1_794_432_596.93,         # Y7
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

# ── Garantías anuales (FLUJO fila 41 / 99) ─────────────────────
GARANTIAS = np.full(YEARS, 98_000_000.0)

# ── Impuestos BASE por componente (IMPUESTOS y FLUJO detallado) ──

IMP_IVA_BASE = np.array([
    0,                       # Y1
    6_551_248_000.55,        # Y2
    11_169_111_453.33,       # Y3
    8_569_193_682.31,        # Y4
    9_023_303_228.90,        # Y5
    9_493_226_493.997,       # Y6
    4_163_044_943.65,        # Y7
    1_862_403_159.33,        # Y8
    2_328_682_897.81,        # Y9
    7_671_096_301.16,        # Y10
    9_381_308_793.89,        # Y11
    7_113_086_916.90,        # Y12
    10_415_627_207.25,       # Y13
    7_917_332_423.98,        # Y14
    8_474_094_816.53,        # Y15
    11_825_298_417.63,       # Y16
    12_415_967_639.89,       # Y17
    12_763_254_480.13,       # Y18
    13_389_895_458.03,       # Y19
    14_035_335_665.25,       # Y20
], dtype=float)

IMP_GANANCIAS_BASE = np.array([
    0,                       # Y1
    9_297_637_948.77,        # Y2
    15_563_371_498.67,       # Y3
    15_226_444_760.33,       # Y4
    14_911_751_294.50,       # Y5
    15_086_260_764.12,       # Y6
    13_474_941_797.92,       # Y7
    12_219_157_827.97,       # Y8
    11_948_745_837.02,       # Y9
    13_321_324_985.19,       # Y10
    15_122_027_235.77,       # Y11
    17_959_309_077.73,       # Y12
    20_820_932_559.04,       # Y13
    22_694_680_997.06,       # Y14
    22_973_538_389.36,       # Y15
    22_873_815_775.47,       # Y16
    22_548_253_158.17,       # Y17
    20_140_603_064.33,       # Y18
    17_086_720_206.32,       # Y19
    8_998_039_835.29,        # Y20
], dtype=float)

IMP_IB_BASE = np.array([
    0,                       # Y1
    1_549_610_873.74,        # Y2
    1_596_099_199.95,        # Y3
    1_643_982_175.95,        # Y4
    1_693_301_641.23,        # Y5
    1_744_100_690.47,        # Y6
    1_796_423_711.18,        # Y7
    1_850_316_422.52,        # Y8
    1_905_825_915.19,        # Y9
    1_963_000_692.65,        # Y10
    2_021_890_713.43,        # Y11
    2_082_547_434.83,        # Y12
    2_145_023_857.87,        # Y13
    2_209_374_573.61,        # Y14
    2_275_655_810.82,        # Y15
    2_343_925_485.14,        # Y16
    2_414_243_249.70,        # Y17
    2_486_670_547.19,        # Y18
    2_561_270_663.60,        # Y19
    2_638_108_783.51,        # Y20
], dtype=float)

IMP_MUNICIPAL_BASE = np.array([
    0,                       # Y1
    309_922_174.75,          # Y2
    319_219_839.99,          # Y3
    328_796_435.19,          # Y4
    338_660_328.25,          # Y5
    348_820_138.09,          # Y6
    359_284_742.24,          # Y7
    370_063_284.50,          # Y8
    381_165_183.04,          # Y9
    392_600_138.53,          # Y10
    404_378_142.69,          # Y11
    416_509_486.97,          # Y12
    429_004_771.57,          # Y13
    441_874_914.72,          # Y14
    455_131_162.16,          # Y15
    468_785_097.03,          # Y16
    482_848_649.94,          # Y17
    497_334_109.44,          # Y18
    512_254_132.72,          # Y19
    527_621_756.70,          # Y20
], dtype=float)

# Impuesto de Sellos: primeros 5 años (IMPUESTOS fila 20)
IMP_SELLOS_BASE = np.array([
    1_331_819_108.93,   # Y1
    1_331_819_108.93,   # Y2
    1_331_819_108.93,   # Y3
    1_331_819_108.93,   # Y4
    1_331_819_108.93,   # Y5
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

IMP_DBCR_BASE = np.array([
    98_053_263.00,       # Y1  (sobre crédito LP)
    900_013_995.47,      # Y2
    927_014_415.33,      # Y3
    954_824_847.79,      # Y4
    983_469_593.23,      # Y5
    1_012_973_681.02,    # Y6
    1_043_362_891.45,    # Y7
    1_074_663_778.20,    # Y8
    1_106_903_691.54,    # Y9
    1_140_110_802.29,    # Y10
    1_174_314_126.36,    # Y11
    1_209_543_550.15,    # Y12
    1_245_829_856.65,    # Y13
    1_283_204_752.35,    # Y14
    1_321_700_894.92,    # Y15
    1_361_351_921.77,    # Y16
    1_402_192_479.42,    # Y17
    1_444_258_253.81,    # Y18
    1_487_586_001.42,    # Y19
    1_532_213_581.46,    # Y20
], dtype=float)

# ── Amortización impositiva (IMPUESTOS fila 48 – variante 5 años obras y repav) ──
# Valores que usa efectivamente la hoja IMPUESTOS del xlsx.
AMORT_IMP_BASE = np.array([
    482_355_681.82,       # Y1
    482_355_681.82,       # Y2
    482_355_681.82,       # Y3
    3_376_489_772.73,     # Y4
    6_270_623_863.64,     # Y5
    9_164_757_954.55,     # Y6
    15_897_835_094.45,    # Y7
    21_686_103_276.27,    # Y8
    24_580_237_367.18,    # Y9
    22_843_756_912.63,    # Y10
    19_949_622_821.72,    # Y11
    14_161_354_639.91,    # Y12
    8_373_086_458.09,     # Y13
    5_478_952_367.18,     # Y14
    7_215_432_821.72,     # Y15
    10_109_566_912.63,    # Y16
    13_727_234_526.27,    # Y17
    23_374_348_162.63,    # Y18
    34_950_884_526.27,    # Y19
    60_998_091_344.45,    # Y20
], dtype=float)

# ── Intereses deducibles del préstamo (PRESTAMO!G col → años 2–7) ──
# Calculo Intereses Deducibles II (IMPUESTOS fila 60) – tope 30% ganancia neta
INT_DEDUCIBLES_BASE = np.array([
    0,                    # Y1
    694_543_946.25,       # Y2
    601_053_410.94,       # Y3
    499_616_180.13,       # Y4
    389_556_784.71,       # Y5
    270_142_340.67,       # Y6
    140_577_668.88,       # Y7
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

# Parámetros de la base imponible
AL_IVA_GASTOS_BASE = 0.11   # IVA sobre gastos operativos (OPEX)

# Ingreso crédito LP: sólo Y1 (FLUJO fila 76)
INGRESO_CREDITO = np.zeros(YEARS)
INGRESO_CREDITO[0] = 8_171_105_250.00

# Alícuotas base
AL_GANANCIAS_BASE = 0.35
AL_IB_BASE        = 0.025
AL_MUNICIPAL_BASE = 0.005
AL_SELLOS_BASE    = 0.012
AL_DBCR_BASE      = 0.012
AL_IVA_BASE       = 0.21

# Tasa de descuento VAN (CONTROL!G21 = 10%)
TASA_VAN_BASE = 0.10


# ══════════════════════════════════════════════════════════════
# 2.  MODELO DE SENSIBILIDAD
# ══════════════════════════════════════════════════════════════

def run_model(
    delta_capex_obras   = 0.0,
    delta_capex_repav   = 0.0,
    delta_opex          = 0.0,
    delta_trafico       = 0.0,   # delta pp sobre tasa crecimiento base (Y3+)
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
    # Y1: 0 (puesta en valor, sin peaje)
    # Y2: UTEQ_ARRANQUE (primer año de cobro)
    # Y3+: crece a tasa_eff = 3% + delta_trafico constante
    uteq = np.zeros(YEARS)
    uteq[0] = 0.0
    uteq[1] = UTEQ_ARRANQUE
    tasa_eff = TRAFICO_CRECIMIENTO_BASE + delta_trafico
    tasa_eff = max(tasa_eff, -0.50)
    for y in range(2, YEARS):
        uteq[y] = uteq[y - 1] * (1 + tasa_eff)

    # ── Ingresos de peaje con IVA ──────────────────────────────
    tarifa_con_iva = tarifa * (1 + al_iva_peaje)
    peaje = np.zeros(YEARS)
    for y in range(1, YEARS):
        peaje[y] = uteq[y] * tarifa_con_iva

    # Factor de tráfico para escalar impuestos proporcionales
    uteq_ref_for_tax = np.zeros(YEARS)
    for y in range(1, YEARS):
        ub = UTEQ_ARRANQUE * ((1 + TRAFICO_CRECIMIENTO_BASE) ** (y - 1))
        uteq_ref_for_tax[y] = uteq[y] / ub if ub > 0 else 1.0

    total_ingresos = peaje + INGRESO_CREDITO

    # ── CAPEX escalado ─────────────────────────────────────────
    # Puesta en Valor (Y1 = fija, no se sensibiliza)
    PUESTA_VALOR = np.zeros(YEARS)
    PUESTA_VALOR[0] = 11_673_007_500.00

    # Obras Obligatorias (FLUJO fila 37) → Y7–Y16
    OBRAS_OBLIG = np.array([
        0, 0, 0, 0, 0, 0,
        16_005_063_750.00,   # Y7
        32_010_127_500.00,   # Y8
        32_010_127_500.00,   # Y9
        32_010_127_500.00,   # Y10
        32_010_127_500.00,   # Y11
        48_015_191_250.00,   # Y12
        32_010_127_500.00,   # Y13
        32_010_127_500.00,   # Y14
        32_010_127_500.00,   # Y15
        16_005_063_750.00,   # Y16
        16_005_063_750.00,   # Y17
        0, 0, 0,
    ], dtype=float)

    # Repavimentación (FLUJO fila 38)
    REPAV = np.array([
        0, 0, 0,
        17_509_511_250.00,   # Y4
        17_509_511_250.00,   # Y5
        17_509_511_250.00,   # Y6
        35_019_022_500.00,   # Y7
        35_019_022_500.00,   # Y8
        35_019_022_500.00,   # Y9
        7_003_804_500.00,    # Y10
        0, 0, 0,
        17_509_511_250.00,   # Y14
        17_509_511_250.00,   # Y15
        17_509_511_250.00,   # Y16
        17_509_511_250.00,   # Y17
        35_019_022_500.00,   # Y18
        35_019_022_500.00,   # Y19
        35_019_022_500.00,   # Y20
    ], dtype=float)

    capex = (PUESTA_VALOR
             + OBRAS_OBLIG * (1 + delta_capex_obras)
             + REPAV       * (1 + delta_capex_repav))

    # ── OPEX escalado ──────────────────────────────────────────
    opex = OPEX_BASE * (1 + delta_opex)

    # ── Impuestos escalados ────────────────────────────────────
    factor_tarifa      = tarifa / TARIFA_BASE
    factor_trafico_avg = uteq_ref_for_tax * factor_tarifa

    imp_iva       = IMP_IVA_BASE      * factor_trafico_avg * ((1 + al_iva_peaje) / (1 + AL_IVA_BASE))
    imp_ib        = IMP_IB_BASE       * factor_trafico_avg * (al_ib       / AL_IB_BASE)
    imp_municipal = IMP_MUNICIPAL_BASE* factor_trafico_avg * (al_municipal / AL_MUNICIPAL_BASE)
    imp_sellos    = IMP_SELLOS_BASE   * (al_sellos / AL_SELLOS_BASE)
    imp_dbcr      = IMP_DBCR_BASE     * factor_trafico_avg * (al_dbcr     / AL_DBCR_BASE)
    imp_dbcr[0]   = IMP_DBCR_BASE[0] * (al_dbcr / AL_DBCR_BASE)   # Y1: DBCR sobre Crédito LP

    # ── Impuesto a las Ganancias ───────────────────────────────
    # BI[y] = peaje[y]/1.21 - GASTOS[y] - (IB+Mun+DBCR+Sellos)[y] - AMORT_IMP[y] - INT_DED_II[y]
    # donde GASTOS = OPEX/1.11 + GARANTIAS
    # Sensibilidades: peaje y gastos escalan; impuestos deducibles escalan con factor_trafico_avg.
    gastos_gan    = opex / (1 + AL_IVA_GASTOS_BASE) + GARANTIAS
    imp_ded_gan   = (imp_ib + imp_municipal + imp_dbcr + imp_sellos)
    bi_bruta      = peaje / (1 + al_iva_peaje) - gastos_gan - imp_ded_gan - AMORT_IMP_BASE - INT_DEDUCIBLES_BASE
    # Años sin ingresos de peaje (Y1): la base imponible es 0, no genera quebranto acumulable.
    bi_bruta      = np.where(peaje == 0, 0.0, bi_bruta)

    quebranto_acum = np.zeros(YEARS)
    imp_ganancias  = np.zeros(YEARS)
    for y in range(YEARS):
        base_y = bi_bruta[y] + (quebranto_acum[y - 1] if y > 0 else 0)
        if base_y <= 0:
            quebranto_acum[y] = base_y
            imp_ganancias[y]  = 0.0
        else:
            quebranto_acum[y] = 0.0
            imp_ganancias[y]  = base_y * al_ganancias

    total_impuestos = imp_iva + imp_ganancias + imp_ib + imp_municipal + imp_sellos + imp_dbcr

    # ── Egresos totales ────────────────────────────────────────
    total_egresos = capex + opex + AMORT_DEUDA_BASE + total_impuestos + GARANTIAS

    # ── Flujo neto ─────────────────────────────────────────────
    flujo = total_ingresos - total_egresos

    # ── Métricas ───────────────────────────────────────────────
    van      = _npv(tasa_van, flujo)
    van_egr  = _npv(tasa_van, total_egresos)
    van_ing  = _npv(tasa_van, total_ingresos)
    vaff_vae = van / van_egr if van_egr != 0 else float("nan")
    mirr_val = _mirr(flujo, tasa_van)
    acum     = np.cumsum(flujo)

    # Payback obras (puesta en valor + obras obligatorias)
    inversion_obras = float(np.sum(PUESTA_VALOR) + np.sum(OBRAS_OBLIG * (1 + delta_capex_obras)))
    payback = next((y + 1 for y, v in enumerate(acum) if v >= inversion_obras), None)

    return dict(
        flujo         = flujo,
        total_ing     = total_ingresos,
        total_egr     = total_egresos,
        peaje         = peaje,
        capex         = capex,
        opex          = opex,
        amort_deuda   = AMORT_DEUDA_BASE.copy(),
        imp_iva       = imp_iva,
        imp_ganancias = imp_ganancias,
        imp_ib        = imp_ib,
        imp_municipal = imp_municipal,
        imp_sellos    = imp_sellos,
        imp_dbcr      = imp_dbcr,
        total_imp     = total_impuestos,
        acum          = acum,
        van           = van,
        van_ing       = van_ing,
        van_egr       = van_egr,
        vaff_vae      = vaff_vae,
        mirr            = mirr_val,
        payback         = payback,
        inversion_obras = inversion_obras,
        uteq            = uteq,
    )


# ══════════════════════════════════════════════════════════════
# 3.  CONSTANTES BASE (calculadas dinámicamente)
# ══════════════════════════════════════════════════════════════

_base_calc    = run_model()
MIRR_BASE     = _base_calc["mirr"]
VAN_BASE      = _base_calc["van"]
VAFF_VAE_BASE = _base_calc["vaff_vae"]


# ══════════════════════════════════════════════════════════════
# 4.  APP STREAMLIT
# ══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Puerto Bahía Blanca – Sensibilidades",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.main { background: #0e1117; }
.block-container { padding-top: 1.2rem; padding-bottom: 1rem; }

/* KPI cards */
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

/* Sidebar section headers */
.sh {
  color: #6c7fe8; font-size: .76rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: .1em;
  margin: 12px 0 4px;
  padding-bottom: 3px;
  border-bottom: 1px solid #2d3650;
}

div[data-testid="stSidebar"] { background: #131720; }
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚓ Puerto Bahía Blanca")
    st.markdown("**GESTIÓN – COAC · 2026–2045**")
    st.markdown("---")

    # ── Tránsito y Tarifa ──────────────────────────────────────
    st.markdown('<div class="sh">🚗 Tránsito y Tarifa</div>', unsafe_allow_html=True)

    tarifa_input = st.number_input(
        "Tarifa base (ARS)",
        min_value=1_000, max_value=50_000,
        value=int(TARIFA_BASE), step=10,
        help=f"Tarifa base del xlsx: $ {TARIFA_BASE:,.0f}. Se aplica desde el Año 2."
    )

    st.caption(
        "📌 **Regla de ingresos:**  \n"
        "**Año 1** → puesta en valor, sin ingresos de peaje.  \n"
        "**Año 2** → tránsito arranque (UTEQs base).  \n"
        "**Año 3+** → crece a tasa base 3% + Δ abajo."
    )

    delta_trafico_pp = st.slider(
        "Δ tasa crecimiento anual Año 3+ (±pp sobre base 3%)",
        min_value=-3.0, max_value=5.0, value=0.0, step=0.01,
        format="%.2f pp",
        help="Afecta al Año 4 en adelante. Tasa base: 3% anual."
    )
    delta_trafico = delta_trafico_pp / 100

    # ── CAPEX ──────────────────────────────────────────────────
    st.markdown('<div class="sh">🏗️ CAPEX – sensibilidades</div>', unsafe_allow_html=True)
    delta_obras = st.slider(
        "Obras obligatorias (%)",
        min_value=-40, max_value=100, value=0, step=1,
        help="Variación % sobre el monto base de obras obligatorias"
    ) / 100
    delta_repav = st.slider(
        "Repavimentación (%)",
        min_value=-40, max_value=100, value=0, step=1,
        help="Variación % sobre el monto base de repavimentaciones"
    ) / 100

    # ── OPEX ───────────────────────────────────────────────────
    st.markdown('<div class="sh">⚙️ OPEX – Conservación y Mantenimiento</div>', unsafe_allow_html=True)
    delta_opex = st.slider(
        "Variación OPEX (%)",
        min_value=-40, max_value=100, value=0, step=1
    ) / 100

    # ── Impuestos ──────────────────────────────────────────────
    st.markdown('<div class="sh">💰 Alícuotas impositivas</div>', unsafe_allow_html=True)
    al_ganancias = st.slider(
        "Ganancias (%)", 0.0, 55.0, 35.0, 0.1,
        format="%.1f %%", help="Base: 35%"
    ) / 100
    al_ib = st.slider(
        "Ingresos Brutos (%)", 0.0, 10.0, 2.5, 0.1,
        format="%.1f %%", help="Base: 2.5%"
    ) / 100
    al_municipal = st.slider(
        "Tasas Municipales (%)", 0.0, 3.0, 0.5, 0.1,
        format="%.1f %%", help="Base: 0.5%"
    ) / 100
    al_sellos = st.slider(
        "Impuesto de Sellos (%)", 0.0, 5.0, 1.2, 0.1,
        format="%.1f %%", help="Base: 1.2% (primeros 5 años)"
    ) / 100
    al_dbcr = st.slider(
        "Débitos y Créditos Bancarios (%)", 0.0, 5.0, 1.2, 0.1,
        format="%.1f %%", help="Base: 1.2%"
    ) / 100
    al_iva_peaje = st.slider(
        "IVA sobre peaje (%)", 0, 27, 21, 1,
        help="Base: 21%"
    ) / 100

    # ── Tasa de descuento ──────────────────────────────────────
    st.markdown('<div class="sh">📐 Tasa de descuento VAN</div>', unsafe_allow_html=True)
    tasa_van = st.slider(
        "Tasa de descuento (%)", 5.0, 25.0, 10.0, 0.1,
        format="%.1f %%"
    ) / 100

    st.markdown("---")
    if st.button("↺  Resetear todo al base", use_container_width=True):
        st.rerun()

# ── EJECUTAR MODELO ────────────────────────────────────────────
sc = run_model(
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

YEARS_RANGE = list(range(2026, 2026 + YEARS))   # 2026..2045


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
# 4.  ENCABEZADO Y KPIs
# ══════════════════════════════════════════════════════════════
st.markdown("# ⚓ Puerto Bahía Blanca — Análisis de Sensibilidades")
st.markdown(
    "Concesión vial 20 años · 2026–2045 &nbsp;|&nbsp; "
    "Modificá los parámetros en el panel ← para ver el impacto en tiempo real"
)
st.divider()

c1, c2, c3, c4 = st.columns(4)
mirr_s   = f"{sc['mirr']:.2%}"    if not np.isnan(sc["mirr"])     else "n/d"
vaff_s   = f"{sc['vaff_vae']:.2%}" if not np.isnan(sc["vaff_vae"]) else "n/d"
pb_año   = sc["payback"]
pb_s     = f"Año {pb_año}  ({2025 + pb_año})" if pb_año is not None else "No recupera"
inv_obras_s = fmt_ars(sc["inversion_obras"])

c1.markdown(kpi("VAFF / VAE", vaff_s,
                sc["vaff_vae"], VAFF_VAE_BASE), unsafe_allow_html=True)
c2.markdown(kpi(f"VAN  (tasa {tasa_van:.0%})", fmt_ars(sc["van"]),
                sc["van"], VAN_BASE), unsafe_allow_html=True)
c3.markdown(kpi("TIR Modificada (MIRR)", mirr_s,
                sc["mirr"], MIRR_BASE), unsafe_allow_html=True)
pb_dlt = "" if pb_año is None else delta_html(0, 0)
c4.markdown(f"""<div class="kpi">
  <div class="lbl">Payback obras · {inv_obras_s}</div>
  <div class="val">{pb_s}</div>
  <div class="dlt">{pb_dlt}</div>
</div>""", unsafe_allow_html=True)

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
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["flujo"]/1e9,
                         marker_color=bc, name="Flujo Neto"),
                  row=1, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="#888", row=1, col=1)

    fig.add_trace(go.Scatter(
        x=YEARS_RANGE, y=sc["acum"]/1e9, mode="lines+markers",
        line=dict(color=C["acc"], width=2.5), marker=dict(size=5),
        fill="tozeroy", fillcolor="rgba(108,127,232,.12)", name="Acumulado"),
        row=1, col=2)
    fig.add_hline(y=0, line_dash="dot", line_color="#888", row=1, col=2)

    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["capex"]/1e9,
                         name="CAPEX", marker_color=C["neg"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["opex"]/1e9,
                         name="OPEX", marker_color=C["warn"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["total_imp"]/1e9,
                         name="Impuestos", marker_color=C["pur"]), row=2, col=1)
    fig.add_trace(go.Bar(x=YEARS_RANGE, y=sc["amort_deuda"]/1e9,
                         name="Deuda LP", marker_color=C["gry"]), row=2, col=1)

    fig.add_trace(go.Scatter(x=YEARS_RANGE, y=sc["total_ing"]/1e9,
                              mode="lines", line=dict(color=C["pos"], width=2.5),
                              name="Ingresos"), row=2, col=2)
    fig.add_trace(go.Scatter(x=YEARS_RANGE, y=sc["total_egr"]/1e9,
                              mode="lines", line=dict(color=C["neg"], width=2.5),
                              name="Egresos"), row=2, col=2)

    fig.update_layout(**PL, barmode="stack", height=640, showlegend=True,
                      legend=dict(orientation="h", y=-0.07,
                                  bgcolor="rgba(0,0,0,0)"))
    for ax in ["xaxis","xaxis2","xaxis3","xaxis4",
               "yaxis","yaxis2","yaxis3","yaxis4"]:
        fig.update_layout(**{ax: dict(gridcolor="#252f45", zeroline=False)})

    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# TAB 2 – TORNADO + SPIDER
# ─────────────────────────────────────────────────────────────
with tab2:
    st.markdown("#### Gráfico Tornado — impacto individual sobre el VAN")
    st.caption("Cada barra aplica un shock de ±20% a UNA sola variable, manteniendo el resto en el valor del panel.")

    BASE_KW = dict(
        delta_capex_obras=delta_obras, delta_capex_repav=delta_repav,
        delta_opex=delta_opex, delta_trafico=delta_trafico,
        tarifa=float(tarifa_input),
        al_ganancias=al_ganancias, al_ib=al_ib,
        al_municipal=al_municipal, al_sellos=al_sellos,
        al_dbcr=al_dbcr, al_iva_peaje=al_iva_peaje, tasa_van=tasa_van,
    )

    shocks = {
        "Obras +20%":         dict(delta_capex_obras=delta_obras+0.20),
        "Obras –20%":         dict(delta_capex_obras=delta_obras-0.20),
        "Repavim. +20%":      dict(delta_capex_repav=delta_repav+0.20),
        "Repavim. –20%":      dict(delta_capex_repav=delta_repav-0.20),
        "OPEX +20%":          dict(delta_opex=delta_opex+0.20),
        "OPEX –20%":          dict(delta_opex=delta_opex-0.20),
        "Tránsito +1pp":      dict(delta_trafico=delta_trafico+0.01),
        "Tránsito –1pp":      dict(delta_trafico=delta_trafico-0.01),
        "Tarifa +20%":        dict(tarifa=float(tarifa_input)*1.20),
        "Tarifa –20%":        dict(tarifa=float(tarifa_input)*0.80),
        "Ganancias +10pp":    dict(al_ganancias=min(0.60, al_ganancias+0.10)),
        "Ganancias –10pp":    dict(al_ganancias=max(0.00, al_ganancias-0.10)),
        "IB +2pp":            dict(al_ib=al_ib+0.02),
        "IB –2pp":            dict(al_ib=max(0, al_ib-0.02)),
        "IVA peaje +3pp":     dict(al_iva_peaje=al_iva_peaje+0.03),
        "IVA peaje –3pp":     dict(al_iva_peaje=max(0, al_iva_peaje-0.03)),
        "Db/Cr +1pp":         dict(al_dbcr=al_dbcr+0.01),
        "Db/Cr –1pp":         dict(al_dbcr=max(0, al_dbcr-0.01)),
        "Tasa descuento +2pp":dict(tasa_van=tasa_van+0.02),
        "Tasa descuento –2pp":dict(tasa_van=max(0.01, tasa_van-0.02)),
    }

    base_van = sc["van"]
    t_rows = []
    for label, ov in shocks.items():
        r = run_model(**{**BASE_KW, **ov})
        t_rows.append({"Variable": label,
                        "ΔVAN": (r["van"] - base_van) / 1e9})
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
        "CAPEX Obras":    lambda p: dict(delta_capex_obras=delta_obras + p/100),
        "CAPEX Repavim.": lambda p: dict(delta_capex_repav=delta_repav + p/100),
        "OPEX":           lambda p: dict(delta_opex=delta_opex + p/100),
        "Tránsito (+pp)": lambda p: dict(delta_trafico=delta_trafico + p/100),
        "Tarifa (+%)":    lambda p: dict(tarifa=float(tarifa_input) * (1 + p/100)),
        "Ganancias (+pp)":lambda p: dict(al_ganancias=max(0, al_ganancias + p/100)),
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

    fig3.add_hline(y=MIRR_BASE*100, line_dash="dash", line_color="#aaa",
                   annotation_text=f"Base {MIRR_BASE*100:.1f}%",
                   annotation_position="bottom right")
    fig3.update_layout(**PL, height=400,
                       margin=dict(t=40, b=50, l=60, r=20),
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

    # ── Mapa 1: MIRR = Δtráfico × CAPEX obras ─────────────────
    st.markdown("#### MIRR (%) — Δ Tránsito (pp) × Obras CAPEX (%)")
    mat1 = np.zeros((len(trafico_rng), len(capex_rng)))
    for i, tr in enumerate(trafico_rng):
        for j, cp in enumerate(capex_rng):
            r = heat(delta_trafico=delta_trafico+tr/100,
                     delta_capex_obras=delta_obras+cp/100)
            mat1[i, j] = r["mirr"]*100 if not np.isnan(r["mirr"]) else 0

    fig4 = go.Figure(go.Heatmap(
        z=mat1.round(1),
        x=[f"{c:+d}%" for c in capex_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng],
        colorscale="RdYlGn", text=mat1.round(1),
        texttemplate="%{text:.1f}%",
        colorbar=dict(title="MIRR (%)", tickfont=dict(color="#c5cdd8")),
    ))
    fig4.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=100,r=20))
    fig4.update_xaxes(title_text="Variación obras CAPEX")
    fig4.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig4, use_container_width=True)

    # ── Mapa 2: VAN = Δtráfico × OPEX ─────────────────────────
    st.markdown("#### VAN ($ MM) — Δ Tránsito × OPEX (%)")
    mat2 = np.zeros((len(trafico_rng), len(opex_rng)))
    for i, tr in enumerate(trafico_rng):
        for j, op in enumerate(opex_rng):
            r = heat(delta_trafico=delta_trafico+tr/100,
                     delta_opex=delta_opex+op/100)
            mat2[i, j] = r["van"] / 1e9

    fig5 = go.Figure(go.Heatmap(
        z=mat2.round(1),
        x=[f"{o:+d}%" for o in opex_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng],
        colorscale="RdYlGn", text=mat2.round(1),
        texttemplate="%{text:.0f}",
        colorbar=dict(title="VAN (MM$)", tickfont=dict(color="#c5cdd8")),
    ))
    fig5.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=100,r=20))
    fig5.update_xaxes(title_text="Variación OPEX")
    fig5.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig5, use_container_width=True)

    # ── Mapa 3: VAN = tasa descuento × obras CAPEX ────────────
    st.markdown("#### VAN ($ MM) — Tasa de descuento × Obras CAPEX (%)")
    mat3 = np.zeros((len(tasa_rng), len(capex_rng)))
    for i, td in enumerate(tasa_rng):
        for j, cp in enumerate(capex_rng):
            r = heat(tasa_van=td/100, delta_capex_obras=delta_obras+cp/100)
            mat3[i, j] = r["van"] / 1e9

    fig6 = go.Figure(go.Heatmap(
        z=mat3.round(1),
        x=[f"{c:+d}%" for c in capex_rng],
        y=[f"{t}%" for t in tasa_rng],
        colorscale="RdYlGn", text=mat3.round(1),
        texttemplate="%{text:.0f}",
        colorbar=dict(title="VAN (MM$)", tickfont=dict(color="#c5cdd8")),
    ))
    fig6.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=80,r=20))
    fig6.update_xaxes(title_text="Variación obras CAPEX")
    fig6.update_yaxes(title_text="Tasa de descuento")
    st.plotly_chart(fig6, use_container_width=True)

    # ── Mapa 4: VAFF/VAE = Δtráfico × Ganancias ───────────────
    st.markdown("#### VAFF/VAE — Δ Tránsito × Alícuota Ganancias (%)")
    mat4 = np.zeros((len(trafico_rng), len(gan_rng)))
    for i, tr in enumerate(trafico_rng):
        for j, ga in enumerate(gan_rng):
            r = heat(delta_trafico=delta_trafico+tr/100,
                     al_ganancias=ga/100)
            mat4[i, j] = r["vaff_vae"] if not np.isnan(r["vaff_vae"]) else 0

    fig7 = go.Figure(go.Heatmap(
        z=mat4.round(4),
        x=[f"{g}%" for g in gan_rng],
        y=[f"{t:+.1f}pp" for t in trafico_rng],
        colorscale="RdYlGn", text=mat4.round(3),
        texttemplate="%{text:.3f}",
        colorbar=dict(title="VAFF/VAE", tickfont=dict(color="#c5cdd8")),
    ))
    fig7.update_layout(**PL, height=370, margin=dict(t=30,b=60,l=100,r=20))
    fig7.update_xaxes(title_text="Alícuota Ganancias")
    fig7.update_yaxes(title_text="Δ crecimiento tránsito")
    st.plotly_chart(fig7, use_container_width=True)


# ── FOOTER ─────────────────────────────────────────────────────
st.divider()
st.caption(
    "Puerto Bahía Blanca (GESTIÓN–COAC) · Modelo de sensibilidades · "
    "Flujos base tomados del xlsx al 1° de marzo 2025 · "
    "Concesión 20 años (2026–2045) · "
    "No incluye recálculo de préstamo ni WACC."
)
