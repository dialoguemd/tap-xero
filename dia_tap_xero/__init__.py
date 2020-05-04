#!/usr/bin/env python3
import argparse
import json
import os

import singer
from singer import metadata, metrics, utils
from singer.catalog import Catalog, CatalogEntry, Schema
from xero.exceptions import XeroUnauthorized

import dia_tap_xero.streams as streams_
from dia_tap_xero.client import XeroClient
from dia_tap_xero.context import Context

REQUIRED_CONFIG_KEYS = [
    "client_id",
    "client_secret",
    "start_date",
    "tenant_id",
    "region_name",
]

LOGGER = singer.get_logger()

env = os.environ.copy()

BAD_CREDS_MESSAGE = (
    "Failed to refresh OAuth token using the credentials from both the config and S3. "
    "The token might need to be reauthorized from the integration's properties "
    "or there could be another authentication issue. Please attempt to reauthorize "
    "the integration."
)


class BadCredsException(Exception):
    pass


def get_abs_path(path):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), path)


def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("-p", "--properties", help="Catalog file with fields selected")
    parser.add_argument("-c", "--config", help="Optional config file")
    parser.add_argument("-s", "--state", help="State file")
    parser.add_argument(
        "-d",
        "--discover",
        help="Build a catalog from the underlying schema",
        action="store_true",
    )

    args = parser.parse_args()

    return args


def load_file(filename):
    file = {}

    try:
        with open(filename) as handle:
            file = json.load(handle)
    except Exception:
        LOGGER.fatal("Failed to decode config file. Is it valid json?")
        raise RuntimeError

    return file


def load_schema(tap_stream_id):
    path = "schemas/{}.json".format(tap_stream_id)
    schema = utils.load_json(get_abs_path(path))
    dependencies = schema.pop("tap_schema_dependencies", [])
    refs = {}
    for sub_stream_id in dependencies:
        refs[sub_stream_id] = load_schema(sub_stream_id)
    if refs:
        singer.resolve_schema_references(schema, refs)
    return schema


def load_metadata(stream, schema):
    mdata = metadata.new()

    mdata = metadata.write(mdata, (), "table-key-properties", stream.pk_fields)
    mdata = metadata.write(
        mdata, (), "forced-replication-method", stream.replication_method
    )

    if stream.bookmark_key:
        mdata = metadata.write(
            mdata, (), "valid-replication-keys", [stream.bookmark_key]
        )

    for field_name in schema["properties"].keys():
        if field_name in stream.pk_fields or field_name == stream.bookmark_key:
            mdata = metadata.write(
                mdata, ("properties", field_name), "inclusion", "automatic"
            )
        else:
            mdata = metadata.write(
                mdata, ("properties", field_name), "inclusion", "available"
            )

    return metadata.to_list(mdata)


def ensure_credentials_are_valid(config):
    XeroClient(config).filter("currencies")


def discover(config):
    catalog = Catalog([])
    for stream in streams_.all_streams:
        schema_dict = load_schema(stream.tap_stream_id)
        mdata = load_metadata(stream, schema_dict)

        schema = Schema.from_dict(schema_dict)
        catalog.streams.append(
            CatalogEntry(
                stream=stream.tap_stream_id,
                tap_stream_id=stream.tap_stream_id,
                key_properties=stream.pk_fields,
                schema=schema,
                metadata=mdata,
            )
        )
    return catalog


def load_and_write_schema(stream):
    singer.write_schema(
        stream.tap_stream_id, load_schema(stream.tap_stream_id), stream.pk_fields
    )


def sync(ctx):
    currently_syncing = ctx.state.get("currently_syncing")
    start_idx = (
        streams_.all_stream_ids.index(currently_syncing) if currently_syncing else 0
    )

    stream_ids_to_sync = [cs.tap_stream_id for cs in ctx.catalog.streams]

    streams = [
        s
        for s in streams_.all_streams[start_idx:]
        if s.tap_stream_id in stream_ids_to_sync
    ]
    for stream in streams:
        ctx.state["currently_syncing"] = stream.tap_stream_id
        ctx.write_state()
        load_and_write_schema(stream)
        stream.sync(ctx)
    ctx.state["currently_syncing"] = None
    ctx.write_state()


def main_impl():
    args = get_args()

    if args.config:
        LOGGER.info("Config json found")
        config = load_file(args.config)
    elif "xero_config" in env:
        LOGGER.info("Env var config found")
        config = json.loads(env["xero_config"])
    else:
        critical("No config found, aborting")
        return

    if args.properties:
        LOGGER.info("Catalog found")
        args.properties = load_file(args.properties)
        catalog = Catalog.from_dict(args.properties) if args.properties else discover()

    if args.state:
        state = args.state
    else:
        state = {}

    if args.discover:
        discover().dump()
        print()
    else:
        sync(Context(config, state, catalog))


def main():
    try:
        main_impl()
    except Exception as exc:
        LOGGER.critical(exc)
        raise exc


if __name__ == "__main__":
    main()
