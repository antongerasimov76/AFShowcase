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
    
    task = req_body.get('TaskID')
    leg = req_body.get('RequestLegID ')


    if task:
        GPT4V_KEY = "1CgfeI6A9QsByYMPMEwFWChmEDGoIiIVPWYquWH0LjbGPkJbwppJJQQJ99BCACHYHv6XJ3w3AAABACOGJFxT"
        #GPT4V_ENDPOINT = "https://m9ai.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=2024-08-01-preview"
        #GPT4V_ENDPOINT = "https://m9ai.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-02-15-preview"
        GPT4V_ENDPOINT = "https://paphos-eus2.openai.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview"
        
        headers = {
            "Content-Type": "application/json",
            "api-key": GPT4V_KEY,
        }
        connection_string = "DefaultEndpointsProtocol=https;AccountName=getaianswerb0488d;AccountKey=pM59bz97AqOMVpC28/51Z/RMPrxUmmv7OEu8ZTHKTXChGV8bdoGLSIGn0XmCj43cK2L65BPpi3XH+AStF90Gzg==;EndpointSuffix=core.windows.net"
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_name = 'tasks'
        filename = str(task) + "/" + str(task) + "-messages.json"

        # Download the CSV content for message history
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        all_content = blob_client.download_blob()
        chat_history_text = all_content.content_as_text()
        chat_history = json.loads(chat_history_text)
        subject = chat_history[0]["subject"]
        clientemail = chat_history[0]["from"]

        # Download the CSV content for parcel data
        filename = str(task) + "/" + str(task) + ".json"
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        all_content = blob_client.download_blob()
        parcel_data_text = all_content.content_as_text()
        #parcel_data = json.loads(parcel_data_text)

        # Download the Vendor Email
        filename = str(task) + "/" + str(task) + "-vendor-request-{" + leg + "}-messages.json"
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

The chat istory with the client: """ + chat_history_text + """

The most recent vendor reply, including any text or attachments: """ + vendor_answer_text + """

The pacel data: """ + parcel_data_text + """

Your task is to analyze the vendor’s reply and determine whether they provided a transportation quotation or not.

Consider the vendor has provided a quotation if the message includes:
A freight price or rate (in any currency)

Transit time or schedule

Service conditions (e.g., Incoterms, surcharges, availability)

Any combination of the above that allows you to assess the offer

Return one of the following structured JSON responses:

1. If the vendor has provided pricing and conditions, return:
{
  "action": "Answer given",
  "vendor answer": "The price and service cinditions are given my vendor",
  "email": {
    "content": "Professional reply to the vendor thanking them for their quotation, politely confirming receipt, and stating that you will proceed with internal processing or get back if additional clarification is needed."
  }
}
2. If the vendor has NOT provided a price, or the message is vague or only asks a question or acknowledges the request, return:
{
  "action": "Clarification",
  "vendor answer": "Full reply message from the vendor in original format",
  "email": {
    "content": "Professional reply asking the vendor to provide the missing pricing and/or other transport conditions. If the vendor asked a question, include a clear and polite answer to that question."
  }
}
Guidelines:
Always use valid JSON syntax with double quotes.
Keep the full vendor reply exactly as it was received in the "vendor answer" field.
Do not paraphrase or modify the vendor’s message.
The "email" → "content" must be written in a polite and professional tone, appropriate for a B2B logistics setting.
If the vendor’s reply is in a language other than English, keep it as-is in "vendor answer", and write the reply email in English.
If the vendor mentions multiple scenarios or options, refer to them clearly (e.g., "Thank you for providing rates for both air and sea transport...").

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

        # Calculate execution time and construct final response
        end_time = datetime.now()
        execution_time_ms = (end_time - start_time).total_seconds() * 1000
        
        final_response = {
            "answer": answer_content,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "execution_time": round(execution_time_ms)
        }

        # Return the final response as JSON
        return func.HttpResponse(json.dumps(final_response), mimetype="application/json")

    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )
