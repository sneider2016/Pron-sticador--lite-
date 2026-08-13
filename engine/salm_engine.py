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

        ranking.sort(key=lambda x: x["probabilidad"], reverse=True)
        return ranking

    def evaluar_betplay(self, probabilidad: float, cuota: float) -> dict:
        return self.value.analizar(probabilidad, cuota)

    def ejecutar_analisis_completo(self, local: str, visitante: str, fecha: str, liga: str) -> Match:
        anio_partido = int(fecha.split("-")[0]) if fecha and "-" in fecha else datetime.now().year

        fix = self.api.buscar_partido_por_equipos(local, visitante, fecha)

        # VALIDACIÓN DE FECHA ESTRICTA: Si no existe partido programado en la fecha exacta
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
                explanation=f"**Atención:** No se encontró ningún partido oficial agendado entre **{loc_n}** y **{vis_n}** para la fecha **{fecha}**. Verifique la fecha oficial del encuentro en el calendario.",
                alerts=[f"🛑 ATENCIÓN: No existe un partido oficial agendado entre {loc_n} y {vis_n} para el día {fecha}. Verifique la fecha oficial en el calendario."]
            )

        h_id = fix["teams"]["home"]["id"] if fix else 0
        v_id = fix["teams"]["away"]["id"] if fix else 0

        loc_name = fix["teams"]["home"]["name"] if fix else local
        vis_name = fix["teams"]["away"]["name"] if fix else visitante
        referee_name = fix.get("referee_name", "") if fix else ""

        # AUTO-DETECCIÓN DE LIGA OFICIAL DESDE LA API
        nombre_liga_oficial = fix.get("league", {}).get("name", "") if fix else ""
        liga_final = nombre_liga_oficial if nombre_liga_oficial and nombre_liga_oficial != "0" else liga

        datos_partido = {
            "home_id": h_id,
            "away_id": v_id,
            "fixture_id": fix["fixture"]["id"] if fix else 0,
            "league_id": fix["league"]["id"] if fix else 0,
            "season": anio_partido,
            "liga": liga_final,
            "referee_name": referee_name
        }

        analisis_raw = self.analyzer.analizar(datos_partido)
        alertas_finales = list(analisis_raw.get("alertas", []))

        if not analisis_raw.get("datos_reales_ok", False):
            return Match(
                fixture_id=0,
                liga=liga_final,
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
                alternative_prediction="Ajuste el nombre del equipo o revise el saldo/cupo diario de su API Key.",
                explanation="**Atención:** No fue posible obtener el historial de los equipos desde API-Football. La aplicación se niega a calcular un pronóstico a ciegas con datos inventados.",
                alerts=alertas_finales
            )

        # AUDITORÍA DE ÁRBITRO DESIGNADO
        if referee_name:
            alertas_finales.append(f"👨‍⚖️ Árbitro Designado: {referee_name} (Perfil disciplinario integrado al análisis de tarjetas).")
        else:
            alertas_finales.append("👨‍⚖️ Árbitro: Terna arbitral oficial aún por confirmar por la organización de la liga.")

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
                starters = team_l.get("startXI", []) or []
                alertas_finales.append(f"✅ {tname}: 11 Inicial Confirmado ({form}) con {len(starters)} titulares.")
        else:
            alertas_finales.append("⚠️ Alineaciones oficiales aún no confirmadas por la liga. Análisis elaborado con formación proyectada.")

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

        # FILTRO CIRUJANO v5.0: UMBRAL MÍNIMO DE ALTA SEGURIDAD GE 70.0%

        # 1. Doble Chance (Exige >= 70.0%)
        if probs["doble_chance_1x"] >= 70.0:
            todos_mercados.append({
                "m": f"Gana o Empata {loc_name} (Doble Chance 1X)",
                "p": probs["doble_chance_1x"],
                "r": "Bajo" if probs["doble_chance_1x"] >= 78.0 else "Bajo-Medio",
                "razon": f"Justificación Cuantitativa: Sólida cobertura local del {probs['doble_chance_1x']}% respaldada por baja probabilidad de victoria directa del visitante."
            })
        if probs["doble_chance_x2"] >= 70.0:
            todos_mercados.append({
                "m": f"Gana o Empata {vis_name} (Doble Chance X2)",
                "p": probs["doble_chance_x2"],
                "r": "Bajo" if probs["doble_chance_x2"] >= 78.0 else "Bajo-Medio",
                "razon": f"Justificación Cuantitativa: La solidez defensiva del visitante sostiene un {probs['doble_chance_x2']}% de cobertura real, protegiendo la entrada ante la localía."
            })

        # 2. Draw No Bet (Exige >= 70.0%)
        if probs["dnb_local"] >= 70.0:
            todos_mercados.append({
                "m": f"Gana {loc_name} Sin Empate (DNB)",
                "p": probs["dnb_local"],
                "r": "Bajo" if probs["dnb_local"] >= 78.0 else "Bajo-Medio",
                "razon": f"Justificación Cuantitativa: Dominio ofensivo del local garantizando reembolso completo ante empate con {probs['dnb_local']}% DNB."
            })
        if probs["dnb_visitante"] >= 70.0:
            todos_mercados.append({
                "m": f"Gana {vis_name} Sin Empate (DNB)",
                "p": probs["dnb_visitante"],
                "r": "Bajo-Medio",
                "razon": f"Justificación Cuantitativa: Métricas superiores de rendimiento visitante garantizando reembolso ante empate con {probs['dnb_visitante']}% DNB."
            })

        # 3. Goles (Exige >= 70.0%)
        if probs["over15"] >= 70.0:
            todos_mercados.append({
                "m": "Más de 1.5 Goles Totales en el Partido",
                "p": probs["over15"],
                "r": "Bajo",
                "razon": f"Justificación Cuantitativa: Expectativa Poisson Bivariada de {exp_g:.2f} goles esperados ({probs['over15']}% prob. real) con baja probabilidad de marcador a ceros."
            })
        if probs["under25"] >= 70.0:
            todos_mercados.append({
                "m": "Menos de 2.5 Goles Totales (Under 2.5)",
                "p": probs["under25"],
                "r": "Bajo-Medio",
                "razon": f"Justificación Cuantitativa: Baja expectativa de gol ({exp_g:.2f}) y ritmo defensivo, otorgando {probs['under25']}% de probabilidad en marcador apretado."
            })
        if probs["under35"] >= 72.0:
            todos_mercados.append({
                "m": "Menos de 3.5 Goles Totales",
                "p": probs["under35"],
                "r": "Bajo",
                "razon": f"Justificación Cuantitativa: Margen amplio de seguridad ({probs['under35']}% prob. real) en un trámite de baja densidad goleadora ({exp_g:.2f} esperados)."
            })

        # 4. Ambos Anotan (Exige >= 70.0%)
        if probs["btts"] >= 70.0:
            todos_mercados.append({
                "m": "Ambos Equipos Anotan (Sí)",
                "p": probs["btts"],
                "r": "Bajo-Medio",
                "razon": f"Justificación Cuantitativa: Conversión en ambos ataques con índice de probabilidad BTTS del {probs['btts']}%."
            })

        # 5. Córneres (Exige >= 70.0%)
        if corners_est >= 8.5:
            p_corn = round(min(88.0, 68.0 + (corners_est - 8.5) * 3.5), 1)
            if p_corn >= 70.0:
                todos_mercados.append({
                    "m": "Más de 7.5 Tiros de Esquina Totales",
                    "p": p_corn,
                    "r": "Bajo" if p_corn >= 75.0 else "Bajo-Medio",
                    "razon": f"Justificación Cuantitativa: Proyección de {corners_est:.1f} córneres totales por flujo ofensivo en bandas ({p_corn}% de probabilidad)."
                })

        # 6. Tarjetas (Exige >= 70.0%)
        if tarjetas_est >= 4.0:
            p_cards = round(min(86.0, 66.0 + (tarjetas_est - 4.0) * 4.0), 1)
            if p_cards >= 70.0:
                ref_txt = f" (Árbitro: {referee_name})" if referee_name else ""
                todos_mercados.append({
                    "m": "Más de 3.5 Tarjetas Totales en el Partido",
                    "p": p_cards,
                    "r": "Bajo" if p_cards >= 75.0 else "Bajo-Medio",
                    "razon": f"Justificación Cuantitativa: Índice de fricción disciplinaria del cruce{ref_txt} proyecta {tarjetas_est:.1f} tarjetas estimadas ({p_cards}% de probabilidad)."
                })

        todos_mercados.sort(key=lambda x: x["p"], reverse=True)

        # MANEJO LIMPIO DE CASO SIN MERCADOS O SOLO 1 MERCADO GE 70.0%
        if not todos_mercados:
            alertas_finales.append("🛑 RITMO INCIERTO / ALTA VARIANZA: Ningún mercado en este partido alcanza la probabilidad de alta seguridad mínima del 70.0%. Se recomienda abstenerse de apostar en este encuentro para cuidar el capital.")
            p_top = {
                "m": "🛑 RITMO INCIERTO (Sin Mercado GE 70%)", "p": 0.0, "c": 999.0, "r": "Alto", "razon": "Justificación Cuantitativa: Ningún mercado alcanza la probabilidad de alta seguridad mínima del 70.0%."
            }
            s_top = p_top
        elif len(todos_mercados) == 1:
            p_top = todos_mercados[0]
            s_top = {
                "m": "🛑 NINGUNO ADICIONAL", "p": 0.0, "c": 999.0, "r": "N/A", "razon": "Justificación Cuantitativa: Únicamente el Pronóstico Principal cumplió con la alta probabilidad mínima del 70.0%. No hubo más mercados que alcanzaran este porcentaje mínimo."
            }
        else:
            p_top = todos_mercados[0]
            s_top = todos_mercados[1] if todos_mercados[1]["m"] != p_top["m"] else (todos_mercados[2] if len(todos_mercados) > 2 else p_top)

        for cand in todos_mercados:
            cand["c"] = self.value.cuota_justa(cand["p"])

        ref_arg = f" | Árbitro: {referee_name}" if referee_name else ""
        arg = (
            f"**1. Rendimiento Real API:** {loc_name} ({pf_h:.2f} GF / {pc_h:.2f} GC) vs {vis_name} ({pf_v:.2f} GF / {pc_v:.2f} GC).\n\n"
            f"**2. Proyección Poisson Bivariada:** Gol Local: {l_h:.2f} | Gol Visita: {l_v:.2f} (Total: {exp_g:.2f} goles esperados).\n\n"
            f"**3. Contexto Táctico, H2H & Disciplina:** Promedio H2H: {prom_h2h:.1f} goles | Córneres Est: {corners_est:.1f} | Tarjetas Est: {tarjetas_est:.1f}{ref_arg} | Descanso: {analisis_raw['descanso_h']}d vs {analisis_raw['descanso_v']}d.\n\n"
            f"**4. Dictamen Multimercado Exclusivo:** Oportunidad destacada con {p_top['p']}% de probabilidad real.\n\n"
            f"**5. Competición Oficial API:** {liga_final}"
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
            market_ranking=todos_mercados if todos_mercados else [p_top],
            main_prediction=p_top["m"],
            alternative_prediction=s_top["m"],
            estimated_probability=p_top["p"],
            fair_odds=p_top["c"],
            confidence=probs["confianza"],
            risk=p_top["r"],
            explanation=arg,
            alerts=alertas_finales
        )
