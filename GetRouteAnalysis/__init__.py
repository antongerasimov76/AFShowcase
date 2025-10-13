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
        GPT4V_ENDPOINT = "https://paphos-eus2.openai.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview"
        #GPT4V_ENDPOINT = "https://paphos-eus2.openai.azure.com/openai/deployments/o1/chat/completions?api-version=2025-01-01-preview"
        #GPT4V_KEY = "1CgfeI6A9QsByYMPMEwFWChmEDGoIiIVPWYquWH0LjbGPkJbwppJJQQJ99BCACHYHv6XJ3w3AAABACOGJFxT"

        headers = {
            "Content-Type": "application/json",
            "api-key": GPT4V_KEY,
        }
        if account_name == "getaianswerb0488d":
            connection_string = "DefaultEndpointsProtocol=https;AccountName=getaianswerb0488d;AccountKey=pM59bz97AqOMVpC28/51Z/RMPrxUmmv7OEu8ZTHKTXChGV8bdoGLSIGn0XmCj43cK2L65BPpi3XH+AStF90Gzg==;EndpointSuffix=core.windows.net"
        else: 
            connection_string = "DefaultEndpointsProtocol=https;AccountName=m9aitasks;AccountKey=eVv1B099DUs+1MGENRqIns6AsNUVtmvFgjJ1e3Vw2hAdCjtOHwVjujtY7mTc81C+KDFPAzU8CTBs+AStwxBIKg==;EndpointSuffix=core.windows.net"
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        filename = str(task) + "/" + str(task) + "-analysis-routes.json"

        # Download the CSV content for routes
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        all_content = blob_client.download_blob()
        routes_text = all_content.content_as_text()
        routes = json.loads(routes_text)

        # Download the CSV content for legs
        filename = str(task) + "/" + str(task) + "-analysis-legs.json"
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        all_content = blob_client.download_blob()
        legs_text = all_content.content_as_text()
        legs = json.loads(legs_text)

        # Download the CSV content for message history
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        all_content = blob_client.download_blob()
        chat_history_text = all_content.content_as_text()
        chat_history = json.loads(chat_history_text)


        # Download the CSV content for parcel data
        filename = str(task) + "/" + str(task) + ".json"
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        all_content = blob_client.download_blob()
        parcel_data_text = all_content.content_as_text()
        parcel_data = json.loads(parcel_data_text)

        # Download the CSV content for meneger comments
        filename = str(task) + "/" + str(task) + "-manager-processing-comment.output"
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        all_content = blob_client.download_blob()
        managercomments_text = all_content.content_as_text()

        payload = {
        "messages": [
            {
            "role": "system",
            "content": [
                {
                "type": "text",
                "text": """You are a Sales Manager Assistant in M9 Logistics Сompany. Your task is to prepare the detailed cost analysis for given parsel for Sales Manager
                for parcel transportation. Sales Manager will use your analisys to prepare Commercial offer to a client. 
                The ruotes are: """ + routes_text + """
                The legs are: """ + legs_text + """
                The parcel data is: """  + parcel_data_text +
                """ CONSIDER MANAGER COMMENTS: """ + managercomments_text + """
                    ANSWER IN LANGUAGE THAT THE USER USED 
                    ANSWER HAVE TO BE AS EMAIL IN HTML FORMAT 
                    THE CHAT HISTORY WITH THE CLIENT: """ + chat_history_text + """      
                    EACH ROUTE CONSISTS OF ONE OR SEVERAL LEGS 
                    THE COSTS OF EACH LEGS ARE GIVEN               
                    THIS COSTS PREDUCTION HAVE TO BE CALCULATED AMONG ALL POSSIBLE ROUTES PROVIDED 
                    PUT THIS COSTS PREDICTION AND TERMS (INCULDING TIMEFRAMES) TO THE START OF THE EMAIL. 
                    THE EMAIL CONTENT SHOULD CONSISTS OF THE WHOLE DATA ICLUDING PRICES AND TERMS (INCULDING TIMEFRAMES) OF THE ALL POSSIBLE ROUTES IN TABLE FORMAT.
                    PLEASE ALWAYS SHOW VENDOR NAMES
                    PUT THE DETAILED EXPLANATION OF YOUR COSTS PREDICTION IN THE END OF THE EMAIL. 
                    ALSO PLEASE DECRIBE HOW MANY ROUTES WERE IN THE SCOPE OF YOUR ANALYSIS.  """
                }

            ]
            },
        ],
        "temperature": 1,
        "top_p": 0.95,
        "max_tokens": 4000
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
