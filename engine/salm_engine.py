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
                market_ranking=[{
                    "m": "🛑 FECHA INCORRECTA O PARTIDO NO PROGRAMADO",
                    "p": 0.0,
                    "c": 999.0,
                    "r": "Alto",
                    "razon": f"No hay partido agendado entre {loc_n} y {vis_n} para el {fecha}."
                }],
                main_prediction="🛑 NO HAY PARTIDO PROGRAMADO PARA ESTA FECHA",
                alternative_prediction="Ajuste la fecha en el calendario oficial.",
                explanation=f"**Atención:** No se encontró ningún partido oficial agendado entre **{loc_n}** y **{vis_n}** para la fecha **{fecha}**.",
                alerts=[f"🛑 ATENCIÓN: Verifique la fecha oficial en el calendario."]
            )

        h_id = fix["teams"]["home"]["id"] if fix else 0
        v_id = fix["teams"]["away"]["id"] if fix else 0
        loc_name = fix["teams"]["home"]["name"] if fix else local
        vis_name = fix["teams"]["away"]["name"] if fix else visitante
        referee_name = fix.get("referee_name", "") if fix else ""

        nombre_liga_oficial = fix.get("league", {}).get("name", "") if fix else ""
        ronda_oficial = fix.get("league", {}).get("round", "") if fix else ""
        liga_final = nombre_liga_oficial if nombre_liga_oficial and nombre_liga_oficial != "0" else liga

        # DETECTOR INTELIGENTE DE FASE BLINDADO (ÚNICA MEJORA APLICADA)
        ronda_lower = ronda_oficial.lower().strip()
        liga_lower = liga_final.lower().strip()
        mes_partido = int(fecha.split("-")[1]) if fecha and "-" in fecha else datetime.now().month

        es_torneo_uefa = any(k in liga_lower for k in ["champions", "europa", "conference"])
        es_previa_verano = es_torneo_uefa and (mes_partido in [6, 7, 8])  # En junio, julio y agosto en Europa siempre son fases previas de ida y vuelta

        palabras_ko = [
            "qualif", "play-off", "playoff", "play off", "cup", "copa", "trophée", "trophy",
            "round of 16", "round of 32", "quarter", "semi", "final", "knockout", "supercopa", "super cup"
        ]
        es_ronda_ko = any(k in ronda_lower for k in palabras_ko) or any(k in liga_lower for k in ["cup", "copa", "trophée", "supercopa"])

        if es_previa_verano or es_ronda_ko:
            es_eliminatoria = True
            texto_competicion = f"{liga_final} (⚠️ Eliminatoria Directa - Mano a Mano)"
        else:
            es_eliminatoria = False
            texto_competicion = f"{liga_final} (Fase de Tabla / 3 Puntos)"

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
        analisis_raw["es_eliminatoria"] = es_eliminatoria
        alertas_finales = list(analisis_raw.get("alertas", []))

        if not analisis_raw.get("datos_reales_ok", False):
            return Match(
                fixture_id=0,
                liga=liga_final,
                fecha=fecha,
                local=loc_name,
                visitante=vis_name,
                market_ranking=[{
                    "m": "🛑 DATOS INSUFICIENTES",
                    "p": 0.0,
                    "c": 999.0,
                    "r": "Alto",
                    "razon": "No se encontraron partidos reales en API-Football."
                }],
                main_prediction="🛑 PRONÓSTICO SUSPENDIDO POR FALTA DE DATOS",
                explanation="No fue posible obtener el historial completo desde API-Football.",
                alerts=alertas_finales
            )

        # AUDITORÍA DE ÁRBITRO
        if referee_name:
            alertas_finales.append(f"👨‍⚖️ Árbitro Designado: {referee_name} (Perfil disciplinario integrado al análisis).")
        else:
            alertas_finales.append("👨‍⚖️ Árbitro: Terna oficial aún por confirmar por la organización.")

        # AUDITORÍA DE ALINEACIONES
        lineups_raw = analisis_raw.get("lineups_data", [])
        confirmados = 0
        if lineups_raw and len(lineups_raw) >= 2:
            for team_l in lineups_raw:
                starters = team_l.get("startXI", []) or []
                if len(starters) >= 7:
                    confirmados += 1

        if confirmados >= 2:
            for team_l in lineups_raw:
                tname = team_l.get("team", {}).get("name", "Equipo")
                form = team_l.get("formation") or "N/A"
                alertas_finales.append(f"✅ {tname}: 11 Inicial Confirmado ({form}).")
        else:
            alertas_finales.append("⚠️ Alineaciones oficiales aún no confirmadas. Análisis con alineación proyectada.")

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
            es_eliminatoria=es_eliminatoria,
            btts_rate=analisis_raw["btts_rate"],
            under25_rate=analisis_raw["under25_rate"]
        )

        es_liga_cerrojo = "argentina" in liga_final.lower() or "betplay" in liga_final.lower()
        corners_est = analisis_raw["corners_est"]
        tarjetas_est = analisis_raw["tarjetas_est"]

        todos_mercados = []

        # 1. DOBLE OPORTUNIDAD (1X / X2)
        if probs["doble_chance_1x"] >= 68.0 and (analisis_raw["elo_h"] >= analisis_raw["elo_v"] - 80):
            todos_mercados.append({
                "m": f"Gana o Empata {loc_name} (1X)",
                "p": probs["doble_chance_1x"],
                "r": "Bajo",
                "razon": f"Cobertura local sólida ({probs['doble_chance_1x']}%) respaldada por ELO ({int(analisis_raw['elo_h'])} vs {int(analisis_raw['elo_v'])})."
            })
        if probs["doble_chance_x2"] >= 68.0 and (analisis_raw["elo_v"] >= analisis_raw["elo_h"] - 80):
            todos_mercados.append({
                "m": f"Gana o Empata {vis_name} (X2)",
                "p": probs["doble_chance_x2"],
                "r": "Bajo",
                "razon": f"Jerarquía visitante ({int(analisis_raw['elo_v'])} ELO) que neutraliza la localía rival ({probs['doble_chance_x2']}%)."
            })

        # 2. DRAW NO BET (DNB / EMPATE NO VÁLIDO)
        if probs["dnb_local"] >= 65.0 and (analisis_raw["elo_h"] >= analisis_raw["elo_v"]):
            todos_mercados.append({
                "m": f"Gana {loc_name} Sin Empate (DNB)",
                "p": probs["dnb_local"],
                "r": "Bajo-Medio",
                "razon": f"Dominio ofensivo local ({probs['dnb_local']}%) garantizando reembolso completo ante empate."
            })
        if probs["dnb_visitante"] >= 65.0 and (analisis_raw["elo_v"] >= analisis_raw["elo_h"]):
            todos_mercados.append({
                "m": f"Gana {vis_name} Sin Empate (DNB)",
                "p": probs["dnb_visitante"],
                "r": "Bajo-Medio",
                "razon": f"Métricas superiores del visitante ({probs['dnb_visitante']}%) garantizando reembolso ante empate."
            })

        # 3. GOLES (OVER / UNDER)
        umbral_o15 = 78.0 if es_liga_cerrojo else 70.0
        if probs["over15"] >= umbral_o15:
            todos_mercados.append({
                "m": "Más de 1.5 Goles Totales",
                "p": probs["over15"],
                "r": "Bajo",
                "razon": f"Expectativa de {probs['exp_goles']:.2f} goles con alta probabilidad de marcadores abiertos ({probs['over15']}%)."
            })

        if probs["under35"] >= 72.0 and not es_eliminatoria:
            todos_mercados.append({
                "m": "Menos de 3.5 Goles Totales",
                "p": probs["under35"],
                "r": "Bajo",
                "razon": f"Partido de trámite regular por puntos con baja densidad goleadora ({probs['exp_goles']:.2f} goles - {probs['under35']}%)."
            })

        if probs["under25"] >= 70.0 and not es_eliminatoria and es_liga_cerrojo:
            todos_mercados.append({
                "m": "Menos de 2.5 Goles Totales (Under 2.5)",
                "p": probs["under25"],
                "r": "Bajo-Medio",
                "razon": f"Trámite de alta fricción táctica y baja expectativa ({probs['exp_goles']:.2f} goles - {probs['under25']}%)."
            })

        # 4. AMBOS EQUIPOS ANOTAN (BTTS)
        if probs["btts"] >= 65.0:
            todos_mercados.append({
                "m": "Ambos Equipos Anotan (Sí)",
                "p": probs["btts"],
                "r": "Bajo-Medio",
                "razon": f"Alta frecuencia ofensiva mutua con {probs['btts']}% de probabilidad bivariada."
            })

        # 5. TIROS DE ESQUINA (CÓRNERES)
        if corners_est >= 8.5:
            p_corn = round(min(88.0, 68.0 + (corners_est - 8.5) * 3.5), 1)
            if p_corn >= 68.0:
                todos_mercados.append({
                    "m": "Más de 7.5 Tiros de Esquina Totales",
                    "p": p_corn,
                    "r": "Bajo" if p_corn >= 75.0 else "Bajo-Medio",
                    "razon": f"Proyección de {corners_est:.1f} córneres totales por volumen de ataque en bandas ({p_corn}%)."
                })

        # 6. TARJETAS DISCIPLINARIAS
        if tarjetas_est >= 4.4:
            p_cards = round(min(88.0, 68.0 + (tarjetas_est - 4.4) * 4.0), 1)
            if p_cards >= 68.0:
                ref_txt = f" (Árbitro: {referee_name})" if referee_name else ""
                todos_mercados.append({
                    "m": "Más de 3.5 Tarjetas Totales",
                    "p": p_cards,
                    "r": "Bajo" if p_cards >= 75.0 else "Bajo-Medio",
                    "razon": f"Fricción disciplinaria{ref_txt} proyecta {tarjetas_est:.1f} tarjetas estimadas ({p_cards}%)."
                })

        # ORDENAR ESTRICTAMENTE POR PROBABILIDAD MATEMÁTICA PURA
        todos_mercados.sort(key=lambda x: x["p"], reverse=True)
        for cand in todos_mercados:
            cand["c"] = self.value.cuota_justa(cand["p"])

        # ASIGNACIÓN DE PRONÓSTICO PRINCIPAL Y SECUNDARIO
        if not todos_mercados:
            alertas_finales.append("🛑 RITMO INCIERTO / ALTA VARIANZA: Ningún mercado superó los filtros estrictos de seguridad. Se recomienda abstenerse.")
            p_top = {"m": "🛑 RITMO INCIERTO (Sin Mercado Seguro)", "p": 0.0, "c": 999.0, "r": "Alto", "razon": "Ningún mercado alcanzó los filtros de seguridad estricta."}
            s_top = p_top
            ranking_final = [p_top]
        elif len(todos_mercados) == 1:
            p_top = todos_mercados[0]
            s_top = {"m": "🛑 NINGUNO ADICIONAL", "p": 0.0, "c": 999.0, "r": "N/A", "razon": "Únicamente el Pronóstico Principal cumplió con los filtros de seguridad."}
            ranking_final = [p_top, s_top]
        else:
            p_top = todos_mercados[0]
            s_top = todos_mercados[1]
            ranking_final = todos_mercados

        ref_arg = f" | Árbitro: {referee_name}" if referee_name else ""
        arg = (
            f"**1. Jerarquía ELO Real:** {loc_name} ({int(analisis_raw['elo_h'])}) vs {vis_name} ({int(analisis_raw['elo_v'])}).\n\n"
            f"**2. Proyección Poisson Bivariada:** Gol Local: {probs['lambda_local']:.2f} | Gol Visita: {probs['lambda_visitante']:.2f} (Total: {probs['exp_goles']:.2f} esperados).\n\n"
            f"**3. Contexto Táctico & Disciplina:** Córneres Est: {corners_est:.1f} | Tarjetas Est: {tarjetas_est:.1f}{ref_arg} | Descanso: {analisis_raw['descanso_h']}d vs {analisis_raw['descanso_v']}d.\n\n"
            f"**4. Competición:** {texto_competicion}."
        )

        return Match(
            fixture_id=fix["fixture"]["id"] if fix else None,
            league_id=fix["league"]["id"] if fix else None,
            season=fix["league"]["season"] if fix else None,
            liga=liga_final,
            fecha=fecha,
            local=loc_name,
            visitante=vis_name,
            h2h=analisis_raw["h2h"],
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
