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
        filename = str(task) + "/" + str(task) + "-messages-simple.yaml"

        # Download the CSV content for message history

        logging.info('blob started')

        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        all_content = blob_client.download_blob()
        chat_history_text = all_content.content_as_text()
        #chat_history = json.loads(chat_history_text)

        logging.info('blob ready')


        payload = {
        "messages": [
            {
            "role": "system",
            "content": [
                {
                "type": "text",
                "text": f"Today is {datetime.now()} " + """You are a Quality Control Reviewer at M9 Logistics.

The conversation you're reviewing has **already been evaluated by another AI agent**, who classified it as:

**"Not a New Request"** — meaning the initial email from the client was determined to be **not** a new inquiry for logistics services (such as freight transportation or customs clearance).

---

### Your task:

You must now **verify** whether this decision was **correct**, based on **the full conversation**, including:
- The **initial message from the client**
- Possible follow-up messages from the client
- The **final message from the manager** (outbound reply)

---

### Background (Summary of First Agent's Criteria):

The first AI agent classified messages as a **new request** only if:
- The **initial email from the client** started a **new conversation** about freight transport or customs clearance.
- It did **not reference prior discussions**, and
- It contained a **clear request to start** a transportation or clearance process.

If the client’s email was a follow-up, or didn’t clearly start a logistics task, it was marked as **"Not a New Request"**.

---

### What You Must Do:

Review the **entire conversation**, especially the manager’s reply, and decide:

- Was the **initial decision ("Not a New Request")** correct?
- Or, does the conversation actually contain a **valid new logistics request** that was misclassified?

---

### Your Output Format (strict JSON):

{
  "review_result": "Request" | "Not a Request",
  "reasoning": "Explain briefly in English why the original classification was correct or incorrect. Focus on whether the initial client message qualifies as a new logistics request, and how the manager’s reply supports or contradicts that."
}

---

### Additional Notes:
- You are **not making a classification from scratch**. You are checking whether the previous agent’s decision **"Not a New Request"** was appropriate.
- Pay special attention to the manager’s reply. If it includes a quote, service confirmation, or logistic handling, it may indicate the original classification was wrong.
- However, if the conversation continues a previous task or the manager simply declines or discusses existing details, the original classification is likely correct.


### **entire conversation**  
""" +                    
chat_history_text
                }
            ]
            },
            {
            "role": "user",
            "content": [
                {
                "type": "text",
                "text": "Content: please see the latest message from the manager"
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
