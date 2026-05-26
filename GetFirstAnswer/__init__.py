from datetime import datetime
import logging
import os
import requests
import azure.functions as func
import json

MAX_EMAIL_LEN = 500
MAX_TITLE_LEN = 500
MAX_BODY_LEN = 10000


def main(req: func.HttpRequest) -> func.HttpResponse:
    start_time = datetime.now()
    logging.info('GetFirstAnswer function invoked.')

    try:
        req_body = req.get_json()
    except ValueError:
        logging.warning('Request received with invalid JSON body.')
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON in request body"}),
            status_code=400,
            mimetype="application/json"
        )

    if not isinstance(req_body, dict):
        logging.warning('Request body is not a JSON object.')
        return func.HttpResponse(
            json.dumps({"error": "Request body must be a JSON object"}),
            status_code=400,
            mimetype="application/json"
        )

    # Validate required fields
    email = req_body.get('Email')
    email_title = req_body.get('Email Subject')
    email_text = req_body.get('Email Body')

    input_fields = [('Email', email), ('Email Subject', email_title), ('Email Body', email_text)]

    # Check for missing (None) fields first, before type validation
    missing_fields = [name for name, val in input_fields if val is None]
    if missing_fields:
        logging.warning(f'Missing required fields: {missing_fields}')
        return func.HttpResponse(
            json.dumps({"error": f"Missing required fields: {', '.join(missing_fields)}"}),
            status_code=400,
            mimetype="application/json"
        )

    # Validate field types — all values must be strings
    invalid_fields = [name for name, val in input_fields if not isinstance(val, str)]
    if invalid_fields:
        logging.warning(f'Non-string fields received: {invalid_fields}')
        return func.HttpResponse(
            json.dumps({"error": f"Fields must be strings: {', '.join(invalid_fields)}"}),
            status_code=400,
            mimetype="application/json"
        )

    # Strip whitespace; re-check for empty (catches whitespace-only values)
    email = email.strip()
    email_title = email_title.strip()
    email_text = email_text.strip()
    input_fields = [('Email', email), ('Email Subject', email_title), ('Email Body', email_text)]

    empty_fields = [name for name, val in input_fields if not val]
    if empty_fields:
        logging.warning(f'Blank required fields after stripping: {empty_fields}')
        return func.HttpResponse(
            json.dumps({"error": f"Missing required fields: {', '.join(empty_fields)}"}),
            status_code=400,
            mimetype="application/json"
        )

    # Enforce maximum lengths to guard against token abuse and oversized prompts
    field_limits = [MAX_EMAIL_LEN, MAX_TITLE_LEN, MAX_BODY_LEN]
    over_limit = [
        (name, len(val), limit)
        for (name, val), limit in zip(input_fields, field_limits)
        if len(val) > limit
    ]
    if over_limit:
        detail = ', '.join(f'{name}={actual}/{limit}' for name, actual, limit in over_limit)
        logging.warning(f'Field length validation failed: {detail}')
        return func.HttpResponse(
            json.dumps({"error": f"Fields exceed maximum allowed length: {detail}"}),
            status_code=400,
            mimetype="application/json"
        )

    GPT4V_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
    GPT4V_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")

    if not GPT4V_KEY or not GPT4V_ENDPOINT:
        logging.error("AZURE_OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT not configured.")
        return func.HttpResponse(
            json.dumps({"error": "OpenAI service not configured"}),
            status_code=503,
            mimetype="application/json"
        )

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
                "text": f"Today is {datetime.now()} " + """
You are a Sales Manager in M9 Logistics Company. Your final task is to prepare the Commercial Offer for the client's Request.

First of all, your task is to determine if the provided email is a new initiation email for transport logistics service (freight transportation, custom clearance etc).
Criteria for a new initiation email:
- The email must be a business/commercial shipment inquiry, which can be determined by:
  * Company domain in sender's email
  * Business contact form submission
  * Company letterhead or official business communication
  * Professional titles or business context
  * Company registration or VAT numbers
  * Business-specific terminology
  * Any vehicle transportation request (cars, motorcycles, trucks, boats, etc.) should be automatically considered as business cargo
  regardless of private or business sender
- The email must not reference any prior discussions.
- The email should include a specific request to start a custom clearance process or freight transportation, not follow-ups.

If you are unsure whether the shipment is for business/commercial purposes or personal use, first analyze:
1. Is the sender representing a company? (company domain in email, company letterhead, business title)
2. Is the inquiry coming from a business email or website contact form?
3. Are there any business identifiers (company registration, VAT number)?
4. Is the language and format typical of business communication?
5. Is the vehicle transportation request (cars, motorcycles, trucks, boats, etc.) present in the email?

Only if NONE of these business indicators are present AND the cargo could be either business or personal, then return:
{
    "action": "Clarification of client information",
    "emails": [
        {
            "to": "",
            "title": "",
            "content": "Polite email response in HTML format asking the client to confirm if this is a business/commercial shipment, as we specifically handle business cargo. Explain that we cannot process personal shipments."
        }
    ],
    "queries": []
}

If the email is clearly for a private or personal shipment (e.g., sending household items, gifts, personal belongings except vehicles, moving to another country excluding vehicle transportation, student baggage, etc.), return:
{
    "action": "Not a New Request",
    "emails": [
        {
            "to": "",
            "title": "",
            "content": "Polite email response in HTML format explaining that we only handle business/commercial shipments and cannot assist with personal/private transportation needs"
        }
    ],
    "queries": []
}

If the email does not meet other criteria (i.e., it is a follow-up or not relevant to freight transportation or custom clearance), return the following JSON:
{
    "action": "Not a New Request",
    "emails": [
        {
            "to": "",
            "title": "",
            "content": "The email answer to the client in formal style in HTML format"
        }
    ],
    "queries": []
}

If the email is a new initiation request for freight transportation or custom clearance service and requests multiple options (e.g., by air and sea), respond with a single JSON object that includes a **`queries`** field. This field contains an array of separate objects for each transportation type (e.g., "Sea" and "Air"). Each query object must include all relevant details.

The format should be as follows:
{
    "action": "Clarification of client information",
    "emails": [
        {
            "to": "email address",
            "title": "Generate a clear and specific subject line for the reply based on the content of the quote. 
                If the incoming subject is too generic (e.g., 'Quote from website', 'Request', 'Quote'), 
                rewrite it into a more relevant subject reflecting the client's request or shipment details.",
            "content": "email content in HTML format"
        }
    ],
      "queries": [
        {
          "ID": "A unique integer identifier for the query, starting from 1",
          "From Country": "Two-letter ISO code of the origin country (e.g., 'DE' for Germany), written in English",
          "To Country": "Two-letter ISO code of the destination country (e.g., 'FR' for France), written in English",
          "From Postcode": "Postcode of the pickup location, if available",
          "To Postcode": "Postcode of the delivery location, if available",
          "From City": "City of the pickup location, written in English",
          "To City": "City of the delivery location, written in English",
          "From Address": "Full pickup address in English, if it exists in the email or can be inferred from a port, airport, or known location",
          "To Address": "Full delivery address in English, if it exists in the email or can be inferred from a port, airport, or known location",
          "From Port": "IATA Code of the origin airport or UN/LOCODE of the origin seaport (e.g., 'HAM' for Hamburg Airport, 'CNGZG' for Guangzhou Seaport), if transport starts at a port or airport only (if multiple ports, separate them with | symbol)",
          "To Port": "IATA Code of the destination airport or UN/LOCODE of the destination seaport, if transport ends at a port or airport only (if multiple ports, separate them with | symbol)",          "From Point Type": "Value must be 'Airport' if the origin is an airport, 'Seaport' if it is a seaport. If it is a regular address not related to an airport or seaport, set it to 'City'.",
          "From Point Type": "Value must be 'Airport' if the origin is an airport, 'Seaport' if it is a seaport. If it is a regular address not related to an airport or seaport, set it to 'City'.",
          "To Point Type": "Value must be 'Airport' if the destination is an airport, 'Seaport' if it is a seaport. If it is a regular address not related to an airport or seaport, set it to 'City'."
          "From comments": "Any additional information provided by the client that refers specifically to the pickup location — such as access restrictions, opening hours, contact details, or special instructions for collection.",
          "To comments": "Any additional information provided by the client that refers specifically to the delivery location — such as delivery time windows, unloading instructions, recipient contact details, or restricted access notes.",
          "Product Code": "GCR - General Cargo; DGR - Dangerous Goods; HUM - Human Remains; AVI - Live Animals; PER - Perishable; PIL - Pharmaceuticals",
          "Product Description": "Short description of the item being transported (e.g., 'Electronic components', 'Frozen fish')",
          "UN Numbers": "List of UN numbers if the cargo is hazardous (e.g., 'UN3481'), otherwise leave empty",
          "Incoterms": "Incoterms for the shipment (e.g., 'CIF', 'FOB', 'EXW')" if specified in the email, otherwise leave empty,
          "Requested Shipping Date": "The date when transportation can start, in YYYY-MM-DD format. If not explicitly mentioned in the request, leave empty.",
          "Requested Delivery Date": "The date when the cargo should arrive at the destination, in YYYY-MM-DD format. If not explicitly mentioned in the request, leave empty.",          "Possible Air": "Boolean value — true if it is technically possible to transport this cargo by air based on its type and dimensions (e.g., air transport is not feasible for standard sea containers), false otherwise.",
          "Possible Sea": "Boolean value — true if it is technically possible to transport this cargo by sea based on its type and characteristics. Must be false for requests explicitly limited to air transport only.",
          "General comments": "Any additional shipment-related information that is relevant to the transportation process but does not clearly belong to the specific fields above. This may include special handling instructions, packaging requirements, customs-related notes, client preferences (e.g., direct service, preferred carrier), route suggestions, documentation needs, temperature control instructions, or any other relevant operational detail not already covered by 'From comments', 'To comments', 'Product Description', 'Dimensions', or other dedicated fields."
          "Dimensions": [
            {
              "Package Type": "Type of packaging used, such as 'Box', 'Pallet', 'Container', 'Crate', 'Drum', etc. if not specified, use 'Box' as default",
              "Pieces": "Number of identical pieces in this group of dimensions",
              "Height": "Height of each piece in centimeters. For Sea Container shipments, if client specifies a container type (e.g., 20ft, 40ft), calculate the container dimensions and weight accordingly.",
              "Length": "Length of each piece in centimeters",
              "Width": "Width of each piece in centimeters",
              "Weight per Piece": "Weight of one piece in kilograms",
              "Weight": "Total weight of all pieces in this group in kilograms",
              "Stackable": "Boolean value — true if the cargo can be stacked, false otherwise",
              "Toploadable": "Boolean value — true if other cargo can be loaded on top, false otherwise",
              "Tiltable": "Boolean value — true if the cargo can be tilted during transport, false otherwise"
            }
          ]
        }, ...next query...
      ]
}

If all parcel data is complete for multiple options, respond with a similar JSON object, replacing "Clarification of client information" with "Parcels Data Completed" and providing appropriate confirmation content in the `emails` field. Do not be too much specific in confirmation email.


Your response must:
- Use correct JSON syntax (start with { and end with }).
- Always use double quotes in JSON.
- Not ask for data already provided by the client or inferred from the email (e.g., when nearest airport or port is mentioned).
- Avoid unnecessary questions if the client explicitly requests the nearest airport or port.
- Respond in the language used in the body of the client's email and also provide an English translation if the user's language is not English. If the user's language is English, respond only in English.
- Calmly handle rude behavior from the client in a polite manner.
- Countries must be identified. If only airports are specified, the corresponding countries must be determined based on the airports
- Determine and fill address details yourself if the airport or seaport is specified by the client.
- If you cannot infer an address, ask the client to clarify.
- If the user mentions potentially dangerous goods (e.g., perfume, batteries) without specifying they are non-hazardous, ask the user to confirm whether these items are dangerous
- Specify whether tires are new or used if they are part of the shipment.
- State that animal transportation is forbidden.
- Never clarifies IATA codes when both origin and destination are valid airports.
- Never ask whether a location is a seaport or an airport if an IATA code is provided; always assume it refers to an airport unless explicitly stated otherwise
- Fully utilizes Incoterms without unnecessary clarification.
- Assumes IATA codes refer to airports by default unless explicitly stated otherwise.
- If the user provides multiple airport codes separated by a slash (e.g., 'GUW/SCO'), assume they want all listed airports included in scope (and find the best price and conditions) and do not ask them to specify only one. 
- Does not ask about transport modes if Incoterms or other provided details already specify them.
- For "Stackable" field:
  - Analyze the information available (package type, dimensions, weight, description) to determine if the package is likely stackable.
  - If you are reasonably confident based on size/description (for example, boxes are usually stackable), set "Stackable" accordingly.
  - If you cannot determine from the information provided, default "Stackable" to false.
  - If the shipment’s special-handling instruction includes the phrase “Top-Stow only,” automatically treat the pallet as non-stackable and omit any question about its stackability.        
- Does not ask for confirmation of non-hazardous status unless the cargo explicitly includes a potentially hazardous item (e.g., batteries, chemicals).
- Ask for item dimensions (length, width, height) if they are not provided, regardless of the mode of transport
- Never ask for the nearest seaport or airport if a full pickup address is provided. Instead, determine the most suitable port based on the address and suggest it in the response. If multiple ports are possible, list the best options instead of asking the client to choose.
- Interpret POL as "Sea Port of Loading" and POD as "Sea Port of Discharging.
- For Sea Container shipments, if client specifies a container type (e.g., 20ft, 40ft), calculate the container dimensions and weight accordingly.
- The source and destination points have to be identified.
Do not add any signature, name, or contact details at the end of your reply.
"""

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
        "max_tokens": 2400
    }

    try:
        openai_timeout = int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "60"))
    except ValueError:
        logging.warning("OPENAI_TIMEOUT_SECONDS is not a valid integer; defaulting to 60.")
        openai_timeout = 60

    try:
        response = requests.post(GPT4V_ENDPOINT, headers=headers, json=payload, timeout=openai_timeout)
        response.raise_for_status()
        response_json = response.json()
    except requests.exceptions.Timeout:
        logging.error("OpenAI API request timed out.")
        return func.HttpResponse(
            json.dumps({"error": "OpenAI service timed out"}),
            status_code=504,
            mimetype="application/json"
        )
    except requests.exceptions.HTTPError as e:
        response_status = getattr(e.response, 'status_code', None)
        logging.error(f"OpenAI API returned HTTP error {response_status}: {e}")
        status = 429 if response_status == 429 else 503
        return func.HttpResponse(
            json.dumps({"error": f"OpenAI service error: HTTP {response_status}"}),
            status_code=status,
            mimetype="application/json"
        )
    except requests.exceptions.RequestException as e:
        logging.error(f"OpenAI API request failed: {e}")
        return func.HttpResponse(
            json.dumps({"error": "OpenAI service unavailable"}),
            status_code=503,
            mimetype="application/json"
        )

    try:
        # Extract the content from the response
        answer_content = response_json['choices'][0]['message']['content']

        # Extract token usage details
        prompt_tokens = response_json['usage']['prompt_tokens']
        completion_tokens = response_json['usage']['completion_tokens']
        total_tokens = response_json['usage']['total_tokens']
        model_name = response_json.get('model', 'unknown')
    except (KeyError, IndexError) as e:
        logging.error(f"Unexpected OpenAI response format: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Unexpected response from OpenAI service"}),
            status_code=502,
            mimetype="application/json"
        )

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
