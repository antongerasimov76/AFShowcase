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
    leg = req_body.get('Request Leg ID')
    container_name = req_body.get('ABS Container')
    account_name = req_body.get('ABS Account Name')
    #logging.info('inputs are fetched')

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
        #subject = chat_history[0]["subject"]
        #clientemail = chat_history[0]["from"]

        # Download the CSV content for parcel data
        filename = str(task) + "/" + str(task) + ".json"
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        all_content = blob_client.download_blob()
        parcel_data_text = all_content.content_as_text()
        #parcel_data = json.loads(parcel_data_text)
        


        # Download the Vendor Email
        filename = str(task) + "/" + str(task) + "-vendor-request-" + leg + "-messages.json"

        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        all_content = blob_client.download_blob()
        vendor_answer_text = all_content.content_as_text()
        #parcel_data = json.loads(parcel_data_text)

        payload = {
        "messages": [
            {
            "role": "system",
            "content": [
                {
                "type": "text",
                "text": f"Today is {datetime.now()} " + """ You are a Procurement Manager at M9 Logistics Company.
You previously sent a rate and service request to a logistics vendor (e.g., carrier, freight agent, or service provider).
Now you have received a reply from the vendor.

You also have access to:

The chat history with the client: """ + chat_history_text + """

The chat history with the vendor including the most recent vendor reply: """ + vendor_answer_text + """

The parcel data: """ + parcel_data_text + """

Your task is to analyze the vendor’s reply and determine whether they have provided a transportation quotation or not.

A quotation is considered valid if the vendor provides:

A freight price or rate (in any currency)

Transit time or schedule

Service conditions (e.g., Incoterms, surcharges, availability)

Any combination of the above that allows you to assess the offer

Return one of the following structured JSON responses:

1. If a valid quotation is provided:
{
  "action": "Answer given",
  "offer summary": "Summarized text including price, transit time, service conditions, and any other relevant notes in a single paragraph.",
  "email": {
    "content": "Professional reply to the vendor in HTML format thanking them for their quotation, politely confirming receipt, and stating that you will proceed with internal processing or get back if additional clarification is needed."
  }
}

2. If the quotation is incomplete, vague, or missing pricing or conditions:
{
  "action": "Clarification",
  "offer summary": "Summarized text of any partial data provided by the vendor — e.g., available routes, general schedule, or any information already included in their message.",
  "email": {
    "content": "Professional reply asking the vendor in HTML format to provide the missing pricing and/or other transport conditions. If the vendor asked a question, include a clear and polite answer to that question."
  }
}
Guidelines:
Use valid JSON with double quotes only
"offer summary" is always included as a single-line or multi-line plain text field, summarizing price, timelines, service terms, and any other known details
Do not include the full vendor message in the JSON
The email should be polite, professional, and appropriate for B2B logistics
If the vendor’s reply is in a foreign language, write the "offer summary" in English
If the vendor provides multiple scenarios (e.g., air vs. sea), refer to all of them in the summary
The "offer summary" field must always be present as a single text field (not a nested object). If the vendor reply is incomplete, summarize what they did provide.
Do not add any signature, name, or contact details at the end of your reply.
"""
                }
            ]
            },
            {
            "role": "user",
            "content": [
                {
                "type": "text",
                "text": "please see the latest message from the vendor"
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
