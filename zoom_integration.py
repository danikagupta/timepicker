import base64
from typing import Tuple, Union

import requests
import streamlit as st

from typing import List, TypedDict, Union, Dict, Any
import json


ZOOM_TOKEN_ENDPOINT = "https://zoom.us/oauth/token"
ZOOM_API_V2_BASE_URL = "https://api.zoom.us/v2/"


def get_acceess_token(client_id: str, client_secret: str) -> Tuple[str, int]:
    data = {
        "grant_type": "account_credentials",
        "account_id": st.secrets['AID'],
    }

    encoded_auth_header = base64.b64encode(
        f"{client_id}:{client_secret}".encode("utf-8")
    ).decode("utf-8")

    headers = {"Host": "zoom.us", "Authorization": f"Basic {encoded_auth_header}"}

    response = requests.post(ZOOM_TOKEN_ENDPOINT, data=data, headers=headers)
    parsed_reponse = response.json()

    access_token = parsed_reponse["access_token"]
    expiry = parsed_reponse["expires_in"]

    return access_token, expiry


def create_authorized_header():
    access_token, _ = get_acceess_token(st.secrets['CID'], st.secrets['CSE'])
    headers = {"Authorization": f"Bearer {access_token}"}
    headers["Content-Type"] = "application/json"
    return headers

def list_meetings(
    user_id: str,
    meeting_type: str,
    next_page_token: Union[str, None] = None,
    from_date: Union[str, None] = None,
    to_date: Union[str, None] = None,
    page_size: int = 100,
) -> Dict[str, Any]:
    list_meetings_url = ZOOM_API_V2_BASE_URL + f"users/{user_id}/meetings"

    zoom_auth_header = create_authorized_header()

    params = {
        "type": meeting_type,
        "next_page_token": next_page_token,
        "page_size": page_size,
        "from": from_date,
        "to": to_date,
    }

    response = requests.get(list_meetings_url, params=params, headers=zoom_auth_header)
    meetings = response.json()

    return meetings

def get_next_page_token(
    user_id: str,
    meeting_type: str,
    next_page_tokens: Union[None, Dict[str, Dict[str, str]]],
) -> Union[str, None]:
    next_page_token = None

    if user_id and meeting_type and next_page_tokens:
        # next_page_tokens = json.load(next_page_tokens)
        next_page_token = next_page_tokens[user_id][meeting_type]

    return next_page_token

def get_schedules():
    next_page_tokens=None
    meeting_types = ["upcoming"]
    user_ids= [
        '14FZQXqLRSODS33uQTVVaw',
        '5uBBBmxkRs2ULd5cfs8Adw',
        'atAAAIDOQYqcONrWd0oxxg',
        'dZ6K_rnJTOO5S-jOUpXf3w',
        'di6QjKDzTA-BsECJM-lqDA',
        'j4IclWA4ScOUmP_grnbflg',
    ]

    limit = 300
    page_size=250

    try:
        all_meetings = {}
        new_next_page_tokens = {}
        for user_id in user_ids:
            all_meetings[user_id] = {}
            new_next_page_tokens[user_id] = {}

            for meeting_type in meeting_types:
                next_page_token = get_next_page_token(
                    user_id, meeting_type, next_page_tokens
                )

                # Fetch a chunk of meetings
                response = list_meetings(
                    user_id,
                    meeting_type,
                    next_page_token=next_page_token,
                    from_date=None,
                    to_date=None,
                    page_size=page_size,
                )
                print(response)

                if "meetings" not in response:
                    message = (
                        "Cannot fetch the zoom meetings! Error: " + response["message"]
                    )
                    print(message)
                    st.write(f"Error: {message}")
                    return 

                if not next_page_tokens or (next_page_tokens and next_page_token):
                    meetings = response["meetings"]
                    new_next_page_token = response["next_page_token"]

                else:
                    meetings = []
                    new_next_page_token = ""

                total_records = response["total_records"]

                all_meetings[user_id][meeting_type] = {}
                all_meetings[user_id][meeting_type]["sessions"] = meetings
                all_meetings[user_id][meeting_type]["total_sessions"] = total_records
                new_next_page_tokens[user_id][meeting_type] = new_next_page_token

        data = {"meetings": all_meetings, "nextPageTokens": new_next_page_tokens}
        st.sidebar.dataframe(data)
        return data

    except Exception as e:
        message = "Cannot fetch the zoom meetings!"
        print(message, " Error: ", str(e))
        st.write(message, " Error: ", str(e))