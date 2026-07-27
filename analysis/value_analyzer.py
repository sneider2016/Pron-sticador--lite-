class ValueAnalyzer:

    def calcular_ev(self, probabilidad: float, cuota: float) -> float:
        """
        Calcula el Valor Esperado (+EV).
        probabilidad: Porcentaje entre 0 y 100.
        EV = (Probabilidad_decimal * Cuota) - 1
        """
        if probabilidad <= 0 or cuota <= 0:
            return -1.0
        prob = probabilidad / 100.0
        ev = (prob * cuota) - 1.0
        return round(ev, 4)

    def cuota_justa(self, probabilidad: float) -> float:
        """
        Calcula la cuota justa ajustada según la probabilidad estimada (0-100%).
        """
        if probabilidad <= 0:
            return 999.0
        return round(100.0 / probabilidad, 2)

    def decidir(self, ev: float) -> str:
        if ev >= 0.10:
            return "🟢 APOSTAR (+EV Fuerte)"
        elif ev > 0.0:
            return "🟡 VALOR MARGINAL (+EV Modesto)"
        else:
            return "🛑 NO APOSTAR (Sin Valor / -EV)"

    def calcular_kelly(self, probabilidad: float, cuota: float, fraccion: float = 0.25) -> dict:
        """
        Calcula la gestión del Bankroll mediante el Criterio de Kelly Fraccionado (1/4 Kelly).
        """
        p = probabilidad / 100.0
        b = cuota - 1.0
        if b <= 0 or p <= 0:
            return {"kelly_pct": 0.0, "stake_sugerido_cop": 0}

        f_kelly = (p * b - (1.0 - p)) / b
        f_ajustado = max(0.0, f_kelly * fraccion)
        f_pct = round(f_ajustado * 100.0, 2)

        stake_cop = round(40000 * (f_pct / 2.5)) if f_pct > 0 else 0
        return {
            "kelly_pct": f_pct,
            "stake_sugerido_cop": max(10000, min(100000, stake_cop)) if stake_cop > 0 else 0
        }

    def clasificar_riesgo(self, probabilidad: float, ev: float) -> str:
        """
        Clasifica cuantitativamente el riesgo de la entrada.
        """
        if probabilidad >= 68.0 and ev >= 0.05:
            return "Bajo"
        elif probabilidad >= 55.0 and ev >= 0.02:
            return "Bajo-Medio"
        elif probabilidad >= 45.0 and ev > 0.0:
            return "Medio"
        else:
            return "Alto"

    def analizar(self, probabilidad: float, cuota: float) -> dict:
        c_justa = self.cuota_justa(probabilidad)
        ev = self.calcular_ev(probabilidad, cuota)
        decision = self.decidir(ev)
        kelly = self.calcular_kelly(probabilidad, cuota)
        riesgo = self.clasificar_riesgo(probabilidad, ev)

        return {
            "probabilidad": round(probabilidad, 1),
            "cuota_justa": c_justa,
            "cuota_betplay": cuota,
            "ev": ev,
            "ev_porcentaje": round(ev * 100.0, 1),
            "decision": decision,
            "riesgo": riesgo,
            "kelly_stake_pct": kelly["kelly_pct"],
            "stake_sugerido_cop": kelly["stake_sugerido_cop"]
        }
