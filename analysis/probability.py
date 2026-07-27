import math
import random


class ProbabilityCalculator:

    def __poisson(self, k: int, lam: float) -> float:
        return (math.pow(lam, k) * math.exp(-lam)) / math.factorial(k)

    def _ajuste_dixon_coles(self, i: int, j: int, l_h: float, l_v: float, rho: float = -0.06) -> float:
        """
        Ajuste Bivariado de Dixon-Coles para corregir marcadores de bajo score.
        """
        if i == 0 and j == 0:
            return 1.0 - (l_h * l_v * rho)
        elif i == 1 and j == 0:
            return 1.0 + (l_v * rho)
        elif i == 0 and j == 1:
            return 1.0 + (l_h * rho)
        elif i == 1 and j == 1:
            return 1.0 - rho
        return 1.0

    def _simulacion_monte_carlo(self, l_h: float, l_v: float, n_sims: int = 10000, rho: float = -0.06) -> dict:
        """
        Ejecuta 10,000 simulaciones estocásticas de Monte Carlo basadas en Poisson con correlación Dixon-Coles.
        """
        wins_h, draws, wins_v = 0, 0, 0
        u15, o15, u25, o25, u35, o35, btts = 0, 0, 0, 0, 0, 0, 0

        # Muestreador rápido de Poisson (Algoritmo de Knuth)
        def _sample_poisson(lam):
            L = math.exp(-lam)
            k = 0
            p = 1.0
            while p > L:
                k += 1
                p *= random.random()
            return k - 1

        for _ in range(n_sims):
            gh = _sample_poisson(l_h)
            gv = _sample_poisson(l_v)

            # Ajuste de densidad bivariada
            tau = self._ajuste_dixon_coles(gh, gv, l_h, l_v, rho)
            if random.random() > min(1.0, tau):
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

        return {
            "p_h": wins_h / n_sims,
            "p_d": draws / n_sims,
            "p_v": wins_v / n_sims,
            "u15": u15 / n_sims,
            "o15": o15 / n_sims,
            "u25": u25 / n_sims,
            "o25": o25 / n_sims,
            "u35": u35 / n_sims,
            "o35": o35 / n_sims,
            "btts": btts / n_sims
        }

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

        # 1. Base de intensidad Poisson
        base_lambda_local = (ataque_local + defensa_visitante) / 2.0
        base_lambda_visitante = (ataque_visitante + defensa_local) / 2.0

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

        # 5. Fatiga y Lesiones
        fatiga_h = 0.90 if descanso_h < 3 else (1.04 if descanso_h >= 6 else 1.0)
        fatiga_v = 0.90 if descanso_v < 3 else (1.04 if descanso_v >= 6 else 1.0)
        bajas_h = max(0.85, 1.0 - (lesiones_h * 0.03))
        bajas_v = max(0.85, 1.0 - (lesiones_v * 0.03))

        # Lambdas finales
        lambda_local = max(0.20, base_lambda_local * factor_fuerza_h * factor_elo_h * factor_xg_h * fatiga_h * bajas_h)
        lambda_visitante = max(0.20, base_lambda_visitante * factor_fuerza_v * factor_elo_v * factor_xg_v * fatiga_v * bajas_v)

        # A. CÁLCULO ANALÍTICO (Poisson + Dixon-Coles)
        p_local_a, p_empate_a, p_visitante_a = 0.0, 0.0, 0.0
        p_u15_a, p_o15_a, p_u25_a, p_o25_a, p_u35_a, p_o35_a = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

        for i in range(8):
            for j in range(8):
                p_base = self.__poisson(i, lambda_local) * self.__poisson(j, lambda_visitante)
                tau = self._ajuste_dixon_coles(i, j, lambda_local, lambda_visitante)
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

        sum_a = max(0.0001, p_local_a + p_empate_a + p_visitante_a)
        p_local_a /= sum_a
        p_empate_a /= sum_a
        p_visitante_a /= sum_a

        p_btts_a = (1.0 - self.__poisson(0, lambda_local)) * (1.0 - self.__poisson(0, lambda_visitante))

        # B. CÁLCULO MONTE CARLO (Simulación Estocástica)
        mc = self._simulacion_monte_carlo(lambda_local, lambda_visitante, n_sims=10000)

        # C. FUSIÓN HÍBRIDA PONDERADA (60% Analítico + 40% Monte Carlo)
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

        p_1x = p_local + p_empate
        p_x2 = p_visitante + p_empate
        p_12 = p_local + p_visitante

        tot_dec = p_local + p_visitante
        p_dnb_h = (p_local / tot_dec) if tot_dec > 0 else 0.5
        p_dnb_v = (p_visitante / tot_dec) if tot_dec > 0 else 0.5

        exp_goles = lambda_local + lambda_visitante

        forma_factor = (forma_local + forma_visitante) / 200.0
        confianza = max(p_local, p_empate, p_visitante, p_under25, p_over15, p_btts) * 100.0
        confianza = max(58.0, min(96.0, confianza * (0.88 + (forma_factor * 0.12))))

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
            "confianza": round(confianza, 1)
        }
