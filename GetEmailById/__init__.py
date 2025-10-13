import logging
import os
import azure.functions as func
import msal
import requests
import json
from datetime import datetime

# --- Main Function ---
def main(req: func.HttpRequest) -> func.HttpResponse:
    start_time = datetime.now()
    def get_env_variable(name):
        #value = os.getenv(name)
        value = os.environ.get(name)
        if not value:
            raise Exception(f"Missing required environment variable: {name}")
        return value

    def get_access_token():
        logging.info("Getting Microsoft Graph access token...")
        scopes = ["https://graph.microsoft.com/.default"]
        result = app.acquire_token_for_client(scopes=scopes)
        if "access_token" in result:
            return result["access_token"]
        else:
            logging.error(f"Token error: {result}")
            return None

    def get_sent_email_by_id(message_id: str) -> dict | None:
        """
        Return the full Microsoft Graph message that lives in **Sent Items**
        for the given Graph `id`.

        Parameters
        ----------
        message_id : str
            The Graph `id` of the message you want (not the internetMessageId).

        Returns
        -------
        dict | None
            The JSON Graph message, or None if something went wrong.
        """
        token = get_access_token()
        if not token:
            return None

        headers = {"Authorization": f"Bearer {token}"}

        url = (f"https://graph.microsoft.com/v1.0/users/{USER_EMAIL}"
            f"/mailFolders('sentitems')/messages/{message_id}")

        resp = requests.get(url, headers=headers)

        if resp.status_code == 200:
            return resp.json()

        logging.error("Failed to fetch sent message %s: %s – %s",
                    message_id, resp.status_code, resp.text)
        return None    
    #main code
    logging.info("SendEmail Function Triggered.")
    CLIENT_ID = get_env_variable("O365_CLIENT_ID")
    logging.info("Client uploaded!")
    logging.info(CLIENT_ID)


    CLIENT_SECRET = get_env_variable("O365_CLIENT_SECRET")
    logging.info(f"CS uploaded!{CLIENT_SECRET}")

    TENANT_ID = get_env_variable("O365_TENANT_ID")
    logging.info("Tenant uploaded!")
    logging.info(TENANT_ID)

    
    USER_EMAIL = get_env_variable("O365_USER_EMAIL")
    logging.info("All data uploaded!")


    AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
    GRAPH_SEND_ENDPOINT = f"https://graph.microsoft.com/v1.0/users/{USER_EMAIL}/sendMail"
    GRAPH_DRAFT_ENDPOINT = f"https://graph.microsoft.com/v1.0/users/{USER_EMAIL}/messages"

    logging.info("app startded!")

    try:
        app = msal.ConfidentialClientApplication(
            CLIENT_ID,
            authority=AUTHORITY,
            client_credential=CLIENT_SECRET
        )
        logging.info("app ready!")
    except Exception as e:
        logging.exception("Failed to initialize MSAL ConfidentialClientApplication.")
        return func.HttpResponse(f"Internal error during app init: {str(e)}", status_code=500)

    try:
        data = req.get_json()
        id = data.get('Email ID')
        USER_EMAIL = data.get('Email Box')

        success = get_sent_email_by_id(id)

        if success:
            # Calculate execution time
            end_time = datetime.now()
            execution_time_ms = (end_time - start_time).total_seconds() * 1000
            
            response = {
                **success,
                "execution_time": round(execution_time_ms)
            }
            
            return func.HttpResponse(
                json.dumps(response),
                status_code=200,
                mimetype="application/json"
        )
        else:
            return func.HttpResponse("Graph API call failed. Check logs.", status_code=500)

    except Exception as e:
        logging.exception("Unhandled exception occurred.")
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)
