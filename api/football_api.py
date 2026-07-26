import requests

from config import API_KEY, HOST


class FootballAPI:

    def __init__(self):

        self.headers = {
            "x-rapidapi-host": HOST,
            "x-rapidapi-key": API_KEY
        }

    def consultar(self, endpoint, parametros):

        url = f"https://{HOST}/{endpoint}"

        try:

            respuesta = requests.get(

                url,

                headers=self.headers,

                params=parametros,

                timeout=10

            )

            if respuesta.status_code == 200:

                return respuesta.json().get("response", [])

        except Exception:

            pass

        return []

    def buscar_partido(self, fecha):

        return self.consultar(

            "fixtures",

            {

                "date": fecha

            }

        )

    def ultimos_partidos(self, team_id, cantidad=10):

        return self.consultar(

            "fixtures",

            {

                "team": team_id,

                "last": cantidad

            }

        )

    def head_to_head(self, local_id, visitante_id):

        return self.consultar(

            "fixtures/headtohead",

            {

                "h2h": f"{local_id}-{visitante_id}",

                "last":10

            }

        )

    def estadisticas_fixture(self, fixture_id):

        return self.consultar(

            "fixtures/statistics",

            {

                "fixture": fixture_id

            }

        )
    def obtener_ligas(self):

        return self.consultar(

            "leagues",

            {

                "current": "true"

            }

        )

    def obtener_equipos(self, league_id, season):

        return self.consultar(

            "teams",

            {

                "league": league_id,

                "season": season

            }

        )

    def obtener_fixtures(self, league_id, season, fecha):

        return self.consultar(

            "fixtures",

            {

                "league": league_id,

                "season": season,

                "date": fecha

            }

        )

    def obtener_clasificacion(self, league_id, season):

        return self.consultar(

            "standings",

            {

                "league": league_id,

                "season": season

            }

        )

    def obtener_lesiones(self, league_id, season):

        return self.consultar(

            "injuries",

            {

                "league": league_id,

                "season": season

            }

        )
