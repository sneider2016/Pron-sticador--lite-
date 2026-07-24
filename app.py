import streamlit as st
import datetime
import requests
import math
import unicodedata
from rapidfuzz import fuzz

# API Keys y Configuración
API_FOOTBALL_KEY = "3e69e51ac95c094a672f790edac978b0"
API_FOOTBALL_HOST = "v3.football.api-sports.io"

# Configuración de la página
st.set_page_config(page_title="Pronosticador Élite App", page_icon="⚽", layout="centered")

st.title("⚽ PRONOSTICADOR ÉLITE 90%")
st.caption("Motor Quirúrgico Basado en Estadísticas Reales, Modelo de Poisson y (+EV)")

st.divider()

# --- FUNCIONES DE NORMALIZACIÓN Y BÚSQUEDA ---

def normalizar_texto(texto):
    """Limpia tildes, caracteres especiales y prefijos/sufijos de clubes."""
    if not texto:
        return ""
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode("utf-8")
    texto = texto.lower()
    basura_lista = ["fc", "cd", "club", "sd", "ca", "s.a.", "deportivo", "atletico", "csd", "csc", "afc"]
    palabras = texto.split()
    palabras_limpias = [p for p in palabras if p not in basura_lista]
    return " ".join(palabras_limpias).strip()

def extraer_palabras_clave(texto):
    texto_norm = normalizar_texto(texto)
    return [p for p in texto_norm.split() if len(p) > 2]

def coincidencia_palabras_clave(query, candidato):
    kw_query = extraer_palabras_clave(query)
    kw_candidato = extraer_palabras_clave(candidato)
    if not kw_query or not kw_candidato:
        return 0
    coincidencias = sum(1 for kw in kw_query if any(kw in kw_c or kw_c in kw for kw_c in kw_candidato))
    return (coincidencias / len(kw_query)) * 100

