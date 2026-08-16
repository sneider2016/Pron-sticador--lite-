import bisect
import math
import random


class ProbabilityCalculator:

    def __poisson(self, k: int, lam: float) -> float:
        if lam <= 0:
            return 1.0 if k == 0 else 0.0
        try:
            return (math.pow(lam, k) * math.exp(-lam)) / math.factorial(k)
        except OverflowError:
            return 0.0

    def _recalibrar_lambdas_bayesiano(self, l_h_raw: float, l_v_raw: float) -> tuple:
        mu_prior = 1.30
        var_prior = 0.55
        alpha_0 = (mu_prior ** 2) / var_prior
        beta_0 = mu_prior / var_prior

        n_obs = 6.0
        lambda_h_post = (alpha_0 + (l_h_raw * n_obs)) / (beta_0 + n_obs)
        lambda_v_post = (alpha_0 + (l_v_raw * n_obs)) / (beta_0 + n_obs)

        return (max(0.20, min(4.80, lambda_h_post)), max(0.20, min(4.80, lambda_v_post)))

    def _calcular_rho_dinamico(self, l_h: float, l_v: float, forma_local: float = 50.0, forma_visitante: float = 50.0, **kwargs) -> float:
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
        tau = 1.0
        if i == 0 and j == 0:
            tau = 1.0 - (l_h * l_v * rho)
        elif i == 1 and j == 0:
            tau = 1.0 + (l_v * rho)
        elif i == 0 and j == 1:
            tau = 1.0 + (l_h * rho)
        elif i == 1 and j == 1:
            tau = 1.0 - rho
        return max(0.02, tau)

    def _calibracion_temperatura_platt(self, prob_decimal: float, temperatura: float = 1.15) -> float:
        p_safe = max(0.001, min(0.999, prob_decimal))
        logit = math.log(p_safe / (1.0 - p_safe))
        logit_calibrado = logit / temperatura
        p_calibrada = 1.0 / (1.0 + math.exp(-logit_calibrado))
        return max(0.001, min(0.999, p_calibrada))

    def _determinar_simulaciones_adaptativas(self, p_h: float, p_d: float, p_v: float) -> int:
        disparidad_1x2 = abs(p_h - p_v)
        if disparidad_1x2 < 0.15:
            return 14000
        elif disparidad_1x2 < 0.35:
            return 9000
        else:
            return 5000

    def _sample_poisson_inversion(self, lam: float, u: float) -> int:
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
        Simulación Monte Carlo estocástica con Muestreo Ponderado y Variables Antitéticas (Reducción de Varianza).
        """
        if seed is not None:
            random.seed(seed)

        w_tot = 0.0
        w_h, w_d, w_v = 0.0, 0.0, 0.0
        w_u15, w_o15, w_u25, w_o25, w_u35, w_o35, w_btts = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

        num_pasos = max(1000, n_sims // 2)
        for paso in range(num_pasos):
            u_h = random.random()
            u_v = random.random()

            # Muestra 1: Primaria
            g_h1 = self._sample_poisson_inversion(l_h, u_h)
            g_v1 = self._sample_poisson_inversion(l_v, u_v)
            tau1 = self._ajuste_dixon_coles(g_h1, g_v1, l_h, l_v, rho)

            # Muestra 2: Antitética (1 - u)
            g_h2 = self._sample_poisson_inversion(l_h, 1.0 - u_h)
            g_v2 = self._sample_poisson_inversion(l_v, 1.0 - u_v)
            tau2 = self._ajuste_dixon_coles(g_h2, g_v2, l_h, l_v, rho)

            for gh, gv, tau in [(g_h1, g_v1, tau1), (g_h2, g_v2, tau2)]:
                w_tot += tau
                if gh > gv: w_h += tau
                elif gh == gv: w_d += tau
                else: w_v += tau

                tot = gh + gv
                if tot < 1.5: w_u15 += tau
                if tot >= 2: w_o15 += tau
                if tot <= 2: w_u25 += tau
                if tot >= 3: w_o25 += tau
                if tot <= 3: w_u35 += tau
                if tot >= 4: w_o35 += tau
                if gh > 0 and gv > 0: w_btts += tau

        w_tot_inv = 1.0 / max(0.00001, w_tot)
        return {
            "p_h": w_h * w_tot_inv, "p_d": w_d * w_tot_inv, "p_v": w_v * w_tot_inv,
            "u15": w_u15 * w_tot_inv, "o15": w_o15 * w_tot_inv, "u25": w_u25 * w_tot_inv,
            "o25": w_o25 * w_tot_inv, "u35": w_u35 * w_tot_inv, "o35": w_o35 * w_tot_inv,
            "btts": w_btts * w_tot_inv
        }

    def _calcular_confianza_avanzada(self, p_h: float, p_d: float, p_v: float, p_u25: float, p_o15: float, p_btts: float, mc_h: float, forma_local: float, forma_visitante: float) -> float:
        """
        Índice de confianza considerando Entropía de Shannon y convergencia Monte Carlo.
        """
        probs_1x2 = [max(0.001, p_h), max(0.001, p_d), max(0.001, p_v)]
        sum_1x2 = sum(probs_1x2)
        probs_1x2_norm = [p / sum_1x2 for p in probs_1x2]

        entropia = -sum(p * math.log2(p) for p in probs_1x2_norm)
        entropia_norm = entropia / math.log2(3.0)
        certeza_informacion = 1.0 - entropia_norm

        sorted_1x2 = sorted(probs_1x2_norm, reverse=True)
        delta_top = sorted_1x2[0] - sorted_1x2[1]

        dif_mc = abs(p_h - mc_h)
        recompensa_consenso = 5.0 if dif_mc < 0.02 else (2.0 if dif_mc < 0.04 else -3.0)

        confianza_base = 52.0 + (delta_top * 25.0) + (certeza_informacion * 15.0) + recompensa_consenso
        return max(55.0, min(95.0, round(confianza_base, 1)))

    def calcular(
        self,
        ataque_local: float,
        defensa_local: float,
        ataque_visitante: float,
        defensa_visitante: float,
        forma_local: float = 50.0,
        forma_visitante: float = 50.0,
        elo_h: float = 1500.0,
        elo_v: float = 1500.0,
        descanso_h: int = 6,
        descanso_v: int = 6,
        home_adv: float = 0.30,
        es_eliminatoria: bool = False,
        btts_rate: float = 0.50,
        under25_rate: float = 0.50,
        **kwargs
    ) -> dict:

        # 1. Base Poisson con Ventaja de Localía
        base_lambda_local = max(0.20, (ataque_local + defensa_visitante) / 2.0 + home_adv)
        base_lambda_visitante = max(0.20, (ataque_visitante + defensa_local) / 2.0)

        # 2. Factor de Jerarquía ELO Dinámico
        dif_elo = elo_h - elo_v
        factor_elo_h = max(0.45, min(2.10, 1.0 + (dif_elo / 450.0)))
        factor_elo_v = max(0.45, min(2.10, 1.0 - (dif_elo / 450.0)))

        fatiga_h = 0.92 if descanso_h < 3 else 1.0
        fatiga_v = 0.92 if descanso_v < 3 else 1.0

        l_h_raw = base_lambda_local * factor_elo_h * fatiga_h
        l_v_raw = base_lambda_visitante * factor_elo_v * fatiga_v

        if es_eliminatoria:
            l_h_raw *= 1.08
            l_v_raw *= 1.08

        # 3. Recalibración Bayesiana de Lambdas
        lambda_local, lambda_visitante = self._recalibrar_lambdas_bayesiano(l_h_raw, l_v_raw)

        # 4. Covarianza lambda_3 y Rho Dinámico
        lambda_3 = min(0.20, lambda_local * lambda_visitante * 0.08)
        rho_dinamico = self._calcular_rho_dinamico(lambda_local, lambda_visitante, forma_local, forma_visitante)

        # A. CÁLCULO ANALÍTICO BIVARIADO POISSON + DIXON-COLES
        matriz_8x8 = [[0.0] * 8 for _ in range(8)]
        suma_raw = 0.0

        for i in range(8):
            for j in range(8):
                p_base = 0.0
                for k in range(min(i, j) + 1):
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

        norm_factor = max(0.0001, suma_raw)
        p_local_a, p_empate_a, p_visitante_a = 0.0, 0.0, 0.0
        p_u15_a, p_o15_a, p_u25_a, p_o25_a, p_u35_a, p_o35_a = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

        for i in range(8):
            for j in range(8):
                p_exacta = matriz_8x8[i][j] / norm_factor
                if i > j: p_local_a += p_exacta
                elif i == j: p_empate_a += p_exacta
                else: p_visitante_a += p_exacta

                tot = i + j
                if tot < 1.5: p_u15_a += p_exacta
                if tot >= 2: p_o15_a += p_exacta
                if tot <= 2: p_u25_a += p_exacta
                if tot >= 3: p_o25_a += p_exacta
                if tot <= 3: p_u35_a += p_exacta
                if tot >= 4: p_o35_a += p_exacta

        p_btts_a = (1.0 - self.__poisson(0, lambda_local)) * (1.0 - self.__poisson(0, lambda_visitante))

        # B. CÁLCULO MONTE CARLO ESTOCÁSTICO ADAPTATIVO
        n_sims = self._determinar_simulaciones_adaptativas(p_local_a, p_empate_a, p_visitante_a)
        mc = self._simulacion_monte_carlo(lambda_local, lambda_visitante, n_sims, rho_dinamico)

        # C. PONDERACIÓN POR ENTROPÍA DE SHANNON
        probs_raw = [max(0.001, p_local_a), max(0.001, p_empate_a), max(0.001, p_visitante_a)]
        entropia = -sum(p * math.log2(p) for p in probs_raw) / math.log2(3.0)
        w_analitico = 0.70 - (entropia * 0.20)
        w_mc = 1.0 - w_analitico

        p_local_raw = (p_local_a * w_analitico) + (mc["p_h"] * w_mc)
        p_empate_raw = (p_empate_a * w_analitico) + (mc["p_d"] * w_mc)
        p_visitante_raw = (p_visitante_a * w_analitico) + (mc["p_v"] * w_mc)

        # D. CALIBRACIÓN DE PLATT / TEMPERATURA
        p_local = self._calibracion_temperatura_platt(p_local_raw)
        p_empate = self._calibracion_temperatura_platt(p_empate_raw)
        p_visitante = self._calibracion_temperatura_platt(p_visitante_raw)

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

        if es_eliminatoria:
            p_under35 = max(0.50, p_under35 * 0.88)
            p_over35 = 1.0 - p_under35

        p_1x = min(0.94, p_local + p_empate)
        p_x2 = min(0.94, p_visitante + p_empate)

        tot_dec = p_local + p_visitante
        p_dnb_h = (p_local / tot_dec) if tot_dec > 0 else 0.5
        p_dnb_v = (p_visitante / tot_dec) if tot_dec > 0 else 0.5

        confianza_final = self._calcular_confianza_avanzada(
            p_local, p_empate, p_visitante, p_under25, p_over15, p_btts,
            mc["p_h"], forma_local, forma_visitante
        )

        return {
            "lambda_local": round(lambda_local, 2),
            "lambda_visitante": round(lambda_visitante, 2),
            "exp_goles": round(lambda_local + lambda_visitante, 2),
            "local": round(p_local * 100.0, 1),
            "empate": round(p_empate * 100.0, 1),
            "visitante": round(p_visitante * 100.0, 1),
            "doble_chance_1x": round(p_1x * 100.0, 1),
            "doble_chance_x2": round(p_x2 * 100.0, 1),
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
