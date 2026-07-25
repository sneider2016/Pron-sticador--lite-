class ProbabilityCalculator:

    def calcular(
        self,
        ataque_local,
        defensa_local,
        ataque_visitante,
        defensa_visitante,
        forma_local,
        forma_visitante,
    ):

        score = (
            ataque_local * 0.25 +
            defensa_visitante * 0.15 +
            forma_local * 0.20 +
            ataque_visitante * 0.20 +
            defensa_local * 0.10 +
            forma_visitante * 0.10
        )

        score = max(0, min(100, score))

        return round(score, 1)
