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
        return func.HttpResponse(
            "Missing 'Task ID' in request body.",
            status_code=400
        )

    try:
        # === Azure OpenAI (same structure as in GetSecondAnswerClient) ===
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
        chat_history = json.loads(chat_history_text)

        subject = chat_history[0].get("subject", "")
        clientemail = chat_history[0].get("interaction email", "")

        # === Load task/parcel data (context) ===
        data_blob_path = f"{task}/{task}.json"
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=data_blob_path)
        parcel_data_text = blob_client.download_blob().content_as_text()

        # === Compose prompt for reminder draft ===
        # Timezone note: company operates EET/EEST (Asia/Nicosia). Ask the model to compute UTC ISO string.
        now_iso = datetime.utcnow().isoformat() + "Z"

        system_text = (
            f"Now (UTC) is {now_iso}. You are a Sales Manager at M9 Logistics.\n"
            "Your task: draft a **polite, concise reminder email** to the client regarding their transportation/customs request. "
            "Use the data below.\n\n"
            "DATA YOU HAVE:\n"
            "I) Current task/request context (JSON):\n"
            f"{parcel_data_text}\n\n"
            "II) Full email/message thread history between you and the client (JSON list):\n"
            f"{chat_history_text}\n\n"
            "WHAT TO DO:\n"
            "1) From the thread, determine exactly **what information we are still waiting for** from the client (e.g., dimensions, HS code, addresses, incoterms, product description, dates). "
            "List these missing items explicitly.\n"
            "2) Draft a **polite reminder email** asking for those specific items. The email should:\n"
            "- Be in the **same language** as the **most recent client message**. If that language is not English, also include an **English translation** below, separated by a clear divider like: '--- English version ---'.\n"
            "- Be short (5–9 sentences), friendly, and professional; non-pushy.\n"
            "- Reference the ongoing request without repeating all prior details.\n"
            "- Offer help and accept attachments/links.\n"
            "- Avoid signatures (no name/role/phone/footer).\n"
            "3) Check the thread for **promised reply times** from the client (absolute like 'on 12 Oct at 14:00', or relative like 'tomorrow', 'послезавтра', 'by Friday EOD', 'next week'). "
            "If found, compute a concrete **UTC ISO 8601** timestamp for when to send the reminder, called `send_time`. Rules:\n"
            "- Resolve relative times against the timestamp of the **message that contains the promise**; if absent, resolve relative to 'Now (UTC)'.\n"
            "- Assume the business local timezone is **Asia/Nicosia**. If the promise has a date but **no time**, default to **10:00** local time that day.\n"
            "- If multiple promises exist, choose the **latest** one.\n"
            "- If the computed time is already in the past, set `send_time` to **\"immidiately\"** (exactly this spelling).\n"
            "- If **no promise** is found, set `send_time` to **\"immidiately\"**.\n\n"
            "OUTPUT FORMAT:\n"
            "Return a single valid JSON object with **double quotes** only, starting with { and ending with }. Use this schema:\n"
            "{\n"
            "  \"action\": \"Reminder Draft\",\n"
            "  \"email\": {\n"
            "    \"to\": \"" + clientemail + "\",\n"
            "    \"title\": \"" + subject + "\",\n"
            "    \"content\": \"<html>...polite reminder body here...</html>\"\n"
            "  },\n"
            "  \"missing_info\": [\"item1\", \"item2\", ...],\n"
            "  \"send_time\": \"YYYY-MM-DDTHH:MM:SSZ or immidiately\"\n"
            "}\n"
            "Notes:\n"
            "- Keep all JSON field **values** (except the HTML body language) in **English**.\n"
            "- Do not add any extra fields.\n"
            "- Do not include a signature.\n"
        )

        user_text = (
            f"email: {clientemail}; title: {subject}; "
            "Task: Prepare the reminder draft and send_time based on the latest thread."
        )

        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": system_text}]
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": user_text}]
                }
            ],
            "temperature": 0.7,
            "top_p": 0.95,
            "max_tokens": 2400
        }

        response = requests.post(GPT4V_ENDPOINT, headers=headers, json=payload)
        response_json = response.json()

        # Pull model answer and usage
        answer_content = response_json['choices'][0]['message']['content']
        prompt_tokens = response_json.get('usage', {}).get('prompt_tokens', None)
        completion_tokens = response_json.get('usage', {}).get('completion_tokens', None)
        total_tokens = response_json.get('usage', {}).get('total_tokens', None)
        model_name = response_json.get('model', 'unknown')

        end_time = datetime.now()
        execution_time_ms = (end_time - start_time).total_seconds() * 1000

        final_response = {
            "answer": answer_content,           # JSON с полем email/content, missing_info и send_time
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "model": model_name,
            "execution_time": round(execution_time_ms)
        }

        return func.HttpResponse(json.dumps(final_response), mimetype="application/json")

    except Exception as e:
        logging.exception("GetReminderDraft failed.")
        return func.HttpResponse(
            f"Internal error: {str(e)}",
            status_code=500
        )
