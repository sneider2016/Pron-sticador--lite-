import datetime
import streamlit as st
from engine.salm_engine import SALMEngine
from config import APP_NAME, VERSION

# Configuración de Streamlit
st.set_page_config(page_title="Pronosticador Élite App", page_icon="⚽", layout="centered")
st.title("⚽ PRONOSTICADOR ÉLITE")
st.caption(f"{APP_NAME} — {VERSION}")
st.divider()

# Instancia global del motor
@st.cache_resource
def obtener_engine():
    return SALMEngine()

engine = obtener_engine()

# Función con Caché para evitar consumo repetido de API
@st.cache_data(ttl=900, show_spinner=False)
def ejecutar_analisis_cached(_engine, local: str, visitante: str, fecha: str, liga: str):
    return _engine.ejecutar_analisis_completo(local, visitante, fecha, liga)

st.subheader("1. Configuración del Partido")

LISTA_LIGAS = [
    "Liga BetPlay 🇨🇴", "Premier League 🇬🇧", "LaLiga 🇪🇸", "Serie A 🇮🇹", "Bundesliga 🇩🇪", "Ligue 1 🇫🇷",
    "UEFA Champions League 🏆", "UEFA Europa League 🏆", "UEFA Conference League 🏆", "Copa Libertadores 🏆",
    "Copa Sudamericana 🏆", "Liga Profesional Argentina 🇦🇷", "Brasileirão Série A 🇧🇷", "Liga MX 🇲🇽", "MLS 🇺🇸", "Otra liga"
]

c1, c2 = st.columns(2)
with c1:
    liga_sel = st.selectbox("Liga", LISTA_LIGAS)
    liga = st.text_input("Nombre:", value="Otra Liga") if liga_sel == "Otra liga" else liga_sel
    local = st.text_input("Equipo Local", value="Tigre")
with c2:
    fecha_consulta = st.date_input("Fecha", datetime.date.today())
    visitante = st.text_input("Equipo Visitante", value="Racing Club")

if st.button("🔎 Generar Análisis Quirúrgico Completo"):
    st.session_state.clear()
    with st.spinner("Consultando alineaciones, estadísticas reales e Inteligencia IA SALM..."):
        f_str = fecha_consulta.strftime("%Y-%m-%d")
        st.session_state["match"] = ejecutar_analisis_cached(engine, local, visitante, f_str, liga)
        st.session_state["analizado"] = True

if st.session_state.get("analizado", False):
    st.divider()
    m = st.session_state["match"]
    ranking = m.market_ranking

    if st.button("🔄 Realizar Nueva Búsqueda", key="btn_top"):
        st.session_state.clear()
        st.rerun()

    st.subheader("2. Dictamen del Pronosticador Élite")

    if m.alerts:
        st.markdown("### 📋 Auditoría de Alineaciones & Alertas de Datos")
        for al in m.alerts:
            if "✅" in al:
                st.info(al)
            elif "⚠️" in al:
                st.warning(al)
            else:
                st.error(al)
        st.write("---")

    st.markdown("### 🔬 Argumentación Táctica Completa")
    st.markdown(m.explanation)
    st.write("---")

    p_top = ranking[0] if ranking else {"m": "N/A", "p": 0.0, "c": 999.0, "r": "N/A", "razon": "N/A"}
    s_top = ranking[1] if len(ranking) > 1 else p_top

    if p_top["p"] > 0:
        st.success(f"🟢 **PRONÓSTICO PRINCIPAL**\n\n**Mercado:** {p_top['m']}\n\n**Cuota Justa:** {p_top['c']:.2f} | **Prob. Real:** {p_top['p']:.1f}%\n\n**Riesgo:** {p_top['r']}\n\n💡 **{p_top['razon']}**")
        st.info(f"🟡 **PRONÓSTICO SECUNDARIO**\n\n**Mercado:** {s_top['m']}\n\n**Cuota Justa:** {s_top['c']:.2f} | **Prob. Real:** {s_top['p']:.1f}%\n\n**Riesgo:** {s_top['r']}\n\n💡 **{s_top['razon']}**")

        st.write("---")
        st.markdown("### 🎯 Verificación en Betplay")
        opcion = st.radio("Mercado a evaluar:", [f"Principal: {p_top['m']}", f"Secundario: {s_top['m']}"], key="rad_m")
        target_m = p_top if "Principal" in opcion else s_top

        c_betplay = st.number_input(f"Cuota actual en Betplay para '{target_m['m']}':", min_value=1.01, max_value=20.0, value=1.75, step=0.01, key="in_c")
        if st.button("⚡ EVALUAR Y APLICAR REGLA DE ORO"):
            eval_res = engine.evaluar_betplay(target_m["p"], c_betplay)
            st.subheader("3. Veredicto Final")
            if eval_res["ev"] <= 0:
                st.error(f"DECISIÓN: {eval_res['decision']}\n\n- Cuota Justa calculada: {eval_res['cuota_justa']}\n- Cuota Betplay ingresada: {c_betplay}\n- La cuota no ofrece Valor Positivo (EV: {eval_res['ev_porcentaje']}%).")
            else:
                st.success(f"DECISIÓN: {eval_res['decision']}")
                st.write(f"**Ventaja +EV:** +{eval_res['ev_porcentaje']}%")
                st.write(f"**Stake Recomendado (1/4 Kelly):** {eval_res['kelly_stake_pct']}% del Bankroll")
                if eval_res['stake_sugerido_cop'] > 0:
                    st.write(f"**Monto Sugerido (Base COP):** ${eval_res['stake_sugerido_cop']:,} COP")

    st.divider()
    if st.button("🔄 Analizar Otro Partido", key="btn_bot"):
        st.session_state.clear()
        st.rerun()
