from datetime import datetime
import logging
import requests
import azure.functions as func
import json
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient


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
    
    task = req_body.get('Task ID')
    container_name = req_body.get('ABS Container')
    account_name = req_body.get('ABS Account Name')

    if task:
        GPT4V_KEY = "1CgfeI6A9QsByYMPMEwFWChmEDGoIiIVPWYquWH0LjbGPkJbwppJJQQJ99BCACHYHv6XJ3w3AAABACOGJFxT"
        #GPT4V_ENDPOINT = "https://m9ai.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=2024-08-01-preview"
        #GPT4V_ENDPOINT = "https://m9ai.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-02-15-preview"
        GPT4V_ENDPOINT = "https://paphos-eus2.openai.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview"
        
        headers = {
            "Content-Type": "application/json",
            "api-key": GPT4V_KEY,
        }
        if account_name == "getaianswerb0488d":
            connection_string = "DefaultEndpointsProtocol=https;AccountName=getaianswerb0488d;AccountKey=pM59bz97AqOMVpC28/51Z/RMPrxUmmv7OEu8ZTHKTXChGV8bdoGLSIGn0XmCj43cK2L65BPpi3XH+AStF90Gzg==;EndpointSuffix=core.windows.net"
        else: 
            connection_string = "DefaultEndpointsProtocol=https;AccountName=m9aitasks;AccountKey=eVv1B099DUs+1MGENRqIns6AsNUVtmvFgjJ1e3Vw2hAdCjtOHwVjujtY7mTc81C+KDFPAzU8CTBs+AStwxBIKg==;EndpointSuffix=core.windows.net"
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        filename = str(task) + "/" + str(task) + "-messages.json"

        # Download the CSV content for message history
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        all_content = blob_client.download_blob()
        chat_history_text = all_content.content_as_text()
        chat_history = json.loads(chat_history_text)
 
        payload = {
        "messages": [
            {
            "role": "system",
            "content": [
                {
                "type": "text",
                "text": f"Today is {datetime.now()} " + """You are a Logistics Assistant at M9 Logistics Company. Your task is to create structured JSON data for a transportation request based on the conversation history with the client.

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
        },
        ...
    ]
}

Please carefully read the chat history with the client to extract all necessary data. If some information is missing or unclear, leave that field empty in the JSON but include the field with an empty value (e.g., "" or []).

The CHAT HISTORY is: """ + chat_history_text + """

IMPORTANT:
- Always ensure country codes and airport codes are correct and properly formatted.
- Dimensions must be in centimeters and kilograms.
- If multiple packages are mentioned, create multiple entries inside "Dimensions".
- For "Stackable" field:
  - Analyze the information available (package type, dimensions, weight, description) to determine if the package is likely stackable.
  - If you are reasonably confident based on size/description (for example, boxes are usually stackable), set "Stackable" accordingly.
  - If you cannot determine from the information provided, default "Stackable" to false.

- Only generate the JSON data. Do not include explanations or additional text.
"""
                }
            ]
            },

        ],
        "temperature": 1,
        "top_p": 0.95,
        "max_tokens": 2400
        }


        response = requests.post(GPT4V_ENDPOINT, headers=headers, json=payload)
        response_json = response.json()

        # Extract the content from the response
        answer_content = response_json['choices'][0]['message']['content']

        # Extract token usage details
        prompt_tokens = response_json['usage']['prompt_tokens']
        completion_tokens = response_json['usage']['completion_tokens']
        total_tokens = response_json['usage']['total_tokens']
        model_name = response_json.get('model', 'unknown')  # fallback на случай отсутствия

        # Calculate execution time and construct final response
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
        # Return the final response as JSON
        return func.HttpResponse(json.dumps(final_response), mimetype="application/json")

    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )
