from api.football_api import FootballAPI


class Analyzer:

    def __init__(self):

        self.api = FootballAPI()

    def analizar(self, datos_partido):

        """
        datos_partido debe contener:

        {
            "fixture_id":...,
            "home_id":...,
            "away_id":...
        }
        """

        home = datos_partido["home_id"]
        away = datos_partido["away_id"]

        recientes_local = self.api.ultimos_partidos(home)

        recientes_visitante = self.api.ultimos_partidos(away)

        h2h = self.api.head_to_head(home, away)

        return {

            "recientes_local": recientes_local,

            "recientes_visitante": recientes_visitante,

            "h2h": h2h

        }
