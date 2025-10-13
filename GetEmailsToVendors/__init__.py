import logging
import requests
import azure.functions as func
import json
import re
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from datetime import datetime


def main(req: func.HttpRequest) -> func.HttpResponse:
    start_time = datetime.now()
    logging.info('Python HTTP trigger function processed a request.')

    
    num_quote = req.params.get('quote')

    if num_quote:
        GPT4V_KEY = "05287303f01b406582788526baca76c3"
        GPT4V_ENDPOINT = "https://m9ai.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-02-15-preview"
        # Regular expression to find digits between brackets
        
        
        
        headers = {
            "Content-Type": "application/json",
            "api-key": GPT4V_KEY,
        }
        connection_string = "DefaultEndpointsProtocol=https;AccountName=getaianswerb0488d;AccountKey=pM59bz97AqOMVpC28/51Z/RMPrxUmmv7OEu8ZTHKTXChGV8bdoGLSIGn0XmCj43cK2L65BPpi3XH+AStF90Gzg==;EndpointSuffix=core.windows.net"
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_name = 'quotes'
        filename = num_quote

        # Download the CSV content
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        all_content = blob_client.download_blob()
        chat_history = all_content.content_as_text()
        transf_history = ""

        filename = num_quote + "JSON"

        # Download the CSV content
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        json_content = blob_client.download_blob()
        json_text = json_content.content_as_text()
        json_data = json.loads(json_text)
        if json_data['Quote Number'] == "":
            json_data['Quote Number'] = num_quote


        parcel_data_text = {
            'Country From': json_data['Country From'],
            'Country To': json_data['Country To'],
            'Postcode From': json_data['Postcode From'],
            'Postcode To': json_data['Postcode To'],
            'City From': json_data['City From'],
            'City To': json_data['City To'],
            'Address From': json_data['Address From'],
            'Address To': json_data['Address To'],
            'Port From': json_data['Port From'],
            'Port To': json_data['Port To'],
            'Item Type': json_data['Item Type'],
            'Item Weight': json_data['Item Weight']
        }

        # Converting the new JSON object to a string
        parcel_data = json.dumps(parcel_data_text, indent=2)

        filename = num_quote + "VENDORSJSON.json"

        # Download the CSV content
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        json_content = blob_client.download_blob()
        json_text = json_content.content_as_text()
        json_data = json.loads(json_text)
        orders_data = json.dumps(json_data)
        # Extract distinct Service Vendor Names
        service_vendor_names = set()

        for entry in json_data:
            service_vendor_names.add(entry['vendorName'])

        # Convert the set back to a list for further processing or printing
        distinct_service_vendor_names = list(service_vendor_names)
        distinct_service_vendor_names_string = ", ".join(distinct_service_vendor_names)
        payload = {
        "messages": [
            {
            "role": "system",
            "content": [
                {
                "type": "text",
                "text": "You are a Sales Manager Assistant in M9 Logistics Сompany. Your task is to prepare emails to Vendors to get their prices of their part of transportations " +
                    " in the next JSON format: " +
                    "{ 'action': 'Emails to Vendors', 'emails': [ {'to': 'Vendor name and Vendor e-mail', 'title': 'email title', 'content': 'well structured email content in HTML format with questions to get the price. If the current Vendor's language is specified then use this language. If not - use language of the Vendor's country '}],'Country From': 'two letters code of the country in english', 'Country To: 'two letters code of the country in english', " +
                    "'Postcode From': 'Postcode if it exists in the email or you can find it by airport, seaport etc', 'Postcode To': 'Postcode if it exists in the email or you can find it by airport, seaport etc', " +    
                    "'City From': 'Name if the city in English', 'City To': 'Name if the city in English', " +
                    "'Address From': 'Address in English if it exists in the email or you can find it by airport, seaport etc', 'Address To': 'Address in English if it exists in the email or you can find it by airport, seaport etc', " +
                    "'Item Type': 'Type of Item', 'Item Weight': 'Weight of Item', 'Quote Number': ''}"   +                 
                "The parcel's data is: " + parcel_data +
                    " ANSWER IN LANGUAGE THAT CURRENT VENDOR USES. IF IT IS NOT SPECIFIED THEN USE LANGUAGE OF THE CURRENT VENDOR'S COUNTRY " +
                    " ANSWER HAVE TO BE AS EMAIL IN HTML FORMAT " +
                    " THE CHAT HISTORY WITH THE CLIENT: " + chat_history +                  
                    " THE VENDORS DATA: " + orders_data +
                    " ALL OF VENDORS: " + distinct_service_vendor_names_string + " have to be covered" +
                    " IF AIRPORT OR SEAPORT IS SPECIFIED DON'T PUT FULL ADRESSES TO EMAILS " +
                    " YOUR ANSWER MUST CONSIST OF CORRECT JSON STARTS FROM { AND ENDS BY }. " +
                    " ALWAYS USE DOUBLE QUOTES IN JSON. " 
                }

            ]
            },
        ],
        "temperature": 1,
        "top_p": 0.95,
        "max_tokens": 4000
        }
        response = requests.post(GPT4V_ENDPOINT, headers=headers, json=payload)
        response = response.json()
        
        # Calculate execution time
        end_time = datetime.now()
        execution_time_ms = (end_time - start_time).total_seconds() * 1000
        
        result = {
            "answer": response['choices'][0]['message']['content'],
            "execution_time": round(execution_time_ms)
        }
        return func.HttpResponse(json.dumps(result))
        #return func.HttpResponse(f"Hello, {GPT4V_KEY}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )
