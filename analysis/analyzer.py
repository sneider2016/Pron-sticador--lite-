class Analyzer:

    def analizar(self, datos_partido):

        """
        Analizador principal de SALM.

        Este módulo recibe toda la información del partido
        y devuelve un resumen estructurado para que el motor
        tome la decisión.
        """

        resultado = {

            "ataque_local": 50,

            "defensa_local": 50,

            "ataque_visitante": 50,

            "defensa_visitante": 50,

            "forma_local": 50,

            "forma_visitante": 50,

            "confianza": 50,

            "riesgo": "MEDIO",

            "mercados": [

                "Más de 1.5 goles",

                "Menos de 3.5 goles",

                "Ambos anotan",

                "Doble oportunidad 1X",

                "Empate no acción Local"

            ]

        }

        return resultado
