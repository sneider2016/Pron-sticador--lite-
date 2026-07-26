from api.football_api import FootballAPI


class Analyzer:

    def __init__(self):
        self.api = FootballAPI()

    def _promedio_goles(self, partidos, team_id):
        """
        Calcula goles a favor y en contra de un equipo
        tomando sus últimos partidos.
        """

        if not partidos:
            return {
                "gf": 1.20,
                "gc": 1.00,
                "forma": 50
            }

        gf = 0
        gc = 0
        puntos = 0

        for partido in partidos:

            es_local = partido["teams"]["home"]["id"] == team_id

            goles_favor = (
                partido["goals"]["home"]
                if es_local
                else partido["goals"]["away"]
            )

            goles_contra = (
                partido["goals"]["away"]
                if es_local
                else partido["goals"]["home"]
            )

            gf += goles_favor
            gc += goles_contra

            if goles_favor > goles_contra:
                puntos += 3

            elif goles_favor == goles_contra:
                puntos += 1

        cantidad = len(partidos)

        forma = (puntos / (cantidad * 3)) * 100

        return {

            "gf": round(gf / cantidad, 2),

            "gc": round(gc / cantidad, 2),

            "forma": round(forma, 1)

        }

    def analizar(self, datos_partido):

        home = datos_partido["home_id"]
        away = datos_partido["away_id"]

        recientes_local = self.api.ultimos_partidos(home, 5)

        recientes_visitante = self.api.ultimos_partidos(away, 5)

        h2h = self.api.head_to_head(home, away)

        datos_local = self._promedio_goles(
            recientes_local,
            home
        )

        datos_visitante = self._promedio_goles(
            recientes_visitante,
            away
        )

        mercados = [

            "Más de 1.5 Goles",

            "Menos de 2.5 Goles",

            "Ambos Anotan",

            "Doble Oportunidad 1X",

            "Empate No Válido Local",

            "Empate No Válido Visitante"

        ]

        confianza = "Alta"

        riesgo = "Bajo"

        return {

            "ataque_local": datos_local["gf"],

            "defensa_local": datos_local["gc"],

            "ataque_visitante": datos_visitante["gf"],

            "defensa_visitante": datos_visitante["gc"],

            "forma_local": datos_local["forma"],

            "forma_visitante": datos_visitante["forma"],

            "mercados": mercados,

            "confianza": confianza,

            "riesgo": riesgo,

            "h2h": h2h

        }
