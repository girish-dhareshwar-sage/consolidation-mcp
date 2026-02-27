import os
from anthropic import Anthropic

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

TOOLS = [
    {
        "name": "get_book",
        "description": "Get consolidation book information using book_id",
        "input_schema": {
            "type": "object",
            "properties": {
                "book_id": {
                    "type": "string",
                    "description": "Book ID like case-1"
                }
            },
            "required": ["book_id"]
        }
    }
]

async def run_llm(messages):
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=messages,
        tools=TOOLS
    )
    return response