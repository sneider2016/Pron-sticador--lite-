from datetime import datetime
from api.football_api import FootballAPI


class Analyzer:

    def __init__(self, api: FootballAPI = None):
        self.api = api if api else FootballAPI()

    def _procesar_historial(self, partidos: list, team_id: int) -> dict:
        if not partidos or not team_id:
            return {
                "partidos": 0,
                "gf": 1.20,
                "gc": 1.00,
                "forma_pts": 50.0,
                "over15_rate": 0.70,
                "over25_rate": 0.50,
                "under25_rate": 0.50,
                "under35_rate": 0.80,
                "btts_rate": 0.50,
                "clean_sheet_rate": 0.30,
                "racha_victorias": 0,
                "racha_invicto": 0,
                "dias_descanso": 6,
            }

        gf_total = 0.0
        gc_total = 0.0
        puntos = 0

        over15_cnt = 0
        over25_cnt = 0
        under25_cnt = 0
        under35_cnt = 0
        btts_cnt = 0
        clean_sheet_cnt = 0

        racha_v = 0
        racha_inv = 0
        evaluando_v = True
        evaluando_inv = True

        for partido in partidos:
            teams = partido.get("teams", {})
            goals = partido.get("goals", {})

            es_local = teams.get("home", {}).get("id") == team_id

            g_favor = (goals.get("home") if goals.get("home") is not None else 0) if es_local else (goals.get("away") if goals.get("away") is not None else 0)
            g_contra = (goals.get("away") if goals.get("away") is not None else 0) if es_local else (goals.get("home") if goals.get("home") is not None else 0)

            gf_total += g_favor
            gc_total += g_contra

            tot_goles = g_favor + g_contra
            if tot_goles >= 2:
                over15_cnt += 1
            if tot_goles >= 3:
                over25_cnt += 1
            if tot_goles <= 2:
                under25_cnt += 1
            if tot_goles <= 3:
                under35_cnt += 1
            if g_favor > 0 and g_contra > 0:
                btts_cnt += 1
            if g_contra == 0:
                clean_sheet_cnt += 1

            if g_favor > g_contra:
                puntos += 3
                if evaluando_v:
                    racha_v += 1
                if evaluando_inv:
                    racha_inv += 1
            elif g_favor == g_contra:
                puntos += 1
                evaluando_v = False
                if evaluando_inv:
                    racha_inv += 1
            else:
                evaluando_v = False
                evaluando_inv = False

        cant = len(partidos)
        forma_pts = (puntos / (cant * 3.0)) * 100.0 if cant > 0 else 50.0

        dias_descanso = 6
        if partidos:
            fecha_str = partidos[0].get("fixture", {}).get("date", "")
            if fecha_str:
                try:
                    fecha_ult = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).date()
                    hoy = datetime.now().date()
                    dias_descanso = max(1, (hoy - fecha_ult).days)
                except Exception:
                    dias_descanso = 6

        return {
            "partidos": cant,
            "gf": round(gf_total / cant, 2) if cant > 0 else 1.20,
            "gc": round(gc_total / cant, 2) if cant > 0 else 1.00,
            "forma_pts": round(forma_pts, 1),
            "over15_rate": round(over15_cnt / cant, 2) if cant > 0 else 0.70,
            "over25_rate": round(over25_cnt / cant, 2) if cant > 0 else 0.50,
            "under25_rate": round(under25_cnt / cant, 2) if cant > 0 else 0.50,
            "under35_rate": round(under35_cnt / cant, 2) if cant > 0 else 0.80,
            "btts_rate": round(btts_cnt / cant, 2) if cant > 0 else 0.50,
            "clean_sheet_rate": round(clean_sheet_cnt / cant, 2) if cant > 0 else 0.30,
            "racha_victorias": racha_v,
            "racha_invicto": racha_inv,
            "dias_descanso": dias_descanso,
        }

    def analizar(self, datos_partido: dict) -> dict:
        home_id = datos_partido.get("home_id", 0)
        away_id = datos_partido.get("away_id", 0)
        fixture_id = datos_partido.get("fixture_id", 0)
        league_id = datos_partido.get("league_id", 0)
        season = datos_partido.get("season", 2024)
        liga = datos_partido.get("liga", "")

        l10_local_raw = self.api.ultimos_partidos(home_id, 10) if home_id else []
        l10_visitante_raw = self.api.ultimos_partidos(away_id, 10) if away_id else []

        l5_local_raw = l10_local_raw[:5] if len(l10_local_raw) >= 5 else l10_local_raw
        l5_visitante_raw = l10_visitante_raw[:5] if len(l10_visitante_raw) >= 5 else l10_visitante_raw

        home_cond_raw = self.api.ultimos_partidos_condicion(home_id, es_local=True, cantidad=5) if home_id else []
        away_cond_raw = self.api.ultimos_partidos_condicion(away_id, es_local=False, cantidad=5) if away_id else []

        stats_l10_h = self._procesar_historial(l10_local_raw, home_id)
        stats_l5_h = self._procesar_historial(l5_local_raw, home_id)
        stats_cond_h = self._procesar_historial(home_cond_raw, home_id)

        stats_l10_v = self._procesar_historial(l10_visitante_raw, away_id)
        stats_l5_v = self._procesar_historial(l5_visitante_raw, away_id)
        stats_cond_v = self._procesar_historial(away_cond_raw, away_id)

        h2h_raw = self.api.head_to_head(home_id, away_id, 10) if (home_id and away_id) else []
        h2h_btts = 0
        h2h_goles_total = 0.0

        if h2h_raw:
            for m in h2h_raw:
                gh = m.get("goals", {}).get("home") or 0
                ga = m.get("goals", {}).get("away") or 0
                if gh > 0 and ga > 0:
                    h2h_btts += 1
                h2h_goles_total += (gh + ga)
            prom_goles_h2h = h2h_goles_total / len(h2h_raw)
        else:
            prom_goles_h2h = stats_l5_h["gf"] + stats_l5_v["gf"]

        clasificacion = self.api.obtener_clasificacion(league_id, season) if (league_id and season) else []
        promedio_goles_liga = 2.50
        posicion_h = 10
        posicion_v = 10

        if clasificacion:
            try:
                standings_list = clasificacion[0].get("league", {}).get("standings", [[]])[0]
                tot_gf = 0
                tot_pj = 0
                for team_st in standings_list:
                    t_id = team_st.get("team", {}).get("id")
                    if t_id == home_id:
                        posicion_h = team_st.get("rank", 10)
                    elif t_id == away_id:
                        posicion_v = team_st.get("rank", 10)

                    all_st = team_st.get("all", {})
                    tot_gf += all_st.get("goals", {}).get("for", 0)
                    tot_pj += all_st.get("played", 0)

                if tot_pj > 0:
                    promedio_goles_liga = round((tot_gf / tot_pj) * 2.0, 2)
            except Exception:
                promedio_goles_liga = 2.50

        lesiones = self.api.obtener_lesiones(fixture_id=fixture_id) if fixture_id else []
        lesiones_h = [l for l in lesiones if l.get("team", {}).get("id") == home_id]
        lesiones_v = [l for l in lesiones if l.get("team", {}).get("id") == away_id]

        gf_loc_efectivo = (stats_l5_h["gf"] * 0.40) + (stats_cond_h["gf"] * 0.40) + (stats_l10_h["gf"] * 0.20)
        gc_loc_efectivo = (stats_l5_h["gc"] * 0.40) + (stats_cond_h["gc"] * 0.40) + (stats_l10_h["gc"] * 0.20)

        gf_vis_efectivo = (stats_l5_v["gf"] * 0.40) + (stats_cond_v["gf"] * 0.40) + (stats_l10_v["gf"] * 0.20)
        gc_vis_efectivo = (stats_l5_v["gc"] * 0.40) + (stats_cond_v["gc"] * 0.40) + (stats_l10_v["gc"] * 0.20)

        fortaleza_ofensiva_h = gf_loc_efectivo / max(0.8, promedio_goles_liga / 2.0)
        fortaleza_defensiva_h = gc_loc_efectivo / max(0.8, promedio_goles_liga / 2.0)

        fortaleza_ofensiva_v = gf_vis_efectivo / max(0.8, promedio_goles_liga / 2.0)
        fortaleza_defensiva_v = gc_vis_efectivo / max(0.8, promedio_goles_liga / 2.0)

        exp_goles = (gf_loc_efectivo + gc_vis_efectivo + gf_vis_efectivo + gc_loc_efectivo) / 2.0
        corners_est = round(8.8 + exp_goles * 0.75, 1)
        tarjetas_est = 4.6 if ("BetPlay" in liga or "Argentina" in liga or "Colombia" in liga or "Libertadores" in liga) else 3.9

        return {
            "ataque_local": round(gf_loc_efectivo, 2),
            "defensa_local": round(gc_loc_efectivo, 2),
            "ataque_visitante": round(gf_vis_efectivo, 2),
            "defensa_visitante": round(gc_vis_efectivo, 2),
            "forma_local": stats_l5_h["forma_pts"],
            "forma_visitante": stats_l5_v["forma_pts"],
            "forma_l10_local": stats_l10_h["forma_pts"],
            "forma_l10_visitante": stats_l10_v["forma_pts"],
            "racha_h": stats_l5_h["racha_invicto"],
            "racha_v": stats_l5_v["racha_invicto"],
            "descanso_h": stats_l5_h["dias_descanso"],
            "descanso_v": stats_l5_v["dias_descanso"],
            "fortaleza_ofensiva_h": round(fortaleza_ofensiva_h, 2),
            "fortaleza_defensiva_h": round(fortaleza_defensiva_h, 2),
            "fortaleza_ofensiva_v": round(fortaleza_ofensiva_v, 2),
            "fortaleza_defensiva_v": round(fortaleza_defensiva_v, 2),
            "clean_sheet_h": stats_l5_h["clean_sheet_rate"],
            "clean_sheet_v": stats_l5_v["clean_sheet_rate"],
            "over15_rate_h": stats_l5_h["over15_rate"],
            "over15_rate_v": stats_l5_v["over15_rate"],
            "over25_rate_h": stats_l5_h["over25_rate"],
            "over25_rate_v": stats_l5_v["over25_rate"],
            "under25_rate_h": stats_l5_h["under25_rate"],
            "under25_rate_v": stats_l5_v["under25_rate"],
            "btts_rate_h": stats_l5_h["btts_rate"],
            "btts_rate_v": stats_l5_v["btts_rate"],
            "h2h": h2h_raw,
            "h2h_btts": h2h_btts,
            "prom_goles_h2h": round(prom_goles_h2h, 2),
            "promedio_goles_liga": promedio_goles_liga,
            "posicion_h": posicion_h,
            "posicion_v": posicion_v,
            "lesiones_h_cnt": len(lesiones_h),
            "lesiones_v_cnt": len(lesiones_v),
            "corners_est": corners_est,
            "tarjetas_est": tarjetas_est,
            "confianza": "Alta",
            "riesgo": "Bajo"
        }
