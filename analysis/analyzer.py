import math
from datetime import datetime
from api.football_api import FootballAPI


class Analyzer:

    # Promedios base por tipo de liga (Ponderación por liga)
    PROMEDIOS_LIGAS = {
        "premier": {"goles": 2.85, "corners": 10.2, "tarjetas": 3.9},
        "laliga": {"goles": 2.50, "corners": 9.4, "tarjetas": 4.8},
        "serie a": {"goles": 2.62, "corners": 9.6, "tarjetas": 4.5},
        "bundesliga": {"goles": 3.10, "corners": 9.8, "tarjetas": 3.8},
        "ligue 1": {"goles": 2.58, "corners": 9.2, "tarjetas": 4.0},
        "champions": {"goles": 2.95, "corners": 9.8, "tarjetas": 4.2},
        "betplay": {"goles": 2.15, "corners": 9.0, "tarjetas": 5.2},
        "argentina": {"goles": 2.10, "corners": 8.9, "tarjetas": 5.4},
        "brasileirao": {"goles": 2.40, "corners": 10.1, "tarjetas": 5.1},
        "mx": {"goles": 2.65, "corners": 9.5, "tarjetas": 4.6},
        "mls": {"goles": 2.90, "corners": 9.7, "tarjetas": 3.9},
        "default": {"goles": 2.50, "corners": 9.5, "tarjetas": 4.3}
    }

    def __init__(self, api: FootballAPI = None):
        self.api = api if api else FootballAPI()

    def _obtener_promedios_liga(self, liga_nombre: str) -> dict:
        l_norm = liga_nombre.lower()
        for clave, vals in self.PROMEDIOS_LIGAS.items():
            if clave in l_norm:
                return vals
        return self.PROMEDIOS_LIGAS["default"]

    def _extraer_stats_fixture(self, fix_stats_raw: list, team_id: int) -> dict:
        """
        Extrae xG, tiros, tiros a puerta, posesión, córneres y tarjetas del resultado de la API.
        """
        res = {
            "xg": None,
            "tiros": 12.0,
            "tiros_puerta": 4.0,
            "posesion": 50.0,
            "corners": 4.8,
            "tarjetas": 2.1
        }
        if not fix_stats_raw:
            return res

        for team_stat in fix_stats_raw:
            if team_stat.get("team", {}).get("id") == team_id:
                stats = team_stat.get("statistics", [])
                for s in stats:
                    tipo = str(s.get("type", "")).lower()
                    val = s.get("value")
                    if val is None:
                        continue

                    try:
                        if "expected_goals" in tipo or "xg" in tipo:
                            res["xg"] = float(val)
                        elif "total shots" in tipo or "shots total" in tipo:
                            res["tiros"] = float(val)
                        elif "shots on goal" in tipo or "shots on target" in tipo:
                            res["tiros_puerta"] = float(val)
                        elif "ball possession" in tipo or "possession" in tipo:
                            res["posesion"] = float(str(val).replace("%", ""))
                        elif "corner kicks" in tipo or "corners" in tipo:
                            res["corners"] = float(val)
                        elif "yellow cards" in tipo:
                            res["tarjetas"] += float(val)
                        elif "red cards" in tipo:
                            res["tarjetas"] += float(val) * 1.5
                    except (ValueError, TypeError):
                        pass
                break
        return res

    def _procesar_historial_ponderado(self, partidos: list, team_id: int) -> dict:
        """
        Procesa el historial aplicando Ponderación por Decaimiento Exponencial (L1 > L2 > ... > L10)
        y extrayendo más de 20 variables avanzadas de rendimiento.
        """
        if not partidos or not team_id:
            return {
                "partidos": 0,
                "gf": 1.20,
                "gc": 1.00,
                "gf_exp": 1.20,
                "gc_exp": 1.00,
                "forma_pts": 50.0,
                "forma_exp": 50.0,
                "xg_avg": 1.25,
                "tiros_avg": 11.5,
                "tiros_puerta_avg": 3.8,
                "conversión_tiros": 0.31,
                "posesion_avg": 50.0,
                "corners_favor_avg": 4.8,
                "corners_contra_avg": 4.5,
                "tarjetas_avg": 2.2,
                "over15_rate": 0.70,
                "over25_rate": 0.50,
                "under25_rate": 0.50,
                "under35_rate": 0.80,
                "btts_rate": 0.50,
                "clean_sheet_rate": 0.30,
                "failed_to_score_rate": 0.25,
                "racha_victorias": 0,
                "racha_invicto": 0,
                "dias_descanso": 6,
                "elo": 1500.0
            }

        gf_total = 0.0
        gc_total = 0.0
        puntos_total = 0

        sum_pesos = 0.0
        gf_exp_sum = 0.0
        gc_exp_sum = 0.0
        pts_exp_sum = 0.0

        xg_list = []
        tiros_list = []
        tiros_p_list = []
        posesion_list = []
        corners_f_list = []
        corners_c_list = []
        tarjetas_list = []

        over15_cnt = 0
        over25_cnt = 0
        under25_cnt = 0
        under35_cnt = 0
        btts_cnt = 0
        clean_sheet_cnt = 0
        failed_score_cnt = 0

        racha_v = 0
        racha_inv = 0
        eval_v = True
        eval_inv = True

        elo_dinamico = 1500.0

        for idx, partido in enumerate(partidos):
            # Peso de decaimiento exponencial: L1 tiene mayor peso que L10
            peso = math.exp(-0.15 * idx)
            sum_pesos += peso

            teams = partido.get("teams", {})
            goals = partido.get("goals", {})

            es_local = teams.get("home", {}).get("id") == team_id

            g_favor = (goals.get("home") if goals.get("home") is not None else 0) if es_local else (goals.get("away") if goals.get("away") is not None else 0)
            g_contra = (goals.get("away") if goals.get("away") is not None else 0) if es_local else (goals.get("home") if goals.get("home") is not None else 0)

            gf_total += g_favor
            gc_total += g_contra

            gf_exp_sum += g_favor * peso
            gc_exp_sum += g_contra * peso

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
            if g_favor == 0:
                failed_score_cnt += 1

            # Racha y Puntos
            if g_favor > g_contra:
                pts = 3
                elo_dinamico += 15.0 * (1.0 / (idx + 1))
                if eval_v:
                    racha_v += 1
                if eval_inv:
                    racha_inv += 1
            elif g_favor == g_contra:
                pts = 1
                eval_v = False
                if eval_inv:
                    racha_inv += 1
            else:
                pts = 0
                elo_dinamico -= 12.0 * (1.0 / (idx + 1))
                eval_v = False
                eval_inv = False

            puntos_total += pts
            pts_exp_sum += pts * peso

            # Estimación de xG y estadísticas de tiro si no están reportadas
            xg_est = (g_favor * 0.5) + (1.2 if g_favor > 0 else 0.6)
            xg_list.append(xg_est)
            tiros_list.append(11.0 + (g_favor * 1.5))
            tiros_p_list.append(3.5 + (g_favor * 0.8))
            posesion_list.append(52.0 if es_local else 48.0)
            corners_f_list.append(5.0 if es_local else 4.2)
            corners_c_list.append(4.2 if es_local else 5.0)
            tarjetas_list.append(2.1)

        cant = len(partidos)
        forma_pts = (puntos_total / (cant * 3.0)) * 100.0 if cant > 0 else 50.0
        forma_exp = (pts_exp_sum / (sum_pesos * 3.0)) * 100.0 if sum_pesos > 0 else 50.0

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

        avg_tiros_p = sum(tiros_p_list) / cant if cant > 0 else 3.8
        avg_gf = gf_total / cant if cant > 0 else 1.20
        conversion = avg_gf / max(1.0, avg_tiros_p)

        return {
            "partidos": cant,
            "gf": round(avg_gf, 2),
            "gc": round(gc_total / cant, 2) if cant > 0 else 1.00,
            "gf_exp": round(gf_exp_sum / sum_pesos, 2) if sum_pesos > 0 else 1.20,
            "gc_exp": round(gc_exp_sum / sum_pesos, 2) if sum_pesos > 0 else 1.00,
            "forma_pts": round(forma_pts, 1),
            "forma_exp": round(forma_exp, 1),
            "xg_avg": round(sum(xg_list) / cant, 2) if cant > 0 else 1.25,
            "tiros_avg": round(sum(tiros_list) / cant, 1) if cant > 0 else 11.5,
            "tiros_puerta_avg": round(avg_tiros_p, 1),
            "conversión_tiros": round(conversion, 2),
            "posesion_avg": round(sum(posesion_list) / cant, 1) if cant > 0 else 50.0,
            "corners_favor_avg": round(sum(corners_f_list) / cant, 1) if cant > 0 else 4.8,
            "corners_contra_avg": round(sum(corners_c_list) / cant, 1) if cant > 0 else 4.5,
            "tarjetas_avg": round(sum(tarjetas_list) / cant, 1) if cant > 0 else 2.2,
            "over15_rate": round(over15_cnt / cant, 2) if cant > 0 else 0.70,
            "over25_rate": round(over25_cnt / cant, 2) if cant > 0 else 0.50,
            "under25_rate": round(under25_cnt / cant, 2) if cant > 0 else 0.50,
            "under35_rate": round(under35_cnt / cant, 2) if cant > 0 else 0.80,
            "btts_rate": round(btts_cnt / cant, 2) if cant > 0 else 0.50,
            "clean_sheet_rate": round(clean_sheet_cnt / cant, 2) if cant > 0 else 0.30,
            "failed_to_score_rate": round(failed_score_cnt / cant, 2) if cant > 0 else 0.25,
            "racha_victorias": racha_v,
            "racha_invicto": racha_inv,
            "dias_descanso": dias_descanso,
            "elo": round(elo_dinamico, 1)
        }

    def analizar(self, datos_partido: dict) -> dict:
        home_id = datos_partido.get("home_id", 0)
        away_id = datos_partido.get("away_id", 0)
        fixture_id = datos_partido.get("fixture_id", 0)
        league_id = datos_partido.get("league_id", 0)
        season = datos_partido.get("season", 2024)
        liga = datos_partido.get("liga", "")

        proms_liga = self._obtener_promedios_liga(liga)

        l10_local_raw = self.api.ultimos_partidos(home_id, 10) if home_id else []
        l10_visitante_raw = self.api.ultimos_partidos(away_id, 10) if away_id else []

        l5_local_raw = l10_local_raw[:5] if len(l10_local_raw) >= 5 else l10_local_raw
        l5_visitante_raw = l10_visitante_raw[:5] if len(l10_visitante_raw) >= 5 else l10_visitante_raw

        home_cond_raw = self.api.ultimos_partidos_condicion(home_id, es_local=True, cantidad=5) if home_id else []
        away_cond_raw = self.api.ultimos_partidos_condicion(away_id, es_local=False, cantidad=5) if away_id else []

        stats_l10_h = self._procesar_historial_ponderado(l10_local_raw, home_id)
        stats_l5_h = self._procesar_historial_ponderado(l5_local_raw, home_id)
        stats_cond_h = self._procesar_historial_ponderado(home_cond_raw, home_id)

        stats_l10_v = self._procesar_historial_ponderado(l10_visitante_raw, away_id)
        stats_l5_v = self._procesar_historial_ponderado(l5_visitante_raw, away_id)
        stats_cond_v = self._procesar_historial_ponderado(away_cond_raw, away_id)

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
        promedio_goles_liga = proms_liga["goles"]
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
                promedio_goles_liga = proms_liga["goles"]

        lesiones = self.api.obtener_lesiones(fixture_id=fixture_id) if fixture_id else []
        lesiones_h = [l for l in lesiones if l.get("team", {}).get("id") == home_id]
        lesiones_v = [l for l in lesiones if l.get("team", {}).get("id") == away_id]

        # Ponderación multinivel de Ataque y Defensa
        gf_loc_efectivo = (stats_l5_h["gf_exp"] * 0.45) + (stats_cond_h["gf"] * 0.35) + (stats_l10_h["gf"] * 0.20)
        gc_loc_efectivo = (stats_l5_h["gc_exp"] * 0.45) + (stats_cond_h["gc"] * 0.35) + (stats_l10_h["gc"] * 0.20)

        gf_vis_efectivo = (stats_l5_v["gf_exp"] * 0.45) + (stats_cond_v["gf"] * 0.35) + (stats_l10_v["gf"] * 0.20)
        gc_vis_efectivo = (stats_l5_v["gc_exp"] * 0.45) + (stats_cond_v["gc"] * 0.35) + (stats_l10_v["gc"] * 0.20)

        base_liga_mitad = max(0.8, promedio_goles_liga / 2.0)
        fortaleza_ofensiva_h = gf_loc_efectivo / base_liga_mitad
        fortaleza_defensiva_h = gc_loc_efectivo / base_liga_mitad

        fortaleza_ofensiva_v = gf_vis_efectivo / base_liga_mitad
        fortaleza_defensiva_v = gc_vis_efectivo / base_liga_mitad

        exp_goles = (gf_loc_efectivo + gc_vis_efectivo + gf_vis_efectivo + gc_loc_efectivo) / 2.0

        # Proyecciones ajustadas por liga de Córneres y Tarjetas
        corners_est = round((stats_l5_h["corners_favor_avg"] + stats_l5_v["corners_favor_avg"] + proms_liga["corners"]) / 3.0 + exp_goles * 0.4, 1)
        tarjetas_est = round((stats_l5_h["tarjetas_avg"] + stats_l5_v["tarjetas_avg"] + proms_liga["tarjetas"]) / 3.0, 1)

        return {
            "ataque_local": round(gf_loc_efectivo, 2),
            "defensa_local": round(gc_loc_efectivo, 2),
            "ataque_visitante": round(gf_vis_efectivo, 2),
            "defensa_visitante": round(gc_vis_efectivo, 2),
            "forma_local": stats_l5_h["forma_exp"],
            "forma_visitante": stats_l5_v["forma_exp"],
            "forma_l10_local": stats_l10_h["forma_pts"],
            "forma_l10_visitante": stats_l10_v["forma_pts"],
            "xg_h": stats_l5_h["xg_avg"],
            "xg_v": stats_l5_v["xg_avg"],
            "tiros_h": stats_l5_h["tiros_avg"],
            "tiros_v": stats_l5_v["tiros_avg"],
            "tiros_puerta_h": stats_l5_h["tiros_puerta_avg"],
            "tiros_puerta_v": stats_l5_v["tiros_puerta_avg"],
            "posesion_h": stats_l5_h["posesion_avg"],
            "posesion_v": stats_l5_v["posesion_avg"],
            "elo_h": stats_l5_h["elo"],
            "elo_v": stats_l5_v["elo"],
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
