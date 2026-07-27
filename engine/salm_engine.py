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
        """
        Análisis rápido por lote de mercados.
        """
        analisis = self.analyzer.analizar(datos_partido)
        probs = self.probability.calcular(
            ataque_local=analisis["ataque_local"],
            defensa_local=analisis["defensa_local"],
            ataque_visitante=analisis["ataque_visitante"],
            defensa_visitante=analisis["defensa_visitante"],
            forma_local=analisis["forma_local"],
            forma_visitante=analisis["forma_visitante"],
            descanso_h=analisis["descanso_h"],
            descanso_v=analisis["descanso_v"],
            lesiones_h=analisis["lesiones_h_cnt"],
            lesiones_v=analisis["lesiones_v_cnt"],
            fortaleza_off_h=analisis["fortaleza_ofensiva_h"],
            fortaleza_def_h=analisis["fortaleza_defensiva_h"],
            fortaleza_off_v=analisis["fortaleza_ofensiva_v"],
            fortaleza_def_v=analisis["fortaleza_defensiva_v"],
            elo_h=analisis["elo_h"],
            elo_v=analisis["elo_v"],
            xg_h=analisis["xg_h"],
            xg_v=analisis["xg_v"],
            fuerza_rival_h=analisis["fuerza_rival_h"],
            fuerza_rival_v=analisis["fuerza_rival_v"]
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

        ranking.sort(key=lambda x: x["probabilidad"], reverse=True)
        return ranking

    def evaluar_betplay(self, probabilidad: float, cuota: float) -> dict:
        return self.value.analizar(probabilidad, cuota)

    def ejecutar_analisis_completo(self, local: str, visitante: str, fecha: str, liga: str) -> Match:
        """
        Ejecuta la fusión completa del Modelo Poisson-Dixon-Coles + Monte Carlo (IA SALM).
        """
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
            "season": fix["league"]["season"] if fix else 2024,
            "liga": liga
        }

        analisis_raw = self.analyzer.analizar(datos_partido)
        probs = self.probability.calcular(
            ataque_local=analisis_raw["ataque_local"],
            defensa_local=analisis_raw["defensa_local"],
            ataque_visitante=analisis_raw["ataque_visitante"],
            defensa_visitante=analisis_raw["defensa_visitante"],
            forma_local=analisis_raw["forma_local"],
            forma_visitante=analisis_raw["forma_visitante"],
            descanso_h=analisis_raw["descanso_h"],
            descanso_v=analisis_raw["descanso_v"],
            lesiones_h=analisis_raw["lesiones_h_cnt"],
            lesiones_v=analisis_raw["lesiones_v_cnt"],
            fortaleza_off_h=analisis_raw["fortaleza_ofensiva_h"],
            fortaleza_def_h=analisis_raw["fortaleza_defensiva_h"],
            fortaleza_off_v=analisis_raw["fortaleza_ofensiva_v"],
            fortaleza_def_v=analisis_raw["fortaleza_defensiva_v"],
            elo_h=analisis_raw["elo_h"],
            elo_v=analisis_raw["elo_v"],
            xg_h=analisis_raw["xg_h"],
            xg_v=analisis_raw["xg_v"],
            fuerza_rival_h=analisis_raw["fuerza_rival_h"],
            fuerza_rival_v=analisis_raw["fuerza_rival_v"]
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

        candidatos = []

        if corners_est >= 9.5:
            candidatos.append({
                "m": "Más de 7.5 Tiros de Esquina (Córneres Totales)",
                "p": 84.0,
                "r": "Bajo",
                "razon": f"Proyección ofensiva combinada de {corners_est:.1f} córneres/juego."
            })

        if tarjetas_est >= 4.5:
            candidatos.append({
                "m": "Más de 3.5 Tarjetas Totales en el Partido",
                "p": 82.0,
                "r": "Bajo",
                "razon": f"Fricción táctica estimada en {liga} (promedio de {tarjetas_est} tarjetas)."
            })

        if probs["btts"] >= 58.0 and analisis_raw["h2h_btts"] >= 3:
            candidatos.append({
                "m": "Ambos Equipos Anotan (Sí)",
                "p": probs["btts"],
                "r": "Bajo-Medio",
                "razon": f"Ambos anotaron en {analisis_raw['h2h_btts']} H2H recientes e índice BTTS de {probs['btts']}%. "
            })

        if exp_g <= 2.10 and prom_h2h <= 2.2:
            candidatos.append({
                "m": "Menos de 2.5 Goles Totales (Under 2.5)",
                "p": probs["under25"],
                "r": "Bajo",
                "razon": f"Expectativa baja en Monte Carlo ({exp_g:.2f} goles) y bloques defensivos compactos."
            })

        if exp_g >= 2.40 and probs["over15"] >= 75.0:
            candidatos.append({
                "m": "Más de 1.5 Goles Totales en el Partido",
                "p": probs["over15"],
                "r": "Bajo",
                "razon": f"Proyección híbrida de {exp_g:.2f} goles con tasa Over 1.5 del {probs['over15']}%."
            })

        if probs["local"] >= 52.0:
            candidatos.append({
                "m": f"Gana {loc_name} Sin Empate (Empate No Válido)",
                "p": probs["dnb_local"],
                "r": "Bajo",
                "razon": f"Dominio local con {probs['local']}% de probabilidad directa y ventaja ELO."
            })
        elif probs["visitante"] >= 42.0:
            candidatos.append({
                "m": f"Gana {vis_name} Sin Empate (Empate No Válido)",
                "p": probs["dnb_visitante"],
                "r": "Bajo-Medio",
                "razon": f"Métricas superiores del visitante ({pf_v:.1f} GF/juego) y ajuste por fuerza rival."
            })

        if not candidatos:
            candidatos.append({
                "m": f"Gana o Empata {loc_name} (Doble Oportunidad 1X)",
                "p": probs["doble_chance_1x"],
                "r": "Bajo",
                "razon": "Ventaja de localía y cobertura frente a empate."
            })
            candidatos.append({
                "m": "Menos de 3.5 Goles Totales",
                "p": probs["under35"],
                "r": "Bajo",
                "razon": "Margen amplio de seguridad para ritmo conservador."
            })

        candidatos.sort(key=lambda x: x["p"], reverse=True)

        for cand in candidatos:
            cand["c"] = self.value.cuota_justa(cand["p"])

        p_top = candidatos[0]
        s_top = candidatos[1] if len(candidatos) > 1 else candidatos[0]

        arg = (
            f"**1. Rendimiento Ajustado (Fuerza Rival):** {loc_name} ({pf_h:.1f} GF / {pc_h:.1f} GC | Rival S_opp: {analisis_raw['fuerza_rival_h']:.2f}) vs "
            f"{vis_name} ({pf_v:.1f} GF / {pc_v:.1f} GC | Rival S_opp: {analisis_raw['fuerza_rival_v']:.2f}).\n\n"
            f"**2. Expectativa Gol (Dixon-Coles + Monte Carlo 10k):** Proyección local: {l_h:.2f} | Visita: {l_v:.2f} (Total: {exp_g:.2f} | xG: {analisis_raw['xg_h']:.2f} vs {analisis_raw['xg_v']:.2f}).\n\n"
            f"**3. Contexto Táctico & H2H:** Promedio H2H {prom_h2h:.1f} goles | Descanso: {analisis_raw['descanso_h']}d vs {analisis_raw['descanso_v']}d.\n\n"
            f"**4. Dictamen Multimercado:** {p_top['razon']}"
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
            analyzed_markets=candidatos,
            market_ranking=candidatos,
            main_prediction=p_top["m"],
            alternative_prediction=s_top["m"],
            estimated_probability=p_top["p"],
            fair_odds=p_top["c"],
            confidence=probs["confianza"],
            risk=p_top["r"],
            explanation=arg
            ) 
