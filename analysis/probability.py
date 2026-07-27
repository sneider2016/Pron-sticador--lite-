import math
import random

class ProbabilityCalculator:

def __poisson(self, k: int, lam: float) -> float:
"""
Cálculo seguro de la masa de probabilidad Poisson P(X = k; lam).
"""
if lam <= 0:
return 1.0 if k == 0 else 0.0
try:
return (math.pow(lam, k) * math.exp(-lam)) / math.factorial(k)
except OverflowError:
return 0.0

def _calcular_rho_dinamico(
self,
l_h: float,
l_v: float,
forma_local: float = 50.0,
forma_visitante: float = 50.0,
elo_h: float = 1500.0,
elo_v: float = 1500.0,
xg_h: float = 1.25,
xg_v: float = 1.25,
fortaleza_off_h: float = 1.0,
fortaleza_def_h: float = 1.0,
fortaleza_off_v: float = 1.0,
fortaleza_def_v: float = 1.0,
btts_rate: float = 0.50,
under25_rate: float = 0.50,
clean_sheet_h: float = 0.30,
clean_sheet_v: float = 0.30,
**kwargs
) -> float:
"""
Calcula dinámicamente el parámetro Rho (rho) de Dixon-Coles mediante modulación no lineal (tanh).
Garantiza estabilidad matemática acotada en el rango [-0.15, -0.005].
"""
exp_goles_comb = (0.50 * (l_h + l_v)) + (0.50 * (xg_h + xg_v))
dif_elo = abs(elo_h - elo_v)
dif_ataques = abs(fortaleza_off_h - fortaleza_off_v)
def_promedio = (fortaleza_def_h + fortaleza_def_v) / 2.0
cs_promedio = (clean_sheet_h + clean_sheet_v) / 2.0

rho_base = -0.06    

f_goles = -0.045 * math.tanh(2.35 - exp_goles_comb)    
mismatch_factor = (dif_elo / 160.0) + (dif_ataques / 0.55)    
f_mismatch = 0.035 * math.tanh(mismatch_factor)    
f_defensa = -0.025 * math.tanh(1.10 - def_promedio) - 0.020 * math.tanh(cs_promedio - 0.30)    
f_tendencia = -0.020 * (under25_rate - 0.50) + 0.010 * (btts_rate - 0.50)    

rho_raw = rho_base + f_goles + f_mismatch + f_defensa + f_tendencia    

return max(-0.15, min(-0.005, round(rho_raw, 4)))

def _ajuste_dixon_coles(self, i: int, j: int, l_h: float, l_v: float, rho: float) -> float:
"""
Ajuste Bivariado de Dixon-Coles con corrección de densidad positiva.
"""
tau = 1.0
if i == 0 and j == 0:
tau = 1.0 - (l_h * l_v * rho)
elif i == 1 and j == 0:
tau = 1.0 + (l_v * rho)
elif i == 0 and j == 1:
tau = 1.0 + (l_h * rho)
elif i == 1 and j == 1:
tau = 1.0 - rho

return max(0.01, tau)

def _determinar_simulaciones_adaptativas(self, p_h: float, p_d: float, p_v: float) -> int:
"""
Determina dinámicamente la cantidad de simulaciones Monte Carlo según el equilibrio del partido.
"""
disparidad_1x2 = abs(p_h - p_v)

if disparidad_1x2 < 0.12:    
    return 16000    
elif disparidad_1x2 < 0.28:    
    return 12000    
elif disparidad_1x2 < 0.45:    
    return 8000    
else:    
    return 6000

def _simulacion_monte_carlo(self, l_h: float, l_v: float, n_sims: int, rho: float) -> dict:
"""
Ejecuta la simulación estocástica de Monte Carlo con muestreo Poisson y corrección Dixon-Coles.
"""
wins_h, draws, wins_v = 0, 0, 0
u15, o15, u25, o25, u35, o35, btts = 0, 0, 0, 0, 0, 0, 0

def _sample_poisson(lam):    
    L = math.exp(-lam)    
    k = 0    
    p = 1.0    
    while p > L:    
        k += 1    
        p *= random.random()    
    return max(0, k - 1)    

for _ in range(n_sims):    
    gh = _sample_poisson(l_h)    
    gv = _sample_poisson(l_v)    

    tau = self._ajuste_dixon_coles(gh, gv, l_h, l_v, rho)    
    if tau < 1.0 and random.random() > tau:    
        gh = _sample_poisson(l_h)    
        gv = _sample_poisson(l_v)    

    if gh > gv:    
        wins_h += 1    
    elif gh == gv:    
        draws += 1    
    else:    
        wins_v += 1    

    tot = gh + gv    
    if tot < 1.5:    
        u15 += 1    
    if tot >= 2:    
        o15 += 1    
    if tot <= 2:    
        u25 += 1    
    if tot >= 3:    
        o25 += 1    
    if tot <= 3:    
        u35 += 1    
    if tot >= 4:    
        o35 += 1    
    if gh > 0 and gv > 0:    
        btts += 1    

n_float = float(n_sims)    
return {    
    "p_h": wins_h / n_float,    
    "p_d": draws / n_float,    
    "p_v": wins_v / n_float,    
    "u15": u15 / n_float,    
    "o15": o15 / n_float,    
    "u25": u25 / n_float,    
    "o25": o25 / n_float,    
    "u35": u35 / n_float,    
    "o35": o35 / n_float,    
    "btts": btts / n_float    
}

def _calcular_confianza_avanzada(
self,
p_h: float,
p_d: float,
p_v: float,
p_u25: float,
p_o15: float,
p_btts: float,
mc_h: float,
forma_local: float,
forma_visitante: float
) -> float:
"""
Calcula un índice de confianza estadística avanzado (55.0 a 96.0) considerando:
1. Entropía de Shannon normalizada de la distribución 1X2.
2. Dispersión global de probabilidad en todos los mercados clave (1X2, U2.5, O1.5, BTTS, DNB, 1X, X2).
3. Coherencia y consistencia entre mercados relacionados (detector de contradicciones).
4. Recompensa por consenso estocástico (Modelo Analítico vs Monte Carlo).
5. Estabilidad y nitidez de la ventaja del resultado preferente.
"""
# A. Entropía de Shannon (1X2)
probs_1x2 = [max(0.001, p_h), max(0.001, p_d), max(0.001, p_v)]
sum_1x2 = sum(probs_1x2)
probs_1x2_norm = [p / sum_1x2 for p in probs_1x2]

entropia = -sum(p * math.log2(p) for p in probs_1x2_norm)    
entropia_norm = entropia / math.log2(3.0)  # [0 = Certeza total, 1 = Incertidumbre total]    

# B. Delta y Dominancia del Mercado Favorito 1X2    
sorted_1x2 = sorted(probs_1x2_norm, reverse=True)    
top1_prob = sorted_1x2[0]    
top2_prob = sorted_1x2[1]    
delta_top = top1_prob - top2_prob    

# C. Dispersión Global de Probabilidades (Desviación Estándar Multimercado)    
p_1x = p_h + p_d    
p_x2 = p_v + p_d    
p_dnb_h = p_h / max(0.001, p_h + p_v)    

mercados_clave = [p_h, p_d, p_v, p_u25, p_o15, p_btts, p_1x, p_x2, p_dnb_h]    
mean_mkts = sum(mercados_clave) / len(mercados_clave)    
var_mkts = sum((m - mean_mkts) ** 2 for m in mercados_clave) / len(mercados_clave)    
std_mkts = math.sqrt(var_mkts)    

# D. Detector de Coherencia Táctica y Contradicciones de Mercado    
penalizacion_coherencia = 0.0    
if p_btts > (p_o15 + 0.02):    
    penalizacion_coherencia += (p_btts - p_o15) * 25.0    

if top1_prob > 0.65 and (p_u25 > 0.65 and p_btts > 0.65):    
    penalizacion_coherencia += 4.0    

coherencia_positiva = 0.0    
if p_o15 >= p_btts and p_o15 > 0.70:    
    coherencia_positiva += 3.0    
if (p_h > 0.55 and p_1x > 0.80) or (p_v > 0.55 and p_x2 > 0.80):    
    coherencia_positiva += 3.0    

# E. Recompensa por Consenso Estocástico (Analítico vs Monte Carlo)    
dif_mc = abs(p_h - mc_h)    
if dif_mc < 0.015:    
    recompensa_consenso = 6.0    
elif dif_mc < 0.035:    
    recompensa_consenso = 3.5    
elif dif_mc > 0.07:    
    recompensa_consenso = -4.0    
else:    
    recompensa_consenso = 0.0    

# F. Estabilidad de Forma y Control de Extremos    
estabilidad_forma = 1.0 - (abs(forma_local - forma_visitante) / 200.0)    

penalizacion_extremo = 0.0    
if top1_prob > 0.88 or top1_prob < 0.35:    
    penalizacion_extremo = 2.5    

# G. FUSIÓN FINAL DE CONFIANZA    
confianza_base = (    
    51.0    
    + (delta_top * 26.0)    
    + ((1.0 - entropia_norm) * 16.0)    
    + (std_mkts * 12.0)    
    + recompensa_consenso    
    + coherencia_positiva    
    - penalizacion_coherencia    
    - penalizacion_extremo    
    + (estabilidad_forma * 3.0)    
)    

return max(55.0, min(96.0, round(confianza_base, 1)))

def calcular(
self,
ataque_local: float,
defensa_local: float,
ataque_visitante: float,
defensa_visitante: float,
forma_local: float = 50.0,
forma_visitante: float = 50.0,
descanso_h: int = 6,
descanso_v: int = 6,
lesiones_h: int = 0,
lesiones_v: int = 0,
fortaleza_off_h: float = 1.0,
fortaleza_def_h: float = 1.0,
fortaleza_off_v: float = 1.0,
fortaleza_def_v: float = 1.0,
elo_h: float = 1500.0,
elo_v: float = 1500.0,
xg_h: float = 1.25,
xg_v: float = 1.25,
fuerza_rival_h: float = 1.0,
fuerza_rival_v: float = 1.0,
btts_rate: float = 0.50,
under25_rate: float = 0.50,
clean_sheet_h: float = 0.30,
clean_sheet_v: float = 0.30,
**kwargs
) -> dict:

# 1. Base de intensidad Poisson con salvaguardas de rango    
base_lambda_local = max(0.20, (ataque_local + defensa_visitante) / 2.0)    
base_lambda_visitante = max(0.20, (ataque_visitante + defensa_local) / 2.0)    

# 2. Multiplicadores de Fortaleza Relativa y Ajuste de Rival    
factor_fuerza_h = (fortaleza_off_h * (2.0 - min(1.8, fortaleza_def_v))) * fuerza_rival_h    
factor_fuerza_v = (fortaleza_off_v * (2.0 - min(1.8, fortaleza_def_h))) * fuerza_rival_v    

# 3. Factor ELO y Ventaja de Localía    
dif_elo = elo_h - elo_v + 65.0    
factor_elo_h = max(0.75, min(1.35, 1.0 + (dif_elo / 1000.0)))    
factor_elo_v = max(0.75, min(1.35, 1.0 - (dif_elo / 1000.0)))    

# 4. Factor xG    
factor_xg_h = max(0.80, min(1.25, xg_h / max(0.8, ataque_local)))    
factor_xg_v = max(0.80, min(1.25, xg_v / max(0.8, ataque_visitante)))    

# 5. Fatiga por descanso e impacto de Bajas    
fatiga_h = 0.90 if descanso_h < 3 else (1.04 if descanso_h >= 6 else 1.0)    
fatiga_v = 0.90 if descanso_v < 3 else (1.04 if descanso_v >= 6 else 1.0)    
bajas_h = max(0.85, 1.0 - (lesiones_h * 0.03))    
bajas_v = max(0.85, 1.0 - (lesiones_v * 0.03))    

# Lambdas finales acotados numéricamente [0.20, 5.50]    
lambda_local = max(0.20, min(5.50, base_lambda_local * factor_fuerza_h * factor_elo_h * factor_xg_h * fatiga_h * bajas_h))    
lambda_visitante = max(0.20, min(5.50, base_lambda_visitante * factor_fuerza_v * factor_elo_v * factor_xg_v * fatiga_v * bajas_v))    

# 6. Cálculo Avanzado de Rho Dinámico para Dixon-Coles    
rho_dinamico = self._calcular_rho_dinamico(    
    lambda_local, lambda_visitante,    
    forma_local=forma_local, forma_visitante=forma_visitante,    
    elo_h=elo_h, elo_v=elo_v,    
    xg_h=xg_h, xg_v=xg_v,    
    fortaleza_off_h=fortaleza_off_h, fortaleza_def_h=fortaleza_def_h,    
    fortaleza_off_v=fortaleza_off_v, fortaleza_def_v=fortaleza_def_v,    
    btts_rate=btts_rate, under25_rate=under25_rate,    
    clean_sheet_h=clean_sheet_h, clean_sheet_v=clean_sheet_v,    
    **kwargs    
)    

# A. CÁLCULO ANALÍTICO (Poisson + Dixon-Coles)    
p_local_a, p_empate_a, p_visitante_a = 0.0, 0.0, 0.0    
p_u15_a, p_o15_a, p_u25_a, p_o25_a, p_u35_a, p_o35_a = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0    

