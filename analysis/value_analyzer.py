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
        Calcula la cuota justa en función de la probabilidad estimada (0-100%).
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

    def analizar(self, probabilidad: float, cuota: float) -> dict:
        c_justa = self.cuota_justa(probabilidad)
        ev = self.calcular_ev(probabilidad, cuota)
        decision = self.decidir(ev)

        return {
            "probabilidad": round(probabilidad, 1),
            "cuota_justa": c_justa,
            "cuota_betplay": cuota,
            "ev": ev,
            "ev_porcentaje": round(ev * 100.0, 1),
            "decision": decision
        }
