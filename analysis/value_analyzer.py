class ValueAnalyzer:

    def calcular_ev(self, probabilidad: float, cuota: float) -> float:
        if probabilidad <= 0 or cuota <= 0:
            return -1.0
        prob = probabilidad / 100.0
        ev = (prob * cuota) - 1.0
        return round(ev, 4)

    def cuota_justa(self, probabilidad: float) -> float:
        if probabilidad <= 0:
            return 999.0
        return round(100.0 / probabilidad, 2)

    def decidir(self, ev: float, ratio_discrepancia: float) -> str:
        # VÁLVULA DE SEGURIDAD ANTI-TRAMPAS DE MERCADO
        if ratio_discrepancia > 1.35:
            return "🛑 NO APOSTAR (Discrepancia Sospechosa con la Casa / Trampa)"
        if ev >= 0.05:
            return "🟢 APOSTAR (+EV Confirmado)"
        elif ev > 0.0:
            return "🟡 VALOR MARGINAL (+EV Modesto)"
        else:
            return "🛑 NO APOSTAR (Sin Valor / -EV)"

    def calcular_kelly(self, probabilidad: float, cuota: float, fraccion: float = 0.20) -> dict:
        """
        Kelly Fraccional con Techo Duro (Flat Cap) para blindar el bankroll contra varianza negativa.
        """
        p = probabilidad / 100.0
        b = cuota - 1.0
        if b <= 0 or p <= 0:
            return {"kelly_pct": 0.0, "stake_sugerido_cop": 0}

        f_kelly = (p * b - (1.0 - p)) / b
        f_ajustado = max(0.0, f_kelly * fraccion)
        f_pct = round(f_ajustado * 100.0, 2)

        # CAP MÁXIMO DE STAKE: Máximo $15.000 COP para evitar pérdidas asimétricas
        MAX_STAKE_PERMITIDO_COP = 15000
        stake_calculado = round(30000 * (f_pct / 2.0)) if f_pct > 0 else 0
        stake_seguro = max(10000, min(MAX_STAKE_PERMITIDO_COP, stake_calculado)) if stake_calculado > 0 else 0

        return {
            "kelly_pct": min(3.0, f_pct),
            "stake_sugerido_cop": stake_seguro
        }

    def clasificar_riesgo(self, probabilidad: float, ev: float) -> str:
        if probabilidad >= 72.0 and ev >= 0.04:
            return "Bajo"
        elif probabilidad >= 60.0 and ev >= 0.02:
            return "Bajo-Medio"
        elif probabilidad >= 50.0 and ev > 0.0:
            return "Medio"
        else:
            return "Alto"

    def analizar(self, probabilidad: float, cuota: float) -> dict:
        c_justa = self.cuota_justa(probabilidad)
        ev = self.calcular_ev(probabilidad, cuota)
        ratio_disc = cuota / c_justa if c_justa > 0 else 1.0
        decision = self.decidir(ev, ratio_disc)
        kelly = self.calcular_kelly(probabilidad, cuota)
        riesgo = self.clasificar_riesgo(probabilidad, ev)

        return {
            "probabilidad": round(probabilidad, 1),
            "cuota_justa": c_justa,
            "cuota_betplay": cuota,
            "ev": ev,
            "ev_porcentaje": round(ev * 100.0, 1),
            "ratio_discrepancia": round(ratio_disc, 2),
            "decision": decision,
            "riesgo": riesgo,
            "kelly_stake_pct": kelly["kelly_pct"],
            "stake_sugerido_cop": kelly["stake_sugerido_cop"]
        }
