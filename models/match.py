from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Match:
    # ==========================
    # Información básica
    # ==========================
    fixture_id: Optional[int] = None
    league_id: Optional[int] = None
    season: Optional[int] = None

    liga: str = ""
    fecha: str = ""

    local: str = ""
    visitante: str = ""

    # ==========================
    # Datos obtenidos desde API
    # ==========================
    statistics: Dict = field(default_factory=dict)
    standings: Dict = field(default_factory=dict)
    h2h: List = field(default_factory=list)
    recent_form: Dict = field(default_factory=dict)
    injuries: List = field(default_factory=list)
    trends: Dict = field(default_factory=dict)

    # ==========================
    # Resultados del análisis
    # ==========================
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

    # ==========================
    # Integración BetPlay
    # ==========================
    betplay_odds: Optional[float] = None
    expected_value: float = 0.0
    final_decision: str = ""
