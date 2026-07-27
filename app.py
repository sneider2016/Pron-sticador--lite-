import datetime, math, os, sys, unicodedata, requests
import streamlit as st
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Similitud de texto
try:
    from rapidfuzz import fuzz
    def similitud(s1: str, s2: str) -> float:
        return float(fuzz.ratio(s1, s2))
except ImportError:
    from difflib import SequenceMatcher
    def similitud(s1: str, s2: str) -> float:
        return float(SequenceMatcher(None, s1, s2).ratio() * 100.0)

# CONFIGURACIÓN DE CLAVES
API_KEYS_BASE = [
    "14db0e108529faed46c94b3163188df5",
    "3e69e51ac95c094a672f790edac978b0"
]
HOST = "v3.football.api-sports.io"
APP_NAME = "Pronósticador Élite Profesional"

def normalizar(t: str) -> str:
    if not t: return ""
    t = unicodedata.normalize("NFD", str(t)).encode("ascii", "ignore").decode("utf-8").lower()
    basura = ["fc", "cd", "club", "sd", "ca", "s.a.", "deportivo", "atletico", "f.c.", "c.d.", "real"]
    palabras = [p for p in t.split() if p not in basura]
    return " ".join(palabras).strip() if palabras else t.strip().lower()

def limpiar_nombre(t: str) -> str:
    if not t: return ""
    t_clean = str(t).strip()
    for sep in [" de ", " del ", " DE ", " DEL "]:
        if sep in t_clean:
            t_clean = t_clean.split(sep)[0].strip()
            break
    return normalizar(t_clean)

def formatear_moneda(valor: float) -> str:
    return f"${valor:,.0f} COP"

@dataclass
class Match:
    local: str = ""
    visitante: str = ""
    market_ranking: List = field(default_factory=list)
    main_prediction: str = ""
    alternative_prediction: str = ""
    explanation: str = ""
    alerts: List[str] = field(default_factory=list)

