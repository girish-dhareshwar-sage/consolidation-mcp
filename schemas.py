from pydantic import BaseModel
from typing import List, Dict, Any


class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []


class ChatResponse(BaseModel):
    type: str  # "text" or "widget"
    content: Any