import os
from datetime import datetime
import re

from fastapi import HTTPException
import requests
import json
from pathlib import Path
from project.config import HEADERS
from project.conspayloads import build_consolidation_payload

# -------------------- LOAD CONFIG --------------------

FIELD_GROUPS = json.loads(
    Path("project/group_field_map.json").read_text(encoding="utf-8")
)

INTACCT_FILTER_URL = os.getenv("INTACCT_FILTER_URL")
INTACCT_CONSOLIDATION_URL = os.getenv("INTACCT_CONSOLIDATION_URL")

# =====================================================
# intent map
# =====================================================

INTENT_MAP = {
    "currency": ["currency", "fx", "exchange rate"],
    "account": ["account", "gl", "cta"],
    "journal": ["stat journal", "stat", "statistical"],
    "department": ["dept"],
    "elimination": ["elim", "auto elimination", "auto", "elimination account"],
    "ownership": ["structure"],
    "audit": ["audit", "created", "modified"]
}

# -------------------- HELPERS --------------------

def clean_llm_json(text_output: str) -> dict:

    # Extract first JSON object using regex
    match = re.search(r"\{.*\}", text_output, re.DOTALL)

    if not match:
        raise ValueError("No JSON object found in LLM response")

    json_str = match.group(0)

    return json.loads(json_str)

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

# =====================================================
# MCP BUSINESS LOGIC (REAL IMPLEMENTATION)
# =====================================================

async def process_get_book(book_name: str, fields: list[str]):

    try:
        api_fields = expand_fields(fields)
        payload = build_payload(book_name, api_fields)

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

        # Build structured rows
        table_rows = []

        for field in api_fields:
            value = extract_field(book_data, field)
            alias = field.split(".")[-1]

            table_rows.append({
                "label": alias.replace("_", " ").title(),
                "value": value
            })

        # 🔥 Standard UI Widget Response
        return {
            "success": True,
            "type": "widget",
            "widget": {
                "widget_type": "table",
                "title": f"Book Details - {book_name}",
                "columns": ["Field", "Value"],
                "rows": [
                    [row["label"], row["value"]]
                    for row in table_rows
                ]
            },
            "meta": {
                "entity": "book",
                "identifier": book_name,
                "row_count": len(table_rows)
            },
            "errors": None
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Intacct API error: {str(e)}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Processing error: {str(e)}"
        )


async def process_consolidate_book(book_name: str, period: str):

    payload = build_consolidation_payload(
        book_name,
        period
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

        success = status.lower() == "success"

        # 🔥 Standard UI Widget Response (Summary Card)
        return {
            "success": success,
            "type": "widget",
            "widget": {
                "widget_type": "summary",
                "title": f"Consolidation Result - {book_name}",
                "status": status,
                "fields": [
                    {"label": "Book Name", "value": book_name},
                    {"label": "Period", "value": period},
                    {"label": "Status", "value": status},
                    {"label": "Message", "value": message},
                    {"label": "Processed At", "value": datetime.utcnow().isoformat()}
                ]
            },
            "meta": {
                "entity": "book",
                "identifier": book_name,
                "period": period,
                "intacct_meta": meta
            },
            "errors": None if success else message
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Consolidation failed: {str(e)}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Processing error: {str(e)}"
        )