class FootballAPI:
    def __init__(self):
        self.keys = [k.strip() for k in API_KEYS_BASE if k and len(k.strip()) > 10]
        self.key_errors = {}
        self.ultimo_error = ""

    def consultar(self, endpoint: str, params: dict) -> list:
        if not self.keys:
            self.ultimo_error = "🛑 No hay API Keys configuradas."
            return []

        keys_a_probar = list(self.keys)
        for key in keys_a_probar:
            headers = {"x-rapidapi-host": HOST, "x-rapidapi-key": key, "x-apisports-key": key}
            try:
                r = requests.get(f"https://{HOST}/{endpoint}", headers=headers, params=params, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    errs = data.get("errors")
                    if errs and isinstance(errs, dict) and len(errs) > 0:
                        msg = str(errs)
                        self.key_errors[key[:6] + "..."] = msg
                        if any(w in msg.lower() for w in ["requests", "limit", "suspended", "access", "token"]):
                            if key in self.keys and len(self.keys) > 1:
                                self.keys.remove(key)
                            continue
                        else:
                            self.ultimo_error = f"⚠️ Error API: {msg}"
                            return []
                    return data.get("response", [])
            except Exception as e:
                self.ultimo_error = f"⚠️ Error de conexión: {str(e)}"

        detalles = " | ".join([f"{k}: {v}" for k, v in self.key_errors.items()])
        self.ultimo_error = f"🛑 Error de API Keys: {detalles}"
        return []

    def buscar_equipo(self, nombre: str) -> dict:
        clean = limpiar_nombre(nombre)
        intentos = [clean, nombre, f"CA {clean}", f"Club {clean}"]
        palabras = clean.split()
        if len(palabras) > 1: intentos.append(palabras[0])

        for q in intentos:
            if not q or len(q) < 3: continue
            res = self.consultar("teams", {"search": q})
            if res:
                mejor, max_s = None, 0.0
                norm_q = normalizar(q)
                for item in res:
                    t_info = item.get("team", {})
                    sc = similitud(norm_q, normalizar(t_info.get("name", "")))
                    if sc > max_s: max_s, mejor = sc, t_info
                return mejor if mejor else res[0].get("team")
        return None

    def buscar_partido(self, local: str, visitante: str, fecha: str):
        self.ultimo_error = ""
        partidos = self.consultar("fixtures", {"date": fecha})
        norm_l, norm_v = normalizar(local), normalizar(visitante)

        if partidos:
            mejor, max_s = None, 0.0
            for p in partidos:
                l_api = p.get("teams", {}).get("home", {}).get("name", "")
                v_api = p.get("teams", {}).get("away", {}).get("name", "")
                sc = (similitud(norm_l, normalizar(l_api)) + similitud(norm_v, normalizar(v_api))) / 2.0
                if sc > 40.0 and sc > max_s: max_s, mejor = sc, p
            if mejor: return mejor

        eq_l, eq_v = self.buscar_equipo(local), self.buscar_equipo(visitante)
        return {
            "fixture": {"id": 0}, "league": {"id": 0, "season": 2026},
            "teams": {
                "home": {"id": eq_l.get("id") if eq_l else 0, "name": eq_l.get("name") if eq_l else local},
                "away": {"id": eq_v.get("id") if eq_v else 0, "name": eq_v.get("name") if eq_v else visitante}
            }
        }

    def ultimos(self, team_id: int) -> list:
        return self.consultar("fixtures", {"team": team_id, "last": 10}) if team_id else []

    def h2h(self, l_id: int, v_id: int) -> list:
        return self.consultar("fixtures/headtohead", {"h2h": f"{l_id}-{v_id}", "last": 10}) if (l_id and v_id) else []

    def alineaciones(self, fixture_id: int) -> list:
        return self.consultar("fixtures/lineups", {"fixture": fixture_id}) if fixture_id else []

    def estadisticas_partido(self, fixture_id: int) -> list:
        return self.consultar("fixtures/statistics", {"fixture": fixture_id}) if fixture_id else []

class Analyzer:
    def __init__(self, api: FootballAPI): self.api = api

    def analizar(self, datos: dict) -> dict:
        h_id, v_id = datos.get("home_id", 0), datos.get("away_id", 0)
        fix_id = datos.get("fixture_id", 0)

        l_h, l_v = self.api.ultimos(h_id), self.api.ultimos(v_id)

        def procesar_partidos(partidos, t_id):
            if not partidos or not t_id: return None
            gf, gc = 0.0, 0.0
            for p in partidos:
                ih = p.get("teams", {}).get("home", {}).get("id") == t_id
                g = p.get("goals", {})
                gf += (g.get("home") or 0) if ih else (g.get("away") or 0)
                gc += (g.get("away") or 0) if ih else (g.get("home") or 0)
            cant = len(partidos)
            return {"gf": round(gf / cant, 2), "gc": round(gc / cant, 2), "cant": cant}

        st_h = procesar_partidos(l_h, h_id)
        st_v = procesar_partidos(l_v, v_id)

        if not st_h or not st_v:
            err = self.api.ultimo_error if self.api.ultimo_error else "No se hallaron partidos en API-Football."
            return {"ok": False, "error_api": err}

        corners_h, corners_v = 0.0, 0.0
        tarjetas_h, tarjetas_v = 0.0, 0.0
        tiene_corners, tiene_tarjetas = False, False

        if fix_id > 0:
            stats_fix = self.api.estadisticas_partido(fix_id)
            if stats_fix:
                for item in stats_fix:
                    tid = item.get("team", {}).get("id")
                    st_list = item.get("statistics", [])
                    c_val, t_val = 0, 0
                    for s in st_list:
                        tp = str(s.get("type", "")).lower()
                        vl = s.get("value") or 0
                        if "corner" in tp: c_val = float(vl)
                        elif "yellow" in tp or "red" in tp: t_val += float(vl)

                    if c_val > 0:
                        tiene_corners = True
                        if tid == h_id: corners_h = c_val
                        else: corners_v = c_val
                    if t_val > 0:
                        tiene_tarjetas = True
                        if tid == h_id: tarjetas_h = t_val
                        else: tarjetas_v = t_val

        lineups_raw = self.api.alineaciones(fix_id) if fix_id > 0 else []
        alertas_alineaciones = []
        if lineups_raw and len(lineups_raw) >= 2:
            for team_l in lineups_raw:
                tname = team_l.get("team", {}).get("name", "Equipo")
                form = team_l.get("formation", "N/A")
                starters = team_l.get("startXI", [])
                alertas_alineaciones.append(f"✅ {tname}: 11 Inicial Confirmado ({form}) con {len(starters)} titulares.")
        else:
            alertas_alineaciones.append("⚠️ Alineaciones oficiales aún no confirmadas por la liga. Análisis elaborado con formación proyectada.")

        h2h_res = self.api.h2h(h_id, v_id)
        tot_h2h = sum((m.get("goals", {}).get("home") or 0) + (m.get("goals", {}).get("away") or 0) for m in h2h_res) if h2h_res else 0.0
        prom_h2h = round(tot_h2h / len(h2h_res), 2) if h2h_res else round(st_h["gf"] + st_v["gf"], 2)

        return {
            "ok": True,
            "gf_h": st_h["gf"], "gc_h": st_h["gc"],
            "gf_v": st_v["gf"], "gc_v": st_v["gc"],
            "prom_h2h": prom_h2h,
            "tiene_corners": tiene_corners,
            "corners_est": corners_h + corners_v if tiene_corners else 0.0,
            "tiene_tarjetas": tiene_tarjetas,
            "tarjetas_est": tarjetas_h + tarjetas_v if tiene_tarjetas else 0.0,
            "alertas_alineaciones": alertas_alineaciones
        }

class ProbabilityCalculator:
    def __poisson(self, k: int, lam: float) -> float:
        return (math.pow(lam, k) * math.exp(-lam)) / math.factorial(k) if lam > 0 else (1.0 if k == 0 else 0.0)

    def calcular(self, gf_h: float, gc_h: float, gf_v: float, gc_v: float) -> dict:
        lh = max(0.20, (gf_h + gc_v) / 2.0)
        lv = max(0.20, (gf_v + gc_h) / 2.0)
        ph, pd, pv = 0.0, 0.0, 0.0
        pu15, po15, pu25, po25, pu35, pbtts = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

        for i in range(8):
            for j in range(8):
                p = self.__poisson(i, lh) * self.__poisson(j, lv)
                if i > j: ph += p
                elif i == j: pd += p
                else: pv += p

                tot = i + j
                if tot < 1.5: pu15 += p
                if tot >= 2: po15 += p
                if tot <= 2: pu25 += p
                if tot >= 3: po25 += p
                if tot <= 3: pu35 += p
                if i > 0 and j > 0: pbtts += p

        tot_p = max(0.001, ph + pd + pv)
        ph, pd, pv = ph / tot_p, pd / tot_p, pv / tot_p

        return {
            "lh": round(lh, 2), "lv": round(lv, 2), "exp": round(lh + lv, 2),
            "local": round(ph * 100.0, 1), "empate": round(pd * 100.0, 1), "visitante": round(pv * 100.0, 1),
            "1x": round((ph + pd) * 100.0, 1), "x2": round((pv + pd) * 100.0, 1),
            "dnb_h": round((ph / max(0.001, ph + pv)) * 100.0, 1),
            "dnb_v": round((pv / max(0.001, ph + pv)) * 100.0, 1),
            "o15": round(po15 * 100.0, 1), "u25": round(pu25 * 100.0, 1),
            "u35": round(pu35 * 100.0, 1), "btts": round(pbtts * 100.0, 1)
        }

class SALMEngine:
    def __init__(self):
        self.api = FootballAPI()
        self.analyzer = Analyzer(api=self.api)
        self.prob = ProbabilityCalculator()

    def ejecutar_analisis(self, local: str, visitante: str, fecha: str, liga: str) -> Match:
        fix = self.api.buscar_partido(local, visitante, fecha)
        h_id, v_id = fix["teams"]["home"]["id"], fix["teams"]["away"]["id"]
        fix_id = fix["fixture"]["id"]
        loc_n, vis_n = fix["teams"]["home"]["name"], fix["teams"]["away"]["name"]

        an = self.analyzer.analizar({"home_id": h_id, "away_id": v_id, "fixture_id": fix_id})
        if not an.get("ok"):
            err_text = an.get("error_api", "No se hallaron partidos en API-Football.")
            return Match(
                local=loc_n, visitante=vis_n,
                main_prediction="🛑 PRONÓSTICO SUSPENDIDO POR API",
                market_ranking=[{"m": "Sin datos", "p": 0.0, "c": 999.0, "r": "Alto", "razon": err_text}],
                explanation=f"**Atención:** {err_text}",
                alerts=[err_text]
            )

        pr = self.prob.calcular(an["gf_h"], an["gc_h"], an["gf_v"], an["gc_v"])
        alertas = list(an.get("alertas_alineaciones", []))

        cands = []
        if pr["1x"] >= 62.0: cands.append({"m": f"Gana o Empata {loc_n} (1X)", "p": pr["1x"], "r": "Bajo", "razon": f"Sólida cobertura local ({pr['1x']}% prob)."})
        if pr["x2"] >= 62.0: cands.append({"m": f"Gana o Empata {vis_n} (X2)", "p": pr["x2"], "r": "Bajo", "razon": f"Cobertura visitante ({pr['x2']}% prob)."})
        if pr["o15"] >= 68.0: cands.append({"m": "Más de 1.5 Goles Totales", "p": pr["o15"], "r": "Bajo", "razon": f"Expectativa Poisson de {pr['exp']:.2f} goles esperados."})
        if pr["u35"] >= 72.0: cands.append({"m": "Menos de 3.5 Goles Totales", "p": pr["u35"], "r": "Bajo", "razon": f"Ritmo controlado ({pr['u35']}% prob)."})
        if pr["btts"] >= 52.0: cands.append({"m": "Ambos Equipos Anotan (Sí)", "p": pr["btts"], "r": "Bajo-Medio", "razon": f"Conversión mutual ({pr['btts']}% BTTS)."})

        if an.get("tiene_corners") and an["corners_est"] >= 8.5:
            p_corn = round(min(88.0, 68.0 + (an["corners_est"] - 8.5) * 4.0), 1)
            cands.append({"m": "Más de 7.5 Tiros de Esquina (Córneres Totales)", "p": p_corn, "r": "Bajo", "razon": f"Proyección real de córneres en API: {an['corners_est']:.1f} córneres."})
        elif not an.get("tiene_corners"):
            alertas.append("⚠️ Datos de córneres no disponibles en API-Football para este partido/liga.")

        if an.get("tiene_tarjetas") and an["tarjetas_est"] >= 4.0:
            p_cards = round(min(86.0, 66.0 + (an["tarjetas_est"] - 4.0) * 4.5), 1)
            cands.append({"m": "Más de 3.5 Tarjetas Totales en el Partido", "p": p_cards, "r": "Bajo", "razon": f"Fricción táctica real registrada: {an['tarjetas_est']:.1f} tarjetas est."})
        elif not an.get("tiene_tarjetas"):
            alertas.append("⚠️ Datos de tarjetas no disponibles en API-Football para este partido/liga.")

        cands.sort(key=lambda x: x["p"], reverse=True)
        for c in cands: c["c"] = round(100.0 / max(0.1, c["p"]), 2)

        p_top = cands[0] if cands else {"m": "Menos de 3.5 Goles Totales", "p": pr["u35"], "c": 1.30, "r": "Bajo", "razon": "Seguridad."}
        s_top = cands[1] if len(cands) > 1 and cands[1]["m"] != p_top["m"] else (cands[2] if len(cands) > 2 else p_top)

        arg = (
            f"**1. Rendimiento Real API:** {loc_n} ({an['gf_h']:.2f} GF / {an['gc_h']:.2f} GC) vs {vis_n} ({an['gf_v']:.2f} GF / {an['gc_v']:.2f} GC).\n\n"
            f"**2. Proyección Poisson:** Gol Local: {pr['lh']:.2f} | Gol Visita: {pr['lv']:.2f} (Total: {pr['exp']:.2f} goles esperados).\n\n"
            f"**3. Historial H2H Real:** Promedio H2H de {an['prom_h2h']:.1f} goles en sus duelos directos.\n\n"
            f"**4. Dictamen Multimercado Exclusivo:** {p_top['razon']}"
        )

        return Match(local=loc_n, visitante=vis_n, market_ranking=cands, main_prediction=p_top["m"], alternative_prediction=s_top["m"], explanation=arg, alerts=alertas)

# ==========================================
# STREAMLIT UI
# ==========================================
st.set_page_config(page_title="Pronosticador Élite App", page_icon="⚽", layout="centered")
st.title("⚽ PRONOSTICADOR ÉLITE 90%")
st.caption(f"{APP_NAME} — Motor Quirúrgico Multimercado")
st.divider()

engine = SALMEngine()

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
    local = st.text_input("Equipo Local", value="A")
with c2:
    fecha_consulta = st.date_input("Fecha", datetime.date.today())
    visitante = st.text_input("Equipo Visitante", value="B")

if st.button("🔎 Generar Análisis Quirúrgico Completo"):
    st.session_state.clear()
    with st.spinner("Consultando alineaciones, estadísticas reales e Inteligencia IA SALM..."):
        f_str = fecha_consulta.strftime("%Y-%m-%d")
        st.session_state["match"] = engine.ejecutar_analisis(local, visitante, f_str, liga)
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
            if "✅" in al: st.info(al)
            elif "⚠️" in al: st.warning(al)
            else: st.error(al)
        st.write("---")

    st.markdown("### 🔬 Argumentación Táctica Completa")
    st.markdown(m.explanation)
    st.write("---")

    p_top = ranking[0] if ranking else {"m": "N/A", "p": 0.0, "c": 0.0, "r": "N/A"}
    s_top = ranking[1] if len(ranking) > 1 else p_top

    if p_top["p"] > 0:
        st.success(f"🟢 **PRONÓSTICO PRINCIPAL**\n\nMercado: {p_top['m']}\n\nCuota Justa: {p_top['c']:.2f} | Prob. Real: {p_top['p']:.1f}%\n\nRiesgo: {p_top['r']}")
        st.info(f"🟡 **PRONÓSTICO SECUNDARIO**\n\nMercado: {s_top['m']}\n\nCuota Justa: {s_top['c']:.2f} | Prob. Real: {s_top['p']:.1f}%\n\nRiesgo: {s_top['r']}")

        st.write("---")
        st.markdown("### 🎯 Verificación en Betplay")
        opcion = st.radio("Mercado a evaluar:", [f"Principal: {p_top['m']}", f"Secundario: {s_top['m']}"], key="rad_m")
        target_m = p_top if "Principal" in opcion else s_top

        c_betplay = st.number_input(f"Cuota actual en Betplay para '{target_m['m']}':", min_value=1.01, max_value=20.0, value=1.75, step=0.01, key="in_c")
        if st.button("⚡ EVALUAR Y APLICAR REGLA DE ORO"):
            prob_dec = target_m["p"] / 100.0
            ev = (prob_dec * c_betplay) - 1.0
            f_kelly = max(0.0, (prob_dec * (c_betplay - 1.0) - (1.0 - prob_dec)) / max(0.01, c_betplay - 1.0)) * 0.25 * 100.0
            st.subheader("3. Veredicto Final")
            if ev <= 0:
                st.error("DECISIÓN: NO APUESTO 🛑\n- La cuota no ofrece Valor Positivo (+EV).")
            else:
                st.success("DECISIÓN: 🟢 APOSTAR (+EV)")
                st.write(f"**Ventaja +EV:** +{ev*100:.1f}%")
                st.write(f"**Kelly Stake:** {f_kelly:.2f}% Bankroll")

    st.divider()
    if st.button("🔄 Analizar Otro Partido", key="btn_bot"):
        st.session_state.clear()
        sDeportivo
