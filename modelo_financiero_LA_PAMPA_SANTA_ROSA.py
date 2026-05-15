"""
LA PAMPA SANTA ROSA – Panel de Sensibilidades Financieras
==========================================================
Replicación fiel del modelo LA_PAMPA_SANTA_ROSA.xlsx.

El modelo NO recalcula el préstamo ni usa WACC.
Los flujos base se toman directamente del xlsx y se
escalan con los factores de sensibilidad ingresados.

Instalación:
    pip install streamlit pandas plotly

Ejecución:
    streamlit run modelo_financiero_LA_PAMPA_SANTA_ROSA.py
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


# Tasa de financiamiento para MIRR (tasa del préstamo, CONTROL!G26 = 8.5%)
# Confirmado en PRESTAMO!D3 = 0.085
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
# 1.  DATOS BASE  (extraídos del xlsx CAUCETE)
# ══════════════════════════════════════════════════════════════
#
# Años de concesión: 1-20 (2026-2045).
# Índice 0 = año inicio concesión (2025/2026, puesta en valor + crédito).
# Los arrays tienen 21 elementos [0..20].

YEARS = 20

# ── Ingresos de peaje con IVA (del sheet FLUJO fila 72) ─────────
# LA PAMPA SANTA ROSA: Y0 = 0 (puesta en valor, sin ingresos peaje)
PEAJE_BASE = np.array([
    0,                         # Y0
    16_423_730_205.18,         # Y1
    16_916_442_111.34,         # Y2
    17_423_935_374.68,         # Y3
    17_946_653_435.92,         # Y4
    18_485_053_038.99,         # Y5
    19_039_604_630.16,         # Y6
    19_610_792_769.07,         # Y7
    20_199_116_552.14,         # Y8
    20_805_090_048.70,         # Y9
    21_429_242_750.16,         # Y10
    22_072_120_032.67,         # Y11
    22_734_283_633.65,         # Y12
    23_416_312_142.66,         # Y13
    24_118_801_506.94,         # Y14
    24_842_365_552.15,         # Y15
    25_587_636_518.71,         # Y16
    26_355_265_614.27,         # Y17
    27_145_923_582.70,         # Y18
    27_960_301_290.18,         # Y19
    27_960_301_290.18,         # Y20 extrapolo
], dtype=float)

# ── Tarifa base y tránsito explícito ───────────────────────────
# Tarifa base sin IVA: $6.000 por UTEQ (CONTROL!C24 = 6000) – idéntico en CÓRDOBA NORTE
TARIFA_BASE = 6_000.0          # ARS por UTEQ, sin IVA
TARIFA_IVA  = TARIFA_BASE * 1.21

# UTEQ_BASE: tránsito implícito derivado del xlsx.
# Y0 = 0 (puesta en valor, sin peaje)
# Y1 = 0 según nueva lógica: el año 1 NO genera ingresos de peaje.
#       El tránsito de referencia (arranque de concesión) lo derivamos
#       del ingreso que el xlsx asigna a Y1, pero NO se cobra ese año.
# Y2 en adelante: tránsito crece sobre el tránsito de arranque.
UTEQ_BASE = np.zeros(YEARS + 1)
# UTEQ_ARRANQUE: tránsito del primer año de cobro (Y1 = 2027).
# PEAJE_BASE[1] = ingresos de peaje de Y1 con IVA incluido (= xlsx FLUJO!D72 × 1.21).
# UTEQ = peaje_con_IVA / (tarifa × (1 + IVA))
UTEQ_ARRANQUE = PEAJE_BASE[1] / TARIFA_IVA   # ≈ 3.380 M UTEQs  (PEAJE_BASE tiene IVA)

# Crecimiento base: 3% anual constante desde Y1
TRAFICO_CRECIMIENTO_BASE = 0.03

# ── CAPEX con IVA (del sheet FLUJO, TOTAL CAPEX fila 39) ────────────────
# Desglose: Obras Puesta en Valor (fila 36) + Obras Obligatorias (fila 37) + Repavimentación (fila 38)
CAPEX_BASE = np.array([
    3_408_660_000.00,     # Y0  puesta en valor
    0,                    # Y1
    0,                    # Y2
    5_112_990_000.00,     # Y3
    5_112_990_000.00,     # Y4
    5_112_990_000.00,     # Y5
    10_552_447_500.00,    # Y6
    10_878_915_000.00,    # Y7
    10_878_915_000.00,    # Y8
    2_698_131_000.00,     # Y9
    652_935_000.00,       # Y10
    979_402_500.00,       # Y11
    652_935_000.00,       # Y12
    5_765_925_000.00,     # Y13
    5_765_925_000.00,     # Y14
    5_439_457_500.00,     # Y15
    5_439_457_500.00,     # Y16
    10_225_980_000.00,    # Y17
    10_225_980_000.00,    # Y18
    10_225_980_000.00,    # Y19
    10_225_980_000.00,    # Y20
], dtype=float)

# ── OPEX con IVA – Conservación y Mantenimiento (FLUJO fila 25) ──────
OPEX_BASE = np.full(YEARS + 1, 4_544_880_000.00)

# ── Amortización deuda (del sheet FLUJO fila 84 – ya es un egreso fijo) ─
# Cuota anual: 523_996_118.04; Año 1 incluye gastos admin (547_856_738.04)
AMORT_DEUDA_BASE = np.array([
    0,                        # Y0
    547_856_738.04,           # Y1 (cuota + gastos admin)
    523_996_118.04,           # Y2
    523_996_118.04,           # Y3
    523_996_118.04,           # Y4
    523_996_118.04,           # Y5
    523_996_118.04,           # Y6
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

# ── Garantías anuales (FLUJO fila 41) ─────────────────────────
GARANTIAS = np.full(YEARS + 1, 20_000_000.0)

# ── Impuestos BASE por componente (del sheet IMPUESTOS detallado) ──
# Todos con IVA / tal como aparecen en el flujo

IMP_IVA_BASE = np.array([
    0,                    # Y0
    965_390_866.90,       # Y1
    2_283_848_223.10,     # Y2
    1_495_265_742.10,     # Y3
    1_597_615_092.62,     # Y4
    1_703_674_556.44,     # Y5
    869_571_727.23,       # Y6
    919_168_351.58,       # Y7
    1_021_274_132.12,     # Y8
    2_546_248_573.67,     # Y9
    3_009_523_968.14,     # Y10
    3_064_438_062.62,     # Y11
    3_236_018_666.93,     # Y12
    2_467_008_821.38,     # Y13
    2_588_928_463.12,     # Y14
    2_771_165_342.86,     # Y15
    2_900_509_890.78,     # Y16
    2_203_015_994.14,     # Y17
    2_340_237_625.03,     # Y18
    2_481_575_904.84,     # Y19
    2_481_575_904.84,     # Y20 extrapolo
], dtype=float)

IMP_GANANCIAS_BASE = np.array([
    0,                    # Y0
    1_327_901_812.31,     # Y1
    3_048_782_139.05,     # Y2
    2_903_616_878.61,     # Y3
    2_763_540_647.04,     # Y4
    2_704_514_262.96,     # Y5
    2_272_691_651.02,     # Y6
    1_853_337_794.81,     # Y7
    1_720_145_036.86,     # Y8
    2_065_098_776.35,     # Y9
    2_533_393_981.40,     # Y10
    3_302_657_068.23,     # Y11
    4_077_250_479.07,     # Y12
    4_561_541_313.72,     # Y13
    4_578_218_593.24,     # Y14
    4_482_403_337.76,     # Y15
    4_318_639_206.44,     # Y16
    3_544_819_360.88,     # Y17
    2_580_168_994.34,     # Y18
    143_110_204.41,       # Y19
    143_110_204.41,       # Y20 extrapolo
], dtype=float)

IMP_IB_BASE = np.array([
    0,                    # Y0
    339_333_268.70,       # Y1
    349_513_266.76,       # Y2
    359_998_664.77,       # Y3
    370_798_624.71,       # Y4
    381_922_583.45,       # Y5
    393_380_260.95,       # Y6
    405_181_668.78,       # Y7
    417_337_118.85,       # Y8
    429_857_232.41,       # Y9
    442_752_949.38,       # Y10
    456_035_537.87,       # Y11
    469_716_604.00,       # Y12
    483_808_102.12,       # Y13
    498_322_345.18,       # Y14
    513_272_015.54,       # Y15
    528_670_176.01,       # Y16
    544_530_281.29,       # Y17
    560_866_189.73,       # Y18
    577_692_175.42,       # Y19
    577_692_175.42,       # Y20 extrapolo
], dtype=float)

IMP_MUNICIPAL_BASE = np.array([
    0,                    # Y0
    67_866_653.74,        # Y1
    69_902_653.35,        # Y2
    71_999_732.95,        # Y3
    74_159_724.94,        # Y4
    76_384_516.69,        # Y5
    78_676_052.19,        # Y6
    81_036_333.76,        # Y7
    83_467_423.77,        # Y8
    85_971_446.48,        # Y9
    88_550_589.88,        # Y10
    91_207_107.57,        # Y11
    93_943_320.80,        # Y12
    96_761_620.42,        # Y13
    99_664_469.04,        # Y14
    102_654_403.11,       # Y15
    105_734_035.20,       # Y16
    108_906_056.26,       # Y17
    112_173_237.95,       # Y18
    115_538_435.08,       # Y19
    115_538_435.08,       # Y20 extrapolo
], dtype=float)

# ── Amortización impositiva (AMORTIZACIONES fila 48) ──────────
AMORT_IMP_BASE = np.array([
    0,                      # Y0
    563_414_876.03,         # Y1
    563_414_876.03,         # Y2
    563_414_876.03,         # Y3
    1_408_537_190.08,       # Y4
    2_253_659_504.13,       # Y5
    2_535_366_942.15,       # Y6
    4_279_573_140.50,       # Y7
    5_969_817_768.60,       # Y8
    6_814_940_082.64,       # Y9
    6_307_866_694.21,       # Y10
    5_462_744_380.17,       # Y11
    3_718_538_181.82,       # Y12
    2_028_293_553.72,       # Y13
    1_183_171_239.67,       # Y14
    1_690_244_628.10,       # Y15
    2_535_366_942.15,       # Y16
    3_591_769_834.71,       # Y17
    6_408_844_214.88,       # Y18
    9_789_333_471.07,       # Y19
    17_395_434_297.52,      # Y20
], dtype=float)

# ── Intereses deducibles efectivos del préstamo (IMPUESTOS fila 60) ──
# Solo aplican años 1-7 (mientras dura el préstamo)
INT_DEDUCIBLES_BASE = np.array([
    0,                      # Y0
    0,                      # Y1
    202_815_270.00,         # Y2
    175_514_897.92,         # Y3
    145_893_994.21,         # Y4
    113_755_313.68,         # Y5
    78_884_845.31,          # Y6
    41_050_387.13,          # Y7
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

# Parámetros de la base imponible
AL_IVA_GASTOS_BASE = 0.11   # IVA sobre gastos operativos (OPEX)

IMP_SELLOS_BASE = np.array([
    216_456_230.08,   # Y0
    216_456_230.08,   # Y1
    216_456_230.08,   # Y2
    216_456_230.08,   # Y3
    216_456_230.08,   # Y4
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
], dtype=float)

IMP_DBCR_BASE = np.array([
    28_632_744.00,        # Y0 (sobre crédito LP)
    197_084_762.46,       # Y1
    202_997_305.34,       # Y2
    209_087_224.50,       # Y3
    215_359_841.23,       # Y4
    221_820_636.47,       # Y5
    228_475_255.56,       # Y6
    235_329_513.23,       # Y7
    242_389_398.63,       # Y8
    249_661_080.58,       # Y9
    257_150_913.00,       # Y10
    264_865_440.39,       # Y11
    272_811_403.60,       # Y12
    280_995_745.71,       # Y13
    289_425_618.08,       # Y14
    298_108_386.63,       # Y15
    307_051_638.22,       # Y16
    316_263_187.37,       # Y17
    325_751_082.99,       # Y18
    335_523_615.48,       # Y19
    335_523_615.48,       # Y20 extrapolo
], dtype=float)

# Alícuotas base (para escalar proporcionalmente)
AL_GANANCIAS_BASE = 0.35
AL_IB_BASE        = 0.025
AL_MUNICIPAL_BASE = 0.005
AL_SELLOS_BASE    = 0.012
AL_DBCR_BASE      = 0.012
AL_IVA_BASE       = 0.21     # IVA del peaje (21%)

# Ingresos crédito LP (solo Y0) – FLUJO fila 76
INGRESO_CREDITO = np.zeros(YEARS + 1)
INGRESO_CREDITO[0] = 2_386_062_000.0

# KPIs base: calculados dinámicamente desde run_model() para evitar diferencias de redondeo
TASA_VAN_BASE = 0.10


# ══════════════════════════════════════════════════════════════
# 2.  MODELO DE SENSIBILIDAD
# ══════════════════════════════════════════════════════════════

def run_model(
    delta_capex_obras   = 0.0,   # % variación obras obligatorias
    delta_capex_repav   = 0.0,   # % variación repavimentación
    delta_opex          = 0.0,   # % variación OPEX total
    delta_trafico       = 0.0,   # delta pp sobre tasa crecimiento base (Y3+)
    tarifa              = TARIFA_BASE,   # tarifa sin IVA (ARS por UTEQ)
    al_ganancias        = AL_GANANCIAS_BASE,
    al_ib               = AL_IB_BASE,
    al_municipal        = AL_MUNICIPAL_BASE,
    al_sellos           = AL_SELLOS_BASE,
    al_dbcr             = AL_DBCR_BASE,
    al_iva_peaje        = AL_IVA_BASE,
    tasa_van            = TASA_VAN_BASE,
):
    # ── Tráfico ─────────────────────────────────────────────────
    # xlsx: Y0=0 (puesta en valor), Y1=UTEQ_ARRANQUE, Y2+=crece 3%/año.
    # El crecimiento es constante desde Y2 en adelante; NO hay salto del 5%.
    uteq = np.zeros(YEARS + 1)
    uteq[0] = 0.0
    tasa_eff = TRAFICO_CRECIMIENTO_BASE + delta_trafico
    tasa_eff = max(tasa_eff, -0.50)
    uteq[1] = UTEQ_ARRANQUE
    for y in range(2, YEARS + 1):
        uteq[y] = uteq[y - 1] * (1 + tasa_eff)

    # ── Ingresos de peaje con IVA ───────────────────────────────
    # peaje[y] = UTEQ × tarifa × (1 + IVA)  →  en $ con IVA
    tarifa_con_iva = tarifa * (1 + al_iva_peaje)
    peaje = np.zeros(YEARS + 1)
    for y in range(1, YEARS + 1):
        peaje[y] = uteq[y] * tarifa_con_iva

    # Factor de tráfico para escalar impuestos proporcionales.
    # Normalizamos contra el uteq del CASO BASE para ese año, de modo que
    # en el caso base factor=1.0 para todos los años y las sensibilidades
    # reflejan solo el cambio incremental respecto al base.
    # uteq_base[y] = UTEQ_ARRANQUE × (1 + TRAFICO_CRECIMIENTO_BASE)^(y-1)
    uteq_ref_for_tax = np.zeros(YEARS + 1)
    for y in range(1, YEARS + 1):
        uteq_base_y = UTEQ_ARRANQUE * ((1 + TRAFICO_CRECIMIENTO_BASE) ** (y - 1))
        uteq_ref_for_tax[y] = uteq[y] / uteq_base_y if uteq_base_y > 0 else 1.0

    total_ingresos = peaje + INGRESO_CREDITO

    # ── CAPEX escalado ──────────────────────────────────────────

    # Distinguimos puesta en valor (Y0), obras oblig. (Y6-Y16)
    # y repavimentación (Y3-Y5, Y6-Y9, Y13-Y20).
    # Como simplificación pragmática aplicamos:
    #   - delta_capex_obras  → todos los años con obras obligatorias
    #   - delta_capex_repav  → todos los años con repavimentación
    # Para la puesta en valor (Y0) no aplicamos sensibilidad (ya ejecutada).

    # Arrays de obras oblig y repav del xlsx (FLUJO filas 37 y 38)
    OBRAS_OBLIG = np.array([
        0,0,0,0,0,0,
        326_467_500, 652_935_000, 652_935_000, 652_935_000,
        652_935_000, 979_402_500, 652_935_000, 652_935_000,
        652_935_000, 326_467_500, 326_467_500, 0, 0, 0, 0,
    ], dtype=float)
    REPAV = np.array([
        0,0,0,
        5_112_990_000, 5_112_990_000, 5_112_990_000,
        10_225_980_000, 10_225_980_000, 10_225_980_000,
        2_045_196_000, 0, 0, 0,
        5_112_990_000, 5_112_990_000, 5_112_990_000,
        5_112_990_000, 10_225_980_000, 10_225_980_000, 10_225_980_000, 10_225_980_000,
    ], dtype=float)
    PUESTA_VALOR = np.array([3_408_660_000.0] + [0]*20, dtype=float)

    capex = (PUESTA_VALOR
             + OBRAS_OBLIG * (1 + delta_capex_obras)
             + REPAV       * (1 + delta_capex_repav))

    # ── OPEX escalado ───────────────────────────────────────────
    opex = OPEX_BASE * (1 + delta_opex)

    # ── Impuestos escalados ─────────────────────────────────────
    # factor_tarifa: ratio tarifa actual / base (para sensibilidades de tarifa).
    # factor_trafico_avg: escala los impuestos proporcionales a ingresos.
    # En el caso base ambos factores = 1.0 → los IMP_*_BASE se usan directamente.
    factor_tarifa      = tarifa / TARIFA_BASE
    factor_trafico_avg = uteq_ref_for_tax * factor_tarifa
    imp_iva       = IMP_IVA_BASE      * factor_trafico_avg * ((1 + al_iva_peaje) / (1 + AL_IVA_BASE))
    imp_ib        = IMP_IB_BASE       * factor_trafico_avg * (al_ib       / AL_IB_BASE)
    imp_municipal = IMP_MUNICIPAL_BASE* factor_trafico_avg * (al_municipal / AL_MUNICIPAL_BASE)
    imp_sellos    = IMP_SELLOS_BASE   * (al_sellos / AL_SELLOS_BASE)
    imp_dbcr      = IMP_DBCR_BASE     * factor_trafico_avg * (al_dbcr     / AL_DBCR_BASE)
    imp_dbcr[0]   = IMP_DBCR_BASE[0] * (al_dbcr / AL_DBCR_BASE)  # Y0: DBCR sobre Crédito LP

    # ── Impuesto a las Ganancias ────────────────────────────────
    # IMP_GANANCIAS_BASE[y] contiene exactamente el impuesto del xlsx para cada año.
    # Para sensibilidades: la base imponible escala con tráfico y tarifa;
    # los cambios de alícuota se aplican sobre la base imponible implícita.
    # Se incorpora el arrastre de quebrantos (pérdidas fiscales de años anteriores).
    bi_base = np.where(AL_GANANCIAS_BASE > 0,
                       IMP_GANANCIAS_BASE / AL_GANANCIAS_BASE, 0.0)
    # Parte de la base imponible que escala con ingresos:
    gastos_base_gan = OPEX_BASE / (1 + AL_IVA_GASTOS_BASE) + GARANTIAS
    bi_ingr_base    = bi_base + gastos_base_gan   # bi_ingr = ingresos_si - imp_ded - amort - int
    # Para sensibilidades, bi_ingr escala igual que los demás impuestos
    bi_ingr_sen  = bi_ingr_base * factor_trafico_avg
    gastos_sen   = opex / (1 + AL_IVA_GASTOS_BASE) + GARANTIAS
    base_imponible = bi_ingr_sen - gastos_sen

    # Quebrantos acumulados + impuesto (replica filas 64-66 del xlsx)
    quebranto_acum = np.zeros(YEARS + 1)
    imp_ganancias  = np.zeros(YEARS + 1)
    for y in range(1, YEARS + 1):
        base_y = base_imponible[y] + quebranto_acum[y - 1]
        if base_y <= 0:
            quebranto_acum[y] = base_y   # acumula quebranto (negativo)
            imp_ganancias[y]  = 0.0
        else:
            quebranto_acum[y] = 0.0
            imp_ganancias[y]  = base_y * al_ganancias

    total_impuestos = imp_iva + imp_ganancias + imp_ib + imp_municipal + imp_sellos + imp_dbcr

    # ── Egresos totales ─────────────────────────────────────────
    total_egresos = capex + opex + AMORT_DEUDA_BASE + total_impuestos + GARANTIAS

    # ── Flujo neto ──────────────────────────────────────────────
    flujo = total_ingresos - total_egresos

    # ── Métricas ────────────────────────────────────────────────
    # VAN/MIRR calculados sobre 20 años (Y0..Y19) — igual que xlsx NPV(C45:V45)
    flujo_20    = flujo[:20]
    egresos_20  = total_egresos[:20]
    ingresos_20 = total_ingresos[:20]
    van       = _npv(tasa_van, flujo_20)
    van_egr   = _npv(tasa_van, egresos_20)
    van_ing   = _npv(tasa_van, ingresos_20)
    vaff_vae  = van / van_egr if van_egr != 0 else float("nan")
    mirr_val  = _mirr(flujo_20, tasa_van)
    acum      = np.cumsum(flujo)

    # Payback de obras: año en que el flujo acumulado cubre
    # la inversión total en obras (puesta en valor + obras obligatorias).
    # La repavimentación NO se incluye por definición del indicador.
    inversion_obras = float(np.sum(PUESTA_VALOR) + np.sum(OBRAS_OBLIG * (1 + delta_capex_obras)))
    # Payback: índice 1-based igual que MATCH() del xlsx (año de concesión 1..20)
    payback   = next((y + 1 for y, v in enumerate(acum[:20]) if v >= inversion_obras), None)

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
    page_title="LA PAMPA SANTA ROSA – Sensibilidades",
    page_icon="🛣️",
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

# ── SIDEBAR ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛣️ LA PAMPA SANTA ROSA")
    st.markdown("**GESTIÓN – COAC · 2026–2045**")
    st.markdown("---")

    # ── Tránsito y Tarifa ──────────────────────────────────────
    st.markdown('<div class="sh">🚗 Tránsito y Tarifa</div>', unsafe_allow_html=True)

    tarifa_input = st.number_input(
        "Tarifa base (ARS)",
        min_value=1_000, max_value=50_000,
        value=int(TARIFA_BASE), step=10,
        help=f"Tarifa base del xlsx: $ {TARIFA_BASE:,.0f}. Se aplica desde el Año 1."
    )

    st.caption(
        "📌 **Regla de ingresos:**  \n"
        "**Año 1** → tránsito arranque (UTEQs base × 1.05), genera ingresos.  \n"
        "**Año 2+** → crece a tasa base 3% + Δ abajo."
    )

    delta_trafico_pp = st.slider(
        "Δ tasa crecimiento anual Año 3+ (±pp sobre base 3%)",
        min_value=-3.0, max_value=5.0, value=0.0, step=0.01,
        format="%.2f pp",
        help="Afecta al Año 2 en adelante. Tasa base: 3% anual."
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

    # ── OPEX ──────────────────────────────────────────────────
    st.markdown('<div class="sh">⚙️ OPEX – Conservación y Mantenimiento</div>', unsafe_allow_html=True)
    delta_opex = st.slider(
        "Variación OPEX (%)",
        min_value=-40, max_value=100, value=0, step=1
    ) / 100

    # ── Impuestos ─────────────────────────────────────────────
    st.markdown('<div class="sh">💰 Alícuotas impositivas</div>', unsafe_allow_html=True)
    al_ganancias = st.slider(
        "Ganancias (%)", 0.0, 55.0, 35.0, 0.1,
        format="%.1f %%",
        help="Base: 35%"
    ) / 100
    al_ib = st.slider(
        "Ingresos Brutos (%)", 0.0, 10.0, 2.5, 0.1,
        format="%.1f %%",
        help="Base: 2.5%"
    ) / 100
    al_municipal = st.slider(
        "Tasas Municipales (%)", 0.0, 3.0, 0.5, 0.1,
        format="%.1f %%",
        help="Base: 0.5%"
    ) / 100
    al_sellos = st.slider(
        "Impuesto de Sellos (%)", 0.0, 5.0, 1.2, 0.1,
        format="%.1f %%",
        help="Base: 1.2% (primeros 5 años)"
    ) / 100
    al_dbcr = st.slider(
        "Débitos y Créditos Bancarios (%)", 0.0, 5.0, 1.2, 0.1,
        format="%.1f %%",
        help="Base: 1.2%"
    ) / 100
    al_iva_peaje = st.slider(
        "IVA sobre peaje (%)", 0, 27, 21, 1,
        help="Base: 21%"
    ) / 100

    # ── Tasa de descuento ─────────────────────────────────────
    st.markdown('<div class="sh">📐 Tasa de descuento VAN</div>', unsafe_allow_html=True)
    tasa_van = st.slider(
        "Tasa de descuento (%)", 5.0, 25.0, 10.0, 0.1,
        format="%.1f %%"
    ) / 100

    st.markdown("---")
    if st.button("↺  Resetear todo al base", use_container_width=True):
        st.rerun()

# ── EJECUTAR MODELO ───────────────────────────────────────────
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

YEARS_RANGE = list(range(2025, 2025 + YEARS + 1))   # 2025..2045


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
# 4.  ENCABEZADO Y KPIs
# ══════════════════════════════════════════════════════════════
st.markdown("# 🛣️ LA PAMPA SANTA ROSA — Análisis de Sensibilidades")
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

# Orden: VAFF/VAE  |  VAN  |  TIR Modificada  |  Payback
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

    # Egresos apilados
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

    trafico_rng = np.arange(-2.0, 3.5, 0.5)   # Δpp sobre base 3%
    capex_rng   = np.arange(-30, 55, 10)        # % variación obras
    opex_rng    = np.arange(-30, 55, 10)
    gan_rng     = np.arange(15, 55, 5)
    tasa_rng    = np.arange(6, 20, 2)

    def heat(**ov):
        return run_model(**{**BASE_KW, **ov})

    # ── Mapa 1: MIRR = Δtráfico × CAPEX obras ────────────────
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

    # ── Mapa 2: VAN = Δtráfico × OPEX ────────────────────────
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

    # ── Mapa 3: VAN = tasa descuento × obras CAPEX ───────────
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

    # ── Mapa 4: VAFF/VAE = Δtráfico × Ganancias ──────────────
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


# ── FOOTER ────────────────────────────────────────────────────
st.divider()
st.caption(
    "LA PAMPA SANTA ROSA (GESTIÓN–COAC) · Modelo de sensibilidades · "
    "Flujos base tomados del xlsx al 1° de marzo 2025 · "
    "Concesión 20 años (2026–2045) · "
    "No incluye recálculo de préstamo ni WACC."
)