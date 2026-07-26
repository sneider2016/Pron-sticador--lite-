from api.football_api import FootballAPI


class Analyzer:

    def __init__(self, api: FootballAPI = None):
        self.api = api if api else FootballAPI()

    def _promedio_goles(self, partidos: list, team_id: int) -> dict:
        if not partidos or not team_id:
            return {
                "gf": 1.20,
                "gc": 1.00,
                "forma": 50.0
            }

        gf, gc, puntos = 0.0, 0.0, 0
        for partido in partidos:
            teams = partido.get("teams", {})
            goals = partido.get("goals", {})

            es_local = teams.get("home", {}).get("id") == team_id

            g_favor = (goals.get("home") or 0) if es_local else (goals.get("away") or 0)
            g_contra = (goals.get("away") or 0) if es_local else (goals.get("home") or 0)

            gf += g_favor
            gc += g_contra

            if g_favor > g_contra:
                puntos += 3
            elif g_favor == g_contra:
                puntos += 1

        cantidad = len(partidos)
        forma = (puntos / (cantidad * 3)) * 100.0 if cantidad > 0 else 50.0

        return {
            "gf": round(gf / cantidad, 2) if cantidad > 0 else 1.20,
            "gc": round(gc / cantidad, 2) if cantidad > 0 else 1.00,
            "forma": round(forma, 1)
        }

    def analizar(self, datos_partido: dict) -> dict:
        home_id = datos_partido.get("home_id", 0)
        away_id = datos_partido.get("away_id", 0)
        liga = datos_partido.get("liga", "")

        recientes_local = self.api.ultimos_partidos(home_id, 5) if home_id else []
        recientes_visitante = self.api.ultimos_partidos(away_id, 5) if away_id else []
        h2h = self.api.head_to_head(home_id, away_id, 5) if (home_id and away_id) else []

        datos_local = self._promedio_goles(recientes_local, home_id)
        datos_visitante = self._promedio_goles(recientes_visitante, away_id)

        # Proyecciones H2H
        h2h_btts = 0
        total_goles_h2h = 0
        if h2h:
            for m in h2h:
                gh = m.get("goals", {}).get("home") or 0
                ga = m.get("goals", {}).get("away") or 0
                if gh > 0 and ga > 0:
                    h2h_btts += 1
                total_goles_h2h += (gh + ga)
            prom_goles_h2h = total_goles_h2h / len(h2h)
        else:
            prom_goles_h2h = datos_local["gf"] + datos_visitante["gf"]

        exp_goles = (datos_local["gf"] + datos_visitante["gc"] + datos_visitante["gf"] + datos_local["gc"]) / 2.0
        corners_est = round(8.5 + exp_goles * 0.8, 1)
        tarjetas_est = 4.5 if ("BetPlay" in liga or "Argentina" in liga or "Colombia" in liga) else 3.8

        return {
            "ataque_local": datos_local["gf"],
            "defensa_local": datos_local["gc"],
            "ataque_visitante": datos_visitante["gf"],
            "defensa_visitante": datos_visitante["gc"],
            "forma_local": datos_local["forma"],
            "forma_visitante": datos_visitante["forma"],
            "h2h": h2h,
            "h2h_btts": h2h_btts,
            "prom_goles_h2h": round(prom_goles_h2h, 2),
            "corners_est": corners_est,
            "tarjetas_est": tarjetas_est,
            "confianza": "Alta",
            "riesgo": "Bajo"
        }
