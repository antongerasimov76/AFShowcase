import logging
import requests
import azure.functions as func
import json
import re
import pandas as pd
import io
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
import PyPDF2
from io import BytesIO
from datetime import datetime



def main(req: func.HttpRequest) -> func.HttpResponse:        
    start_time = datetime.now()
    logging.info('Python HTTP trigger function processed a request.')

    
    num_quote = req.params.get('quote')

    if num_quote:
        GPT4V_KEY = "05287303f01b406582788526baca76c3"
        GPT4V_ENDPOINT = "https://m9ai.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-02-15-preview"
        # Regular expression to find digits between brackets
        connection_string = "DefaultEndpointsProtocol=https;AccountName=getaianswerb0488d;AccountKey=pM59bz97AqOMVpC28/51Z/RMPrxUmmv7OEu8ZTHKTXChGV8bdoGLSIGn0XmCj43cK2L65BPpi3XH+AStF90Gzg==;EndpointSuffix=core.windows.net"
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)

        container_name = 'quotes'
        filename = num_quote

        # Download the CSV content
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        all_content = blob_client.download_blob()
        chat_history = all_content.content_as_text()
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

        # Getting token
        url = "https://login.microsoftonline.com/00d68c5c-345f-476b-b239-50c6598f031e/oauth2/v2.0/token"
        data = {
            'grant_type': 'client_credentials',
            'client_id': 'e2d524aa-1aa6-4cc5-831b-2028a3cf1736',
            'client_secret': '0Fs8Q~~~WequjWc9SKmfVv3G29zu6mMLGvhR9a6D',
            'scope': 'https://api.businesscentral.dynamics.com/.default'
        }

        # Make the POST request
        response = requests.post(url, data=data)
        response_data = response.json()
        access_token = response_data['access_token']

        # Get requestID by source
        url = "https://api.businesscentral.dynamics.com/v2.0/00d68c5c-345f-476b-b239-50c6598f031e/m9ai/api/m9ai/routeengine/v1.0/companies(2df5c7f5-b438-ef11-8e52-6045bde99e43)/requests?$filter=source eq '"+ num_quote +"'"
        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        # Make the GET request
        response = requests.get(url, headers=headers)
        data = response.json()
        request_id = data['value'][0]['id']

        # getting routes
        url = "https://api.businesscentral.dynamics.com/v2.0/00d68c5c-345f-476b-b239-50c6598f031e/m9ai/api/m9ai/routeengine/v1.0/companies(2df5c7f5-b438-ef11-8e52-6045bde99e43)/requests(" + request_id + ")?$expand=routes"
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        # Make the GET request
        response = requests.get(url, headers=headers)

        data = response.json()
        # Check the response status code
        if response.status_code == 200:
            # Successful response, print the JSON data
            logging.info(response.json())
        else:
            # Failed response, print the error details
            logging.info(f"Error: {response.status_code}")
            logging.info(response.text)
        data = response.json()

        #proccessing legs
        base_url = "https://api.businesscentral.dynamics.com/v2.0/00d68c5c-345f-476b-b239-50c6598f031e/m9ai/api/m9ai/routeengine/v1.0"
        company_id = "2df5c7f5-b438-ef11-8e52-6045bde99e43"
        res = "Parcel data: " + parcel_data
        for route in data['routes']:
            route_id = route['id']           
            # Construct the URL
            url = f"{base_url}/companies({company_id})/routes({route_id})?$expand=routelegs"
            response = requests.get(url, headers=headers)
            data_routes = response.json()           
            all_legs_answer_given = True  # Assume all legs have 'Answer given' status
            new_route_exists = False  # Assume there are no a new route

            # Loop over each leg in the route
            for leg in data_routes['routelegs']:
                if leg['status'] != 'Answer given':
                    all_legs_answer_given = False 
                    break
            # Check if all legs have the 'Answer given' status
            if all_legs_answer_given: 
                data = response.json()
                data1 = {
                    'id': data['id'],
                    'description': data['description'],
                    'score': data['score'],
                    'routelegs': [
                        {
                            'id': leg['id'],
                            'fromPointCode': leg['fromPointCode'],
                            'toPointCode': leg['toPointCode'],
                            'modeOfTransport': leg['modeOfTransport'],
                            'costs': leg['result'],
                            'email': leg['email'],
                            'contact': leg['contact'],
                            'vendorName': leg['vendorName'],
                            'vendorCountyCode': leg['vendorCountyCode'],
                            'vendorLanguage': leg['vendorLanguage']
                        } for leg in data['routelegs']
                    ]
                }
                data1_str = json.dumps(data1)

                # Create the result string
                res += " Possible Route: " + data1_str  
                if route['status'] != 'Price Calculated':
                    new_route_exists = True
                    #Set route status to Calculated
                    url = "https://api.businesscentral.dynamics.com/v2.0/00d68c5c-345f-476b-b239-50c6598f031e/m9ai/api/m9ai/routeengine/v1.0/companies(2df5c7f5-b438-ef11-8e52-6045bde99e43)/routes(" + route_id + ")"
                    payload = {
                        "status": "Price Calculated"
                    }
                    headers = {
                        'Authorization': f'Bearer {access_token}',
                        'Content-Type': 'application/json',
                        'If-Match': '*'
                    }               
                    # Send PATCH request
                    response = requests.patch(url, headers=headers, json=payload)                      
              
        #Generating the answer
        logging.info(new_route_exists)
        if new_route_exists:
            logging.info(filename)
            headers = {
                "Content-Type": "application/json",
                "api-key": GPT4V_KEY,
            }
            logging.info(filename)

            payload = {
            "messages": [
                {
                "role": "system",
                "content": [
                    {
                    "type": "text",
                    "text": "You are a Sales Manager Assistant in M9 Logistics Сompany. Your task is to prepare the detailed analysis for the Commercial Offer for Sales Manager " +
                    "for parcel transportation. Sales Manager will use your analisys to prepare Commercial offer. The data is: " + res +
                    " ANSWER IN LANGUAGE THAT THE USER USED " +
                    " ANSWER HAVE TO BE AS EMAIL IN HTML FORMAT " +
                    " THE CHAT HISTORY WITH THE CLIENT: " + chat_history +                    
                    " THIS ANALYSIS HAVE TO BE CALCULATED AMONG ALL POSSIBLE ROUTES PROVIDED " +
                    " PUT ANALYSIS PREDICTION TO THE START OF THE EMAIL. " +
                    " THE EMAIL CONTENT SHOULD CONSISTS OF THE WHOLE DATA ICLUDING PRICES AND TERMS (INCULDING TIMEFRAMES) OF THE ALL POSSIBLE ROUTES IN TABLE FORMAT. " +
                    " PLEASE ALWAYS SHOW VENDOR NAMES " +
                    " PUT THE DETAILED EXPLANATION OF YOUR COSTS PREDICTION IN THE END OF THE EMAIL. " +
                    " ALSO PLEASE DECRIBE HOW MANY ROUTES WERE IN THE SCOPE OF YOUR ANALYSIS. " 
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
            
            answer = {
                "answer": response['choices'][0]['message']['content'],
                "execution_time": round(execution_time_ms)
            }
            return func.HttpResponse(json.dumps(answer))
        else: 
            return func.HttpResponse("No new routes")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )
