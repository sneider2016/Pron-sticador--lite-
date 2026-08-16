from datetime import datetime
from api.football_api import FootballAPI
from analysis.analyzer import Analyzer
from analysis.probability import ProbabilityCalculator
from analysis.value_analyzer import ValueAnalyzer
from models.match import Match


class SALMEngine:

    def __init__(self):
        self.api = FootballAPI()
        self.analyzer = Analyzer(api=self.api)
        self.probability = ProbabilityCalculator()
        self.value = ValueAnalyzer()

    def evaluar_betplay(self, probabilidad: float, cuota: float) -> dict:
        return self.value.analizar(probabilidad, cuota)

    def ejecutar_analisis_completo(self, local: str, visitante: str, fecha: str, liga: str) -> Match:
        anio_partido = int(fecha.split("-")[0]) if fecha and "-" in fecha else datetime.now().year
        fix = self.api.buscar_partido_por_equipos(local, visitante, fecha)

        if fix and fix.get("fixture", {}).get("id", 0) == 0:
            loc_n = fix["teams"]["home"]["name"] if fix else local
            vis_n = fix["teams"]["away"]["name"] if fix else visitante
            return Match(
                fixture_id=0,
                liga=liga,
                fecha=fecha,
                local=loc_n,
                visitante=vis_n,
                market_ranking=[{"m": "🛑 FECHA INCORRECTA", "p": 0.0, "c": 999.0, "r": "Alto", "razon": "No hay partido oficial agendado."}],
                main_prediction="🛑 NO HAY PARTIDO PROGRAMADO",
                explanation=f"No se encontró partido oficial entre {loc_n} y {vis_n} para el {fecha}.",
                alerts=[f"🛑 ATENCIÓN: Verifique la fecha oficial en el calendario."]
            )

        h_id = fix["teams"]["home"]["id"] if fix else 0
        v_id = fix["teams"]["away"]["id"] if fix else 0
        loc_name = fix["teams"]["home"]["name"] if fix else local
        vis_name = fix["teams"]["away"]["name"] if fix else visitante
        referee_name = fix.get("referee_name", "") if fix else ""

        nombre_liga_oficial = fix.get("league", {}).get("name", "") if fix else ""
        liga_final = nombre_liga_oficial if nombre_liga_oficial and nombre_liga_oficial != "0" else liga

        datos_partido = {
            "home_id": h_id,
            "away_id": v_id,
            "home_name": loc_name,
            "away_name": vis_name,
            "fixture_id": fix["fixture"]["id"] if fix else 0,
            "league_id": fix["league"]["id"] if fix else 0,
            "season": anio_partido,
            "liga": liga_final,
            "referee_name": referee_name
        }

        analisis_raw = self.analyzer.analizar(datos_partido)
        alertas_finales = list(analisis_raw.get("alertas", []))

        probs = self.probability.calcular(
            ataque_local=analisis_raw["ataque_local"],
            defensa_local=analisis_raw["defensa_local"],
            ataque_visitante=analisis_raw["ataque_visitante"],
            defensa_visitante=analisis_raw["defensa_visitante"],
            forma_local=analisis_raw["forma_local"],
            forma_visitante=analisis_raw["forma_visitante"],
            elo_h=analisis_raw["elo_h"],
            elo_v=analisis_raw["elo_v"],
            descanso_h=analisis_raw["descanso_h"],
            descanso_v=analisis_raw["descanso_v"],
            home_adv=analisis_raw["home_adv"],
            es_eliminatoria=analisis_raw["es_eliminatoria"]
        )

        es_liga_cerrojo = "argentina" in liga_final.lower() or "betplay" in liga_final.lower()
        es_eliminatoria = analisis_raw["es_eliminatoria"]

        todos_mercados = []

        # 1. Doble Oportunidad (Exige >= 68% y diferencial de ELO a favor)
        if probs["doble_chance_1x"] >= 68.0 and (analisis_raw["elo_h"] >= analisis_raw["elo_v"] - 80):
            todos_mercados.append({
                "m": f"Gana o Empata {loc_name} (1X)",
                "p": probs["doble_chance_1x"],
                "r": "Bajo",
                "razon": f"Cobertura local sólida respaldada por ELO ({int(analisis_raw['elo_h'])} vs {int(analisis_raw['elo_v'])})."
            })
        if probs["doble_chance_x2"] >= 68.0 and (analisis_raw["elo_v"] >= analisis_raw["elo_h"] - 80):
            todos_mercados.append({
                "m": f"Gana o Empata {vis_name} (X2)",
                "p": probs["doble_chance_x2"],
                "r": "Bajo",
                "razon": f"Superioridad de jerarquía visitante ({int(analisis_raw['elo_v'])} ELO) que neutraliza la localía rival."
            })

        # 2. Draw No Bet (DNB - Para cuotas de valor 1.70 - 2.05)
        if probs["dnb_local"] >= 65.0:
            todos_mercados.append({
                "m": f"Gana {loc_name} Sin Empate (DNB)",
                "p": probs["dnb_local"],
                "r": "Bajo-Medio",
                "razon": "Dominio ofensivo local con seguro de reembolso ante empate."
            })
        if probs["dnb_visitante"] >= 65.0:
            todos_mercados.append({
                "m": f"Gana {vis_name} Sin Empate (DNB)",
                "p": probs["dnb_visitante"],
                "r": "Bajo-Medio",
                "razon": "Métricas superiores del visitante con seguro de reembolso ante empate."
            })

        # 3. Goles con Candado por Liga y Eliminatoria
        umbral_over15 = 78.0 if es_liga_cerrojo else 70.0
        if probs["over15"] >= umbral_over15:
            todos_mercados.append({
                "m": "Más de 1.5 Goles Totales",
                "p": probs["over15"],
                "r": "Bajo",
                "razon": f"Expectativa de {probs['exp_goles']:.2f} goles con volumen ofensivo confirmado."
            })

        # Under 3.5 PROHIBIDO en fases previas de Champions/Conference de alta volatilidad
        if probs["under35"] >= 72.0 and not es_eliminatoria:
            todos_mercados.append({
                "m": "Menos de 3.5 Goles Totales",
                "p": probs["under35"],
                "r": "Bajo",
                "razon": f"Partido de liga regular con baja densidad goleadora esperada ({probs['exp_goles']:.2f} goles)."
            })

        todos_mercados.sort(key=lambda x: x["p"], reverse=True)
        for cand in todos_mercados:
            cand["c"] = self.value.cuota_justa(cand["p"])

        if not todos_mercados:
            p_top = {"m": "🛑 NO APOSTAR (Riesgo / Sin Valor Claro)", "p": 0.0, "c": 999.0, "r": "Alto", "razon": "Ningún mercado superó los filtros de seguridad estricta."}
            s_top = p_top
            ranking_final = [p_top]
        elif len(todos_mercados) == 1:
            p_top = todos_mercados[0]
            s_top = {"m": "🛑 NINGUNO ADICIONAL", "p": 0.0, "c": 999.0, "r": "N/A", "razon": "Solo un mercado cumplió con la seguridad requerida."}
            ranking_final = [p_top, s_top]
        else:
            p_top = todos_mercados[0]
            s_top = todos_mercados[1]
            ranking_final = todos_mercados

        arg = (
            f"**1. Jerarquía ELO Real:** {loc_name} ({int(analisis_raw['elo_h'])}) vs {vis_name} ({int(analisis_raw['elo_v'])}).\n\n"
            f"**2. Expectativa Goleadora:** Gol Local: {probs['lambda_local']:.2f} | Gol Visita: {probs['lambda_visitante']:.2f} (Total: {probs['exp_goles']:.2f}).\n\n"
            f"**3. Contexto de Competición:** {liga_final} {'(Eliminatoria Directa - Alta Volatilidad)' if es_eliminatoria else '(Liga Regular)'}."
        )

        return Match(
            fixture_id=fix["fixture"]["id"] if fix else None,
            league_id=fix["league"]["id"] if fix else None,
            season=fix["league"]["season"] if fix else None,
            liga=liga_final,
            fecha=fecha,
            local=loc_name,
            visitante=vis_name,
            analyzed_markets=todos_mercados,
            market_ranking=ranking_final,
            main_prediction=p_top["m"],
            alternative_prediction=s_top["m"],
            estimated_probability=p_top["p"],
            fair_odds=p_top["c"],
            confidence=probs["confianza"],
            risk=p_top["r"],
            explanation=arg,
            alerts=alertas_finales
        )
