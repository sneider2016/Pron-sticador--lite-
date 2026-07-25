from analysis.analyzer import Analyzer
from analysis.probability import ProbabilityCalculator
from analysis.value_analyzer import ValueAnalyzer


class SALMEngine:

    def __init__(self):

        self.analyzer = Analyzer()
        self.probability = ProbabilityCalculator()
        self.value = ValueAnalyzer()

    def analizar(self, datos_partido):

        analisis = self.analyzer.analizar(datos_partido)

        probabilidad = self.probability.calcular(
            ataque_local=analisis["ataque_local"],
            defensa_local=analisis["defensa_local"],
            ataque_visitante=analisis["ataque_visitante"],
            defensa_visitante=analisis["defensa_visitante"],
            forma_local=analisis["forma_local"],
            forma_visitante=analisis["forma_visitante"],
        )

        mercados = analisis["mercados"]

        ranking = []

        for mercado in mercados:

            cuota_justa = round(100 / probabilidad, 2)

            ranking.append({

                "mercado": mercado,

                "probabilidad": probabilidad,

                "confianza": analisis["confianza"],

                "riesgo": analisis["riesgo"],

                "cuota_justa": cuota_justa

            })

        ranking.sort(

            key=lambda x: x["probabilidad"],

            reverse=True

        )

        return ranking

    def evaluar_betplay(self, mercado, cuota):

        ev = self.value.calcular_ev(

            mercado["probabilidad"],

            cuota

        )

        decision = self.value.decidir(ev)

        return {

            "ev": ev,

            "decision": decision

        }
