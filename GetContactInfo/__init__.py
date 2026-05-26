

import logging
import requests
import azure.functions as func
import json
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from datetime import datetime
from shared_code.config import OPENAI_API_KEY, OPENAI_ENDPOINT, BLOB_CONNECTION_STRING_PRIMARY, BLOB_CONNECTION_STRING_SECONDARY

def main(req: func.HttpRequest) -> func.HttpResponse:
    start_time = datetime.now()
    logging.info('Python HTTP trigger function processed a request.')

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            "Invalid request body",
            status_code=400
        )
    
    task = req_body.get('Task ID')
    container_name = req_body.get('ABS Container')
    account_name = req_body.get('ABS Account Name')

    if task:
        headers = {
            "Content-Type": "application/json",
            "api-key": OPENAI_API_KEY,
        }

        if account_name == "getaianswerb0488d":
            connection_string = BLOB_CONNECTION_STRING_PRIMARY
        else: 
            connection_string = BLOB_CONNECTION_STRING_SECONDARY

        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        filename = str(task) + "/" + str(task) + "-messages.json"

        # Download message history
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        all_content = blob_client.download_blob()
        chat_history_text = all_content.content_as_text()
        chat_history = json.loads(chat_history_text)
        subject = chat_history[0]["subject"]
        clientemail = chat_history[0].get("interaction email")

        # Prepare payload for GPT with direct chat history text
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": """Extract client contact information from the email conversation below. Return ONLY a JSON object with the following fields:
- name: Client's full name
- companyName: Company name
- address: Full street address
- countryCode: Two-letter country code (e.g., GB, US, DE)
- city: City name
- county: County or state name
- phoneNo: Main phone number (base number without extension)
- phoneNoExt: Extension part of the main phone number (if any)
- mobilePhoneNo: Mobile phone number
- email: Email address
- faxNo: Fax number
- homePage: Website URL
- languageCode: Three-letter language code in Microsoft Business Central format (e.g., ENG for English, RUS for Russian, DEU for German, FRA for French)

Example format:
{
    "name": "John Smith",
    "companyName": "Company Ltd",
    "address": "123 Business Street",
    "countryCode": "GB",
    "city": "London",
    "county": "Greater London",
    "phoneNo": "+44 20 1234 5678",
    "phoneNoExt": "1234",
    "mobilePhoneNo": "+44 7700 123456",
    "email": "john.smith@company.com",
    "faxNo": "+44 20 1234 5679",
    "homePage": "www.company.com",
    "languageCode": "ENG"
}

If any field cannot be found, use null as the value.

Email conversation:
""" + chat_history_text
                }
            ],
            "temperature": 0.7,
            "max_tokens": 3000,
            "response_format": {"type": "json_object"}
        }

        # Get client info from GPT
        response = requests.post(OPENAI_ENDPOINT, headers=headers, json=payload)
        response_json = response.json()

        # Format the final response
        usage = response_json.get('usage', {})
        answer_content = response_json['choices'][0]['message']['content']
        
        # Calculate execution time in milliseconds
        end_time = datetime.now()
        execution_time_ms = (end_time - start_time).total_seconds() * 1000
        
        final_response = {
            "answer": answer_content,
            "prompt_tokens": usage.get('prompt_tokens'),
            "completion_tokens": usage.get('completion_tokens'),
            "total_tokens": usage.get('total_tokens'),
            "model": response_json.get('model', 'unknown'),
            "execution_time": round(execution_time_ms)
        }

        return func.HttpResponse(
            json.dumps(final_response),
            mimetype="application/json"
        )
    else:
        return func.HttpResponse(
            "Please pass a Task ID in the request body",
            status_code=400
        )