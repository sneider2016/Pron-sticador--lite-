import bisect
import math
import random


class ProbabilityCalculator:

    def __poisson(self, k: int, lam: float) -> float:
        """
        Masa de probabilidad Poisson P(X = k; lam) numéricamente estable.
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
        forma_visitante: float = 50.0
    ) -> float:
        """
        Calcula el parámetro de dependencia Rho (rho) de Dixon-Coles derivado de la teoría
        de verosimilitud de Poisson Bivariada.
        
        rho = - ( P_poisson(0,0) / sqrt(l_h * l_v) ) * (1 - D^2) * F_div
        donde:
        - P_poisson(0,0) = exp(-(l_h + l_v)) es la probabilidad pura del resultado 0-0.
        - D = |l_h - l_v| / (l_h + l_v) es la disparidad relativa de intensidad.
        - F_div = 1.0 - (|forma_local - forma_visitante| / 100.0) es la convergencia de forma.
        """
        mu_total = l_h + l_v
        if mu_total <= 0:
            return -0.05

        # 1. Probabilidad analítica del estado cero-cero en Poisson independiente
        p_00 = math.exp(-mu_total)

        # 2. Media geométrica de intensidad (desviación de escala)
        geom_mean = math.sqrt(max(0.01, l_h * l_v))

        # 3. Disparidad relativa de fuerzas (0.0 = paridad total, 1.0 = desbalance extremo)
        disparidad = abs(l_h - l_v) / mu_total
        factor_simetria = max(0.0, 1.0 - (disparidad ** 2))

        # 4. Divergencia de forma reciente
        forma_div = max(0.0, 1.0 - (abs(forma_local - forma_visitante) / 100.0))

        # Derivación teórica pura de rho
        rho_calculado = - (p_00 / geom_mean) * factor_simetria * forma_div

        # Acotamiento estricto de seguridad [-0.15, -0.005]
        return max(-0.15, min(-0.005, round(rho_calculado, 4)))

    def _ajuste_dixon_coles(self, i: int, j: int, l_h: float, l_v: float, rho: float) -> float:
        """
        Factor de ajuste de densidad bivariada tau(i, j) de Dixon-Coles.
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
        Determina la cantidad de iteraciones Monte Carlo según el grado de equilibrio del partido.
        """
        disparidad_1x2 = abs(p_h - p_v)

        if disparidad_1x2 < 0.15:
            return 16000  # Máxima resolución para partidos muy ajustados
        elif disparidad_1x2 < 0.35:
            return 10000
        else:
            return 6000   # Favorito claro

    def _simulacion_monte_carlo_directa(self, cdf_1d: list, n_sims: int) -> dict:
        """
        Ejecuta la simulación estocástica Monte Carlo mediante Muestreo Categórico Directo (Inversión CDF).
        Mantiene consistencia al 100% con la matriz de probabilidad bivariada Dixon-Coles sin sesgos de rechazo.
        """
        wins_h, draws, wins_v = 0, 0, 0
        u15, o15, u25, o25, u35, o35, btts = 0, 0, 0, 0, 0, 0, 0

        for _ in range(n_sims):
            r = random.random()
            # Muestreo rápido por búsqueda binaria en la CDF acumulada
            idx = bisect.bisect_right(cdf_1d, r)
            idx = min(63, idx)

            gh = idx // 8
            gv = idx % 8

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
        Calcula el índice de confianza estadística (55.0 a 96.0) fundamentado en:
        1. Entropía de Shannon Normalizada (Grado de certeza de la distribución 1X2).
        2. Divergencia Estocástica / Convergencia entre la Distribución Analítica y Monte Carlo.
        3. Separación Delta entre la primera y segunda opción principal.
        4. Coherencia probabilística entre mercados relacionados.
        """
        # 1. Entropía de Shannon Normalizada
        probs_1x2 = [max(0.001, p_h), max(0.001, p_d), max(0.001, p_v)]
        sum_1x2 = sum(probs_1x2)
        p_norm = [p / sum_1x2 for p in probs_1x2]

        entropia = -sum(p * math.log2(p) for p in p_norm)
        entropia_norm = entropia / math.log2(3.0)  # [0.0 = Certeza total, 1.0 = Caos total]
        certeza_informacion = 1.0 - entropia_norm

        # 2. Delta de Dominancia
        p_sorted = sorted(p_norm, reverse=True)
        delta_top = p_sorted[0] - p_sorted[1]

        # 3. Convergencia Analítica vs Monte Carlo
        divergencia_mc = abs(p_h - mc_h)
        factor_convergencia = math.exp(-30.0 * divergencia_mc)

        # 4. Axioma probabilístico: P(BTTS) <= P(Over 1.5)
        penalizacion_coherencia = 0.0
        if p_btts > (p_o15 + 0.005):
            penalizacion_coherencia = (p_btts - p_o15) * 30.0

        estabilidad_forma = 1.0 - (abs(forma_local - forma_visitante) / 200.0)

        confianza_calculada = (
            55.0
            + (certeza_informacion * 18.0)
            + (delta_top * 14.0)
            + (factor_convergencia * 6.0)
            + (estabilidad_forma * 3.0)
            - penalizacion_coherencia
        )

        return max(55.0, min(96.0, round(confianza_calculada, 1)))

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
        **kwargs
    ) -> dict:

        # 1. Intensidades base Poisson con salvaguardas
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

        # 5. Fatiga e Impacto de Bajas
        fatiga_h = 0.90 if descanso_h < 3 else (1.04 if descanso_h >= 6 else 1.0)
        fatiga_v = 0.90 if descanso_v < 3 else (1.04 if descanso_v >= 6 else 1.0)
        bajas_h = max(0.85, 1.0 - (lesiones_h * 0.03))
        bajas_v = max(0.85, 1.0 - (lesiones_v * 0.03))

        # Lambdas finales
        lambda_local = max(0.20, min(5.50, base_lambda_local * factor_fuerza_h * factor_elo_h * factor_xg_h * fatiga_h * bajas_h))
        lambda_visitante = max(0.20, min(5.50, base_lambda_visitante * factor_fuerza_v * factor_elo_v * factor_xg_v * fatiga_v * bajas_v))

        # 6. Rho Dinámico derivado de la masa Poisson 0-0 y simetría
        rho_dinamico = self._calcular_rho_dinamico(lambda_local, lambda_visitante, forma_local, forma_visitante)

        # A. CÁLCULO DE MATRIZ Y RECUPERACIÓN DE MASA POR TRUNCAMIENTO (0-7 Goles)
        matriz_8x8 = [[0.0] * 8 for _ in range(8)]
        suma_raw = 0.0

        for i in range(8):
            for j in range(8):
                p_base = self.__poisson(i, lambda_local) * self.__poisson(j, lambda_visitante)
                tau = self._ajuste_dixon_coles(i, j, lambda_local, lambda_visitante, rho_dinamico)
                p_val = max(0.0, p_base * tau)
                matriz_8x8[i][j] = p_val
                suma_raw += p_val

        # Normalización estricta (Recupera al 100% la masa truncada del rabo)
        norm_factor = max(0.0001, suma_raw)
        cdf_acumulada = []
        acumulado = 0.0

        p_local_a, p_empate_a, p_visitante_a = 0.0, 0.0, 0.0
        p_u15_a, p_o15_a, p_u25_a, p_o25_a, p_u35_a, p_o35_a = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

        for i in range(8):
            for j in range(8):
                p_exacta = matriz_8x8[i][j] / norm_factor
                matriz_8x8[i][j] = p_exacta

                acumulado += p_exacta
                cdf_acumulada.append(acumulado)

                if i > j:
                    p_local_a += p_exacta
                elif i == j:
                    p_empate_a += p_exacta
                else:
                    p_visitante_a += p_exacta

                tot = i + j
                if tot < 1.5:
                    p_u15_a += p_exacta
                if tot >= 2:
                    p_o15_a += p_exacta
                if tot <= 2:
                    p_u25_a += p_exacta
                if tot >= 3:
                    p_o25_a += p_exacta
                if tot <= 3:
                    p_u35_a += p_exacta
                if tot >= 4:
                    p_o35_a += p_exacta

        p_btts_a = (1.0 - self.__poisson(0, lambda_local)) * (1.0 - self.__poisson(0, lambda_visitante))

        # B. CÁLCULO MONTE CARLO CATEGÓRICO DIRECTO
        n_sims = self._determinar_simulaciones_adaptativas(p_local_a, p_empate_a, p_visitante_a)
        mc = self._simulacion_monte_carlo_directa(cdf_acumulada, n_sims)

        # C. FUSIÓN HÍBRIDA PONDERADA (60% Analítico Exacto + 40% Monte Carlo Categórico)
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

        # D. CÁLCULO DE CONFIANZA AVANZADO
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
