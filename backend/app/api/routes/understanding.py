from fastapi import APIRouter, Query

from app.agents.understanding.event_understanding_agent import EventUnderstandingAgent

router = APIRouter()

_agent = EventUnderstandingAgent()


@router.get("/understand")
def understand_text(text: str = Query(..., description="Free text to classify, e.g. a news headline.")):
    """Real text classification + location extraction over arbitrary
    text (spec section 7) -- the same analysis IngestionAgent runs over
    every related_news article, exposed standalone for ad-hoc use.
    """
    return _agent.analyze(text).model_dump()
