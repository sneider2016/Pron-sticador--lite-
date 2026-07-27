import requests
from rapidfuzz import fuzz
from config import API_KEY, HOST
from utils.helpers import normalizar


class FootballAPI:

    def __init__(self):
        self.headers = {
            "x-rapidapi-host": HOST,
            "x-rapidapi-key": API_KEY,
            "x-apisports-key": API_KEY
        }

    def consultar(self, endpoint: str, parametros: dict) -> list:
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

    def buscar_partido(self, fecha: str) -> list:
        return self.consultar("fixtures", {"date": fecha})

    def buscar_equipo_por_nombre(self, nombre_equipo: str) -> dict:
        """
        Busca directamente un equipo por nombre para obtener su ID real si la fecha falla.
        """
        norm_query = normalizar(nombre_equipo)
        res = self.consultar("teams", {"search": norm_query})
        if not res:
            # Reintento con consulta directa si la normalización removió palabras clave
            res = self.consultar("teams", {"search": nombre_equipo})

        if res:
            mejor_eq = None
            max_s = 0
            for item in res:
                t_name = item.get("team", {}).get("name", "")
                score = fuzz.ratio(norm_query, normalizar(t_name))
                if score > max_s:
                    max_s = score
                    mejor_eq = item.get("team")
            if mejor_eq and max_s >= 40:
                return mejor_eq
            elif res:
                return res[0].get("team")
        return None

    def buscar_partido_por_equipos(self, local: str, visitante: str, fecha: str):
        """
        Busca el partido por fecha y equipos. Si no lo encuentra por fecha exacta,
        resuelve los IDs reales de ambos equipos para extraer sus datos estadísticos reales.
        """
        partidos = self.buscar_partido(fecha)
        norm_loc = normalizar(local)
        norm_vis = normalizar(visitante)

        if partidos:
            mejor_match = None
            max_score = 0

            for p in partidos:
                l_api = p.get("teams", {}).get("home", {}).get("name", "")
                v_api = p.get("teams", {}).get("away", {}).get("name", "")

                s1 = fuzz.ratio(norm_loc, normalizar(l_api))
                s2 = fuzz.ratio(norm_vis, normalizar(v_api))
                score = (s1 + s2) / 2.0

                if score > 40 and score > max_score:
                    max_score = score
                    mejor_match = p

            if mejor_match:
                return mejor_match

        # RESPALDO INTELIGENTE: Si no se encuentra el fixture en la fecha dada,
        # se obtienen los IDs reales de ambos clubes para analizar sus estadísticas reales.
        eq_loc = self.buscar_equipo_por_nombre(local)
        eq_vis = self.buscar_equipo_por_nombre(visitante)

        if eq_loc or eq_vis:
            h_id = eq_loc.get("id") if eq_loc else 0
            h_name = eq_loc.get("name") if eq_loc else local
            v_id = eq_vis.get("id") if eq_vis else 0
            v_name = eq_vis.get("name") if eq_vis else visitante

            return {
                "fixture": {"id": 0},
                "league": {"id": 0, "season": 2026},
                "teams": {
                    "home": {"id": h_id, "name": h_name},
                    "away": {"id": v_id, "name": v_name}
                }
            }

        return None

    def ultimos_partidos(self, team_id: int, cantidad: int = 10) -> list:
        if not team_id:
            return []
        return self.consultar("fixtures", {"team": team_id, "last": cantidad})

    def ultimos_partidos_condicion(self, team_id: int, es_local: bool, cantidad: int = 5) -> list:
        if not team_id:
            return []
        param = {"team": team_id, "last": cantidad, "venue": "home" if es_local else "away"}
        return self.consultar("fixtures", param)

    def head_to_head(self, local_id: int, visitante_id: int, cantidad: int = 10) -> list:
        if not local_id or not visitante_id:
            return []
        return self.consultar(
            "fixtures/headtohead",
            {"h2h": f"{local_id}-{visitante_id}", "last": cantidad}
        )

    def estadisticas_fixture(self, fixture_id: int) -> list:
        if not fixture_id:
            return []
        return self.consultar("fixtures/statistics", {"fixture": fixture_id})

    def obtener_ligas(self) -> list:
        return self.consultar("leagues", {"current": "true"})

    def obtener_equipos(self, league_id: int, season: int) -> list:
        return self.consultar("teams", {"league": league_id, "season": season})

    def obtener_fixtures(self, league_id: int, season: int, fecha: str) -> list:
        return self.consultar(
            "fixtures",
            {"league": league_id, "season": season, "date": fecha}
        )

    def obtener_clasificacion(self, league_id: int, season: int) -> list:
        if not league_id or not season:
            return []
        return self.consultar(
            "standings",
            {"league": league_id, "season": season}
        )

    def obtener_lesiones(self, fixture_id: int = None, team_id: int = None) -> list:
        params = {}
        if fixture_id:
            params["fixture"] = fixture_id
        elif team_id:
            params["team"] = team_id
        else:
            return []
        return self.consultar("injuries", params)
