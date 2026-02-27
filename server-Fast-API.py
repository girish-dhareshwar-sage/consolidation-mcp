# server.py

import json
import sys
from pathlib import Path
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from project.config import HEADERS
from project.conspayloads import build_consolidation_payload

sys.stdout.reconfigure(encoding="utf-8")

app = FastAPI(title="Consolidation Copilot API")

# -------------------- LOAD CONFIG --------------------

FIELD_GROUPS = json.loads(
    Path("project/group_field_map.json").read_text(encoding="utf-8")
)

INTACCT_FILTER_URL = "https://api.intacct.com/ia/api/v1/services/core/query"
INTACCT_CONSOLIDATION_URL="https://api.intacct.com/ia/api/v1-beta2/services/consolidation/book/consolidate"

INTENT_MAP = {
    "currency": ["currency", "fx", "exchange rate"],
    "account": ["account", "gl", "cta"],
    "journal": ["stat journal", "stat", "statistical"],
    "department": ["dept"],
    "elimination": ["elim", "auto elimination", "auto", "elimination account"],
    "ownership": ["structure"],
    "audit": ["audit", "created", "modified"]
}

# -------------------- REQUEST MODEL --------------------
class BookRequest(BaseModel):
    book_id: str
    fields: list[str]

# ✅ Request Model
class ConsolidationRequest(BaseModel):
    book_name: str
    period: str
# -------------------- HELPERS --------------------

def resolve_intents(requested_fields: list[str]) -> set[str]:
    resolved = set()

    for user_field in requested_fields:
        user_field_lower = user_field.lower()

        for intent, keywords in INTENT_MAP.items():
            if any(keyword in user_field_lower for keyword in keywords):
                resolved.add(intent)

    return resolved


def expand_fields(requested_fields: list[str]) -> list[str]:

    expanded = []
    resolved_groups = resolve_intents(requested_fields)

    for field in requested_fields:
        key = field.lower()

        # Direct group match
        if key in FIELD_GROUPS:
            group_fields = FIELD_GROUPS[key]

            if isinstance(group_fields, dict):
                expanded.extend(group_fields.values())
            else:
                expanded.extend(group_fields)

            continue

        # Intent match
        matched = False
        for group in resolved_groups:
            if group in FIELD_GROUPS:
                group_fields = FIELD_GROUPS[group]

                if isinstance(group_fields, dict):
                    expanded.extend(group_fields.values())
                else:
                    expanded.extend(group_fields)

                matched = True

        # Raw fallback
        if not matched:
            expanded.append(field)

    return sorted(set(expanded))


def extract_field(result, field_path):

    if field_path in result:
        return result[field_path]

    value = result
    for key in field_path.split("."):
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None

    return value


def format_response(book_id, result, api_fields):

    if isinstance(result, list):
        if not result:
            return f"📘 Book: {book_id}\nNo data found"
        result = result[0]

    lines = [f"📘 Book: {book_id}"]

    for field in api_fields:
        value = extract_field(result, field)
        alias = field.split(".")[-1]
        lines.append(f"{alias} = {value}")

    return "\n".join(lines)


def build_payload(book_id, api_fields):
    return {
        "object": "consolidation/book",
        "fields": api_fields,
        "filters": {
            "1": {"$eq": {"id": book_id}},
            "2": {"$eq": {"status": "active"}}
        },
        "filterExpression": "1 and 2"
    }

# -------------------- ROUTES --------------------

@app.get("/")
def root():
    return {"status": "Sage Copilot API running 🚀"}


@app.post("/get_book")
def get_book(request: BookRequest):

    try:
        api_fields = expand_fields(request.fields)
        payload = build_payload(request.book_id, api_fields)

        response = requests.post(
            INTACCT_FILTER_URL,
            headers=HEADERS,
            json=payload,
            timeout=30
        )

        response.raise_for_status()
        response_json = response.json()

        book_data = response_json.get("ia::result", {})

        if isinstance(book_data, list):
            book_data = book_data[0] if book_data else {}

        # ✅ Build table rows
        table_rows = []
        for field in api_fields:
            value = extract_field(book_data, field)
            alias = field.split(".")[-1]
            table_rows.append({
                "field": alias,
                "value": value
            })

        return {
            "success": True,
            "action": "get_book",
            "entity": "book",
            "identifier": request.book_id,
            "display_type": "table",
            "message": "Book details retrieved successfully",
            "data": table_rows,
            "meta": {
                "row_count": len(table_rows)
            },
            "errors": None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ API Endpoint
@app.post("/consolidate_book")
def consolidate_book(request: ConsolidationRequest):

    payload = build_consolidation_payload(
        request.book_name,
        request.period
    )

    try:
        response = requests.post(
            INTACCT_CONSOLIDATION_URL,
            headers=HEADERS,
            json=payload,
            timeout=60
        )

        response.raise_for_status()
        data = response.json()

        result = data.get("ia::result", {})
        meta = data.get("ia::meta", {})

        status = result.get("status", "unknown")
        message = result.get("message", "No message returned")

        return {
            "success": status == "success",
            "action": "consolidate_book",
            "entity": "book",
            "identifier": request.book_name,
            "display_type": "summary",
            "message": message,
            "data": {
                "book_name": request.book_name,
                "period": request.period,
                "status": status
            },
            "meta": meta,
            "errors": None
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Consolidation failed: {str(e)}"
        )