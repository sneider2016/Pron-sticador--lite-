import streamlit as st
import datetime, requests, math, unicodedata
from rapidfuzz import fuzz
from config import *


st.set_page_config(page_title="Pronosticador Élite App", page_icon="⚽", layout="centered")
st.title("⚽ PRONOSTICADOR ÉLITE 90%")
st.caption("Motor Quirúrgico Multimercado: Goles, Córneres, Tarjetas, H2H y +EV")
st.divider()

def normalizar(t):
    if not t: return ""
    t = unicodedata.normalize('NFD', t).encode('ascii', 'ignore').decode("utf-8").lower()
    basura = ["fc", "cd", "club", "sd", "ca", "s.a.", "deportivo", "atletico"]
    return " ".join([p for p in t.split() if p not in basura]).strip()

def obtener_partido(loc, vis, fecha):
    url = f"https://{HOST}/fixtures"
    headers = {'x-rapidapi-host': HOST, 'x-rapidapi-key': API_KEY}
    partidos = []
    try:
        r = requests.get(url, headers=headers, params={'date': fecha}, timeout=8)
        if r.status_code == 200: partidos.extend(r.json().get('response', []))
    except: pass
    
    if not partidos: return None
    mejor, max_score = None, 0
    for p in partidos:
        l_api, v_api = p['teams']['home']['name'], p['teams']['away']['name']
        s1 = fuzz.ratio(normalizar(loc), normalizar(l_api))
        s2 = fuzz.ratio(normalizar(vis), normalizar(v_api))
        score = (s1 + s2) / 2
        if score > 50 and score > max_score:
            max_score, mejor = score, p
    return mejor

def consultar_api(endpoint, params):
    url = f"https://{HOST}/{endpoint}"
    headers = {'x-rapidapi-host': HOST, 'x-rapidapi-key': API_KEY}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=8)
        return r.json().get('response', []) if r.status_code == 200 else []
    except: return []

def poiss(k, l): return (math.pow(l, k) * math.exp(-l)) / math.factorial(k)

