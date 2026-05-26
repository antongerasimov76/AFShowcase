import logging
import requests
import azure.functions as func
import json
from datetime import datetime
from shared_code.config import OPENAI_API_KEY, OPENAI_ENDPOINT


def main(req: func.HttpRequest) -> func.HttpResponse:
    start_time = datetime.now()
    logging.info('Python HTTP trigger function processed a request.')

    try:
        # Read the request body
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            "Invalid request body",
            status_code=400
        )
    
    email = req_body.get('Email')
    email_title = req_body.get('Email Subject')
    email_text = req_body.get('Email Body')
    logging.info('Data ready')

    if email:
        headers = {
            "Content-Type": "application/json",
            "api-key": OPENAI_API_KEY,
        }

        payload = {
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

        logging.info('Payload ready')

        response = requests.post(OPENAI_ENDPOINT, headers=headers, json=payload)
        response_json = response.json()

        # Extract the content from the response
        answer_content = response_json['choices'][0]['message']['content']

        # Extract token usage details
        usage = response_json.get('usage', {})
        prompt_tokens = usage.get('prompt_tokens')
        completion_tokens = usage.get('completion_tokens')
        total_tokens = usage.get('total_tokens')
        model_name = response_json.get('model', 'unknown')

        # Construct your final response
        end_time = datetime.now()
        execution_time_ms = (end_time - start_time).total_seconds() * 1000
        
        final_response = {
            "answer": answer_content,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "model": model_name,
            "execution_time": round(execution_time_ms)
        }

        return func.HttpResponse(json.dumps(final_response), mimetype="application/json")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass Email in the request body.",
             status_code=200
        )
