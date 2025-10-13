
# shared_code/GetZeroAnswer.py
import os
import json
import logging
from datetime import datetime
import requests


def run(payload: dict) -> dict:
    """
    Логика GetZeroAnswer, адаптированная под вызов из Durable activity.
    Вход: payload (dict) — то, что приходило в HTTP body.
    Выход: dict — пойдёт в output оркестратора.
    """
    start_time = datetime.utcnow()
    logging.info("GetZeroAnswer: started")

    payload = payload or {}
    email = payload.get("Email")
    email_title = payload.get("Email Subject")
    email_text = payload.get("Email Body")

    if not email:
        return {"error": "Email is required", "execution_time": 0}

    # Читаем конфиг из переменных окружения (Application Settings)
    gpt5nano_endpoint = os.getenv(
        "GPT5NANO_ENDPOINT",
        "https://paphos-eus2.openai.azure.com/openai/deployments/gpt-5-nano/chat/completions?api-version=2025-01-01-preview"
    )
    gpt5nano_key = os.getenv("GPT5NANO_KEY")
    if not gpt5nano_key:
        return {"error": "Missing GPT5NANO_KEY in application settings", "execution_time": 0}

    headers = {
        "Content-Type": "application/json",
        "api-key": gpt5nano_key,
    }

    body = {
        "messages": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": """Task Objective:
Your task is to determine if the provided email is a new request for freight transportation or customs clearance services.

Criteria for a New Request:
The email must not reference any prior discussions (i.e., it should not be a follow-up).
The email must contain a specific request to initiate a freight transportation service or customs clearance.
The email must relate to logistics services (e.g., shipping, warehousing, customs).
Advertisement or promotional emails should not be considered a new request.

Response Format:
Respond ONLY with a valid JSON object (json), no prose
If it's a new request: { "action": "Request" }
Otherwise: { "action": "Other" }
"""
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"email: {email}; title: {email_title}; Content: {email_text}"
                    }
                ]
            }
        ],
        "temperature": 1,
        "max_completion_tokens": 5400,
        "response_format": {"type": "json_object"}
    }

    try:
        logging.info("GetZeroAnswer: calling GPT-5-nano")
        resp = requests.post(gpt5nano_endpoint, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        answer_content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        model_name = data.get("model", "unknown")

        exec_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        return {
            "answer": answer_content,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "model": model_name,
            "execution_time": exec_ms
        }

    except requests.exceptions.RequestException as e:
        logging.exception("GetZeroAnswer: API request failed")
        return {
            "error": f"API request failed: {e}",
            "execution_time": int((datetime.utcnow() - start_time).total_seconds() * 1000)
        }
    except (KeyError, ValueError, IndexError) as e:
        logging.exception("GetZeroAnswer: error processing API response")
        return {
            "error": f"Error processing API response: {e}",
            "execution_time": int((datetime.utcnow() - start_time).total_seconds() * 1000)
        }