def obtener_datos_partido_por_fecha(equipo_local, equipo_visitante, fecha_str):
    url = f"https://{API_FOOTBALL_HOST}/fixtures"
    headers = {
        'x-rapidapi-host': API_FOOTBALL_HOST,
        'x-rapidapi-key': API_FOOTBALL_KEY
    }
    
    fecha_dt = datetime.datetime.strptime(fecha_str, "%Y-%m-%d")
    fecha_manana = (fecha_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    partidos = []
    for f in [fecha_str, fecha_manana]:
        try:
            response = requests.get(url, headers=headers, params={'date': f}, timeout=8)
            if response.status_code == 200 and response.json().get('response'):
                partidos.extend(response.json()['response'])
        except Exception:
            pass
            
    if not partidos:
        return None

    mejor_coincidencia = None
    puntaje_maximo = 0
    
    for p in partidos:
        loc_api = p['teams']['home']['name']
        vis_api = p['teams']['away']['name']
        
        score_kw_loc = coincidencia_palabras_clave(equipo_local, loc_api)
        score_kw_vis = coincidencia_palabras_clave(equipo_visitante, vis_api)
        score_kw = (score_kw_loc + score_kw_vis) / 2
        
        s_loc = normalizar_texto(equipo_local)
        s_vis = normalizar_texto(equipo_visitante)
        loc_api_norm = normalizar_texto(loc_api)
        vis_api_norm = normalizar_texto(vis_api)
        
        score_fuzz_loc = max(fuzz.ratio(s_loc, loc_api_norm), fuzz.partial_ratio(s_loc, loc_api_norm))
        score_fuzz_vis = max(fuzz.ratio(s_vis, vis_api_norm), fuzz.partial_ratio(s_vis, vis_api_norm))
        score_fuzz = (score_fuzz_loc + score_fuzz_vis) / 2
        
        puntaje_total = max(score_kw, score_fuzz)
        
        if puntaje_total > 50 and puntaje_total > puntaje_maximo:
            puntaje_maximo = puntaje_total
            mejor_coincidencia = p
            
    return mejor_coincidencia

def obtener_lineups_oficiales(fixture_id):
    url = f"https://{API_FOOTBALL_HOST}/fixtures/lineups"
    headers = {
        'x-rapidapi-host': API_FOOTBALL_HOST,
        'x-rapidapi-key': API_FOOTBALL_KEY
    }
    try:
        response = requests.get(url, headers=headers, params={'fixture': fixture_id}, timeout=6)
        if response.status_code == 200:
            data = response.json()
            if data.get('response') and len(data['response']) >= 2:
                return data['response']
        return None
    except Exception:
        return None

def obtener_clima_estadio(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json().get('current_weather', {})
        return None
    except Exception:
        return None

# --- OPCIÓN A: MOTOR DE ANÁLISIS BASADO EN DATOS REALES DE LA API Y POISSON ---

def obtener_historial_equipo(team_id):
    """Consulta los últimos 5 partidos jugados por un equipo para calcular sus promedios de gol."""
    url = f"https://{API_FOOTBALL_HOST}/fixtures"
    headers = {
        'x-rapidapi-host': API_FOOTBALL_HOST,
        'x-rapidapi-key': API_FOOTBALL_KEY
    }
    params = {'team': team_id, 'last': 5}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=8)
        if response.status_code == 200:
            return response.json().get('response', [])
    except Exception:
        pass
    return []

def calcular_poisson(k, lambda_val):
    """Fórmula de Distribución de Poisson para probabilidad de goles."""
    return (math.pow(lambda_val, k) * math.exp(-lambda_val)) / math.factorial(k)

def motor_analisis_quirurgico_real(team_home_id, team_away_id, home_name, away_name, liga_nombre):
    """
    Analiza estadísticas reales del API, calcula esperanzas de gol y aplica el Modelo Poisson.
    """
    hist_home = obtener_historial_equipo(team_home_id)
    hist_away = obtener_historial_equipo(team_away_id)
    
    # Procesar promedios reales de goles del local
    goles_f_home, goles_c_home = 0, 0
    if hist_home:
        for m in hist_home:
            is_home = m['teams']['home']['id'] == team_home_id
            goles_f_home += m['goals']['home'] if is_home else m['goals']['away']
            goles_c_home += m['goals']['away'] if is_home else m['goals']['home']
        p_f_home = goles_f_home / len(hist_home)
        p_c_home = goles_c_home / len(hist_home)
    else:
        p_f_home, p_c_home = 1.3, 1.1

    # Procesar promedios reales de goles del visitante
    goles_f_away, goles_c_away = 0, 0
    if hist_away:
        for m in hist_away:
            is_away = m['teams']['away']['id'] == team_away_id
            goles_f_away += m['goals']['away'] if is_away else m['goals']['home']
            goles_c_away += m['goals']['home'] if is_away else m['goals']['away']
        p_f_away = goles_f_away / len(hist_away)
        p_c_away = goles_c_away / len(hist_away)
    else:
        p_f_away, p_c_away = 1.0, 1.2

    # Expectativa de goles para el partido (Lambda)
    lambda_home = (p_f_home + p_c_away) / 2
    lambda_away = (p_f_away + p_c_home) / 2
    
    # Calcular matriz de probabilidades de marcadores (hasta 5x5)
    prob_home_win = 0.0
    prob_draw = 0.0
    prob_away_win = 0.0
    prob_under_35 = 0.0
    
    for i in range(6):
        for j in range(6):
            p = calcular_poisson(i, lambda_home) * calcular_poisson(j, lambda_away)
            if i > j:
                prob_home_win += p
            elif i == j:
                prob_draw += p
            else:
                prob_away_win += p
            
            if (i + j) < 3.5:
                prob_under_35 += p

    prob_1x = prob_home_win + prob_draw
    prob_x2 = prob_away_win + prob_draw
    
    # Evaluación de mercado óptimo según los datos reales
    if prob_1x >= prob_x2 and lambda_home >= lambda_away:
        mercado_p = f"Gana o Empata {home_name} + Under 3.5 Goles"
        prob_real = min(88, max(60, int((prob_1x * 0.6 + prob_under_35 * 0.4) * 100)))
        mercado_r = f"Gana {home_name} Sin Empate (Apuesta Sin Empate)"
        prob_real_r = min(82, max(58, int(prob_home_win * 100)))
    else:
        mercado_p = f"Gana o Empata {away_name} + Under 3.5 Goles"
        prob_real = min(88, max(60, int((prob_x2 * 0.6 + prob_under_35 * 0.4) * 100)))
        mercado_r = f"Under 2.5 Goles Totales en el Partido"
        prob_real_r = min(82, max(58, int(prob_under_35 * 100)))

    cuota_p = round(1 / (prob_real / 100), 2)
    cuota_r = round(1 / (prob_real_r / 100), 2)

    tactica = (
        f"Análisis estadístico sobre los últimos 5 partidos de cada club en {liga_nombre}. "
        f"{home_name} registra una media de {p_f_home:.1f} goles anotados y {p_c_home:.1f} recibidos. "
        f"Por su parte, {away_name} genera {p_f_away:.1f} goles a favor y concede {p_c_away:.1f} en promedio. "
        f"El modelo de Poisson establece una expectativa de {lambda_home:.2f} goles para el local y {lambda_away:.2f} para la visita."
    )

    return {
        "principal": mercado_p,
        "cuota_p": cuota_p,
        "prob_p": prob_real,
        "regenerado": mercado_r,
        "cuota_r": cuota_r,
        "prob_r": prob_real_r,
        "tactica": tactica
    }

# --- SECCIÓN 1: ENTRADA DE DATOS ---
st.subheader("1. Configuración del Partido")

col1, col2 = st.columns(2)
with col1:
    lista_ligas = [
        "Premier League (Inglaterra)", "LaLiga (España)", "Serie A (Italia)", "Bundesliga (Alemania)",
        "Ligue 1 (Francia)", "UEFA Champions League", "UEFA Europa League", "Copa Libertadores",
        "Copa Sudamericana", "Liga BetPlay (Colombia)", "Brasileirão (Brasil)", "Liga Profesional (Argentina)", "Otra liga"
    ]
    liga = st.selectbox("Liga / Torneo", lista_ligas)
    local = st.text_input("Equipo Local", value="Santa Fe")
with col2:
    fecha_consulta = st.date_input("Fecha", datetime.date.today())
    visitante = st.text_input("Equipo Visitante", value="Caracas")

confirmacion_manual = st.checkbox("⚙️ Confirmar alineaciones manualmente (Bypass si ya las viste en prensa)")

if st.button("🔎 Generar Análisis Quirúrgico Completo"):
    with st.spinner("Consultando estadísticas reales e historial en API..."):
        fecha_str = fecha_consulta.strftime("%Y-%m-%d")
        datos_partido = obtener_datos_partido_por_fecha(local, visitante, fecha_str)
        
        alertas_auto = []
        reporte_clima = "☀️ Clima normal para la práctica deportiva."
        reporte_alineaciones = "✅ Alineaciones verificadas."

        if datos_partido:
            fixture_id = datos_partido['fixture']['id']
            home_id = datos_partido['teams']['home']['id']
            away_id = datos_partido['teams']['away']['id']
            home_real_name = datos_partido['teams']['home']['name']
            away_real_name = datos_partido['teams']['away']['name']
            
            # Ejecución del análisis sobre la API real
            analisis = motor_analisis_quirurgico_real(home_id, away_id, home_real_name, away_real_name, liga)

            # Verificación de Clima
            venue = datos_partido.get('fixture', {}).get('venue', {})
            lat, lon = venue.get('latitude'), venue.get('longitude')
            if lat and lon:
                clima = obtener_clima_estadio(lat, lon)
                if clima:
                    temp = clima.get('temperature', 20)
                    if temp > 35 or temp < 2:
                        alertas_auto.append(f"Temperatura extrema ({temp}°C)")
                        reporte_clima = f"⚠️ Temperatura extrema ({temp}°C)."

            # Verificación de Nóminas
            if confirmacion_manual:
                reporte_alineaciones = "✅ Alineaciones confirmadas manualmente por el usuario."
            else:
                lineups = obtener_lineups_oficiales(fixture_id)
                if not lineups:
                    alertas_auto.append("Alineaciones oficiales aún no confirmadas en la API")
                    reporte_alineaciones = "⚠️ Nóminas pendientes por confirmación oficial en API."
                else:
                    reporte_alineaciones = "✅ Alineaciones 100% confirmadas en la API."
        else:
            alertas_auto.append("Partido no enlazado en la API para la fecha seleccionada")
            reporte_alineaciones = "⚠️ No se pudo enlazar la planilla del partido."
            analisis = {
                "principal": f"Gana o Empata {local} + Under 3.5 Goles",
                "cuota_p": 1.60, "prob_p": 75,
                "regenerado": f"Under 2.5 Goles Totales",
                "cuota_r": 1.70, "prob_r": 70,
                "tactica": "No se encontraron datos históricos en API para este cruce puntual. Se requiere ingreso manual."
            }

        st.session_state['analizado'] = True
        st.session_state['analisis'] = analisis
        st.session_state['alertas_auto'] = alertas_auto
        st.session_state['reporte_clima'] = reporte_clima
        st.session_state['reporte_alineaciones'] = reporte_alineaciones

# --- SECCIÓN 2: REPORTE TÁCTICO Y FLUJO REGENERATIVO ---
if st.session_state.get('analizado', False):
    st.divider()
    an = st.session_state.get('analisis')
    
    st.subheader("2. Dictamen del Pronosticador Élite")
    
    st.markdown("### 🔬 Análisis Estadístico Reales (Poisson)")
    st.write(f"_{an['tactica']}_")
    
    st.write("---")
    
    st.success(f"🎯 **PRONÓSTICO PRINCIPAL RECOMENDADO**\n\n"
               f"**Mercado:** {an['principal']}\n\n"
               f"**Cuota Justa Calculada:** {an['cuota_p']:.2f} | **Prob. Real Estimada:** {an['prob_p']}%")
    
    st.write("---")
    st.markdown("### 🎯 Filtro de Disponibilidad en Betplay")
    
    disp_principal = st.radio(
        f"¿El mercado '{an['principal']}' está disponible en Betplay?",
        options=["Sí, está disponible", "No está disponible"],
        index=0
    )
    
    mercado_evaluar = an['principal']
    cuota_justa_evaluar = an['cuota_p']
    bloqueo_mercado = False

    if disp_principal == "No está disponible":
        st.warning("🔄 **ACTIVANDO RE-ANÁLISIS AUTOMÁTICO...**")
        st.success(f"🔄 **NUEVO PRONÓSTICO REGENERADO DE GRAN VALOR**\n\n"
                   f"**Mercado:** {an['regenerado']}\n\n"
                   f"**Cuota Justa Calculada:** {an['cuota_r']:.2f} | **Prob. Real Estimada:** {an['prob_r']}%")
        
        disp_regenerado = st.radio(
            f"¿Esta nueva opción ('{an['regenerado']}') está disponible en Betplay?",
            options=["Sí, está disponible", "Tampoco está disponible"],
            index=0
        )
        
        if disp_regenerado == "Sí, está disponible":
            mercado_evaluar = an['regenerado']
            cuota_justa_evaluar = an['cuota_r']
        else:
            bloqueo_mercado = True
            st.error("🛑 **MERCADO CAPADO:** La casa de apuestas no ofrece estas líneas. **CERO RIESGO: NO APOSTAR.**")

    if not bloqueo_mercado:
        st.write("---")
        st.markdown(f"**Verificación de Cuota para:** `{mercado_evaluar}`")
        cuota_betplay = st.number_input(
            f"Ingresa la cuota actual en Betplay para '{mercado_evaluar}':", 
            min_value=1.01, max_value=20.0, value=1.75, step=0.01
        )
        
        st.write("---")
        st.markdown("### 🛡️ Diagnóstico de Seguridad Automático")
        st.write(f"- **Clima:** {st.session_state.get('reporte_clima')}")
        st.write(f"- **Nóminas:** {st.session_state.get('reporte_alineaciones')}")
        
        alertas_encontradas = st.session_state.get('alertas_auto', [])
        if alertas_encontradas:
            st.warning("**Alertas de riesgo detectadas:**\n" + "\n".join([f"• {a}" for a in alertas_encontradas]))
        else:
            st.success("🟢 **Filtro Limpio:** Cero riesgos detectados. Partido apto.")

        # --- SECCIÓN 3: VEREDICTO DE LA REGLA DE ORO ---
        st.divider()
        if st.button("⚡ EVALUAR Y APLICAR REGLA DE ORO"):
            prob_estimada = 1 / cuota_justa_evaluar
            ev = (prob_estimada * cuota_betplay) - 1
            
            st.subheader("3. Veredicto Final")
            
            if len(alertas_encontradas) > 0 or ev <= 0:
                st.error("DECISIÓN: NO APUESTO 🛑")
                st.write(f"**Razones del rechazo:**")
                if ev <= 0:
                    st.write(f"- La cuota en Betplay ({cuota_betplay}) no ofrece Valor Positivo (+EV) frente a la Cuota Justa ({cuota_justa_evaluar:.2f}).")
                if len(alertas_encontradas) > 0:
                    st.write(f"- Bloqueo por alertas activas:")
                    for al in alertas_encontradas:
                        st.write(f"  • {al}")
            else:
                st.success("DECISIÓN: APUESTO 🟢")
                st.write(f"**Mercado Validado:** {mercado_evaluar}")
                st.write(f"**Análisis de Valor (+EV):** Ventaja matemática positiva del +{ev*100:.1f}%.")
                st.write("**Entrada Sugerida:** 1 Unidad ($40.000 COP)")
                st.write(f"**Retorno Potencial:** ${40000 * cuota_betplay:,.0f} COP")

# --- BOTÓN DE REINICIO AUTOMÁTICO ---
st.divider()
if st.button("🔄 Analizar Otro Partido"):
    st.session_state.clear()
    st.rerun()
