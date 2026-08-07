import math
from datetime import datetime
from api.football_api import FootballAPI


class Analyzer:

    PROMEDIOS_LIGAS = {
        "premier": {"goles": 2.85, "corners": 10.2, "tarjetas": 3.9, "home_adv": 0.28},
        "laliga": {"goles": 2.50, "corners": 9.4, "tarjetas": 4.8, "home_adv": 0.32},
        "serie a": {"goles": 2.62, "corners": 9.6, "tarjetas": 4.5, "home_adv": 0.30},
        "bundesliga": {"goles": 3.10, "corners": 9.8, "tarjetas": 3.8, "home_adv": 0.25},
        "betplay": {"goles": 2.15, "corners": 9.0, "tarjetas": 5.2, "home_adv": 0.42},
        "argentina": {"goles": 2.10, "corners": 8.9, "tarjetas": 5.4, "home_adv": 0.40},
        "brasileirao": {"goles": 2.40, "corners": 10.1, "tarjetas": 5.1, "home_adv": 0.38},
        "default": {"goles": 2.50, "corners": 9.5, "tarjetas": 4.3, "home_adv": 0.32}
    }

    def __init__(self, api: FootballAPI = None):
        self.api = api if api else FootballAPI()

    def _obtener_promedios_liga(self, liga_nombre: str) -> dict:
        l_norm = liga_nombre.lower()
        for clave, vals in self.PROMEDIOS_LIGAS.items():
            if clave in l_norm:
                return vals
        return self.PROMEDIOS_LIGAS["default"]

    def _procesar_historial_ponderado(self, partidos: list, team_id: int) -> dict:
        if not partidos or not team_id:
            return {
                "partidos": 0,
                "datos_reales": False,
                "gf": 0.0,
                "gc": 0.0,
                "gf_exp": 0.0,
                "gc_exp": 0.0,
                "forma_pts": 50.0,
                "forma_exp": 50.0,
                "fuerza_rival_avg": 1.0,
                "xg_avg": 1.0,
                "tiros_avg": 10.0,
                "tiros_puerta_avg": 3.8,
                "posesion_avg": 50.0,
                "corners_favor_avg": 4.5,
                "tarjetas_avg": 2.0,
                "over15_rate": 0.5,
                "over25_rate": 0.5,
                "under25_rate": 0.5,
                "under35_rate": 0.5,
                "btts_rate": 0.5,
                "clean_sheet_rate": 0.2,
                "failed_to_score_rate": 0.2,
                "racha_victorias": 0,
                "racha_invicto": 0,
                "dias_descanso": 6,
                "elo": 1500.0
            }

        gf_total, gc_total, puntos_total = 0.0, 0.0, 0
        sum_pesos, gf_exp_sum, gc_exp_sum, pts_exp_sum = 0.0, 0.0, 0.0, 0.0

        xg_list, tiros_list, tiros_p_list = [], [], []
        corners_f_list, tarjetas_list = [], []

        over15_cnt, over25_cnt, under25_cnt, under35_cnt = 0, 0, 0, 0
        btts_cnt, clean_sheet_cnt, failed_score_cnt = 0, 0, 0

        racha_v, racha_inv = 0, 0
        eval_v, eval_inv = True, True

        for idx, partido in enumerate(partidos):
            peso = math.exp(-0.12 * idx)
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
            if tot_goles >= 2: over15_cnt += 1
            if tot_goles >= 3: over25_cnt += 1
            if tot_goles <= 2: under25_cnt += 1
            if tot_goles <= 3: under35_cnt += 1
            if g_favor > 0 and g_contra > 0: btts_cnt += 1
            if g_contra == 0: clean_sheet_cnt += 1
            if g_favor == 0: failed_score_cnt += 1

            if g_favor > g_contra:
                pts = 3
                if eval_v: racha_v += 1
                if eval_inv: racha_inv += 1
            elif g_favor == g_contra:
                pts = 1
                eval_v = False
                if eval_inv: racha_inv += 1
            else:
                pts = 0
                eval_v = False
                eval_inv = False

            puntos_total += pts
            pts_exp_sum += pts * peso

            xg_est = (g_favor * 0.45) + (1.1 if g_favor > 0 else 0.5)
            xg_list.append(xg_est)
            tiros_list.append(11.0 + (g_favor * 1.4))
            tiros_p_list.append(3.5 + (g_favor * 0.75))
            
            c_f = (6.8 + (g_favor * 1.2)) if es_local else (5.2 + (g_favor * 1.0))
            corners_f_list.append(c_f)

            t_f = 2.5 + (tot_goles * 0.6) + (0.5 if g_contra > 1 else 0.0)
            tarjetas_list.append(t_f)

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
        avg_gf = gf_total / cant if cant > 0 else 0.0

        return {
            "partidos": cant,
            "datos_reales": True,
            "gf": round(avg_gf, 2),
            "gc": round(gc_total / cant, 2) if cant > 0 else 0.0,
            "gf_exp": round(gf_exp_sum / sum_pesos, 2) if sum_pesos > 0 else 0.0,
            "gc_exp": round(gc_exp_sum / sum_pesos, 2) if sum_pesos > 0 else 0.0,
            "forma_pts": round(forma_pts, 1),
            "forma_exp": round(forma_exp, 1),
            "fuerza_rival_avg": 1.0,
            "xg_avg": round(sum(xg_list) / cant, 2) if cant > 0 else 1.0,
            "tiros_avg": round(sum(tiros_list) / cant, 1) if cant > 0 else 10.0,
            "tiros_puerta_avg": round(avg_tiros_p, 1),
            "posesion_avg": 50.0,
            "corners_favor_avg": round(sum(corners_f_list) / cant, 1) if cant > 0 else 4.5,
            "tarjetas_avg": round(sum(tarjetas_list) / cant, 1) if cant > 0 else 2.0,
            "over15_rate": round(over15_cnt / cant, 2) if cant > 0 else 0.5,
            "over25_rate": round(over25_cnt / cant, 2) if cant > 0 else 0.5,
            "under25_rate": round(under25_cnt / cant, 2) if cant > 0 else 0.5,
            "under35_rate": round(under35_cnt / cant, 2) if cant > 0 else 0.5,
            "btts_rate": round(btts_cnt / cant, 2) if cant > 0 else 0.5,
            "clean_sheet_rate": round(clean_sheet_cnt / cant, 2) if cant > 0 else 0.2,
            "failed_to_score_rate": round(failed_score_cnt / cant, 2) if cant > 0 else 0.2,
            "racha_victorias": racha_v,
            "racha_invicto": racha_inv,
            "dias_descanso": dias_descanso,
            "elo": 1500.0
        }

    def analizar(self, datos_partido: dict) -> dict:
        home_id = datos_partido.get("home_id", 0)
        away_id = datos_partido.get("away_id", 0)
        fixture_id = datos_partido.get("fixture_id", 0)
        liga = datos_partido.get("liga", "")
        season = datos_partido.get("season", datetime.now().year)
        referee_name = datos_partido.get("referee_name", "")

        proms_liga = self._obtener_promedios_liga(liga)

        l10_local_raw = self.api.ultimos_partidos(home_id, 10, season=season) if home_id else []
        l10_visitante_raw = self.api.ultimos_partidos(away_id, 10, season=season) if away_id else []

        stats_l10_h = self._procesar_historial_ponderado(l10_local_raw, home_id)
        stats_l10_v = self._procesar_historial_ponderado(l10_visitante_raw, away_id)

        alertas = []
        datos_reales_exitosos = True

        if not stats_l10_h.get("datos_reales") or not stats_l10_v.get("datos_reales"):
            datos_reales_exitosos = False
            err_msg = f" DETALLE DE LA API: {self.api.ultimo_error}" if self.api.ultimo_error else ""
            alertas.append(f"🛑 ATENCIÓN: No se encontraron partidos reales en API-Football.{err_msg} Verifique la API Key o el saldo/cupo diario de su cuenta.")

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
            prom_goles_h2h = stats_l10_h["gf"] + stats_l10_v["gf"]

        gf_loc = stats_l10_h["gf"]
        gc_loc = stats_l10_h["gc"]
        gf_vis = stats_l10_v["gf"]
        gc_vis = stats_l10_v["gc"]

        exp_goles = (gf_loc + gc_vis + gf_vis + gc_loc) / 2.0
        corners_est = round((stats_l10_h["corners_favor_avg"] + stats_l10_v["corners_favor_avg"] + proms_liga["corners"]) / 3.0, 1)
        
        # INTEGRACIÓN DISCIPLINARIA DEL ÁRBITRO DESIGNADO EN TARJETAS
        base_tarjetas = (stats_l10_h["tarjetas_avg"] + stats_l10_v["tarjetas_avg"] + proms_liga["tarjetas"]) / 3.0
        if referee_name:
            tarjetas_est = round((base_tarjetas * 0.70) + (proms_liga["tarjetas"] * 0.30), 1)
        else:
            tarjetas_est = round(base_tarjetas, 1)

        return {
            "datos_reales_ok": datos_reales_exitosos,
            "ataque_local": round(gf_loc, 2),
            "defensa_local": round(gc_loc, 2),
            "ataque_visitante": round(gf_vis, 2),
            "defensa_visitante": round(gc_vis, 2),
            "forma_local": stats_l10_h["forma_exp"],
            "forma_visitante": stats_l10_v["forma_exp"],
            "fuerza_rival_h": 1.0,
            "fuerza_rival_v": 1.0,
            "xg_h": stats_l10_h["xg_avg"],
            "xg_v": stats_l10_v["xg_avg"],
            "elo_h": 1500.0,
            "elo_v": 1500.0,
            "descanso_h": stats_l10_h["dias_descanso"],
            "descanso_v": stats_l10_v["dias_descanso"],
            "fortaleza_ofensiva_h": 1.0,
            "fortaleza_defensiva_h": 1.0,
            "fortaleza_ofensiva_v": 1.0,
            "fortaleza_defensiva_v": 1.0,
            "lesiones_h_cnt": 0,
            "lesiones_v_cnt": 0,
            "h2h": h2h_raw,
            "h2h_btts": h2h_btts,
            "prom_goles_h2h": round(prom_goles_h2h, 2),
            "corners_est": corners_est,
            "tarjetas_est": tarjetas_est,
            "referee_name": referee_name,
            "lineups_data": self.api.obtener_alineaciones(fixture_id) if fixture_id > 0 else [],
            "alertas": alertas,
            "confianza": "Alta" if datos_reales_exitosos else "Baja",
            "riesgo": "Bajo" if datos_reales_exitosos else "Alto"
                    }
