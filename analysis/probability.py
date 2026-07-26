import math


class ProbabilityCalculator:

    def __poisson(self, k, lam):
        return (math.pow(lam, k) * math.exp(-lam)) / math.factorial(k)

    def calcular(
        self,
        ataque_local,
        defensa_local,
        ataque_visitante,
        defensa_visitante,
        forma_local,
        forma_visitante,
    ):

        # Intensidad esperada de gol
        lambda_local = max(
            0.20,
            (ataque_local + defensa_visitante) / 2
        )

        lambda_visitante = max(
            0.20,
            (ataque_visitante + defensa_local) / 2
        )

        p_local = 0
        p_empate = 0
        p_visitante = 0
        p_under25 = 0
        p_over15 = 0

        for i in range(6):

            for j in range(6):

                p = (
                    self.__poisson(i, lambda_local)
                    *
                    self.__poisson(j, lambda_visitante)
                )

                if i > j:
                    p_local += p

                elif i == j:
                    p_empate += p

                else:
                    p_visitante += p

                if (i + j) <= 2:
                    p_under25 += p

                if (i + j) >= 2:
                    p_over15 += p

        p_btts = (
            (1 - self.__poisson(0, lambda_local))
            *
            (1 - self.__poisson(0, lambda_visitante))
        )

        forma_factor = (
            (forma_local + forma_visitante)
            / 200
        )

        confianza = (
            max(
                p_local,
                p_empate,
                p_visitante,
                p_under25,
                p_over15,
                p_btts
            )
            * 100
        )

        confianza *= (0.90 + (forma_factor * 0.10))

        confianza = max(50, min(95, confianza))

        return {

            "local": round(p_local * 100, 1),

            "empate": round(p_empate * 100, 1),

            "visitante": round(p_visitante * 100, 1),

            "under25": round(p_under25 * 100, 1),

            "over15": round(p_over15 * 100, 1),

            "btts": round(p_btts * 100, 1),

            "confianza": round(confianza, 1)

        }
