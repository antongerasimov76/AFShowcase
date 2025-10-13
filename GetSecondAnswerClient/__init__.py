from datetime import datetime
import logging
import requests
import azure.functions as func
import json
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient


def main(req: func.HttpRequest) -> func.HttpResponse:
    start_time = datetime.now()
    logging.info('GetReminderDraft HTTP trigger function started.')

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid request body", status_code=400)

    task = req_body.get('Task ID')
    container_name = req_body.get('ABS Container')
    account_name = req_body.get('ABS Account Name')

    if not task:
        return func.HttpResponse("Missing 'Task ID' in request body.", status_code=400)

    try:
        # === Azure OpenAI (same style as original) ===
        GPT4V_KEY = "1CgfeI6A9QsByYMPMEwFWChmEDGoIiIVPWYquWH0LjbGPkJbwppJJQQJ99BCACHYHv6XJ3w3AAABACOGJFxT"
        GPT4V_ENDPOINT = "https://paphos-eus2.openai.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview"

        headers = {
            "Content-Type": "application/json",
            "api-key": GPT4V_KEY,
        }

        # === Azure Blob Storage (same selection logic) ===
        if account_name == "getaianswerb0488d":
            connection_string = "DefaultEndpointsProtocol=https;AccountName=getaianswerb0488d;AccountKey=pM59bz97AqOMVpC28/51Z/RMPrxUmmv7OEu8ZTHKTXChGV8bdoGLSIGn0XmCj43cK2L65BPpi3XH+AStF90Gzg==;EndpointSuffix=core.windows.net"
        else:
            connection_string = "DefaultEndpointsProtocol=https;AccountName=m9aitasks;AccountKey=eVv1B099DUs+1MGENRqIns6AsNUVtmvFgjJ1e3Vw2hAdCjtOHwVjujtY7mTc81C+KDFPAzU8CTBs+AStwxBIKg==;EndpointSuffix=core.windows.net"

        blob_service_client = BlobServiceClient.from_connection_string(connection_string)

        # === Load chat history ===
        messages_blob_path = f"{task}/{task}-messages.json"
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=messages_blob_path)
        chat_history_text = blob_client.download_blob().content_as_text()
        # можно не парсить, но валидность проверим
        _ = json.loads(chat_history_text)

        # === Load task/request context ===
        data_blob_path = f"{task}/{task}.json"
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=data_blob_path)
        parcel_data_text = blob_client.download_blob().content_as_text()
        # _ = json.loads(parcel_data_text)  # при желании валидируем

        # === Compose payload with triple-quoted prompt ===
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Today is {datetime.utcnow().isoformat()}Z " + """
You are a Sales Manager at M9 Logistics.

TASK:
Prepare a **polite reminder** to the client about the status of their transportation/customs request. 
We might be waiting either for **additional information** and/or for the **order confirmation** — determine this from the thread.

YOU HAVE:
I) Current task/request data (JSON):
""" + parcel_data_text + """
II) Full email/message thread (JSON list):
""" + chat_history_text + """

WHAT TO DO:
1) From the thread, determine precisely what is still pending:
   - missing data items (e.g., dimensions, HS code, addresses, dates, Incoterms, etc.);
   - and/or that we are waiting for **order confirmation**.
2) Draft a **short, friendly, professional HTML email** that:
   - politely reminds the client about the pending items and/or the needed order confirmation;
   - keeps 5–9 sentences, non-pushy tone, offers help, allows attachments/links;
   - uses the **language of the client's most recent message**. 
     If that language is not English, include an **English translation** below separated with a line: `--- English version ---`.
   - do NOT add any signature or contact details.
3) Detect any **promised reply time** in the thread (absolute or relative, including phrases like "tomorrow", "послезавтра", "by Friday EOD", etc.).
   Compute a concrete **UTC ISO 8601** timestamp for when to send the reminder (`send_time`) using these rules:
   - Resolve relative promises against the timestamp of the message that contains the promise; if not available, use current UTC.
   - Business local timezone is **Asia/Nicosia**. If a date is given without time, default to **10:00** local time.
   - If multiple promises exist, use the **latest** one.
   - If the computed time is in the past, set `send_time` to "immidiately".
   - If no promise exists, set `send_time` to "immidiately".

OUTPUT:
Return a single **valid JSON** object (double quotes only), exactly with these fields:
{
  "action": "Reminder Draft",
  "email": {
    "content": "<html>...the polite reminder body...</html>"
  },
  "missing_info": ["item1", "item2", "..."],    // may be empty if nothing is missing
  "awaiting_order_confirmation": true|false,     // whether we wait for order confirmation
  "send_time": "YYYY-MM-DDTHH:MM:SSZ or immidiately"
}

RULES:
- Keep all JSON values (except the HTML email language content) in **English**.
- Do not add extra fields.
- Do not include subject, recipients, signatures, names, or contacts.
- Be concise and professional; calm tone even if client is rude.
"""
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Prepare the reminder draft and send_time based on the provided data and thread."
                        }
                    ]
                }
            ],
            "temperature": 0.7,
            "top_p": 0.95,
            "max_tokens": 2400
        }

        response = requests.post(GPT4V_ENDPOINT, headers=headers, json=payload)
        response_json = response.json()

        answer_content = response_json['choices'][0]['message']['content']
        usage = response_json.get('usage', {})
        prompt_tokens = usage.get('prompt_tokens')
        completion_tokens = usage.get('completion_tokens')
        total_tokens = usage.get('total_tokens')
        model_name = response_json.get('model', 'unknown')

        end_time = datetime.now()
        execution_time_ms = (end_time - start_time).total_seconds() * 1000

        final_response = {
            "answer": answer_content,   # JSON с email.content, missing_info, awaiting_order_confirmation, send_time
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "model": model_name,
            "execution_time": round(execution_time_ms)
        }

        return func.HttpResponse(json.dumps(final_response), mimetype="application/json")

    except Exception as e:
        logging.exception("GetReminderDraft failed.")
        return func.HttpResponse(f"Internal error: {str(e)}", status_code=500)
