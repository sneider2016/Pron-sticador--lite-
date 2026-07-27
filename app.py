import datetime
import os
import sys

# Agregar la raíz del proyecto a sys.path para habilitar la importación de carpetas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import streamlit as st
from config import APP_NAME
from utils.helpers import formatear_moneda

# Importación del motor SALM desde engine/salm_engine.py
try:
    from engine.salm_engine import SALMEngine
except ModuleNotFoundError:
    try:
        from salm_engine import SALMEngine
    except ModuleNotFoundError as err:
        st.error(
            f"⚠️ No se pudo cargar 'engine/salm_engine.py'. "
            f"Verifica la estructura de archivos en GitHub. Detalle: {err}"
        )
        st.stop()

st.set_page_config(page_title="Pronosticador Élite App", page_icon="⚽", layout="centered")
st.title("⚽ PRONOSTICADOR ÉLITE 90%")
st.caption(f"{APP_NAME} — Motor Quirúrgico Multimercado: Goles, Córneres, Tarjetas, H2H y +EV")
st.divider()

engine = SALMEngine()

# SECCIÓN 1: Configuración del Partido
st.subheader("1. Configuración del Partido")

# Lista de ligas configuradas
LISTA_LIGAS = [
    "Liga BetPlay 🇨🇴",
    "Premier League 🇬🇧",
    "LaLiga 🇪🇸",
    "Serie A 🇮🇹",
    "Bundesliga 🇩🇪",
    "Ligue 1 🇫🇷",
    "UEFA Champions League 🏆",
    "UEFA Europa League 🏆",
    "UEFA Conference League 🏆",
    "Liga Profesional Argentina 🇦🇷",
    "Brasileirão Série A 🇧🇷",
    "Liga MX 🇲🇽",
    "MLS 🇺🇸",
    "Otra liga"
]

c1, c2 = st.columns(2)
with c1:
    liga_seleccionada = st.selectbox("Liga", LISTA_LIGAS)
    
    # Campo dinámico si el usuario escoge 'Otra liga'
    if liga_seleccionada == "Otra liga":
        liga = st.text_input("Nombre de la Liga:", value="Otra Liga")
    else:
        liga = liga_seleccionada

    local = st.text_input("Equipo Local", value="Deportivo Cali")

with c2:
    fecha_consulta = st.date_input("Fecha", datetime.date.today())
    visitante = st.text_input("Equipo Visitante", value="Jaguares")

if st.button("🔎 Generar Análisis Quirúrgico Completo"):
    st.session_state.clear()
    with st.spinner("Consultando estadísticas reales e Inteligencia IA SALM..."):
        f_str = fecha_consulta.strftime("%Y-%m-%d")
        partido_analizado = engine.ejecutar_analisis_completo(local, visitante, f_str, liga)

        st.session_state["analizado"] = True
        st.session_state["match"] = partido_analizado

# SECCIÓN 2 Y 3: Dictamen y Verificación
if st.session_state.get("analizado", False):
    st.divider()
    match = st.session_state["match"]
    ranking = match.market_ranking

    p_top = ranking[0]
    s_top = ranking[1] if len(ranking) > 1 else ranking[0]

    st.subheader("2. Dictamen del Pronosticador Élite")
    st.markdown("### 🔬 Argumentación Táctica Completa")
    st.markdown(match.explanation)
    st.write("---")

    st.success(
        f"🟢 **PRONÓSTICO PRINCIPAL (Riesgo Bajo)**\n\n"
        f"**Mercado:** {p_top['m']}\n\n"
        f"**Cuota Justa:** {p_top['c']:.2f} | **Prob. Real:** {p_top['p']:.1f}%\n\n"
        f"**Riesgo:** {p_top['r']}"
    )

    st.info(
        f"🟡 **PRONÓSTICO SECUNDARIO (Riesgo Bajo-Medio)**\n\n"
        f"**Mercado:** {s_top['m']}\n\n"
        f"**Cuota Justa:** {s_top['c']:.2f} | **Prob. Real:** {s_top['p']:.1f}%\n\n"
        f"**Riesgo:** {s_top['r']}"
    )

    st.write("---")
    st.markdown("### 🎯 Verificación en Betplay")

    opcion = st.radio(
        "Mercado a evaluar:",
        [f"Principal: {p_top['m']}", f"Secundario: {s_top['m']}"],
        key="rad_m",
    )

    es_principal = "Principal" in opcion
    target_market = p_top if es_principal else s_top

    disponible = st.radio(
        f"¿'{target_market['m']}' disponible en Betplay?",
        ["Sí, está disponible", "No está disponible"],
        key="rad_d",
    )

    if disponible == "Sí, está disponible":
        c_betplay = st.number_input(
            f"Cuota actual en Betplay para '{target_market['m']}':",
            min_value=1.01,
            max_value=20.0,
            value=1.75,
            step=0.01,
            key="in_c",
        )

        st.divider()
        if st.button("⚡ EVALUAR Y APLICAR REGLA DE ORO"):
            eval_res = engine.evaluar_betplay(target_market["p"], c_betplay)

            st.subheader("3. Veredicto Final")
            if eval_res["ev"] <= 0:
                st.error("DECISIÓN: NO APUESTO 🛑")
                st.write(
                    f"- La cuota en Betplay ({c_betplay}) no ofrece Valor Positivo (+EV) frente a la Cuota Justa ({target_market['c']:.2f})."
                )
            else:
                st.success(f"DECISIÓN: {eval_res['decision']}")
                st.write(f"**Mercado Validado:** {target_market['m']}")
                st.write(f"**Análisis de Valor (+EV):** Ventaja matemática del +{eval_res['ev_porcentaje']}%.")
                st.write("**Entrada Sugerida:** 1 Unidad ($40.000 COP)")
                st.write(f"**Retorno Potencial:** {formatear_moneda(40000 * c_betplay)}")
    else:
        st.error("🛑 MERCADO NO DISPONIBLE en Betplay. Evalúa la otra opción o descarta el partido.")

st.divider()
if st.button("🔄 Analizar Otro Partido"):
    st.session_state.clear()
    st.rerun()
