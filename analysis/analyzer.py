import math
from datetime import datetime
from api.football_api import FootballAPI


class Analyzer:

    PROMEDIOS_LIGAS = {
        "premier": {"goles": 2.85, "corners": 10.2, "tarjetas": 3.9, "home_adv": 0.28, "elo_base": 1750},
        "laliga": {"goles": 2.50, "corners": 9.4, "tarjetas": 4.8, "home_adv": 0.32, "elo_base": 1720},
        "serie a": {"goles": 2.62, "corners": 9.6, "tarjetas": 4.5, "home_adv": 0.30, "elo_base": 1700},
        "bundesliga": {"goles": 3.10, "corners": 9.8, "tarjetas": 3.8, "home_adv": 0.25, "elo_base": 1710},
        "eredivisie": {"goles": 3.15, "corners": 10.5, "tarjetas": 3.4, "home_adv": 0.25, "elo_base": 1550},
        "jupiler": {"goles": 2.80, "corners": 9.8, "tarjetas": 4.2, "home_adv": 0.28, "elo_base": 1520},
        "betplay": {"goles": 2.15, "corners": 9.0, "tarjetas": 5.2, "home_adv": 0.42, "elo_base": 1420},
        "argentina": {"goles": 2.05, "corners": 8.8, "tarjetas": 5.4, "home_adv": 0.40, "elo_base": 1500},
        "brasileirao": {"goles": 2.40, "corners": 10.1, "tarjetas": 5.1, "home_adv": 0.38, "elo_base": 1600},
        "mls": {"goles": 2.95, "corners": 9.7, "tarjetas": 3.8, "home_adv": 0.30, "elo_base": 1450},
        "leagues cup": {"goles": 2.90, "corners": 9.5, "tarjetas": 4.1, "home_adv": 0.15, "elo_base": 1460},
        "champions": {"goles": 2.95, "corners": 9.8, "tarjetas": 4.2, "home_adv": 0.20, "elo_base": 1800},
        "europa": {"goles": 2.85, "corners": 9.6, "tarjetas": 4.3, "home_adv": 0.22, "elo_base": 1650},
        "conference": {"goles": 2.80, "corners": 9.4, "tarjetas": 4.4, "home_adv": 0.25, "elo_base": 1480},
        "default": {"goles": 2.50, "corners": 9.5, "tarjetas": 4.3, "home_adv": 0.30, "elo_base": 1500}
    }

    # Jerarquías especiales de clubes para evitar trampas tipo Excelsior vs PSV
    ELOS_CLUBES_ELITE = {
        "psv": 1820, "ajax": 1740, "feyenoord": 1760, "excelsior": 1410,
        "real madrid": 1950, "barcelona": 1920, "sevilla": 1680, "rayo vallecano": 1590,
        "manchester city": 1960, "liverpool": 1930, "arsenal": 1910,
        "bayern munich": 1940, "bayer leverkusen": 1860, "dortmund": 1810,
        "paris saint germain": 1890, "aston villa": 1780,
        "river plate": 1680, "boca juniors": 1650, "racing club": 1620, "banfield": 1480,
        "san lorenzo": 1540, "union santa fe": 1490, "platense": 1460, "independiente": 1550,
        "flamengo": 1720, "palmeiras": 1730, "cruzeiro": 1580, "sao paulo": 1630, "gremio": 1600
    }

    def __init__(self, api: FootballAPI = None):
        self.api = api if api else FootballAPI()

    def _obtener_promedios_liga(self, liga_nombre: str) -> dict:
        l_norm = liga_nombre.lower()
        for clave, vals in self.PROMEDIOS_LIGAS.items():
            if clave in l_norm:
                return vals
        return self.PROMEDIOS_LIGAS["default"]

    def _estimar_elo_equipo(self, nombre_equipo: str, liga_nombre: str, stats_recientes: dict) -> float:
        norm_t = nombre_equipo.lower().strip()
        for club, elo in self.ELOS_CLUBES_ELITE.items():
            if club in norm_t:
                return float(elo)

        proms = self._obtener_promedios_liga(liga_nombre)
        elo_base = proms.get("elo_base", 1500.0)

        # Ajuste dinámico según forma reciente y diferencial de gol
        forma_pts = stats_recientes.get("forma_pts", 50.0)
        dg = stats_recientes.get("gf", 1.0) - stats_recientes.get("gc", 1.0)
        elo_ajustado = elo_base + ((forma_pts - 50.0) * 2.5) + (dg * 30.0)
        return round(max(1200.0, min(2050.0, elo_ajustado)), 1)

    def _procesar_historial_ponderado(self, partidos: list, team_id: int) -> dict:
        if not partidos or not team_id:
            return {
                "partidos": 0,
                "datos_reales": False,
                "gf": 0.0,
                "gc": 0.0,
                "forma_pts": 50.0,
                "forma_exp": 50.0,
                "volumen_ofensivo_real": 3.5,
                "under25_rate": 0.5,
                "over15_rate": 0.5,
                "btts_rate": 0.5,
                "dias_descanso": 6
            }

        gf_total, gc_total, puntos_total = 0.0, 0.0, 0
        sum_pesos, gf_exp_sum, gc_exp_sum, pts_exp_sum = 0.0, 0.0, 0.0, 0.0
        over15_cnt, under25_cnt, btts_cnt = 0, 0, 0

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

            tot_g = g_favor + g_contra
            if tot_g >= 2: over15_cnt += 1
            if tot_g <= 2: under25_cnt += 1
            if g_favor > 0 and g_contra > 0: btts_cnt += 1

            if g_favor > g_contra:
                pts = 3
            elif g_favor == g_contra:
                pts = 1
            else:
                pts = 0

            puntos_total += pts
            pts_exp_sum += pts * peso

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

        avg_gf = gf_total / cant if cant > 0 else 0.0
        avg_gc = gc_total / cant if cant > 0 else 0.0

        return {
            "partidos": cant,
            "datos_reales": True,
            "gf": round(avg_gf, 2),
            "gc": round(avg_gc, 2),
            "gf_exp": round(gf_exp_sum / sum_pesos, 2) if sum_pesos > 0 else 0.0,
            "gc_exp": round(gc_exp_sum / sum_pesos, 2) if sum_pesos > 0 else 0.0,
            "forma_pts": round(forma_pts, 1),
            "forma_exp": round(forma_exp, 1),
            "over15_rate": round(over15_cnt / cant, 2) if cant > 0 else 0.5,
            "under25_rate": round(under25_cnt / cant, 2) if cant > 0 else 0.5,
            "btts_rate": round(btts_cnt / cant, 2) if cant > 0 else 0.5,
            "dias_descanso": dias_descanso
        }

    def analizar(self, datos_partido: dict) -> dict:
        home_id = datos_partido.get("home_id", 0)
        away_id = datos_partido.get("away_id", 0)
        fixture_id = datos_partido.get("fixture_id", 0)
        home_name = datos_partido.get("home_name", "")
        away_name = datos_partido.get("away_name", "")
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
            alertas.append("🛑 ATENCIÓN: Historial incompleto en API-Football. Análisis con datos base.")

        # CÁLCULO ELO DINÁMICO REAL
        elo_h = self._estimar_elo_equipo(home_name, liga, stats_l10_h)
        elo_v = self._estimar_elo_equipo(away_name, liga, stats_l10_v)

        h2h_raw = self.api.head_to_head(home_id, away_id, 8) if (home_id and away_id) else []
        h2h_goles_total = 0.0
        if h2h_raw:
            for m in h2h_raw:
                gh = m.get("goals", {}).get("home") or 0
                ga = m.get("goals", {}).get("away") or 0
                h2h_goles_total += (gh + ga)
            prom_goles_h2h = h2h_goles_total / len(h2h_raw)
        else:
            prom_goles_h2h = stats_l10_h["gf"] + stats_l10_v["gf"]

        corners_est = round(proms_liga["corners"], 1)
        tarjetas_est = round(proms_liga["tarjetas"] + (0.5 if referee_name else 0.0), 1)

        # DETECTOR DE ELIMINATORIA / VOLATILIDAD
        es_eliminatoria = any(k in liga.lower() for k in ["qualif", "champions", "conference", "europa", "playoff", "cup"])

        return {
            "datos_reales_ok": datos_reales_exitosos,
            "ataque_local": stats_l10_h["gf_exp"],
            "defensa_local": stats_l10_h["gc_exp"],
            "ataque_visitante": stats_l10_v["gf_exp"],
            "defensa_visitante": stats_l10_v["gc_exp"],
            "forma_local": stats_l10_h["forma_exp"],
            "forma_visitante": stats_l10_v["forma_exp"],
            "elo_h": elo_h,
            "elo_v": elo_v,
            "descanso_h": stats_l10_h["dias_descanso"],
            "descanso_v": stats_l10_v["dias_descanso"],
            "prom_goles_h2h": round(prom_goles_h2h, 2),
            "corners_est": corners_est,
            "tarjetas_est": tarjetas_est,
            "referee_name": referee_name,
            "es_eliminatoria": es_eliminatoria,
            "home_adv": proms_liga["home_adv"],
            "lineups_data": self.api.obtener_alineaciones(fixture_id) if fixture_id > 0 else [],
            "alertas": alertas,
            "confianza": "Alta" if datos_reales_exitosos else "Baja",
            "riesgo": "Bajo" if datos_reales_exitosos else "Alto"
                    }