for i in range(8):    
    for j in range(8):    
        p_base = self.__poisson(i, lambda_local) * self.__poisson(j, lambda_visitante)    
        tau = self._ajuste_dixon_coles(i, j, lambda_local, lambda_visitante, rho_dinamico)    
        p = max(0.0, p_base * tau)    

        if i > j:    
            p_local_a += p    
        elif i == j:    
            p_empate_a += p    
        else:    
            p_visitante_a += p    

        tot = i + j    
        if tot < 1.5:    
            p_u15_a += p    
        if tot >= 2:    
            p_o15_a += p    
        if tot <= 2:    
            p_u25_a += p    
        if tot >= 3:    
            p_o25_a += p    
        if tot <= 3:    
            p_u35_a += p    
        if tot >= 4:    
            p_o35_a += p    

# Normalización matemática de la distribución analítica    
sum_a = max(0.0001, p_local_a + p_empate_a + p_visitante_a)    
p_local_a /= sum_a    
p_empate_a /= sum_a    
p_visitante_a /= sum_a    

p_btts_a = (1.0 - self.__poisson(0, lambda_local)) * (1.0 - self.__poisson(0, lambda_visitante))    

# B. CÁLCULO MONTE CARLO ADAPTATIVO    
n_sims = self._determinar_simulaciones_adaptativas(p_local_a, p_empate_a, p_visitante_a)    
mc = self._simulacion_monte_carlo(lambda_local, lambda_visitante, n_sims, rho_dinamico)    

# C. FUSIÓN HÍBRIDA PONDERADA (60% Analítico + 40% Monte Carlo Adaptativo)    
p_local = (p_local_a * 0.60) + (mc["p_h"] * 0.40)    
p_empate = (p_empate_a * 0.60) + (mc["p_d"] * 0.40)    
p_visitante = (p_visitante_a * 0.60) + (mc["p_v"] * 0.40)    

p_under15 = (p_u15_a * 0.60) + (mc["u15"] * 0.40)    
p_over15 = (p_o15_a * 0.60) + (mc["o15"] * 0.40)    
p_under25 = (p_u25_a * 0.60) + (mc["u25"] * 0.40)    
p_over25 = (p_o25_a * 0.60) + (mc["o25"] * 0.40)    
p_under35 = (p_u35_a * 0.60) + (mc["u35"] * 0.40)    
p_over35 = (p_o35_a * 0.60) + (mc["o35"] * 0.40)    
p_btts = (p_btts_a * 0.60) + (mc["btts"] * 0.40)    

# Derivaciones de Doble Chance y Draw No Bet    
p_1x = p_local + p_empate    
p_x2 = p_visitante + p_empate    
p_12 = p_local + p_visitante    

tot_dec = p_local + p_visitante    
p_dnb_h = (p_local / tot_dec) if tot_dec > 0 else 0.5    
p_dnb_v = (p_visitante / tot_dec) if tot_dec > 0 else 0.5    

exp_goles = lambda_local + lambda_visitante    

# D. CÁLCULO DE CONFIANZA AVANZADO REPOTENCIADO    
confianza_final = self._calcular_confianza_avanzada(    
    p_local, p_empate, p_visitante,    
    p_under25, p_over15, p_btts,    
    mc["p_h"], forma_local, forma_visitante    
)    

return {    
    "lambda_local": round(lambda_local, 2),    
    "lambda_visitante": round(lambda_visitante, 2),    
    "exp_goles": round(exp_goles, 2),    
    "local": round(p_local * 100.0, 1),    
    "empate": round(p_empate * 100.0, 1),    
    "visitante": round(p_visitante * 100.0, 1),    
    "doble_chance_1x": round(p_1x * 100.0, 1),    
    "doble_chance_x2": round(p_x2 * 100.0, 1),    
    "doble_chance_12": round(p_12 * 100.0, 1),    
    "dnb_local": round(p_dnb_h * 100.0, 1),    
    "dnb_visitante": round(p_dnb_v * 100.0, 1),    
    "under15": round(p_under15 * 100.0, 1),    
    "over15": round(p_over15 * 100.0, 1),    
    "under25": round(p_under25 * 100.0, 1),    
    "over25": round(p_over25 * 100.0, 1),    
    "under35": round(p_under35 * 100.0, 1),    
    "over35": round(p_over35 * 100.0, 1),    
    "btts": round(p_btts * 100.0, 1),    
    "confianza": confianza_final    
    }
