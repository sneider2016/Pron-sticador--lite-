class ValueAnalyzer:

    def calcular_ev(self, probabilidad, cuota):
        """
        Calcula el Valor Esperado (Expected Value).

        EV = (Probabilidad * Cuota) - 1
        """

        prob = probabilidad / 100

        ev = (prob * cuota) - 1

        return round(ev, 4)

    def cuota_justa(self, probabilidad):
        """
        Calcula la cuota justa según la probabilidad estimada.
        """

        if probabilidad <= 0:
            return 999.0

        return round(100 / probabilidad, 2)

    def decidir(self, ev):

        if ev >= 0.10:
            return "🟢 APOSTAR"

        elif ev >= 0.03:
            return "🟡 VALOR MARGINAL"

        else:
            return "🔴 NO APOSTAR"

    def analizar(self, probabilidad, cuota):

        cuota_justa = self.cuota_justa(probabilidad)

        ev = self.calcular_ev(
            probabilidad,
            cuota
        )

        return {

            "probabilidad": round(probabilidad, 1),

            "cuota_justa": cuota_justa,

            "cuota_betplay": cuota,

            "ev": ev,

            "decision": self.decidir(ev)

        }
