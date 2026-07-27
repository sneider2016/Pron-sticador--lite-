import datetime
import math
import os
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests
import streamlit as st

# Manejo seguro de la librería de similitud
try:
    from rapidfuzz import fuzz
    def calcular_similitud(s1: str, s2: str) -> float:
        return fuzz.ratio(s1, s2)
except ImportError:
    from difflib import SequenceMatcher
    def calcular_similitud(s1: str, s2: str) -> float:
        return SequenceMatcher(None, s1, s2).ratio() * 100.0

# ==========================================
# CONFIGURACIÓN
# ==========================================
API_KEY = "3e69e51ac95c094a672f790edac978b0"
HOST = "v3.football.api-sports.io"
APP_NAME = "Pronósticador Élite Profesional"

# ==========================================
# FUNCIONES DE LIMPIEZA DE NOMBRES
# ==========================================
def normalizar(t: str) -> str:
    if not t:
        return ""
    t = unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode("utf-8").lower()
    basura = ["fc", "cd", "club", "sd", "ca", "s.a.", "deportivo", "atletico", "f.c.", "c.d.", "real"]
    palabras = [p for p in t.split() if p not in basura]
    return " ".join(palabras).strip() if palabras else t.strip().lower()

def limpiar_nombre_busqueda(t: str) -> str:
    if not t:
        return ""
    t_norm = normalizar(t)
    paises_y_sufijos = [
        "de argentina", "de brasil", "de colombia", "de uruguay", "de venezuela",
        "de mexico", "de chile", "de ecuador", "de peru", "de paraguay", "de bolivia",
        "de espana", "de inglaterra", "de italia", "de alemania", "de francia",
        "argentina", "brasil", "colombia", "uruguay", "venezuela", "mexico", "chile"
    ]
    for sufijo in paises_y_sufijos:
        if t_norm.endswith(sufijo):
            t_norm = t_norm[:-len(sufijo)].strip()
            break
    return t_norm if t_norm else t.strip()

def formatear_moneda(valor: float) -> str:
    return f"${valor:,.0f} COP"

# ==========================================
# MODELO MATCH
# ==========================================
@dataclass
class Match:
    fixture_id: Optional[int] = None
    league_id: Optional[int] = None
    season: Optional[int] = None
    liga: str = ""
    fecha: str = ""
    local: str = ""
    visitante: str = ""
    statistics: Dict = field(default_factory=dict)
    standings: Dict = field(default_factory=dict)
    h2h: List = field(default_factory=list)
    recent_form: Dict = field(default_factory=dict)
    injuries: List = field(default_factory=list)
    lineups: Dict = field(default_factory=dict)
    analyzed_markets: List = field(default_factory=list)
    market_ranking: List = field(default_factory=list)
    main_prediction: str = ""
    alternative_prediction: str = ""
    estimated_probability: float = 0.0
    fair_odds: float = 0.0
    confidence: float = 0.0
    risk: str = ""
    explanation: str = ""
    alerts: List[str] = field(default_factory=list)
    betplay_odds: Optional[float] = None
    expected_value: float = 0.0
    final_decision: str = ""

# ==========================================
# CLIENTE API FOOTBALL
# ==========================================
class FootballAPI:
    def __init__(self):
        self.headers = {
            "x-rapidapi-host": HOST,
            "x-rapidapi-key": API_KEY,
            "x-apisports-key": API_KEY
        }

    def consultar(self, endpoint: str, parametros: dict) -> list:
        url = f"https://{HOST}/{endpoint}"
        try:
            r = requests.get(url, headers=self.headers, params=parametros, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return data.get("response", [])
        except Exception:
            pass
        return []

    def buscar_equipo_por_nombre(self, nombre_equipo: str) -> dict:
        nombre_limpio = limpiar_nombre_busqueda(nombre_equipo)
        intentos = [nombre_limpio, nombre_equipo]
        palabras = nombre_limpio.split()
        if len(palabras) > 1:
            intentos.append(palabras[0])

        for q in intentos:
            if not q or len(q) < 3:
                continue
            res = self.consultar("teams", {"search": q})
            if res:
                mejor_eq = None
                max_s = 0
                q_norm = normalizar(q)
                for item in res:
                    t_info = item.get("team", {})
                    t_name = t_info.get("name", "")
                    score = calcular_similitud(q_norm, normalizar(t_name))
                    if score > max_s:
                        max_s = score
                        mejor_eq = t_info
                if mejor_eq:
                    return mejor_eq
                elif res:
                    return res[0].get("team")
        return None

    def buscar_partido_por_equipos(self, local: str, visitante: str, fecha: str):
        partidos = self.consultar("fixtures", {"date": fecha})
        norm_loc = normalizar(local)
        norm_vis = normalizar(visitante)

        if partidos:
            mejor_match = None
            max_score = 0
            for p in partidos:
                l_api = p.get("teams", {}).get("home", {}).get("name", "")
                v_api = p.get("teams", {}).get("away", {}).get("name", "")
                s1 = calcular_similitud(norm_loc, normalizar(l_api))
                s2 = calcular_similitud(norm_vis, normalizar(v_api))
                score = (s1 + s2) / 2.0
                if score > 40 and score > max_score:
                    max_score = score
                    mejor_match = p
            if mejor_match:
                return mejor_match

        eq_loc = self.buscar_equipo_por_nombre(local)
        eq_vis = self.buscar_equipo_por_nombre(visitante)

        h_id = eq_loc.get("id") if eq_loc else 0
        h_name = eq_loc.get("name") if eq_loc else local
        v_id = eq_vis.get("id") if eq_vis else 0
        v_name = eq_vis.get("name") if eq_vis else visitante

        return {
            "fixture": {"id": 0},
            "league": {"id": 0, "season": 2026},
            "teams": {
                "home": {"id": h_id, "name": h_name},
                "away": {"id": v_id, "name": v_name}
            },
            "encontrado_loc": eq_loc is not None,
            "encontrado_vis": eq_vis is not None
        }

    def ultimos_partidos(self, team_id: int, cantidad: int = 10) -> list:
        if not team_id:
            return []
        return self.consultar("fixtures", {"team": team_id, "last": cantidad})

    def head_to_head(self, local_id: int, visitante_id: int, cantidad: int = 10) -> list:
        if not local_id or not visitante_id:
            return []
        return self.consultar("fixtures/headtohead", {"h2h": f"{local_id}-{visitante_id}", "last": cantidad})

# ==========================================
# ANALIZADOR REAL
# ==========================================
class Analyzer:
    def __init__(self, api: FootballAPI):
        self.api = api

    def _procesar_historial(self, partidos: list, team_id: int) -> dict:
        if not partidos or not team_id:
            return {"datos_reales": False}

        gf_total, gc_total = 0.0, 0.0
        for p in partidos:
            teams = p.get("teams", {})
            goals = p.get("goals", {})
            es_local = teams.get("home", {}).get("id") == team_id
            g_favor = (goals.get("home") if goals.get("home") is not None else 0) if es_local else (goals.get("away") if goals.get("away") is not None else 0)
            g_contra = (goals.get("away") if goals.get("away") is not None else 0) if es_local else (goals.get("home") if goals.get("home") is not None else 0)
            gf_total += g_favor
            gc_total += g_contra

        cant = len(partidos)
        return {
            "datos_reales": True,
            "cant": cant,
            "gf": round(gf_total / cant, 2),
            "gc": round(gc_total / cant, 2)
        }

    def analizar(self, datos_partido: dict) -> dict:
        home_id = datos_partido.get("home_id", 0)
        away_id = datos_partido.get("away_id", 0)

        l10_h = self.api.ultimos_partidos(home_id, 10) if home_id else []
        l10_v = self.api.ultimos_partidos(away_id, 10) if away_id else []

        st_h = self._procesar_historial(l10_h, home_id)
        st_v = self._procesar_historial(l10_v, away_id)

        if not st_h.get("datos_reales") or not st_v.get("datos_reales"):
            return {"datos_reales_ok": False}

        h2h = self.api.head_to_head(home_id, away_id, 10) if (home_id and away_id) else []
        tot_h2h = 0.0
        if h2h:
            for m in h2h:
                gh = m.get("goals", {}).get("home") or 0
                ga = m.get("goals", {}).get("away") or 0
                tot_h2h += (gh + ga)
            prom_h2h = tot_h2h / len(h2h)
        else:
            prom_h2h = st_h["gf"] + st_v["gf"]

        return {
            "datos_reales_ok": True,
            "ataque_local": st_h["gf"],
            "defensa_local": st_h["gc"],
            "ataque_visitante": st_v["gf"],
            "defensa_visitante": st_v["gc"],
            "prom_goles_h2h": round(prom_h2h, 2),
            "h2h": h2h
        }

# ==========================================
# CÁLCULO PROBABILÍSTICO
# ==========================================
class ProbabilityCalculator:
    def __poisson(self, k: int, lam: float) -> float:
        return (math.pow(lam, k) * math.exp(-lam)) / math.factorial(k) if lam > 0 else (1.0 if k == 0 else 0.0)

    def calcular(self, ataque_local: float, defensa_local: float, ataque_visitante: float, defensa_visitante: float) -> dict:
        lambda_h = max(0.20, (ataque_local + defensa_visitante) / 2.0)
        lambda_v = max(0.20, (ataque_visitante + defensa_local) / 2.0)

        p_h, p_d, p_v = 0.0, 0.0, 0.0
        p_u15, p_o15, p_u25, p_o25, p_u35, p_btts = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

        for i in range(8):
            for j in range(8):
                p = self.__poisson(i, lambda_h) * self.__poisson(j, lambda_v)
                if i > j: p_h += p
                elif i == j: p_d += p
                else: p_v += p

                tot = i + j
                if tot < 1.5: p_u15 += p
                if tot >= 2: p_o15 += p
                if tot <= 2: p_u25 += p
                if tot >= 3: p_o25 += p
                if tot <= 3: p_u35 += p
                if i > 0 and j > 0: p_btts += p

        tot_p = max(0.001, p_h + p_d + p_v)
        p_h, p_d, p_v = p_h/tot_p, p_d/tot_p, p_v/tot_p

        p_1x = p_h + p_d
        p_x2 = p_v + p_d
        p_dnb_h = p_h / max(0.001, p_h + p_v)
        p_dnb_v = p_v / max(0.001, p_h + p_v)

        return {
            "lambda_local": round(lambda_h, 2),
            "lambda_visitante": round(lambda_v, 2),
            "exp_goles": round(lambda_h + lambda_v, 2),
            "local": round(p_h * 100.0, 1),
            "empate": round(p_d * 100.0, 1),
            "visitante": round(p_v * 100.0, 1),
            "doble_chance_1x": round(p_1x * 100.0, 1),
            "doble_chance_x2": round(p_x2 * 100.0, 1),
            "dnb_local": round(p_dnb_h * 100.0, 1),
            "dnb_visitante": round(p_dnb_v * 100.0, 1),
            "over15": round(p_o15 * 100.0, 1),
            "under25": round(p_u25 * 100.0, 1),
            "over25": round(p_o25 * 100.0, 1),
            "under35": round(p_u35 * 100.0, 1),
            "btts": round(p_btts * 100.0, 1),
            "confianza": 82.0
        }

# ==========================================
# VALOR ESPERADO
# ==========================================
class ValueAnalyzer:
    def cuota_justa(self, probabilidad: float) -> float:
        return round(100.0 / max(0.1, probabilidad), 2)

    def analizar(self, probabilidad: float, cuota: float) -> dict:
        p = probabilidad / 100.0
        ev = (p * cuota) - 1.0
        f_kelly = max(0.0, (p * (cuota - 1.0) - (1.0 - p)) / max(0.01, cuota - 1.0)) * 0.25
        return {
            "ev": round(ev, 4),
            "ev_porcentaje": round(ev * 100.0, 1),
            "decision": "🟢 APOSTAR (+EV)" if ev > 0.0 else "🛑 NO APOSTAR",
            "kelly_stake_pct": round(f_kelly * 100.0, 2)
        }

# ==========================================
# MOTOR SALM
# ==========================================
class SALMEngine:
    def __init__(self):
        self.api = FootballAPI()
        self.analyzer = Analyzer(api=self.api)
        self.probability = ProbabilityCalculator()
        self.value = ValueAnalyzer()

    def evaluar_betplay(self, probabilidad: float, cuota: float) -> dict:
        return self.value.analizar(probabilidad, cuota)

    def ejecutar_analisis_completo(self, local: str, visitante: str, fecha: str, liga: str) -> Match:
        fix = self.api.buscar_partido_por_equipos(local, visitante, fecha)

        h_id = fix["teams"]["home"]["id"] if fix else 0
        v_id = fix["teams"]["away"]["id"] if fix else 0
        loc_name = fix["teams"]["home"]["name"] if fix else local
        vis_name = fix["teams"]["away"]["name"] if fix else visitante

        datos_partido = {"home_id": h_id, "away_id": v_id}
        analisis_raw = self.analyzer.analizar(datos_partido)

        if not analisis_raw.get("datos_reales_ok"):
            return Match(
                local=loc_name,
                visitante=vis_name,
                main_prediction="🛑 SIN DATOS REALES EN API-FOOTBALL",
                market_ranking=[{"m": "Sin datos", "p": 0.0, "c": 999.0, "r": "Alto", "razon": "No se obtuvieron partidos de la API."}],
                explanation=f"**Atención:** No fue posible obtener el historial de partidos reales para **{local}** o **{visitante}** desde API-Football. Por favor simplifica el nombre (ej. escribe 'Tigre' o 'Santos') o verifica el cupo de tu API Key.",
                alerts=[f"🛑 API Error: No se halló historial para '{local}' o '{visitante}'."]
            )

        probs = self.probability.calcular(
            analisis_raw["ataque_local"],
            analisis_raw["defensa_local"],
            analisis_raw["ataque_visitante"],
            analisis_raw["defensa_visitante"]
        )

        pf_h = analisis_raw["ataque_local"]
        pc_h = analisis_raw["defensa_local"]
        pf_v = analisis_raw["ataque_visitante"]
        pc_v = analisis_raw["defensa_visitante"]

        exp_g = probs["exp_goles"]
        prom_h2h = analisis_raw["prom_goles_h2h"]

        candidatos = []
        if probs["doble_chance_1x"] >= 62.0:
            candidatos.append({"m": f"Gana o Empata {loc_name} (Doble Chance 1X)", "p": probs["doble_chance_1x"], "r": "Bajo", "razon": f"Sólida cobertura local ({probs['doble_chance_1x']}% prob)."})
        if probs["doble_chance_x2"] >= 62.0:
            candidatos.append({"m": f"Gana o Empata {vis_name} (Doble Chance X2)", "p": probs["doble_chance_x2"], "r": "Bajo", "razon": f"Cobertura visitante ({probs['doble_chance_x2']}% prob)."})
        if probs["over15"] >= 68.0:
            candidatos.append({"m": "Más de 1.5 Goles Totales en el Partido", "p": probs["over15"], "r": "Bajo", "razon": f"Expectativa Poisson de {exp_g:.2f} goles."})
        if probs["under35"] >= 72.0:
            candidatos.append({"m": "Menos de 3.5 Goles Totales", "p": probs["under35"], "r": "Bajo", "razon": f"Ritmo controlado ({probs['under35']}% prob)."})
        if probs["btts"] >= 52.0:
            candidatos.append({"m": "Ambos Equipos Anotan (Sí)", "p": probs["btts"], "r": "Bajo-Medio", "razon": f"Conversión mutual ({probs['btts']}% BTTS)."})

        candidatos.sort(key=lambda x: x["p"], reverse=True)

        for cand in candidatos:
            cand["c"] = self.value.cuota_justa(cand["p"])

        p_top = candidatos[0] if candidatos else {"m": "Menos de 3.5 Goles Totales", "p": probs["under35"], "c": 1.30, "r": "Bajo", "razon": "Seguridad."}
        s_top = candidatos[1] if len(candidatos) > 1 and candidatos[1]["m"] != p_top["m"] else (candidatos[2] if len(candidatos) > 2 else p_top)

        arg = (
            f"**1. Rendimiento Real API-Football:** {loc_name} ({pf_h:.2f} GF / {pc_h:.2f} GC) vs {vis_name} ({pf_v:.2f} GF / {pc_v:.2f} GC).\n\n"
            f"**2. Proyección Poisson:** Gol Local: {probs['lambda_local']:.2f} | Gol Visita: {probs['lambda_visitante']:.2f} (Total: {exp_g:.2f} goles esperados).\n\n"
            f"**3. Historial H2H Real:** Promedio H2H de {prom_h2h:.1f} goles en sus enfrentamientos directos.\n\n"
            f"**4. Dictamen Multimercado Exclusivo:** {p_top['razon']}"
        )

        return Match(
            local=loc_name,
            visitante=vis_name,
            market_ranking=candidatos,
            main_prediction=p_top["m"],
            alternative_prediction=s_top["m"],
            explanation=arg
        )

# ==========================================
# STREAMLIT UI
# ==========================================
st.set_page_config(page_title="Pronosticador Élite App", page_icon="⚽", layout="centered")
st.title("⚽ PRONOSTICADOR ÉLITE 90%")
st.caption(f"{APP_NAME} — Motor Quirúrgico Multimercado")
st.divider()

engine = SALMEngine()

st.subheader("1. Configuración del Partido")

# Lista ampliada de ligas con Libertadores y Sudamericana
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
    "Copa Libertadores 🏆",
    "Copa Sudamericana 🏆",
    "Liga Profesional Argentina 🇦🇷",
    "Brasileirão Série A 🇧🇷",
    "Liga MX 🇲🇽",
    "MLS 🇺🇸",
    "Otra liga"
]

c1, c2 = st.columns(2)
with c1:
    liga_sel = st.selectbox("Liga", LISTA_LIGAS)
    liga = st.text_input("Nombre:", value="Otra Liga") if liga_sel == "Otra liga" else liga_sel
    local = st.text_input("Equipo Local", value="Deportivo Cali")
with c2:
    fecha_consulta = st.date_input("Fecha", datetime.date.today())
    visitante = st.text_input("Equipo Visitante", value="Jaguares")

if st.button("🔎 Generar Análisis Quirúrgico Completo"):
    st.session_state.clear()
    with st.spinner("Consultando API-Football e Inteligencia IA SALM..."):
        f_str = fecha_consulta.strftime("%Y-%m-%d")
        partido_analizado = engine.ejecutar_analisis_completo(local, visitante, f_str, liga)
        st.session_state["analizado"] = True
        st.session_state["match"] = partido_analizado

if st.session_state.get("analizado", False):
    st.divider()
    match = st.session_state["match"]
    ranking = match.market_ranking

    p_top = ranking[0]
    s_top = ranking[1] if len(ranking) > 1 else ranking[0]

    st.subheader("2. Dictamen del Pronosticador Élite")

    if match.alerts:
        st.markdown("### 📋 Alertas de Datos")
        for al in match.alerts:
            st.error(al)
        st.write("---")

    st.markdown("### 🔬 Argumentación Táctica Completa")
    st.markdown(match.explanation)
    st.write("---")

    if p_top["p"] > 0:
        st.success(f"🟢 **PRONÓSTICO PRINCIPAL**\n\n**Mercado:** {p_top['m']}\n\n**Cuota Justa:** {p_top['c']:.2f} | **Prob. Real:** {p_top['p']:.1f}%\n\n**Riesgo:** {p_top['r']}")
        st.info(f"🟡 **PRONÓSTICO SECUNDARIO**\n\n**Mercado:** {s_top['m']}\n\n**Cuota Justa:** {s_top['c']:.2f} | **Prob. Real:** {s_top['p']:.1f}%\n\n**Riesgo:** {s_top['r']}")

        st.write("---")
        st.markdown("### 🎯 Verificación en Betplay")
        opcion = st.radio("Mercado a evaluar:", [f"Principal: {p_top['m']}", f"Secundario: {s_top['m']}"], key="rad_m")
        target_market = p_top if "Principal" in opcion else s_top

        c_betplay = st.number_input(f"Cuota actual en Betplay para '{target_market['m']}':", min_value=1.01, max_value=20.0, value=1.75, step=0.01, key="in_c")
        if st.button("⚡ EVALUAR Y APLICAR REGLA DE ORO"):
            eval_res = engine.evaluar_betplay(target_market["p"], c_betplay)
            st.subheader("3. Veredicto Final")
            if eval_res["ev"] <= 0:
         
