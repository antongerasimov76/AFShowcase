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
    try:
        # Read the request body
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            "Invalid request body",
            status_code=400
        )
    
    email = req_body.get('email')
    email_title = req_body.get('email_title')
    email_text = req_body.get('email_text')


    if email:
        GPT4V_KEY = "05287303f01b406582788526baca76c3"
        GPT4V_ENDPOINT = "https://m9ai.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-02-15-preview"
        # Regular expression to find digits between brackets
        pattern = r'\[(\d+)\]'

        # Search for the pattern in the email_title
        match = re.search(pattern, email_title)

        if match:
            # Extract the digits
            num_quote = match.group(1)        
        
        
        
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
            'Item Weight': json_data['Item Weight'],
            'Quote Number': json_data['Quote Number']
        }

        # Converting the new JSON object to a string
        parcel_data = json.dumps(parcel_data_text, indent=2)

        if json_data['Country To'] != "" and json_data['Country From'] != "" :
            transf_history = "The preliminary price: 560EUR"
        else: transf_history = ""



        payload = {
        "messages": [
            {
            "role": "system",
            "content": [
                {
                "type": "text",
                "text": "You are a Sales Manager in M9 Logistics Сompany. Your final task is to prepare the Commercial Offer for the client's Request a Quote. " +
                "First of all, you have to clarify if the current email is from a client or from a supplier (vendor). " +
                "If the email from a client: " +
                    "To prepare the Commercial Offer we have to have all the parcel's data: " + parcel_data +
                    " Please check if client's email complete the gaps in parcel's data. "
                    " If not you have to prepare the email to the client with questions to get the data that client has not provided yet among: " +
                    " address from and adress to (country, city, address and postcodes are needed ONLY if you can't find it by airport, seaport etc), what exactly are the items to send, what is the weight and so on " +
                    " in the next format: " +
                    "{ 'action': 'Clarification of client information', 'emails': [ {'to': 'email address', 'title': 'email title', 'content': 'email content in HTML format. If preliminary price exists you have to provide it '}],'Country From': 'two letters code of the country in english', 'Country To: 'two letters code of the country in english', " +
                    "'Postcode From': 'Postcode from', 'Postcode To': 'Postcode to', " +    
                    "'City From': 'Name if the city in English', 'City To': 'Name if the city in English', " +
                    "'Address From': 'Address in English if it exists in the email or you can find it by airport, seaport etc', 'Address To': 'Address in English if it exists in the email or you can find it by airport, seaport etc', " +
                    "'Port From': 'The code of Airport or Seaport if From is Airport or Seaport', 'Port To': 'The code of Airport or Seaport if To is Airport or Seaport', " + 
                    "'Item Type': 'Type of Item', 'Item Weight': 'Weight of Item', 'Quote Number': ''}" +
                    " If we have all of the parcel's data (INCLUDING POSTCODES!) return an answer " +
                    " in the next format: " +
                    "{ 'action': 'Parcels Data Completed', 'emails': [ {'to': 'email address', 'title': 'email title', 'content': 'email content in HTML format that client has provided all of we need and we will go back soon with the Commercial Offer '}],'Country From': 'two letters code of the country in english', 'Country To: 'two letters code of the country in english', " +
                    "'Postcode From': 'Postcode from', 'Postcode To': 'Postcode to', " +    
                    "'City From': 'Name if the city in English', 'City To': 'Name if the city in English', " +
                    "'Address From': 'Address in English if it exists in the email or you can find it by airport, seaport etc', 'Address To': 'Address in English if it exists in the email or you can find it by airport, seaport etc', " +
                    "'Port From': 'The code of Airport or Seaport if From is Airport or Seaport', 'Port To': 'The code of Airport or Seaport if To is Airport or Seaport', " +                     
                    "'Item Type': 'Type of Item', 'Item Weight': 'Weight of Item', 'Quote Number': ''}" +
                    " YOUR ANSWER MUST CONSIST OF CORRECT JSON STARTS FROM { AND ENDS BY }. " +  
                    " ALWAYS USE DUOUBLE QUOTES IN JSON. " +                  
                    " DON'T ASK THE DATA THAT CLIENT HAS ALREADY PROVIDED OR THAT YOU'VE FOUND BY YOURSELF. " +
                    " IF YOU'VE FOUND ADDRESS AND POSTCODES BY AIRPORT OR SEAPORT DON'T ASK USER ABOUT IT. " +
                    " IF POSTCODES ARE STILL UNCLEAR YOU HAVE TO CONTINUE ASKING. " +
                    " ANSWER TO CLIENT SHOULD BE THE SAME LANGUAGE THAT USER EMAIL " +
                    " IF THE CLIENT'S BEHAVIOR IS RUDE TRY TO CALM HIM IN POLITE WAY. " +
                    " IF USER WANTS TO SEND TYRES YOU HAVE TO SPECIFY ARE THE TYRES ARE USED OR NOT. " + 
                    " IT'S FORBIDDEN TO TRANSPORT ANIMALS" +
                    " THE CHAT HISTORY: " + chat_history +
                " If the email from a supplier (vendor): " +                    
                    " return the answer in the next format: " +
                    "{ 'action': 'New Vendor Email', 'emails': [ {'to': 'vendor email address', 'title': 'vendor email title', 'content': 'vendor email content cleared from html tags}]," +
                    "'Price': 'the price given by the vendor', " +
                    "'Quote Number': ''}" +
                    " YOUR ANSWER MUST CONSIST OF CORRECT JSON STARTS FROM { AND ENDS BY }. " +  
                    " ALWAYS USE DUOUBLE QUOTES IN JSON. " 
                }

            ]
            },
            {
            "role": "user",
            "content": [
                {
                "type": "text",
                "text": f"email: {email}; title: {email_title}; Content: {email_text}"
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
