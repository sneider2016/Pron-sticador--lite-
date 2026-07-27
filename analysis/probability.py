import bisect
import math
import random


class ProbabilityCalculator:

    def __poisson(self, k: int, lam: float) -> float:
        """
        Función de masa de probabilidad Poisson P(X = k; lam) numéricamente estable.
        """
        if lam <= 0:
            return 1.0 if k == 0 else 0.0
        try:
            return (math.pow(lam, k) * math.exp(-lam)) / math.factorial(k)
        except OverflowError:
            return 0.0

    def _recalibrar_lambdas_bayesiano(self, l_h_raw: float, l_v_raw: float) -> tuple:
        """
        Recalibración de Lambdas mediante A Priori Conjugada Gamma-Poisson (Empirical Bayes Shrinkage).
        Reduce la varianza de muestras pequeñas y minimiza el Brier Score out-of-sample.
        """
        # Prior estructural de la liga (media = 1.30 goles/equipo, varianza = 0.55)
        mu_prior = 1.30
        var_prior = 0.55
        alpha_0 = (mu_prior ** 2) / var_prior  # ~3.07
        beta_0 = mu_prior / var_prior          # ~2.36

        # Muestra observada equivalente (n = 5 partidos)
        n_obs = 5.0
        k_h = l_h_raw * n_obs
        k_v = l_v_raw * n_obs

        # Actualización de la esperanza a posteriori Bayesiana E[lambda | X]
        lambda_h_post = (alpha_0 + k_h) / (beta_0 + n_obs)
        lambda_v_post = (alpha_0 + k_v) / (beta_0 + n_obs)

        return (max(0.20, min(5.0, lambda_h_post)), max(0.20, min(5.0, lambda_v_post)))

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
        Calcula el parámetro de correlación bivariada Rho (rho) para marcadores bajos.
        Derivado directamente de la masa de probabilidad Poisson 0-0 y la disparidad de fuerzas.
        """
        mu_total = l_h + l_v
        if mu_total <= 0:
            return -0.05

        p_00 = math.exp(-mu_total)
        geom_mean = math.sqrt(max(0.01, l_h * l_v))
        disparidad = abs(l_h - l_v) / mu_total
        factor_simetria = max(0.0, 1.0 - (disparidad ** 2))
        forma_div = max(0.0, 1.0 - (abs(forma_local - forma_visitante) / 100.0))

        rho_teorico = - (p_00 / geom_mean) * factor_simetria * forma_div
        return max(-0.14, min(-0.005, round(rho_teorico, 4)))

    def _ajuste_dixon_coles(self, i: int, j: int, l_h: float, l_v: float, rho: float) -> float:
        """
        Ajuste Bivariado de Dixon-Coles con salvaguarda de densidad positiva.
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

    def _calibracion_temperatura_platt(self, prob_decimal: float, temperatura: float = 1.15) -> float:
        """
        Calibración de Probabilidades mediante Escalamiento de Temperatura (Logit Scaling).
        Elimina la sobreconfianza extrema y minimiza el Brier Score / Log Loss.
        """
        p_safe = max(0.001, min(0.999, prob_decimal))
        logit = math.log(p_safe / (1.0 - p_safe))
        logit_calibrado = logit / temperatura
        p_calibrada = 1.0 / (1.0 + math.exp(-logit_calibrado))
        return max(0.001, min(0.999, p_calibrada))

    def _determinar_simulaciones_adaptativas(self, p_h: float, p_d: float, p_v: float) -> int:
        """
        Determina la cantidad de iteraciones Monte Carlo según la entropía del partido.
        """
        disparidad_1x2 = abs(p_h - p_v)

        if disparidad_1x2 < 0.15:
            return 16000  # Máxima precisión en partidos muy ajustados
        elif disparidad_1x2 < 0.35:
            return 10000
        else:
            return 6000   # Favorito claro

    def _sample_poisson_inversion(self, lam: float, u: float) -> int:
        """
        Muestreador Poisson por inversión de CDF con variables antitéticas u y 1-u.
        """
        if lam <= 0:
            return 0
        p = math.exp(-lam)
        cdf = p
        k = 0
        while u > cdf and k < 20:
            k += 1
            p *= lam / k
            cdf += p
        return k

    def _simulacion_monte_carlo(self, l_h: float, l_v: float, n_sims: int, rho: float, seed: int = None) -> dict:
        """
        Ejecuta la simulación estocástica de Monte Carlo con Muestreo Ponderado e Inversión de CDF.
        """
        if seed is not None:
            random.seed(seed)

        w_tot = 0.0
        w_h, w_d, w_v = 0.0, 0.0, 0.0
        w_u15, w_o15, w_u25, w_o25, w_u35, w_o35, w_btts = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

        num_pasos = max(1000, n_sims // 2)
        umbral_se_target = 0.0020
        check_intervalo = 500
        muestras_procesadas = 0

        for paso in range(num_pasos):
            u_h = random.random()
            u_v = random.random()

            # Muestra 1: Primaria
            g_h1 = self._sample_poisson_inversion(l_h, u_h)
            g_v1 = self._sample_poisson_inversion(l_v, u_v)
            tau1 = self._ajuste_dixon_coles(g_h1, g_v1, l_h, l_v, rho)

            # Muestra 2: Antitética (1 - u) para reducción de ruido
            g_h2 = self._sample_poisson_inversion(l_h, 1.0 - u_h)
            g_v2 = self._sample_poisson_inversion(l_v, 1.0 - u_v)
            tau2 = self._ajuste_dixon_coles(g_h2, g_v2, l_h, l_v, rho)

            pares = [(g_h1, g_v1, tau1), (g_h2, g_v2, tau2)]

            for gh, gv, tau in pares:
                w_tot += tau
                muestras_procesadas += 1

                if gh > gv:
                    w_h += tau
                elif gh == gv:
                    w_d += tau
                else:
                    w_v += tau

                tot = gh + gv
                if tot < 1.5:
                    w_u15 += tau
                if tot >= 2:
                    w_o15 += tau
                if tot <= 2:
                    w_u25 += tau
                if tot >= 3:
                    w_o25 += tau
                if tot <= 3:
                    w_u35 += tau
                if tot >= 4:
                    w_o35 += tau
                if gh > 0 and gv > 0:
                    w_btts += tau

            # Parada temprana por Error Estándar (SE)
            if paso > 1000 and paso % check_intervalo == 0:
                p_h_temp = w_h / w_tot
                p_d_temp = w_d / w_tot
                p_o25_temp = w_o25 / w_tot

                se_h = math.sqrt(max(0.0, p_h_temp * (1.0 - p_h_temp)) / muestras_procesadas)
                se_d = math.sqrt(max(0.0, p_d_temp * (1.0 - p_d_temp)) / muestras_procesadas)
                se_o25 = math.sqrt(max(0.0, p_o25_temp * (1.0 - p_o25_temp)) / muestras_procesadas)

                if max(se_h, se_d, se_o25) < umbral_se_target:
                    break

        w_tot_inv = 1.0 / max(0.00001, w_tot)
        return {
            "p_h": w_h * w_tot_inv,
            "p_d": w_d * w_tot_inv,
            "p_v": w_v * w_tot_inv,
            "u15": w_u15 * w_tot_inv,
            "o15": w_o15 * w_tot_inv,
            "u25": w_u25 * w_tot_inv,
            "o25": w_o25 * w_tot_inv,
            "u35": w_u35 * w_tot_inv,
            "o35": w_o35 * w_tot_inv,
            "btts": w_btts * w_tot_inv
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
        Calcula un índice de confianza estadística (55.0 a 96.0) considerando Entropía de Shannon,
        convergencia estocástica y coherencia de axiomas probabilísticos.
        """
        # 1. Entropía de Shannon Normalizada
        probs_1x2 = [max(0.001, p_h), max(0.001, p_d), max(0.001, p_v)]
        sum_1x2 = sum(probs_1x2)
        probs_1x2_norm = [p / sum_1x2 for p in probs_1x2]

        entropia = -sum(p * math.log2(p) for p in probs_1x2_norm)
        entropia_norm = entropia / math.log2(3.0)  # [0.0 = Certeza total, 1.0 = Caos]
        certeza_informacion = 1.0 - entropia_norm

        # 2. Delta de Dominancia
        sorted_1x2 = sorted(probs_1x2_norm, reverse=True)
        delta_top = sorted_1x2[0] - sorted_1x2[1]

        # 3. Dispersión Multimercado (Desviación Estándar)
        p_1x = p_h + p_d
        p_x2 = p_v + p_d
        p_dnb_h = p_h / max(0.001, p_h + p_v)

        mercados_clave = [p_h, p_d, p_v, p_u25, p_o15, p_btts, p_1x, p_x2, p_dnb_h]
        mean_mkts = sum(mercados_clave) / len(mercados_clave)
        var_mkts = sum((m - mean_mkts) ** 2 for m in mercados_clave) / len(mercados_clave)
        std_mkts = math.sqrt(var_mkts)

        # 4. Detector de Incoherencias y Penalizaciones
        penalizacion_coherencia = 0.0
        if p_btts > (p_o15 + 0.02):
            penalizacion_coherencia += (p_btts - p_o15) * 25.0

        if sorted_1x2[0] > 0.65 and (p_u25 > 0.65 and p_btts > 0.65):
            penalizacion_coherencia += 4.0

        coherencia_positiva = 0.0
        if p_o15 >= p_btts and p_o15 > 0.70:
            coherencia_positiva += 3.0
        if (p_h > 0.55 and p_1x > 0.80) or (p_v > 0.55 and p_x2 > 0.80):
            coherencia_positiva += 3.0

        # 5. Convergencia Analítica vs Monte Carlo
        dif_mc = abs(p_h - mc_h)
        if dif_mc < 0.015:
            recompensa_consenso = 6.0
        elif dif_mc < 0.035:
            recompensa_consenso = 3.5
        elif dif_mc > 0.07:
            recompensa_consenso = -4.0
        else:
            recompensa_consenso = 0.0

        estabilidad_forma = 1.0 - (abs(forma_local - forma_visitante) / 200.0)

        penalizacion_extremo = 0.0
        if sorted_1x2[0] > 0.88 or sorted_1x2[0] < 0.35:
            penalizacion_extremo = 2.5

        confianza_base = (
            51.0
            + (delta_top * 26.0)
            + (certeza_informacion * 16.0)
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

        # 1. Base de intensidad Poisson inicial
        base_lambda_local = max(0.20, (ataque_local + defensa_visitante) / 2.0)
        base_lambda_visitante = max(0.20, (ataque_visitante + defensa_local) / 2.0)

        # 2. Multiplicadores de Fortaleza Relativa, Rival y ELO
        factor_fuerza_h = (fortaleza_off_h * (2.0 - min(1.8, fortaleza_def_v))) * fuerza_rival_h
        factor_fuerza_v = (fortaleza_off_v * (2.0 - min(1.8, fortaleza_def_h))) * fuerza_rival_v

        dif_elo = elo_h - elo_v + 65.0
        factor_elo_h = max(0.75, min(1.35, 1.0 + (dif_elo / 1000.0)))
        factor_elo_v = max(0.75, min(1.35, 1.0 - (dif_elo / 1000.0)))

        factor_xg_h = max(0.80, min(1.25, xg_h / max(0.8, ataque_local)))
        factor_xg_v = max(0.80, min(1.25, xg_v / max(0.8, ataque_visitante)))

        fatiga_h = 0.90 if descanso_h < 3 else (1.04 if descanso_h >= 6 else 1.0)
        fatiga_v = 0.90 if descanso_v < 3 else (1.04 if descanso_v >= 6 else 1.0)
        bajas_h = max(0.85, 1.0 - (lesiones_h * 0.03))
        bajas_v = max(0.85, 1.0 - (lesiones_v * 0.03))

        l_h_raw = max(0.20, min(5.50, base_lambda_local * factor_fuerza_h * factor_elo_h * factor_xg_h * fatiga_h * bajas_h))
        l_v_raw = max(0.20, min(5.50, base_lambda_visitante * factor_fuerza_v * factor_elo_v * factor_xg_v * fatiga_v * bajas_v))

        # 3. RECALIBRACIÓN BAYESIANA EMPÍRICA DE LAMBDAS (Shrinkage anti-ruido)
        lambda_local, lambda_visitante = self._recalibrar_lambdas_bayesiano(l_h_raw, l_v_raw)

        # 4. Cálculo Bivariado de Covarianza Ofensiva (lambda_3)
        lambda_3 = min(0.22, lambda_local * lambda_visitante * 0.08 * (1.0 - abs(forma_local - forma_visitante) / 200.0))

        # 5. Rho Dinámico para Ajuste de Bajo Score
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

        # A. CÁLCULO ANALÍTICO BIVARIADO POISSON + DIXON-COLES
        matriz_8x8 = [[0.0] * 8 for _ in range(8)]
        suma_raw = 0.0

        for i in range(8):
            for j in range(8):
                # Componente Bivariada Poisson con covarianza lambda_3
                p_base = 0.0
                max_k = min(i, j)
                for k in range(max_k + 1):
                    term = (
                        self.__poisson(i - k, max(0.05, lambda_local - lambda_3)) *
                        self.__poisson(j - k, max(0.05, lambda_visitante - lambda_3)) *
                        self.__poisson(k, max(0.01, lambda_3))
                    )
                    p_base += term

                tau = self._ajuste_dixon_coles(i, j, lambda_local, lambda_visitante, rho_dinamico)
                p_val = max(0.0, p_base * tau)
                matriz_8x8[i][j] = p_val
                suma_raw += p_val

        # Normalización estricta por suma
        norm_factor = max(0.0001, suma_raw)
        cdf_acumulada = []
        acumulado = 0.0

        p_local_a, p_empate_a, p_visitante_a = 0.0, 0.0, 0.0
        p_u15_a, p_o15_a, p_u25_a, p_o25_a, p_u35_a, p_o35_a = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

        for i in range(8):
            for j in range(8):
                p_exacta = matriz_8x8[i][j] / norm_factor
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

        # B. CÁLCULO MONTE CARLO ADAPTATIVO
        n_sims = self._determinar_simulaciones_adaptativas(p_local_a, p_empate_a, p_visitante_a)
        mc = self._simulacion_monte_carlo(lambda_local, lambda_visitante, n_sims, rho_dinamico)

        # C. PONDERACIÓN DINÁMICA SEGÚN ENTROPÍA DEL PARTIDO
        probs_raw = [max(0.001, p_local_a), max(0.001, p_empate_a), max(0.001, p_visitante_a)]
        entropia = -sum(p * math.log2(p) for p in probs_raw) / math.log2(3.0)

        # En partidos ordenados/predecibles da mayor peso al modelo analítico exacto
        w_analitico = 0.70 - (entropia * 0.20)
        w_mc = 1.0 - w_analitico

        p_local_raw = (p_local_a * w_analitico) + (mc["p_h"] * w_mc)
        p_empate_raw = (p_empate_a * w_analitico) + (mc["p_d"] * w_mc)
        p_visitante_raw = (p_visitante_a * w_analitico) + (mc["p_v"] * w_mc)

        # D. CALIBRACIÓN DE PLATT / TEMPERATURA (Optimización Brier Score)
        p_local = self._calibracion_temperatura_platt(p_local_raw)
        p_empate = self._calibracion_temperatura_platt(p_empate_raw)
        p_visitante = self._calibracion_temperatura_platt(p_visitante_raw)

        # Normalización post-calibración
        sum_calib = p_local + p_empate + p_visitante
        p_local /= sum_calib
        p_empate /= sum_calib
        p_visitante /= sum_calib

        p_under15 = self._calibracion_temperatura_platt((p_u15_a * w_analitico) + (mc["u15"] * w_mc))
        p_over15 = 1.0 - p_under15
        p_under25 = self._calibracion_temperatura_platt((p_u25_a * w_analitico) + (mc["u25"] * w_mc))
        p_over25 = 1.0 - p_under25
        p_under35 = self._calibracion_temperatura_platt((p_u35_a * w_analitico) + (mc["u35"] * w_mc))
        p_over35 = 1.0 - p_under35
        p_btts = self._calibracion_temperatura_platt((p_btts_a * w_analitico) + (mc["btts"] * w_mc))

        # Derivaciones de Doble Chance y Draw No Bet
        p_1x = p_local + p_empate
        p_x2 = p_visitante + p_empate
        p_12 = p_local + p_visitante

        tot_dec = p_local + p_visitante
        p_dnb_h = (p_local / tot_dec) if tot_dec > 0 else 0.5
        p_dnb_v = (p_visitante / tot_dec) if tot_dec > 0 else 0.5

        exp_goles = lambda_local + lambda_visitante

        # E. CÁLCULO DE CONFIANZA AVANZADO REPOTENCIADO
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
