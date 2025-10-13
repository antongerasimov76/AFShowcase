import logging
import requests
import azure.functions as func
import json
from datetime import datetime


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
    
    draft_text = req_body.get('Draft Body')
    email_text = req_body.get('Email Body')
    #logging.info(email_text)
    #logging.info('Data ready')
    #logging.info(draft_text)


    if draft_text:
        GPT4V_KEY = "05287303f01b406582788526baca76c3"
#        GPT4V_KEY = "1CgfeI6A9QsByYMPMEwFWChmEDGoIiIVPWYquWH0LjbGPkJbwppJJQQJ99BCACHYHv6XJ3w3AAABACOGJFxT"
#        GPT4V_ENDPOINT = "https://paphos-eus2.openai.azure.com/openai/deployments/o4-mini/chat/completions?api-version=2025-01-01-preview"
#        GPT4V_ENDPOINT = "https://m9ai.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=2024-08-01-preview"
        GPT4V_ENDPOINT = "https://m9ai.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-02-15-preview"

        headers = {
            "Content-Type": "application/json",
            "api-key": GPT4V_KEY,
        }
        payload = {
        "messages": [
            {
            "role": "system",
            "content": [
                {
                "type": "text",
                "text": """
You are an assistant that evaluates how closely an AI-generated draft email matches the final email sent by a human sales manager at M9 Logistics.

Your goal is to return a JSON object with:
{
  "score": float,   // similarity score from 0.00 to 1.00
  "explanation": string  // reasoning behind the score
}

### Evaluation Criteria:
1. ✅ Semantic Meaning — Highest priority  
   Focus on intent, stage of the process, and whether the draft correctly reflects the current state of communication.  
   - If the draft suggests the quote is being prepared or all data is received, but the final email asks the client for more information, this is a serious semantic error.  
   - In such cases, the score must not exceed 0.2.

🔴 Example (semantic contradiction, critical consequence):  
Draft: "We will prepare a commercial offer..."  
Final: "Which dates are you needed?"  
➡️ Score: 0.2 or lower — Draft assumes completeness; final reveals missing info.

🔴 Example:  
Draft: "We have all the data."  
Final: "Please clarify your dimensions."  
➡️ Score: 0.2 or lower — Contradiction with high consequence.

---

2. ⚠️ Moderate inconsistencies — score 0.3–0.6  
   Example:  
   Draft: "Please confirm if the goods are hazardous."  
   Final: "All set, we will now prepare your offer."  
   ➡️ Score: ~0.3–0.4

---

3. ✅ Minor differences — score 0.7–1.0  
   Differences only in tone, grammar, or formatting — meaning matches.  
   Example:  
   Draft: "We are ready to provide you a quote."  
   Final: "Everything clear, thank you."  
   ➡️ Score: ~0.9

---

🚫 Irrelevant Draft Rule:  
If the draft email has no overlap in meaning, content, or business context with the final email, return:
{
  "score": 0.00,
  "explanation": "The draft and final emails are unrelated in meaning or context."
}

Return **only** a valid JSON object, nothing else.
"""
                }
            ]
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"The draft body provided by AI: {draft_text}; a manager's email body: {email_text}"
                }
            ]
        },
    ],
        "temperature": 0.2,
        "top_p": 1,
        "max_tokens": 500
        }
        logging.info('Payload ready')

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
