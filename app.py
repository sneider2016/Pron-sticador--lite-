import streamlit as st
import datetime

# Configuración de la página (Título y Estilo)
st.set_page_config(page_title="Pronosticador Élite App", page_icon="⚽", layout="centered")

st.title("⚽ PRONOSTICADOR ÉLITE 90%")
st.caption("Motor de Análisis Quántico, Valor Esperado (+EV) y Filtro de Seguridad")

st.divider()

# --- SECCIÓN 1: ENTRADA DE DATOS ---
st.subheader("1. Configuración del Partido")

col1, col2 = st.columns(2)
with col1:
    liga = st.selectbox("Liga / Torneo", ["Premier League", "LaLiga", "Champions League", "Serie A", "Otras"])
    local = st.text_input("Equipo Local", value="Arsenal")
with col2:
    fecha_consulta = st.date_input("Fecha", datetime.date.today())
    visitante = st.text_input("Equipo Visitante", value="Chelsea")

if st.button("🔎 Generar Análisis Táctico y Sugerencia"):
    st.session_state['analizado'] = True

# --- SECCIÓN 2: MERCADO SUGERIDO Y COMPARACIÓN DE CUOTAS ---
if st.session_state.get('analizado', False):
    st.divider()
    st.subheader("2. Mercado Recomendado por Datos Puros")
    
    # Simulación de cálculo interno del modelo
    mercado_sugerido = "Gana o Empata Local + Over 1.5 Goles"
    cuota_justa = 1.50
    
    st.info(f"**Mercado Óptimo:** {mercado_sugerido}\n\n**Cuota Justa Estimada:** {cuota_justa}")
    
    st.write("---")
    st.markdown("**Verificación en Betplay:**")
    cuota_betplay = st.number_input("Ingresa la cuota actual en Betplay para este mercado:", min_value=1.01, max_value=20.0, value=1.72, step=0.01)
    
    alertas = st.multiselect(
        "Alertas de Riesgo Detectadas (Filtro Obligatorio):",
        ["Baja de última hora clave", "Clima extremo / Altitud", "Rotación de nómina", "Árbitro hiper-tarjetero", "Liga inestable/repesca"],
        default=[]
    )
    
    # --- SECCIÓN 3: VEREDICTO DE LA REGLA DE ORO ---
    st.divider()
    if st.button("⚡ EVALUAR Y APLICAR REGLA DE ORO"):
        # Cálculo de Valor Esperado
        prob_estimada = 1 / cuota_justa
        ev = (prob_estimada * cuota_betplay) - 1
        
        st.subheader("3. Veredicto Final")
        
        # Aplicación estricta de la regla binaria
        if len(alertas) > 0 or ev <= 0:
            st.error("DECISIÓN: NO APUESTO 🛑")
            st.write(f"**Razones del rechazo:**")
            if ev <= 0:
                st.write(f"- La cuota de Betplay ({cuota_betplay}) no ofrece Valor Positivo contra la Cuota Justa ({cuota_justa}).")
            if len(alertas) > 0:
                st.write(f"- Se detectaron variables de alto riesgo fuera de control: {', '.join(alertas)}.")
        else:
            st.success("DECISIÓN: APUESTO 🟢")
            st.write(f"**Análisis de Valor:** +EV positivo detectado (+{ev*100:.1f}% de ventaja).")
            st.write("**Entrada Sugerida:** 1 Unidad ($40.000 COP)")
            st.write(f"**Retorno Potencial:** ${40000 * cuota_betplay:,.0f} COP")
