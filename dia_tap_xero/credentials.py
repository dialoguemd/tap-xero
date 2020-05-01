import base64
import json
from pathlib import Path

import backoff
import boto3
import requests
import singer
from botocore.exceptions import ClientError as BotoClientError
from oauthlib.oauth1 import SIGNATURE_RSA, SIGNATURE_TYPE_AUTH_HEADER
from requests_oauthlib import OAuth1
from xero.auth import PartnerCredentials

LOGGER = singer.get_logger()

# Initializes ssm client to fetch Xero token parameter
SSM = boto3.client("ssm")


def build_oauth_headers(config):
    # Get refresh token from AWS SSM
    parameter = SSM.get_parameter(
        Name="/airflow/tap_xero_refresh_token", WithDecryption=True
    )

    config["refresh_token"] = parameter["Parameter"]["Value"]

    config = refresh_tokens(config)

    oauth_headers = {
        "Authorization": "Bearer " + config["access_token"],
        "Xero-tenant-id": config["tenant_id"],
        "Accept": "application/json",
    }

    return oauth_headers


def rotate_refresh_tokens(config, json_response):

    config["refresh_token"] = json_response["refresh_token"]
    config["access_token"] = json_response["access_token"]

    # Rotate refresh token on AWS SSM
    SSM.put_parameter(
        Name="/airflow/tap_xero_refresh_token",
        Overwrite=True,
        Value=json_response["refresh_token"],
        Type="SecureString",
    )

    return config


def refresh_tokens(config):
    token_refresh_url = "https://identity.xero.com/connect/token"
    b64_id_secret = base64.b64encode(
        bytes(config["client_id"] + ":" + config["client_secret"], "utf-8")
    ).decode("utf-8")
    response = requests.post(
        token_refresh_url,
        headers={
            "Authorization": "Basic " + b64_id_secret,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "refresh_token", "refresh_token": config["refresh_token"]},
    )
    json_response = response.json()

    config = rotate_refresh_tokens(config, json_response)

    LOGGER.info("Credentials refreshed, new tokens saved to config")
    return config
