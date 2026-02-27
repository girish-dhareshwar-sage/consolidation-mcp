# server.py
import os
import json
import sys
from typing import List, Optional, Dict, Any

import anthropic
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from book_service import process_get_book, process_consolidate_book, clean_llm_json
from schemas import ChatRequest, ChatResponse

sys.stdout.reconfigure(encoding="utf-8")

app = FastAPI(title="Consolidation MCP + Claude AI")

# =====================================================
# CONFIG of Claude
# =====================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise Exception("ANTHROPIC_API_KEY not set")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# -------------------- REQUEST MODEL --------------------
class BookRequest(BaseModel):
    book_id: str
    fields: list[str]

# ✅ Request Model
class ConsolidationRequest(BaseModel):
    book_name: str
    period: str

# -------------------- ROUTES --------------------
# ✅ API Endpoint
@app.get("/")
def root():
    return {"status": "Sage Copilot API running 🚀"}

# =====================================================
# LLM INTENT PARSER USING CLAUDE
# =====================================================

def parse_with_claude(user_message: str) -> Dict[str, Any]:
    """
    Ask Claude to extract structured intent.
    """

    system_prompt = """
You are an API intent parser.

Extract structured JSON from user request.

Available actions:

1) get_book
   parameters:
     - book_name (string)
     - fields (array of strings)

2) consolidate_book
   parameters:
     - book_name (string)
     - period (string)

Return ONLY valid JSON.

Example:

User: give me currency and exchange rate for CASE-1
Output:
{
  "action": "get_book",
  "book_name": "CASE-1",
  "fields": ["currency", "exchange_rate"]
}

User: consolidate CASE-2 for Sep 2021
Output:
{
  "action": "consolidate_book",
  "book_name": "CASE-2",
  "period": "Sep 2021"
}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=500,
        temperature=0,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_message}
        ]
    )

    text_output = response.content[0].text.strip()

    try:
        parsed = clean_llm_json(text_output)
        return parsed
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"LLM returned invalid JSON: {text_output}"
        )


# =====================================================
# CHAT ENDPOINT
# =====================================================

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main AI entrypoint.
    PHP / JS frontend will call this.
    """

    parsed = parse_with_claude(request.message)

    action = parsed.get("action")

    if action == "get_book":
        result = await process_get_book(
            book_name=parsed["book_name"],
            fields=parsed["fields"]
        )

        return {
            "type": "widget",
            "content": result
        }

    elif action == "consolidate_book":
        result = await process_consolidate_book(
            book_name=parsed["book_name"],
            period=parsed["period"]
        )

        return {
            "type": "widget",
            "content": result
        }

    else:
        raise HTTPException(status_code=400, detail="Unknown action")


@app.post("/get_book")
async def get_book(request: BookRequest):
    return await process_get_book(
        book_name=request.book_name,
        fields=request.fields
    )

@app.post("/consolidate_book")
async def consolidate_book(request: ConsolidationRequest):
    return await process_consolidate_book(
        book_name=request.book_name,
        period=request.period
    )