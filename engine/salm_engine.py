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

    def analizar(self, datos_partido: dict) -> list:
        analisis = self.analyzer.analizar(datos_partido)
        probs = self.probability.calcular(
            ataque_local=analisis["ataque_local"],
            defensa_local=analisis["defensa_local"],
            ataque_visitante=analisis["ataque_visitante"],
            defensa_visitante=analisis["defensa_visitante"],
            forma_local=analisis["forma_local"],
            forma_visitante=analisis["forma_visitante"]
        )

        mercados_mapeo = [
            ("Más de 1.5 Goles", probs["over15"]),
            ("Menos de 2.5 Goles", probs["under25"]),
            ("Ambos Anotan", probs["btts"]),
            ("Doble Oportunidad 1X", probs["doble_chance_1x"]),
            ("Empate No Válido Local", probs["dnb_local"]),
            ("Empate No Válido Visitante", probs["dnb_visitante"]),
        ]

        ranking = []
        for mercado_nombre, prob_val in mercados_mapeo:
            c_justa = self.value.cuota_justa(prob_val)
            ranking.append({
                "mercado": mercado_nombre,
                "probabilidad": prob_val,
                "confianza": analisis["confianza"],
                "riesgo": analisis["riesgo"],
                "cuota_justa": c_justa
            })

        ranking.sort(key=lambda x: x["p"], reverse=True)
        return ranking

    def evaluar_betplay(self, probabilidad: float, cuota: float) -> dict:
        return self.value.analizar(probabilidad, cuota)

    def ejecutar_analisis_completo(self, local: str, visitante: str, fecha: str, liga: str) -> Match:
        fix = self.api.buscar_partido_por_equipos(local, visitante, fecha)

        h_id = fix["teams"]["home"]["id"] if fix else 0
        v_id = fix["teams"]["away"]["id"] if fix else 0

        loc_name = fix["teams"]["home"]["name"] if fix else local
        vis_name = fix["teams"]["away"]["name"] if fix else visitante

        datos_partido = {
            "home_id": h_id,
            "away_id": v_id,
            "fixture_id": fix["fixture"]["id"] if fix else 0,
            "league_id": fix["league"]["id"] if fix else 0,
            "season": 2026,
            "liga": liga
        }

        analisis_raw = self.analyzer.analizar(datos_partido)
        alertas_finales = list(analisis_raw.get("alertas", []))

        # SI LA API NO OBTUVO PARTIDOS REALES, CANCELA EL PRONÓSTICO FALSO
        if not analisis_raw.get("datos_reales_ok", False):
            return Match(
                fixture_id=0,
                liga=liga,
                fecha=fecha,
                local=loc_name,
                visitante=vis_name,
                market_ranking=[{
                    "m": "🛑 DATOS INSUFICIENTES DE API",
                    "p": 0.0,
                    "c": 999.0,
                    "r": "Alto",
                    "razon": "No se encontraron partidos reales en API-Football."
                }],
                main_prediction="🛑 PRONÓSTICO SUSPENDIDO POR FALTA DE DATOS REALES",
                alternative_prediction="Ajuste el nombre del equipo o revise el saldo/cupo de su API Key.",
                explanation="**Atención:** No fue posible obtener el historial de los equipos desde API-Football. La aplicación se niega a calcular un pronóstico a ciegas con datos inventados.",
                alerts=alertas_finales
            )

        probs = self.probability.calcular(
            ataque_local=analisis_raw["ataque_local"],
            defensa_local=analisis_raw["defensa_local"],
            ataque_visitante=analisis_raw["ataque_visitante"],
            defensa_visitante=analisis_raw["defensa_visitante"],
            forma_local=analisis_raw["forma_local"],
            forma_visitante=analisis_raw["forma_visitante"]
        )

        pf_h = analisis_raw["ataque_local"]
        pc_h = analisis_raw["defensa_local"]
        pf_v = analisis_raw["ataque_visitante"]
        pc_v = analisis_raw["defensa_visitante"]

        l_h = probs["lambda_local"]
        l_v = probs["lambda_visitante"]
        exp_g = probs["exp_goles"]
        prom_h2h = analisis_raw["prom_goles_h2h"]
        corners_est = analisis_raw["corners_est"]
        tarjetas_est = analisis_raw["tarjetas_est"]

        todos_mercados = []

        # 1. Doble Chance
        if probs["doble_chance_1x"] >= 60.0:
            todos_mercados.append({
                "m": f"Gana o Empata {loc_name} (Doble Chance 1X)",
                "p": probs["doble_chance_1x"],
                "r": "Bajo" if probs["doble_chance_1x"] >= 78.0 else "Bajo-Medio",
                "razon": f"Sólida cobertura local con {probs['doble_chance_1x']}% de probabilidad real."
            })
        if probs["doble_chance_x2"] >= 60.0:
            todos_mercados.append({
                "m": f"Gana o Empata {vis_name} (Doble Chance X2)",
                "p": probs["doble_chance_x2"],
                "r": "Bajo" if probs["doble_chance_x2"] >= 78.0 else "Bajo-Medio",
                "razon": f"Rendimiento visitante con {probs['doble_chance_x2']}% de cobertura victoria/empate."
            })

        # 2. Draw No Bet (DNB)
        if probs["dnb_local"] >= 58.0:
            todos_mercados.append({
                "m": f"Gana {loc_name} Sin Empate (DNB)",
                "p": probs["dnb_local"],
                "r": "Bajo" if probs["dnb_local"] >= 72.0 else "Bajo-Medio",
                "razon": f"Dominio local superior con {probs['dnb_local']}% DNB."
            })
        if probs["dnb_visitante"] >= 58.0:
            todos_mercados.append({
                "m": f"Gana {vis_name} Sin Empate (DNB)",
                "p": probs["dnb_visitante"],
                "r": "Bajo-Medio",
                "razon": f"Métricas de la visita ({pf_v:.1f} GF/juego) con {probs['dnb_visitante']}% DNB."
            })

        # 3. Goles
        if probs["over15"] >= 68.0:
            todos_mercados.append({
                "m": "Más de 1.5 Goles Totales en el Partido",
                "p": probs["over15"],
                "r": "Bajo",
                "razon": f"Expectativa Poisson de {exp_g:.2f} goles esperados ({probs['over15']}% de probabilidad)."
            })
        if probs["under25"] >= 55.0:
            todos_mercados.append({
                "m": "Menos de 2.5 Goles Totales (Under 2.5)",
                "p": probs["under25"],
                "r": "Bajo-Medio",
                "razon": f"Baja expectativa de gol ({exp_g:.2f}) y ritmo defensivo."
            })
        if probs["under35"] >= 72.0:
            todos_mercados.append({
                "m": "Menos de 3.5 Goles Totales",
                "p": probs["under35"],
                "r": "Bajo",
                "razon": f"Margen amplio de seguridad con {probs['under35']}% de probabilidad real."
            })

        # 4. Ambos Anotan (BTTS)
        if probs["btts"] >= 52.0:
            todos_mercados.append({
                "m": "Ambos Equipos Anotan (Sí)",
                "p": probs["btts"],
                "r": "Bajo-Medio",
                "razon": f"Conversión en ambos frentes con índice BTTS del {probs['btts']}%."
            })

        todos_mercados.sort(key=lambda x: x["p"], reverse=True)

        for cand in todos_mercados:
            cand["c"] = self.value.cuota_justa(cand["p"])

        p_top = todos_mercados[0] if todos_mercados else {
            "m": "Menos de 3.5 Goles Totales", "p": probs["under35"], "c": 1.30, "r": "Bajo", "razon": "Ritmo conservador proyectado."
        }
        
        s_top = todos_mercados[1] if len(todos_mercados) > 1 and todos_mercados[1]["m"] != p_top["m"] else (todos_mercados[2] if len(todos_mercados) > 2 else p_top)

        arg = (
            f"**1. Rendimiento Real API:** {loc_name} ({pf_h:.2f} GF / {pc_h:.2f} GC) vs {vis_name} ({pf_v:.2f} GF / {pc_v:.2f} GC).\n\n"
            f"**2. Proyección Poisson Bivariada:** Gol Local: {l_h:.2f} | Gol Visita: {l_v:.2f} (Total: {exp_g:.2f} goles).\n\n"
            f"**3. Contexto Táctico & H2H:** Promedio H2H {prom_h2h:.1f} goles | Descanso: {analisis_raw['descanso_h']}d vs {analisis_raw['descanso_v']}d.\n\n"
            f"**4. Dictamen Multimercado Exclusivo:** {p_top['razon']}"
        )

        return Match(
            fixture_id=fix["fixture"]["id"] if fix else None,
            league_id=fix["league"]["id"] if fix else None,
            season=fix["league"]["season"] if fix else None,
            liga=liga,
            fecha=fecha,
            local=loc_name,
            visitante=vis_name,
            h2h=analisis_raw["h2h"],
            analyzed_markets=todos_mercados,
            market_ranking=todos_mercados,
            main_prediction=p_top["m"],
            alternative_prediction=s_top["m"],
            estimated_probability=p_top["p"],
            fair_odds=p_top["c"],
            confidence=probs["confianza"],
            risk=p_top["r"],
            explanation=arg,
            alerts=alertas_finales
        )
