import os
import re
import json
import requests

CLIENT_ID = os.getenv("ACCURATE_CLIENT_ID")
CLIENT_SECRET = os.getenv("ACCURATE_CLIENT_SECRET")

TOKEN_FILE = "token.json"


# =========================================
# CLEAN TERM
# =========================================
def clean_term(term_name):

    if not term_name:
        return 0

    term_name = str(term_name).upper()

    if 'COD' in term_name or 'C.O.D' in term_name:
        return 0

    match = re.search(r'(\d+)', term_name)

    if match:
        return int(match.group(1))

    return 0


# =========================================
# LOAD TOKEN
# =========================================
def load_token():

    try:
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)

    except FileNotFoundError:
        return None

    except Exception as e:
        print(f"ERROR LOAD TOKEN: {e}")
        return None


# =========================================
# SAVE TOKEN
# =========================================
def save_token(token_data):

    with open(TOKEN_FILE, "w") as f:
        json.dump(
            token_data,
            f,
            indent=4
        )


# =========================================
# REFRESH ACCESS TOKEN
# =========================================
def refresh_access_token():

    token_data = load_token()

    if not token_data:
        return None

    refresh_token = token_data.get(
        "refresh_token"
    )

    response = requests.post(
        "https://account.accurate.id/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        },
        auth=(
            CLIENT_ID,
            CLIENT_SECRET
        ),
        timeout=20
    )

    new_token_data = response.json()

    print("REFRESH TOKEN RESPONSE:")
    print(new_token_data)

    if "access_token" in new_token_data:

        save_token(new_token_data)

        return new_token_data.get(
            "access_token"
        )

    return None


# =========================================
# GET VALID ACCESS TOKEN
# =========================================
def get_valid_access_token():

    token_data = load_token()

    if not token_data:
        return None

    access_token = token_data.get(
        "access_token"
    )

    headers = {
        "Authorization":
        f"Bearer {access_token}"
    }

    try:

        test_response = requests.get(
            "https://account.accurate.id/api/db-list.do",
            headers=headers,
            timeout=10
        )

        if test_response.status_code == 401:

            print(
                "TOKEN EXPIRED -> REFRESHING"
            )

            access_token = (
                refresh_access_token()
            )

        return access_token

    except requests.exceptions.Timeout:

        print(
            "REQUEST TIMEOUT KE ACCURATE"
        )

        return access_token

    except Exception as e:

        print(
            "ERROR VALIDASI TOKEN:"
        )

        print(e)

        return access_token