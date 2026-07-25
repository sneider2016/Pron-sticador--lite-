class ValueAnalyzer:

    def calcular_ev(self, probabilidad, cuota):
        probabilidad_decimal = probabilidad / 100
        ev = (probabilidad_decimal * cuota) - 1
        return round(ev, 3)

    def decidir(self, ev):
        if ev >= 0.08:
            return "✅ APOSTAR"

        if ev >= 0.03:
            return "🟡 REVISAR"

        return "❌ NO APOSTAR"
