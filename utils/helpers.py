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


def limpiar_nombre_busqueda(t: str) -> str:
    """
    Remueve sufijos de países que hacen fallar el buscador de API-Football.
    Ejemplo: 'Tigre de argentina' -> 'Tigre'
             'Santos de Brasil' -> 'Santos'
             'Nacional de Uruguay' -> 'Nacional'
    """
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


def porcentaje(valor: float) -> str:
    return f"{valor:.1f}%"


def confianza(valor: float) -> str:
    return f"{valor:.1f}/100"


def formatear_moneda(valor: float) -> str:
    return f"${valor:,.0f} COP"
