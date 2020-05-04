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


class XeroCredentials(object):
    def __init__(self, config):
        self.SSM = boto3.client("ssm", region_name=config["region_name"])
        self.config = config

    def build_oauth_headers(self):
        # Get refresh token from AWS SSM
        parameter = self.SSM.get_parameter(
            Name="/airflow/tap_xero_refresh_token", WithDecryption=True
        )

        self.config["refresh_token"] = parameter["Parameter"]["Value"]

        self.config = self.refresh_tokens()

        oauth_headers = {
            "Authorization": "Bearer " + self.config["access_token"],
            "Xero-tenant-id": self.config["tenant_id"],
            "Accept": "application/json",
        }

        return oauth_headers

    def rotate_refresh_tokens(self, json_response):

        self.config["refresh_token"] = json_response["refresh_token"]
        self.config["access_token"] = json_response["access_token"]

        # Rotate refresh token on AWS SSM
        self.SSM.put_parameter(
            Name="/airflow/tap_xero_refresh_token",
            Overwrite=True,
            Value=json_response["refresh_token"],
            Type="SecureString",
        )

        return self.config

    def refresh_tokens(self):
        token_refresh_url = "https://identity.xero.com/connect/token"
        b64_id_secret = base64.b64encode(
            bytes(
                self.config["client_id"] + ":" + self.config["client_secret"], "utf-8"
            )
        ).decode("utf-8")
        response = requests.post(
            token_refresh_url,
            headers={
                "Authorization": "Basic " + b64_id_secret,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.config["refresh_token"],
            },
        )
        json_response = response.json()

        self.rotate_refresh_tokens(json_response)

        LOGGER.info("Credentials refreshed, new tokens saved to config")
        return self.config