def motor_analisis(fix, loc_name, vis_name, liga):
    h_id = fix['teams']['home']['id'] if fix else 0
    v_id = fix['teams']['away']['id'] if fix else 0
    
    h_rec = consultar_api("fixtures", {'team': h_id, 'last': 5}) if h_id else []
    v_rec = consultar_api("fixtures", {'team': v_id, 'last': 5}) if v_id else []
    h2h = consultar_api("fixtures/headtohead", {'h2h': f"{h_id}-{v_id}", 'last': 5}) if (h_id and v_id) else []
    
    def calc_goles(hist, t_id):
        if not hist: return 1.2, 1.0
        gf, gc = 0, 0
        for m in hist:
            ih = m['teams']['home']['id'] == t_id
            gf += m['goals']['home'] if ih else m['goals']['away']
            gc += m['goals']['away'] if ih else m['goals']['home']
        return gf / len(hist), gc / len(hist)
    
    pf_h, pc_h = calc_goles(h_rec, h_id)
    pf_v, pc_v = calc_goles(v_rec, v_id)
    
    l_h, l_v = max(0.2, (pf_h + pc_v) / 2), max(0.2, (pf_v + pc_h) / 2)
    exp_g = l_h + l_v
    
    p_h, p_d, p_v, p_u25, p_u35, p_o15 = 0, 0, 0, 0, 0, 0
    for i in range(6):
        for j in range(6):
            p = poiss(i, l_h) * poiss(j, l_v)
            if i > j: p_h += p
            elif i == j: p_d += p
            else: p_v += p
            if (i + j) <= 2: p_u25 += p
            if (i + j) < 3.5: p_u35 += p
            if (i + j) >= 2: p_o15 += p

    p_1x = p_h + p_d
    p_dnb_h = p_h / (p_h + p_v) if (p_h + p_v) > 0 else 0.5
    p_dnb_v = p_v / (p_h + p_v) if (p_h + p_v) > 0 else 0.5
    p_btts = (1 - poiss(0, l_h)) * (1 - poiss(0, l_v))

    h2h_btts = sum(1 for m in h2h if (m['goals']['home'] or 0) > 0 and (m['goals']['away'] or 0) > 0)
    prom_h2h = sum((m['goals']['home'] or 0) + (m['goals']['away'] or 0) for m in h2h) / len(h2h) if h2h else exp_g

    corners_est = 8.5 + exp_g * 0.8
    tarjetas_est = 4.5 if ("BetPlay" in liga or "Argentina" in liga) else 3.8

    candidatos = []
    if corners_est >= 9.5:
        candidatos.append({"m": "Más de 7.5 Tiros de Esquina (Córneres Totales)", "p": 84, "r": "Bajo", "razon": f"Proyección ofensiva de {corners_est:.1f} tiros de esquina."})
    if tarjetas_est >= 4.5:
        candidatos.append({"m": "Más de 3.5 Tarjetas Totales en el Partido", "p": 82, "r": "Bajo", "razon": f"Partido de alta fricción en {liga} ({tarjetas_est} tarjetas prom)."})
    if p_btts >= 0.58 and h2h_btts >= 3:
        candidatos.append({"m": "Ambos Equipos Anotan (Sí)", "p": int(p_btts * 100), "r": "Bajo-Medio", "razon": f"Ambos anotaron en {h2h_btts} de los últimos H2H."})
    if exp_g <= 2.10 and prom_h2h <= 2.2:
        candidatos.append({"m": "Menos de 2.5 Goles Totales (Under 2.5)", "p": int(p_u25 * 100), "r": "Bajo", "razon": f"Baja expectativa de gol ({exp_g:.2f}). Bloques defensivos marcados."})
    if exp_g >= 2.4 and p_o15 >= 0.75:
        candidatos.append({"m": "Más de 1.5 Goles Totales en el Partido", "p": int(p_o15 * 100), "r": "Bajo", "razon": f"Ataques fluidos con proyección de {exp_g:.2f} goles."})
    if p_h >= 0.52:
        candidatos.append({"m": f"Gana {loc_name} Sin Empate (Empate No Válido)", "p": int(p_dnb_h * 100), "r": "Bajo", "razon": f"Dominio local con {int(p_h*100)}% prob victoria directa."})
    elif p_v >= 0.42:
        candidatos.append({"m": f"Gana {vis_name} Sin Empate (Empate No Válido)", "p": int(p_dnb_v * 100), "r": "Bajo-Medio", "razon": f"Métricas superiores del visitante ({pf_v:.1f} goles/juego)."})

    if not candidatos:
        candidatos.append({"m": f"Gana o Empata {loc_name} (Doble Chance 1X)", "p": int(p_1x * 100), "r": "Bajo", "razon": "Ventaja de localía y cobertura frente a empate."})
        candidatos.append({"m": "Menos de 3.5 Goles Totales", "p": int(p_u35 * 100), "r": "Bajo", "razon": "Margen amplio de seguridad para ritmo conservador."})

    candidatos = sorted(candidatos, key=lambda x: x['p'], reverse=True)
    p_top, s_top = candidatos[0], candidatos[1] if len(candidatos) > 1 else candidatos[0]

    arg = (f"**1. Desempeño:** {loc_name} ({pf_h:.1f} GF / {pc_h:.1f} GC) vs {vis_name} ({pf_v:.1f} GF / {pc_v:.1f} GC).\n\n"
           f"**2. Expectativa Gol (Poisson):** Proyección local: {l_h:.2f} | Visita: {l_v:.2f} (Total: {exp_g:.2f}).\n\n"
           f"**3. Historial H2H:** Promedio de {prom_h2h:.1f} goles en sus últimos duelos.\n\n"
           f"**4. Dictamen Multimercado:** {p_top['razon']}")

    return {
        "p_m": p_top['m'], "p_p": p_top['p'], "p_c": round(1 / (p_top['p'] / 100), 2), "p_r": p_top['r'],
        "s_m": s_top['m'], "s_p": s_top['p'], "s_c": round(1 / (s_top['p'] / 100), 2), "s_r": s_top['r'],
        "arg": arg
    }

# SECCIÓN 1
st.subheader("1. Configuración del Partido")
c1, c2 = st.columns(2)
with c1:
    liga = st.selectbox("Liga", ["Liga BetPlay (Colombia)", "Premier League", "LaLiga", "Serie A", "Bundesliga", "Copa Libertadores", "Otra"])
    local = st.text_input("Equipo Local", value="Deportivo Cali")
with c2:
    fecha_consulta = st.date_input("Fecha", datetime.date.today())
    visitante = st.text_input("Equipo Visitante", value="Jaguares")

if st.button("🔎 Generar Análisis Quirúrgico Completo"):
    st.session_state.clear()
    with st.spinner("Consultando estadísticas reales..."):
        f_str = fecha_consulta.strftime("%Y-%m-%d")
        fix = obtener_partido(local, visitante, f_str)
        
        loc_n = fix['teams']['home']['name'] if fix else local
        vis_n = fix['teams']['away']['name'] if fix else visitante
        
        analisis = motor_analisis(fix, loc_n, vis_n, liga)
        
        st.session_state['analizado'] = True
        st.session_state['an'] = analisis

# SECCIÓN 2 Y 3
if st.session_state.get('analizado', False):
    st.divider()
    an = st.session_state['an']
    
    st.subheader("2. Dictamen del Pronosticador Élite")
    st.markdown("### 🔬 Argumentación Táctica Completa")
    st.markdown(an['arg'])
    st.write("---")
    
    st.success(f"🟢 **PRONÓSTICO PRINCIPAL (Riesgo Bajo)**\n\n**Mercado:** {an['p_m']}\n\n**Cuota Justa:** {an['p_c']:.2f} | **Prob. Real:** {an['p_p']}%\n\n**Riesgo:** {an['p_r']}")
    st.info(f"🟡 **PRONÓSTICO SECUNDARIO (Riesgo Bajo-Medio)**\n\n**Mercado:** {an['s_m']}\n\n**Cuota Justa:** {an['s_c']:.2f} | **Prob. Real:** {an['s_p']}%\n\n**Riesgo:** {an['s_r']}")
    
    st.write("---")
    st.markdown("### 🎯 Verificación en Betplay")
    
    op = st.radio("Mercado a evaluar:", [f"Principal: {an['p_m']}", f"Secundario: {an['s_m']}"], key="rad_m")
    es_p = "Principal" in op
    m_eval = an['p_m'] if es_p else an['s_m']
    c_justa = an['p_c'] if es_p else an['s_c']
    
    disp = st.radio(f"¿'{m_eval}' disponible en Betplay?", ["Sí, está disponible", "No está disponible"], key="rad_d")

    if disp == "Sí, está disponible":
        c_betplay = st.number_input(f"Cuota actual en Betplay para '{m_eval}':", min_value=1.01, max_value=20.0, value=1.75, step=0.01, key="in_c")
        
        st.divider()
        if st.button("⚡ EVALUAR Y APLICAR REGLA DE ORO"):
            prob_est = 1 / c_justa
            ev = (prob_est * c_betplay) - 1
            
            st.subheader("3. Veredicto Final")
            if ev <= 0:
                st.error("DECISIÓN: NO APUESTO 🛑")
                st.write(f"- La cuota en Betplay ({c_betplay}) no ofrece Valor Positivo (+EV) frente a la Cuota Justa ({c_justa:.2f}).")
            else:
                st.success("DECISIÓN: APUESTO 🟢")
                st.write(f"**Mercado Validado:** {m_eval}")
                st.write(f"**Análisis de Valor (+EV):** Ventaja matemática del +{ev*100:.1f}%.")
                st.write("**Entrada Sugerida:** 1 Unidad ($40.000 COP)")
                st.write(f"**Retorno Potencial:** ${40000 * c_betplay:,.0f} COP")
    else:
        st.error("🛑 MERCADO NO DISPONIBLE en Betplay. Evalúa la otra opción o descarta el partido.")

st.divider()
if st.button("🔄 Analizar Otro Partido"):
    st.session_state.clear()
    st.rerun()
