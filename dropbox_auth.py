import json
import time
import os
import requests

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "dropbox_token.json")

def refresh_dropbox_token():
    with open(TOKEN_FILE, "r") as f:
        token_data = json.load(f)

    refresh_token = token_data["refresh_token"]
    app_key = token_data["app_key"]
    app_secret = token_data["app_secret"]

    response = requests.post(
        "https://api.dropboxapi.com/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        auth=(app_key, app_secret),
    )

    if response.ok:
        new_data = response.json()
        token_data["access_token"] = new_data["access_token"]
        token_data["expires_at"] = time.time() + new_data.get("expires_in", 14400)
        with open(TOKEN_FILE, "w") as f:
            json.dump(token_data, f)
        return token_data["access_token"]
    else:
        raise Exception(f"❌ Failed to refresh Dropbox token: {response.text}")

def get_dropbox_access_token():
    with open(TOKEN_FILE, "r") as f:
        token_data = json.load(f)

    if time.time() >= token_data.get("expires_at", 0):
        return refresh_dropbox_token()
    return token_data["access_token"]
