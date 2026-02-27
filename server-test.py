from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/")
def root():
    return {"status": "Copilot running 🚀"}

@app.post("/ask")
def ask(data: dict):
    question = data.get("question", "")

    # Demo-safe fallback
    if not question:
        return {"answer": "Please ask a question 😊"}

    # Replace this later with your real logic
    return {
        "answer": f"📘 Copilot Answer:\nYou asked → {question}"
    }