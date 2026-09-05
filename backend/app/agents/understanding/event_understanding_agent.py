"""Real text classification and location extraction over free text --
news articles, primarily (spec section 7).

Two deliberately transparent, reproducible techniques rather than a
black box:

1. Category: TF-IDF cosine similarity against hand-written reference
   terms per category. Not a trained supervised classifier -- there is
   no labeled "this article is about a storm" dataset anywhere in this
   repo, and inventing labels to train one against would be exactly the
   kind of fabrication this project avoids elsewhere. The reference
   terms are an explicit, readable definition of each category, and the
   similarity score is a real, checkable number.

2. Locations: substring matching against this system's own real
   gazetteer -- the 20 digital twin ports (app/twin/coordinates.py) and
   8 monitored corridors (MONITORED_LOCATIONS). A generic NER model
   would recognize far more places than this system can act on; a
   location that isn't a twin port or a monitored corridor isn't
   something the route optimizer or risk agent can do anything with
   regardless of how confidently it's recognized, so matching against
   the real, finite list this system already understands is more
   directly useful here than general-purpose NER.
"""

from typing import Dict, List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.agents.ingestion.live_conditions_client import MONITORED_LOCATIONS
from app.schemas.agent_io import NewsUnderstanding
from app.twin.coordinates import PORT_COORDINATES

def _aliases_for(name: str) -> List[str]:
    """A monitored corridor's canonical name sometimes carries a
    parenthetical qualifier ("Suez Canal (Gulf of Suez)", "English
    Channel (Dover)") that real news text never actually uses -- it
    says "the Suez Canal", not the full canonical form. Matching only
    the exact canonical string would silently miss every real mention.
    Both the canonical name and its unqualified prefix are checked;
    either match reports the canonical name."""
    aliases = [name]
    if " (" in name:
        aliases.append(name.split(" (", 1)[0])
    return aliases

# {alias_lower: canonical_name}, longest alias first so a more specific
# alias is checked before a shorter one that might also appear in it.
_GAZETTEER_ALIASES: Dict[str, str] = {
    alias.lower(): name
    for name in sorted(set(PORT_COORDINATES) | {loc["name"] for loc in MONITORED_LOCATIONS})
    for alias in _aliases_for(name)
}
GAZETTEER: List[str] = sorted(set(_GAZETTEER_ALIASES.values()))
_ALIASES_BY_LENGTH = sorted(_GAZETTEER_ALIASES, key=len, reverse=True)

# Explicit, hand-written per spec's own "avoid unnecessarily using an
# LLM for every simple classification task" -- these are a definition,
# not a learned artifact. Extend this dict to add a category.
CATEGORY_EXEMPLARS: Dict[str, str] = {
    "Storm / Weather": "storm gale hurricane typhoon cyclone rough seas high waves swell wind damage weather delay",
    "Piracy / Security": "piracy hijack armed robbery kidnap ransom attack security incident vessel boarded pirates",
    "Port Congestion": "port congestion backlog delay queue anchorage waiting berth capacity terminal bottleneck",
    "Collision / Accident": "collision grounding accident fire explosion sinking capsized damaged hull crash",
    "Environmental / Spill": "oil spill pollution environmental damage leak contamination cleanup spillage",
    "Labor / Strike": "strike labor dispute union walkout port workers industrial action picket",
    "Geopolitical / Sanctions": "sanctions blockade war conflict military tension trade restriction embargo strikes missile",
}


class EventUnderstandingAgent:
    def __init__(self) -> None:
        self._categories = list(CATEGORY_EXEMPLARS.keys())
        self._vectorizer = TfidfVectorizer(stop_words="english")
        self._exemplar_matrix = self._vectorizer.fit_transform(CATEGORY_EXEMPLARS.values())

    def analyze(self, text: str) -> NewsUnderstanding:
        text = (text or "").strip()
        text_lower = text.lower()
        matched_locations: List[str] = []
        for alias in _ALIASES_BY_LENGTH:
            canonical = _GAZETTEER_ALIASES[alias]
            if canonical in matched_locations:
                continue
            if alias in text_lower:
                matched_locations.append(canonical)

        if not text:
            return NewsUnderstanding(
                category="Uncategorized", category_confidence=0.0,
                matched_locations=matched_locations, reasoning="No text provided to classify.",
            )

        doc_vector = self._vectorizer.transform([text])
        similarities = cosine_similarity(doc_vector, self._exemplar_matrix)[0]
        best_index = int(similarities.argmax())
        best_score = float(similarities[best_index])

        if best_score <= 0:
            return NewsUnderstanding(
                category="Uncategorized", category_confidence=0.0,
                matched_locations=matched_locations,
                reasoning="No category reference terms matched this text.",
            )

        category = self._categories[best_index]
        reasoning = f"TF-IDF cosine similarity to '{category}' reference terms: {best_score:.3f}."
        if matched_locations:
            reasoning += f" Mentions monitored location(s): {', '.join(matched_locations)}."

        return NewsUnderstanding(
            category=category,
            category_confidence=round(min(best_score, 1.0), 3),
            matched_locations=matched_locations,
            reasoning=reasoning,
        )
