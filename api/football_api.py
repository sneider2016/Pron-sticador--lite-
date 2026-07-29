import requests
from datetime import datetime
from rapidfuzz import fuzz
from config import API_KEY, HOST
from utils.helpers import normalizar, limpiar_nombre_busqueda


class FootballAPI:

    def __init__(self):
        self.headers = {
            "x-apisports-key": API_KEY
        }
        self.ultimo_error = ""

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
                data = respuesta.json()
                errors = data.get("errors")
                if errors and isinstance(errors, dict) and len(errors) > 0:
                    msg = str(errors)
                    self.ultimo_error = f"Error en API-Football: {msg}"
                    return []
                return data.get("response", [])
            else:
                self.ultimo_error = f"Código HTTP {respuesta.status_code}"
        except Exception as e:
            self.ultimo_error = f"Error de conexión: {str(e)}"
        return []

    def buscar_partido(self, fecha: str) -> list:
        return self.consultar("fixtures", {"date": fecha})

    def buscar_equipo_por_nombre(self, nombre_equipo: str) -> dict:
        nombre_limpio = limpiar_nombre_busqueda(nombre_equipo)
        intentos = [nombre_limpio, nombre_equipo]
        palabras = nombre_limpio.split()
        if len(palabras) > 1:
            intentos.append(palabras[0])

        for query in intentos:
            if not query or len(query) < 3:
                continue
            res = self.consultar("teams", {"search": query})
            if res:
                mejor_eq = None
                max_s = 0.0
                query_norm = normalizar(query)
                for item in res:
                    t_info = item.get("team", {})
                    t_name = t_info.get("name", "")
                    score = fuzz.ratio(query_norm, normalizar(t_name))
                    if score > max_s:
                        max_s = score
                        mejor_eq = t_info

                if mejor_eq:
                    return mejor_eq
                elif res:
                    return res[0].get("team")

        return None

    def buscar_partido_por_equipos(self, local: str, visitante: str, fecha: str):
        partidos = self.buscar_partido(fecha)
        norm_loc = normalizar(local)
        norm_vis = normalizar(visitante)

        anio = int(fecha.split("-")[0]) if fecha and "-" in fecha else 2024

        if partidos:
            mejor_match = None
            max_score = 0.0

            for p in partidos:
                l_api = p.get("teams", {}).get("home", {}).get("name", "")
                v_api = p.get("teams", {}).get("away", {}).get("name", "")

                s1 = fuzz.ratio(norm_loc, normalizar(l_api))
                s2 = fuzz.ratio(norm_vis, normalizar(v_api))
                score = (s1 + s2) / 2.0

                if score > 35 and score > max_score:
                    max_score = score
                    mejor_match = p

            if mejor_match:
                return mejor_match

        eq_loc = self.buscar_equipo_por_nombre(local)
        eq_vis = self.buscar_equipo_por_nombre(visitante)

        h_id = eq_loc.get("id") if eq_loc else 0
        h_name = eq_loc.get("name") if eq_loc else local
        v_id = eq_vis.get("id") if eq_vis else 0
        v_name = eq_vis.get("name") if eq_vis else visitante

        return {
            "fixture": {"id": 0},
            "league": {"id": 0, "season": anio},
            "teams": {
                "home": {"id": h_id, "name": h_name},
                "away": {"id": v_id, "name": v_name}
            },
            "encontrado_loc": eq_loc is not None,
            "encontrado_vis": eq_vis is not None
        }

    def ultimos_partidos(self, team_id: int, cantidad: int = 10) -> list:
        """
        Obtiene el historial de partidos usando la temporada 2024 (100% compatible gratis).
        """
        if not team_id:
            return []
        
        # Consultar la temporada 2024 permitida en el plan gratuito
        res = self.consultar("fixtures", {"team": team_id, "season": 2024})
        
        if not res or len(res) < 3:
            res_prev = self.consultar("fixtures", {"team": team_id, "season": 2023})
            res = (res_prev or []) + (res or [])

        if res:
            terminados = [
                p for p in res 
                if p.get("fixture", {}).get("status", {}).get("short") in ["FT", "AET", "PEN"]
            ]
            terminados.sort(
                key=lambda x: x.get("fixture", {}).get("date", ""), 
                reverse=True
            )
            return terminados[:cantidad]

        return []

    def ultimos_partidos_condicion(self, team_id: int, es_local: bool, cantidad: int = 5) -> list:
        todos = self.ultimos_partidos(team_id, cantidad=15)
        if not todos:
            return []
        condicion = [
            p for p in todos 
            if (p.get("teams", {}).get("home", {}).get("id") == team_id if es_local else p.get("teams", {}).get("away", {}).get("id") == team_id)
        ]
        return condicion[:cantidad]

    def head_to_head(self, local_id: int, visitante_id: int, cantidad: int = 10) -> list:
        if not local_id or not visitante_id:
            return []
        res = self.consultar("fixtures/headtohead", {"h2h": f"{local_id}-{visitante_id}"})
        if res:
            res.sort(key=lambda x: x.get("fixture", {}).get("date", ""), reverse=True)
            return res[:cantidad]
        return []

    def estadisticas_fixture(self, fixture_id: int) -> list:
        if not fixture_id:
            return []
        return self.consultar("fixtures/statistics", {"fixture": fixture_id})

    def obtener_alineaciones(self, fixture_id: int) -> list:
        if not fixture_id:
            return []
        return self.consultar("fixtures/lineups", {"fixture": fixture_id})

    def obtener_ligas(self) -> list:
        return self.consultar("leagues", {"current": "true"})

    def obtener_equipos(self, league_id: int, season: int = 2024) -> list:
        return self.consultar("teams", {"league": league_id, "season": season})

    def obtener_fixtures(self, league_id: int, season: int, fecha: str) -> list:
        return self.consultar("fixtures", {"league": league_id, "season": season, "date": fecha})

    def obtener_clasificacion(self, league_id: int, season: int = 2024) -> list:
        if not league_id:
            return []
        return self.consultar("standings", {"league": league_id, "season": season})

    def obtener_lesiones(self, fixture_id: int = None, team_id: int = None) -> list:
        params = {}
        if fixture_id:
            params["fixture"] = fixture_id
        elif team_id:
            params["team"] = team_id
        else:
            return []
        return self.consultar("injuries", params)
