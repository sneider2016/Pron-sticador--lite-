import math


class ProbabilityCalculator:

    def __poisson(self, k: int, lam: float) -> float:
        return (math.pow(lam, k) * math.exp(-lam)) / math.factorial(k)

    def _ajuste_dixon_coles(self, i: int, j: int, l_h: float, l_v: float, rho: float = -0.06) -> float:
        """
        Ajuste Bivariado de Dixon-Coles para corregir subestimación de marcadores de bajo score (0-0, 1-0, 0-1, 1-1).
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
        **kwargs
    ) -> dict:

        # 1. Base de intensidad Poisson
        base_lambda_local = (ataque_local + defensa_visitante) / 2.0
        base_lambda_visitante = (ataque_visitante + defensa_local) / 2.0

        # 2. Multiplicador por Fortaleza Relativa Ofensiva y Defensiva
        factor_fuerza_h = (fortaleza_off_h * (2.0 - min(1.8, fortaleza_def_v)))
        factor_fuerza_v = (fortaleza_off_v * (2.0 - min(1.8, fortaleza_def_h)))

        # 3. Factor ELO Relativo y ventaja de Localía
        dif_elo = elo_h - elo_v + 65.0  # +65 puntos por localía
        factor_elo_h = max(0.75, min(1.35, 1.0 + (dif_elo / 1000.0)))
        factor_elo_v = max(0.75, min(1.35, 1.0 - (dif_elo / 1000.0)))

        # 4. Impacto xG (Expectativa de gol de calidad)
        factor_xg_h = max(0.80, min(1.25, xg_h / max(0.8, ataque_local)))
        factor_xg_v = max(0.80, min(1.25, xg_v / max(0.8, ataque_visitante)))

        # 5. Fatiga por descanso
        fatiga_h = 0.90 if descanso_h < 3 else (1.04 if descanso_h >= 6 else 1.0)
        fatiga_v = 0.90 if descanso_v < 3 else (1.04 if descanso_v >= 6 else 1.0)

        # 6. Bajas e Lesiones
        bajas_h = max(0.85, 1.0 - (lesiones_h * 0.03))
        bajas_v = max(0.85, 1.0 - (lesiones_v * 0.03))

        # Lambdas finales
        lambda_local = max(0.20, base_lambda_local * factor_fuerza_h * factor_elo_h * factor_xg_h * fatiga_h * bajas_h)
        lambda_visitante = max(0.20, base_lambda_visitante * factor_fuerza_v * factor_elo_v * factor_xg_v * fatiga_v * bajas_v)

        p_local = 0.0
        p_empate = 0.0
        p_visitante = 0.0
        p_under15 = 0.0
        p_over15 = 0.0
        p_under25 = 0.0
        p_over25 = 0.0
        p_under35 = 0.0
        p_over35 = 0.0

        for i in range(8):
            for j in range(8):
                p_base = self.__poisson(i, lambda_local) * self.__poisson(j, lambda_visitante)
                tau = self._ajuste_dixon_coles(i, j, lambda_local, lambda_visitante)
                p = max(0.0, p_base * tau)

                if i > j:
                    p_local += p
                elif i == j:
                    p_empate += p
                else:
                    p_visitante += p

                total_goles = i + j
                if total_goles < 1.5:
                    p_under15 += p
                if total_goles >= 2:
                    p_over15 += p
                if total_goles <= 2:
                    p_under25 += p
                if total_goles >= 3:
                    p_over25 += p
                if total_goles <= 3:
                    p_under35 += p
                if total_goles >= 4:
                    p_over35 += p

        # Normalización matemática de la matriz de probabilidad
        suma_total_p = max(0.0001, p_local + p_empate + p_visitante)
        p_local /= suma_total_p
        p_empate /= suma_total_p
        p_visitante /= suma_total_p

        p_btts = (1.0 - self.__poisson(0, lambda_local)) * (1.0 - self.__poisson(0, lambda_visitante))
        p_1x = p_local + p_empate
        p_x2 = p_visitante + p_empate
        p_12 = p_local + p_visitante

        total_decisivo = p_local + p_visitante
        p_dnb_h = (p_local / total_decisivo) if total_decisivo > 0 else 0.5
        p_dnb_v = (p_visitante / total_decisivo) if total_decisivo > 0 else 0.5

        exp_goles = lambda_local + lambda_visitante

        # Nivel de confianza ponderado
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
