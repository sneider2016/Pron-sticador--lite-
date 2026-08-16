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

        return (max(0.20, min(4.5, lambda_h_post)), max(0.20, min(4.5, lambda_v_post)))

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
        return max(0.05, tau)

    def _calibracion_temperatura_platt(self, prob_decimal: float, temperatura: float = 1.18) -> float:
        p_safe = max(0.001, min(0.999, prob_decimal))
        logit = math.log(p_safe / (1.0 - p_safe))
        logit_calibrado = logit / temperatura
        p_calibrada = 1.0 / (1.0 + math.exp(-logit_calibrado))
        return max(0.001, min(0.999, p_calibrada))

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
        **kwargs
    ) -> dict:

        # 1. Base Poisson con ventaja de campo de la liga
        base_lambda_h = max(0.20, (ataque_local + defensa_visitante) / 2.0 + home_adv)
        base_lambda_v = max(0.20, (ataque_visitante + defensa_local) / 2.0)

        # 2. Factor de Jerarquía ELO Real
        dif_elo = elo_h - elo_v
        factor_elo_h = max(0.40, min(2.10, 1.0 + (dif_elo / 450.0)))
        factor_elo_v = max(0.40, min(2.10, 1.0 - (dif_elo / 450.0)))

        l_h_raw = base_lambda_h * factor_elo_h
        l_v_raw = base_lambda_v * factor_elo_v

        # Ajuste en eliminatorias de alta volatilidad
        if es_eliminatoria:
            l_h_raw *= 1.08
            l_v_raw *= 1.08

        # 3. Recalibración Bayesiana
        lambda_local, lambda_visitante = self._recalibrar_lambdas_bayesiano(l_h_raw, l_v_raw)

        # Matriz Bivariada Dixon-Coles 8x8
        rho = -0.06
        p_local_a, p_empate_a, p_visitante_a = 0.0, 0.0, 0.0
        p_u15_a, p_o15_a, p_u25_a, p_o25_a, p_u35_a, p_o35_a = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        matriz = [[0.0] * 8 for _ in range(8)]
        suma_raw = 0.0

        for i in range(8):
            for j in range(8):
                p_base = self.__poisson(i, lambda_local) * self.__poisson(j, lambda_visitante)
                tau = self._ajuste_dixon_coles(i, j, lambda_local, lambda_visitante, rho)
                val = max(0.0, p_base * tau)
                matriz[i][j] = val
                suma_raw += val

        norm_factor = max(0.0001, suma_raw)
        for i in range(8):
            for j in range(8):
                p_exacta = matriz[i][j] / norm_factor
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

        # Calibración Platt
        p_local = self._calibracion_temperatura_platt(p_local_a)
        p_empate = self._calibracion_temperatura_platt(p_empate_a)
        p_visitante = self._calibracion_temperatura_platt(p_visitante_a)

        s_tot = p_local + p_empate + p_visitante
        p_local /= s_tot
        p_empate /= s_tot
        p_visitante /= s_tot

        p_o15 = self._calibracion_temperatura_platt(p_o15_a)
        p_u25 = self._calibracion_temperatura_platt(p_u25_a)
        p_u35 = self._calibracion_temperatura_platt(p_u35_a)
        p_btts = self._calibracion_temperatura_platt(p_btts_a)

        # Si es eliminatoria castigamos Under 3.5 por el riesgo de partido roto
        if es_eliminatoria:
            p_u35 = max(0.50, p_u35 * 0.88)

        p_1x = min(0.92, p_local + p_empate)
        p_x2 = min(0.92, p_visitante + p_empate)

        tot_dec = p_local + p_visitante
        p_dnb_h = (p_local / tot_dec) if tot_dec > 0 else 0.5
        p_dnb_v = (p_visitante / tot_dec) if tot_dec > 0 else 0.5

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
            "over15": round(p_o15 * 100.0, 1),
            "under25": round(p_u25 * 100.0, 1),
            "under35": round(p_u35 * 100.0, 1),
            "btts": round(p_btts * 100.0, 1),
            "confianza": 80.0
        }
