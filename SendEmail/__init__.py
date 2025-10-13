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

    # --- Send Email ---
    def send_email(subject, body, to_emails):
        logging.info("Sending email via Graph API...")
        token = get_access_token()
        if not token:
            return False

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body},
                "toRecipients": [{"emailAddress": {"address": email}} for email in to_emails]
            },
            "saveToSentItems": "true"
        }

        response = requests.post(GRAPH_SEND_ENDPOINT, headers=headers, json=payload)
        logging.info(f"Graph API response: {response.status_code}")
        return response.status_code == 202

    # --- Save as Draft ---
    def create_reply_draft_with_custom_answer(original_message_id, reply_html):
        token = get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Step 1: Create a reply draft
        url = f"https://graph.microsoft.com/v1.0/users/{draft_emailtarget}/messages/{original_message_id}/createReply"
        response = requests.post(url, headers=headers)

        if response.status_code != 201:
            logging.error(f"Failed to create reply draft: {response.status_code}, {response.text}")
            return None

        draft = response.json()
        draft_id = draft['id']
        quoted_body = draft['body']['content']  # This includes the original message quote

        logging.info("Draft reply created successfully.")

        # Step 2: Prepend your message above the original content
        #updated_body = f"<p>{reply_html}</p><br><hr>{quoted_body}"
        if quoted_body_flag:
            updated_body = f'{reply_html}<div id="appendonsend"></div>{quoted_body}' #<div id="appendonsend"></div> is needed to be able to remove quoted body in BC

        else:
            updated_body = reply_html

        patch_url = f"https://graph.microsoft.com/v1.0/users/{draft_emailtarget}/messages/{draft_id}"
        to_recipients = [{"emailAddress": {"address": email}} for email in recipients]

        patch_headers = {
            **headers,
            "Prefer": "return=representation"   # 👈 makes PATCH return the full message object
        }

        patch_payload = {
            "body": {
                "contentType": "HTML",
                "content": updated_body
            },
            "toRecipients": to_recipients
        }

        patch_response = requests.patch(patch_url, headers=patch_headers, json=patch_payload)
        if patch_response.status_code != 200:
            logging.error(f"Failed to update reply draft body: {patch_response.status_code}, {patch_response.text}")
            return None
        updated_msg = patch_response.json()          # <- full message
        internet_id = updated_msg.get("internetMessageId")

        # Fallback: if Prefer header ever changes behaviour
        if not internet_id:
            get_url = f"{patch_url}?$select=internetMessageId"
            get_resp = requests.get(get_url, headers=headers)
            if get_resp.status_code == 200:
                internet_id = get_resp.json().get("internetMessageId")

        # --- Mark original message as unread ---
        mark_unread_url = f"https://graph.microsoft.com/v1.0/users/{draft_emailtarget}/messages/{original_message_id}"
        mark_unread_payload = {"isRead": False}
        requests.patch(mark_unread_url, headers=headers, json=mark_unread_payload)

        # --- Ensure "AI: Draft ✓" category exists and tag the message ---
        CATEGORY_NAME = "AI: Draft ✓"

        # 1) Создаём категорию в masterCategories (если уже есть — игнорируем 409)
        create_cat_url = f"https://graph.microsoft.com/v1.0/users/{draft_emailtarget}/outlook/masterCategories"
        create_cat_payload = {
            "displayName": CATEGORY_NAME,
            "color": "preset4"  # green пресет в Outlook
        }
        resp = requests.post(create_cat_url, headers=headers, json=create_cat_payload)
        if resp.status_code not in (200, 201, 409):
            raise RuntimeError(f"Failed to ensure category: {resp.status_code} {resp.text}")

        # 2) Получаем текущие категории письма
        get_msg_url = f"https://graph.microsoft.com/v1.0/users/{draft_emailtarget}/messages/{original_message_id}?$select=categories"
        msg_resp = requests.get(get_msg_url, headers=headers)
        msg_resp.raise_for_status()
        current_categories = msg_resp.json().get("categories", [])

        # 3) Добавляем нашу категорию (без дубликатов) и записываем обратно
        new_categories = list({*current_categories, CATEGORY_NAME})
        patch_msg_url = f"https://graph.microsoft.com/v1.0/users/{draft_emailtarget}/messages/{original_message_id}"
        patch_payload = {"categories": new_categories}
        requests.patch(patch_msg_url, headers=headers, json=patch_payload)

        return {
            "draft_id": draft_id,
            "internetMessageId": internet_id
        }


    def create_forward_draft_with_custom_answer(original_message_id, forward_html):
        token = get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Step 1: Create a forward draft (includes original attachments automatically)
        url = f"https://graph.microsoft.com/v1.0/users/{draft_emailtarget}/messages/{original_message_id}/createForward"
        response = requests.post(url, headers=headers)

        if response.status_code != 201:
            logging.error(f"Failed to create forward draft: {response.status_code}, {response.text}")
            return None

        draft = response.json()
        draft_id = draft['id']
        original_body = draft['body']['content']  # This includes the forwarded message content

        logging.info("Draft forward created successfully.")

        # Step 2: Prepend your custom message above the original content
        # Forwarding typically includes the original content block; keep or replace as needed
        updated_body = f"{forward_html}<br><br>{original_body}" if quoted_body_flag else forward_html

        patch_url = f"https://graph.microsoft.com/v1.0/users/{draft_emailtarget}/messages/{draft_id}"
        to_recipients = [{"emailAddress": {"address": email}} for email in recipients]

        patch_headers = {
            **headers,
            "Prefer": "return=representation"  # makes PATCH return the full message object
        }

        patch_payload = {
            "body": {
                "contentType": "HTML",
                "content": updated_body
            },
            "toRecipients": to_recipients
        }

        patch_response = requests.patch(patch_url, headers=patch_headers, json=patch_payload)
        if patch_response.status_code != 200:
            logging.error(f"Failed to update forward draft body: {patch_response.status_code}, {patch_response.text}")
            return None

        updated_msg = patch_response.json()
        internet_id = updated_msg.get("internetMessageId")

        # Fallback: if Prefer header ever changes behaviour
        if not internet_id:
            get_url = f"{patch_url}?$select=internetMessageId"
            get_resp = requests.get(get_url, headers=headers)
            if get_resp.status_code == 200:
                internet_id = get_resp.json().get("internetMessageId")
        # --- Mark original message as unread ---
        mark_unread_url = f"https://graph.microsoft.com/v1.0/users/{draft_emailtarget}/messages/{original_message_id}"
        mark_unread_payload = {"isRead": False}
        requests.patch(mark_unread_url, headers=headers, json=mark_unread_payload)

        return {
            "draft_id": draft_id,
            "internetMessageId": internet_id
        }

    
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
        subject = data.get('Email Subject')
        body = data.get('Email Body')
        reply_id = data.get('Reply ID')
        mode = data.get('Mode')

        recipients = data.get('Recipients', [])
        if isinstance(recipients, str):
            try:
                recipients = json.loads(recipients)
            except json.JSONDecodeError:
                logging.error("Failed to decode 'recipients' JSON string")
                recipients = []


        draft_emailtarget = data.get('Draft Email Box')

        quoted_body_flag = data.get('Quoted Body Flag')


        #send = data.get('send', True)  # Default to sending
        send = False

        if not subject or not body or not recipients:
            return func.HttpResponse("Missing required fields.", status_code=400)

        logging.info(f"{'Sending' if send else 'Saving draft'} email to {recipients}")

        if send:
            success = send_email(subject, body, recipients)
        else:
            if mode == "forward":
                success = create_forward_draft_with_custom_answer(reply_id, body)
            else:
                success = create_reply_draft_with_custom_answer(reply_id, body)

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
