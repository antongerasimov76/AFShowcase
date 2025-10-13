import logging
import json
import mimetypes
import base64
import requests
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from io import BytesIO
from datetime import datetime

# GPT-4.1 settings
GPT4_KEY = "1CgfeI6A9QsByYMPMEwFWChmEDGoIiIVPWYquWH0LjbGPkJbwppJJQQJ99BCACHYHv6XJ3w3AAABACOGJFxT"
GPT4_ENDPOINT = "https://paphos-eus2.openai.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview"

SYSTEM_PROMPT = """
You are a logistics assistant.
Extract only useful data for freight transportation or customs clearance:
- cargo dimensions, weight, volume
- cargo description and properties
- packaging details
- origin and destination points (POL/POD)
- shipping or delivery dates
- rates and validity
- other relevant details
If the attachment contains no useful logistics data, return an EMPTY string (no text at all).
Respond concisely with facts only; do not add explanations.
"""

def analyze_with_gpt(file_bytes, file_type):
    headers = {"Content-Type": "application/json", "api-key": GPT4_KEY}

    if file_type.startswith("image/"):
        encoded = base64.b64encode(file_bytes).decode("utf-8")
        messages = [
            {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{file_type};base64,{encoded}"}}
            ]},
        ]
    else:
        try:
            text_content = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            text_content = ""
        messages = [
            {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
            {"role": "user", "content": [{"type": "text", "text": text_content}]},
        ]

    payload = {
        "messages": messages,
        "temperature": 1,
        "max_completion_tokens": 800,
    }

    r = requests.post(GPT4_ENDPOINT, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()

    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})  # {prompt_tokens, completion_tokens, total_tokens}
    model = data.get("model", "gpt-4.1")

    return text, usage, model

def main(req: func.HttpRequest) -> func.HttpResponse:
    start_time = datetime.now()
    logging.info('Processing request for attachment analysis.')

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid request body", status_code=400)

    task_id = req_body.get('Task ID')
    container_name = req_body.get('ABS Container')
    account_name = req_body.get('ABS Account Name')
    message_id = str(req_body.get('Message ID'))

    if not (task_id and container_name and account_name and message_id):
        return func.HttpResponse("Missing parameters", status_code=400)

    # Select correct connection string
    if account_name == "getaianswerb0488d":
        connection_string = "DefaultEndpointsProtocol=https;AccountName=getaianswerb0488d;AccountKey=pM59bz97AqOMVpC28/51Z/RMPrxUmmv7OEu8ZTHKTXChGV8bdoGLSIGn0XmCj43cK2L65BPpi3XH+AStF90Gzg==;EndpointSuffix=core.windows.net"
    else: 
        connection_string = "DefaultEndpointsProtocol=https;AccountName=m9aitasks;AccountKey=eVv1B099DUs+1MGENRqIns6AsNUVtmvFgjJ1e3Vw2hAdCjtOHwVjujtY7mTc81C+KDFPAzU8CTBs+AStwxBIKg==;EndpointSuffix=core.windows.net"

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)

    blobs = container_client.list_blobs(name_starts_with=f"{task_id}/Attachments/")
    extracted_by_file = {}
    sum_prompt = 0
    sum_completion = 0
    sum_total = 0
    model_name = None

    for blob in blobs:
        if f"_{message_id}_" not in blob.name:
            continue

        file_type, _ = mimetypes.guess_type(blob.name)
        if not file_type:
            file_type = "application/octet-stream"

        blob_bytes = container_client.download_blob(blob).readall()

        try:
            text, usage, model = analyze_with_gpt(blob_bytes, file_type)

            # Skip empty / “no data” style outputs
            norm = (text or "").strip().lower()
            no_data_markers = (
                "no relevant data",
                "no relevant information",
                "not relevant",
                "please upload",
            )
            if not norm or any(m in norm for m in no_data_markers):
                continue

            extracted_by_file[blob.name] = text

            # Aggregate usage
            sum_prompt += int(usage.get("prompt_tokens", 0))
            sum_completion += int(usage.get("completion_tokens", 0))
            sum_total += int(usage.get("total_tokens", 0))
            model_name = model  # same deployment, okay to take the latest
        except Exception as e:
            # You can choose to omit errors from the final `answer`
            logging.warning(f"Failed to analyze {blob.name}: {e}")

    # Build the required final shape
    final_answer_str = json.dumps(extracted_by_file, ensure_ascii=False)  # exactly “what it outputs now” as a string

    # Calculate execution time
    end_time = datetime.now()
    execution_time_ms = (end_time - start_time).total_seconds() * 1000

    final_response = {
        "answer": final_answer_str,
        "prompt_tokens": sum_prompt,
        "completion_tokens": sum_completion,
        "total_tokens": sum_total,
        "model": model_name or "gpt-4.1-2025-04-14",
        "execution_time": round(execution_time_ms)
    }

    return func.HttpResponse(json.dumps(final_response, ensure_ascii=False), mimetype="application/json")