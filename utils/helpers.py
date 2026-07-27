import unicodedata


def normalizar(t: str) -> str:
    """
    Normaliza textos removiendo acentos, caracteres especiales y prefijos comunes de clubes.
    """
    if not t:
        return ""
    t = unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode("utf-8").lower()
    basura = ["fc", "cd", "club", "sd", "ca", "s.a.", "deportivo", "atletico", "f.c.", "c.d.", "real"]
    palabras = [p for p in t.split() if p not in basura]
    return " ".join(palabras).strip() if palabras else t.strip().lower()


def porcentaje(valor: float) -> str:
    return f"{valor:.1f}%"


def confianza(valor: float) -> str:
    return f"{valor:.1f}/100"


def formatear_moneda(valor: float) -> str:
    return f"${valor:,.0f} COP"
