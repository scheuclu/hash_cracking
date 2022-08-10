import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']
import base64
from email.message import EmailMessage

CREDS_FILE='./token.json'

def get_creds():
    creds = Credentials.from_authorized_user_file(CREDS_FILE, SCOPES)
    return creds

def message_from_string(content):
    message = EmailMessage()

    message.set_content(content)
    message['To'] = '<todo>@gmail.com'
    message['From'] = '<todo>@gmail.com'
    message['Subject'] = " "

    # encoded message
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()) \
        .decode()

    create_message = {
        'raw': encoded_message
    }

    return create_message


def message_from_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    return message_from_string(content)


def send_file_via_mail(filepath):
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = get_creds()
    service = build('gmail', 'v1', credentials=creds)
    message_body = message_from_file(filepath)
    send_message = (service.users().messages().send
                    (userId="me", body=message_body).execute())
    print(F'Message Id: {send_message["id"]}')

def send_string_via_mail(s):
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = get_creds()
    service = build('gmail', 'v1', credentials=creds)
    message_body = message_from_string(s)
    send_message = (service.users().messages().send
                    (userId="me", body=message_body).execute())
    print(F'Message Id: {send_message["id"]}')


if __name__ == '__main__':
    send_string_via_mail('This is a test.')
