import decimal
import json
import re
import time as tm
from datetime import date, datetime, time
from os.path import join

import pytz
import requests
import six
import xero.utils
from singer.utils import strftime
from xero.exceptions import XeroUnauthorized

from dia_tap_xero.credentials import XeroCredentials

BASE_URL = "https://api.xero.com/api.xro/2.0"


def _json_load_object_hook(_dict):
    """Hook for json.parse(...) to parse Xero date formats."""
    # This was taken from the pyxero library and modified
    # to format the dates according to RFC3339
    for key, value in _dict.items():
        if isinstance(value, six.string_types):
            value = xero.utils.parse_date(value)
            if value:
                if type(value) == date:
                    value = datetime.combine(value, time.min)
                value = value.replace(tzinfo=pytz.UTC)
                _dict[key] = strftime(value)
    return _dict


class XeroClient(object):
    def __init__(self, config):
        self.session = requests.Session()
        self.oauth_headers = XeroCredentials(config).build_oauth_headers()
        self.user_agent = config.get("user_agent")

    def update_credentials(self, new_config):
        self.oauth = XeroCredentials(new_config).build_oauth_headers()

    def filter(self, tap_stream_id, *args, since=None, **params):
        xero_resource_name = tap_stream_id.title().replace("_", "")
        url = join(BASE_URL, xero_resource_name)

        # Because Xero limits to 60 calls per minute, sleep for a second before calling
        tm.sleep(1)

        request = requests.Request(
            "GET", url, headers=self.oauth_headers, params=params
        )
        response = self.session.send(request.prepare())
        if response.status_code == 401:
            raise XeroUnauthorized(response)
        response.raise_for_status()
        response_meta = json.loads(
            response.text,
            object_hook=_json_load_object_hook,
            parse_float=decimal.Decimal,
        )
        response_body = response_meta.pop(xero_resource_name)
        return response_body
