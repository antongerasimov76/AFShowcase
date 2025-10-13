import logging
import requests
import azure.functions as func
import json
import re
import pandas as pd
import io
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from datetime import datetime


def main(req: func.HttpRequest) -> func.HttpResponse:
    start_time = datetime.now()
 # ======================================================================================
# Функция поиска по индексу (на выходе json примеры)
# ======================================================================================
    def search(origincountry, origincity, destcountry, destcity, examplesquantity):

        connection_string = "DefaultEndpointsProtocol=https;AccountName=getaianswerb0488d;AccountKey=pM59bz97AqOMVpC28/51Z/RMPrxUmmv7OEu8ZTHKTXChGV8bdoGLSIGn0XmCj43cK2L65BPpi3XH+AStF90Gzg==;EndpointSuffix=core.windows.net"
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_name = 'm9ai-transportation-cases'

        def download_json(json_filename):
            container_client = blob_service_client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(json_filename)
            blob_data = blob_client.download_blob().readall()
            json_string = blob_data.decode('utf-8')
            json_object = json.loads(json_string)
            return json_object

        origincountry = origincountry.upper()
        origincity = origincity.upper()
        destcountry = destcountry.upper()
        destcity = destcity.upper()

        indexdir = f"Index/[{origincountry}.{destcountry}]"
        indexfilename = f"{indexdir}/index.json"
        index = download_json(indexfilename)

        searchresults = []
        findcounter = 0

        # прямое полное совпадение из какого города в какой
        # ИЗ страна=US, город=NEWYORK  в страна=RU, город=MOSCOW
        if origincity != '' and destcity != '':
            for cc in index[:]:
                if cc["F"] == origincity and cc["T"] == destcity:
                    findcounter += 1
                    if findcounter <= examplesquantity:
                        datafile = f"{indexdir}/{cc['O']}.json"
                        data = download_json(datafile)
                        searchresults.append(data)
                        index.remove(cc)

        # ИЗ страна=US, город=''  в страна=RU, город=MOSCOW
        if origincity == '' and destcity != '':
            for cc in index[:]:
                if cc["T"] == destcity:
                    findcounter += 1
                    if findcounter <= examplesquantity:
                        datafile = f"{indexdir}/{cc['O']}.json"
                        data = download_json(datafile)
                        searchresults.append(data)
                        index.remove(cc)

        # ИЗ страна=US, город=NEWYORK  в страна=RU, город=''
        if origincity != '' and destcity == '':
            for cc in index[:]:
                if cc["F"] == origincity:
                    findcounter += 1
                    if findcounter <= examplesquantity:
                        datafile = f"{indexdir}/{cc['O']}.json"
                        data = download_json(datafile)
                        searchresults.append(data)
                        index.remove(cc)

        # .любые с любым городом
        for cc in index[:]:
            findcounter += 1
            if findcounter <= examplesquantity:
                datafile = f"{indexdir}/{cc['O']}.json"
                data = download_json(datafile)
                searchresults.append(data)
                index.remove(cc)

        return searchresults

    def getprompt(x):
        def fixempty(x):
            if x == '':
                return 'Not provided'
            return x

        def getAWBInfo(x):
            counter = 0
            cargolines = ""
            for c in x["Air Transportation Stage Details"]:
                counter += 1
                currentcargoline = (
                    f"{counter}. AWB: {c['AWB No.']}; "
                    f"Issued by: {c['Issued By']} "
                    f"by {c['Execution Date']}:\n"
                )
                currentcargoline += f" - Shipper: {fixempty(c['Shipper'])}\n"
                currentcargoline += f" - Consignee: {fixempty(c['Consignee'])}\n"
                currentcargoline += f" - Departure Country Code: {fixempty(c['Departure Country Code'])}\n"
                currentcargoline += f" - Departure Airport Code: {fixempty(c['Departure Airport'])}\n"
                currentcargoline += f" - Destination Country Code: {fixempty(c['Destination Country Code'])}\n"
                currentcargoline += f" - Destination Airport: {fixempty(c['Destination Airport'])}\n"
                currentcargoline += f" - Handling Information: {fixempty(c['Handling Information'])}\n"
                currentcargoline += f" - No. of Pieces: {fixempty(c['No. of Pieces'])}\n"
                currentcargoline += f" - Gross Weight: {fixempty(c['Gross Weight'])}\n"
                currentcargoline += f" - Charges Description: {fixempty(c['Charges Description'])}\n"
                currentcargoline += f" - Volume: {fixempty(c['Total Volume'])}\n"

                cargolines += currentcargoline
            return cargolines

        def getSeaInfo(x):
            counter = 0
            cargolines = ""
            for c in x["See Transportation Stage Details"]:
                counter += 1
                currentcargoline = (
                    f"{counter}. B/L No: {c['B/L No.']}; "
                    f"Issued by: {c['Issued By']}:\n"
                )
                currentcargoline += f" - Shipper: {fixempty(c['Shipper'])}\n"
                currentcargoline += f" - Consignee: {fixempty(c['Consignee'])}\n"
                currentcargoline += f" - Port of loading Country Code: {fixempty(c['Port of loading Country Code'])}\n"
                currentcargoline += f" - Port of loading: {fixempty(c['Port of loading'])}\n"
                currentcargoline += f" - Port of discharge Country Code: {fixempty(c['Port of discharge Country Code'])}\n"
                currentcargoline += f" - Port of discharge: {fixempty(c['Port of discharge'])}\n"
                currentcargoline += f" - Ocean Vessel / Voyage No: {fixempty(c['Ocean Vessel / Voyage No'])}\n"
                currentcargoline += f" - No. of Packages or Containers: {fixempty(c['No. of Packages or Containers'])}\n"
                currentcargoline += f" - Total Gross Weight: {fixempty(c['Total Gross Weight'])}\n"

                cargolines += currentcargoline
            return cargolines

        def getChargesDescription(x):
            counter = 0
            charges = ""
            for e in x["Transportation Charges"]:
                counter += 1
                description = e['Service/Charge Description'].replace("\n", "")

                charges += (
                    f"{counter}. {description}: Amount {e['Amount']} {e['Currency Code']}; "
                    f"Vendor/Agent of the service: {e['Service Vendor Name']}; "
                )
                if e['Vendor Blocked'] != " ":
                    charges += f"Vendor status: {e['Vendor Blocked']}; "

                if e['Vendor e-mail'] != '':
                    charges += f"Vendor status: {e['Vendor e-mail']}; "

                charges += f"Vendor Last Invoice Date: {e['Vendor Last Invoice Date']} \n"

            if charges == '':
                charges = '[Warning] There is no the information about charges.\n'

            return charges

        outtest = (
            f"Transportation company {x['Company Name']} carried out the transportation: {x['FWO No.']} Date: {x['Posting Date']} \n"
            f"Origin and destination: \n"
            f"from country code: {x['From Country Code']}, city: {x['From City']} \n"
            f"to country code: {x['To Country Code']}, city: {x['To City']} \n"
            f"for client:  {x['Ordering Party Name']} \n"
            f"General cargo description {x['General Description of the Cargo']} \n"
            f"Detailed Goods Description: {x['Detailed Goods Desription']}"
        )
        if x['No. of Pieces'] != '':
            outtest += f"No. of Pieces: {x['No. of Pieces']} \n"

        if x['Gross Weight'] != '':
            outtest += f"Gross Weight: {x['Gross Weight']} \n"

        outtest += (
            f"The cost of transportation, taking into account all expenses, was: \n"
            f"Amount: {x['Transportation Cost Amount']} {x['Currency Code']} \n"
            f"The expenses incurred by the company for organizing this shipment: \n"
            f"{getChargesDescription(x)}"
        )

        if x['Comment'] != '':
            outtest += f"Comment: {x['Comment']}\n"

        # пока есть инфа только из AWB
        if 'Air Transportation Stage Details' in x:
            outtest += f"The transportation included a flight(s). \n"
            outtest += f"Airwaybill (AWB) and House AirwayBill can contains similar information but House AirWaybill contiain info about real shipper and confignee.\n"
            outtest += f"Detailed description from the Air Waybill (House Airwaybill) about the airports, shipper and consignee, and the goods listed below: \n"
            outtest += getAWBInfo(x)

        if 'See Transportation Stage Details' in x:
            outtest += f"The transportation included a sea freight(s). \n"
            outtest += f"Detailed information from the 'Sea Bill of Lading' about the ports, shipper and consignee, and the goods listed below: \n"
            outtest += getSeaInfo(x)

        return outtest


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
            'Item Weight': json_data['Item Weight'],
            'Quote Number': json_data['Quote Number']
        }

        # Converting the new JSON object to a string
        parcel_data = json.dumps(parcel_data_text, indent=2)

        if json_data['Country To'] != "" and json_data['Country From'] != "" :
            transf_history = "The preliminary price: 560EUR"
        else: transf_history = ""

        results = search(json_data['Country From'], json_data['City From'], json_data['Country To'], json_data['City To'], 50)
        #string_list = [str(item) for item in results]

        # Join the strings with a space or any other separator
        #data_text = " ".join(string_list)
        data_text = "\n".join(getprompt(item) for item in results)

        #uploading excel and json
        df = pd.DataFrame(results)
        excel_buffer = io.BytesIO()

        # Save the DataFrame to the buffer in Excel format
        df.to_excel(excel_buffer, index=False, sheet_name='Orders Data')

        # Make sure to seek to the beginning of the buffer before reading it
        excel_buffer.seek(0)

        # Initialize BlobServiceCent and BlobClient
        blob_name = f'{num_quote}.xlsx'             # The name you want for the blob

        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

        # Upload the in-memory file to Azure Blob Storage
        blob_client.upload_blob(excel_buffer, overwrite=True)

        #Uploading json
        json_data = json.dumps(results)

        json_buffer = io.BytesIO(json_data.encode('utf-8'))

        # Make sure to seek to the beginning of the buffer before reading it
        json_buffer.seek(0)

        # Initialize BlobServiceClient and BlobClient
        blob_name = f'{num_quote}ORDERSJSON.json'             # The name you want for the blob

        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

        # Upload the in-memory JSON data to Azure Blob Storage
        blob_client.upload_blob(json_buffer, overwrite=True)

        # Extract distinct Service Vendor Names
        service_vendor_names = set()

        for entry in results:
            if 'Transportation Charges' in entry:
                for charge in entry['Transportation Charges']:
                    if 'Service Vendor Name' in charge:
                        service_vendor_names.add(charge['Service Vendor Name'])

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
                "text": "You are a Sales Manager Assistant in M9 Logistics Сompany. Your task is to prepare the detailed analysis for the Commercial Offer for Sales Manager " +
                "for parcel transportation. Sales Manager will use your analisys to prepare Commercial offer. The parcel's data is: " + parcel_data +
                    " ANSWER IN LANGUAGE THAT THE USER USED " +
                    " ANSWER HAVE TO BE AS EMAIL IN HTML FORMAT " +
                   # " ANSWER IN RUSSIONA LANGUAGE " +
                    " THE CHAT HISTORY WITH THE CLIENT: " + chat_history +                    
                    " THE SIMILAR PREVIOUS ORDERS: " + data_text +
                    " THE VENDORS ARE COVERED IN THESE ORDERS: " + distinct_service_vendor_names_string +
                    " YOU HAVE TO PREDICT the M9 expenses incurred by the company for organizing this shipment BASED ON DEEP ANALISING OF ALL SIMILAR ORDERS AND HIGHLY DETAILED EXPLANATION OF THE COSTS. " +
                    " THIS COSTS PREDUCTION HAVE TO BE CALCULATED AMONG ALL PREVIOUS ORDERS, NOT JUST THE TOP ONE. " +
                    " PUT THIS COSTS PREDICTION TO THE START OF THE EMAIL. " +
                    " THE EMAIL CONTENT SHOULD CONSISTS OF THE WHOLE DATA OF THE ONLY ONE THE MOST SIMILAR ORDER IN TABLE FORMAT. " +
                    " WHILE THE COSTS PREDICTION HAVE TO BE BASED ON THE WHOLE SCOPE OF PREVIOUS ORDERS. " +
                    " PUT THE DETAILED EXPLANATION OF YOUR COSTS PREDICTION IN THE END OF THE EMAIL. " +
                    " ALSO PLEASE DECRIBE HOW MANY ORDERS AND HOW MANY VENDORS WERE IN THE SCOPE OF YOUR ANALYSIS. " 
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
        #return func.HttpResponse(f"Hello, {GPT4V_KEY}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )
