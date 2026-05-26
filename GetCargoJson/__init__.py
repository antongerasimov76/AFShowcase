from datetime import datetime
import logging
import requests
import azure.functions as func
import json
from azure.storage.blob import BlobServiceClient

from shared.config import (
    OPENAI_ENDPOINT,
    get_blob_connection_string,
    get_openai_headers,
)


SYSTEM_PROMPT = """You are a Logistics Assistant at M9 Logistics Company. Your task is to create structured JSON data for a transportation request based on the conversation history with the client.

The required JSON format is:
{
    "From Country": "Two-letter country code (ISO 3166-1 alpha-2)",
    "From Airport": "IATA airport code (if multiple ports, separate them with | symbol)",
    "To Country": "Two-letter country code (ISO 3166-1 alpha-2)",
    "To Airport": "IATA airport code (if multiple ports, separate them with | symbol)",
    "Date": "YYYY-MM-DD",
    "Product Code": "GCR - General Cargo; DGR - Dangerous Goods; HUM - Human Remains; AVI - Live Animals; PER - Perishable; PIL - Pharmaceuticals",
    "Dimensions": [
        {
            "Pieces": Number of pieces,
            "Length": Length in centimeters,
            "Width": Width in centimeters,
            "Height": Height in centimeters,
            "Weight": Weight in kilograms,
            "Stackable": true or false
        }
    ]
}

IMPORTANT:
- Always ensure country codes and airport codes are correct and properly formatted.
- Dimensions must be in centimeters and kilograms.
- If multiple packages are mentioned, create multiple entries inside "Dimensions".
- For "Stackable" field: analyze available info to determine if stackable. Default to false if unsure.
- Only generate the JSON data. Do not include explanations or additional text.
"""


def build_payload(chat_history_text: str) -> dict:
    """Build the OpenAI API request payload."""
    return {
        "messages": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": f"Today is {datetime.now()} " + SYSTEM_PROMPT + f"\n\nThe CHAT HISTORY is: {chat_history_text}"
                    }
                ]
            },
        ],
        "temperature": 1,
        "top_p": 0.95,
        "max_tokens": 2400
    }


def main(req: func.HttpRequest) -> func.HttpResponse:
    start_time = datetime.now()
    logging.info('GetCargoJson: Processing request.')

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid request body", status_code=400)

    task = req_body.get('Task ID')
    container_name = req_body.get('ABS Container')
    account_name = req_body.get('ABS Account Name')

    if not task:
        return func.HttpResponse(
            json.dumps({"error": "Task ID is required"}),
            status_code=400,
            mimetype="application/json"
        )
    if not container_name:
        return func.HttpResponse(
            json.dumps({"error": "ABS Container is required"}),
            status_code=400,
            mimetype="application/json"
        )
    if not account_name:
        return func.HttpResponse(
            json.dumps({"error": "ABS Account Name is required"}),
            status_code=400,
            mimetype="application/json"
        )

    # Get blob connection and download chat history
    try:
        connection_string = get_blob_connection_string(account_name)
    except ValueError as exc:
        logging.warning("GetCargoJson: invalid storage account configuration: %s", exc)
        return func.HttpResponse(
            json.dumps({"error": "Invalid storage account configuration"}),
            status_code=400,
            mimetype="application/json"
        )
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    filename = f"{task}/{task}-messages.json"

    blob_client = blob_service_client.get_blob_client(
        container=container_name, blob=filename
    )
    chat_history_text = blob_client.download_blob().content_as_text()

    # Call Azure OpenAI
    payload = build_payload(chat_history_text)
    response = requests.post(
        OPENAI_ENDPOINT,
        headers=get_openai_headers(),
        json=payload,
        timeout=60
    )
    response.raise_for_status()
    response_json = response.json()

    # Extract results
    answer_content = response_json['choices'][0]['message']['content']
    usage = response_json['usage']
    end_time = datetime.now()
    execution_time_ms = (end_time - start_time).total_seconds() * 1000

    final_response = {
        "answer": answer_content,
        "prompt_tokens": usage['prompt_tokens'],
        "completion_tokens": usage['completion_tokens'],
        "total_tokens": usage['total_tokens'],
        "model": response_json.get('model', 'unknown'),
        "execution_time": round(execution_time_ms)
    }

    return func.HttpResponse(
        json.dumps(final_response), mimetype="application/json"
    )