import logging
import uuid

import boto3

from flask import Flask, abort, redirect, render_template, request, make_response, url_for

from pyxtream.client import Client
from pyxtream.connection import Connection
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)
app = Flask(__name__)


def create_presigned_url(bucket_name, object_name, expiration=3600):
    """Generate a presigned URL to share an S3 object

    :param bucket_name: string
    :param object_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """

    # Generate a presigned URL for the S3 object
    s3_client = boto3.client('s3')
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name,
                                                            'Key': object_name},
                                                    ExpiresIn=expiration)
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL
    return response


def filter_channels(channels):
    return [c for c in channels if not c["name"].strip().startswith("===")]


def required_fields(*fields):
    missing = []
    for f in fields:
        fv = request.args.get(f)
        if fv is None:
            missing.append(f)
    return missing


def xc_client_from_req():
    missing = required_fields("host", "username", "password")
    if missing:
        abort(400, f"missing fields: {', '.join(missing)}")

    host = request.args.get("host")
    username = request.args.get("username")
    password = request.args.get("password")

    c = Connection(host,
                   scheme=request.args.get("scheme", "https"),
                   username=username,
                   password=password)
    return Client(c)


@app.route('/xc/live/playlist.m3u8')
def playlist():
    extension = request.args.get("extension", "ts")
    filter_category = request.args.get("category")
    client = xc_client_from_req()

    if client.get_user_info()['user_info']['auth'] == 0:
        abort(401)

    categories = {c["category_id"]: c["category_name"] for c in client.get_live_categories()}

    filtered = [ch for ch in filter_channels(client.get_live_streams()) if
                filter_category is None or categories.get(ch["category_id"], 'Unknown').lower().startswith(filter_category.lower())]

    for channel in filtered:
        if not channel["epg_channel_id"]:
            category = categories.get(channel["category_id"])
            log.debug(f'Channel without EPG ID: {channel["name"].strip()} ({channel["stream_id"]}) ({category})')

    channels = [
        {"CUID": channel["stream_id"],
         "tvg-id": channel["epg_channel_id"],
         "tvg-name": channel["name"].strip(),
         "tvg-logo": channel["stream_icon"],
         "group-title": categories.get(channel["category_id"]),
         "name": channel["name"].strip(),
         "url": client.live_url(channel["stream_id"], extension=extension)
         }
        for channel in filtered
    ]

    response = make_response(render_template("playlist.m3u8.tmpl", channels=channels))
    response.mimetype = "application/x-mpegURL"

    return response


def plus1_epg_id(epg_channel_id):
    tvg_id_parts = epg_channel_id.strip().rsplit(".", 1)
    if len(tvg_id_parts) > 1:
        return f"{tvg_id_parts[0]}plus1.{tvg_id_parts[1]}"
    else:
        return f"{epg_channel_id.strip()}plus1"


@app.route('/xc/timeshift/playlist.m3u8')
def timeshift_playlist():
    try:
        shift = int(request.args.get("shift", "1"))
    except ValueError:
        abort(400, "invalid shift value")
        return

    client = xc_client_from_req()
    categories = {c["category_id"]: c["category_name"] for c in client.get_live_categories()}
    channels = []
    for ch in client.get_live_streams():
        if ch['tv_archive']:
            # create +1 names
            ch['name'] = f"{ch['name'].strip()} +1"
            ch['epg_channel_id'] = ch['epg_channel_id'] and plus1_epg_id(ch['epg_channel_id'])
            channels.append(ch)

    channels = [
        {"CUID": f'{channel["stream_id"]}+1',
         "tvg-id": channel["epg_channel_id"],
         "tvg-name": channel["name"].strip(),
         "tvg-logo": channel["stream_icon"],
         "group-title": categories.get(channel["category_id"]),
         "name": channel["name"].strip(),
         "url": url_for('timeshift_channel',
                        stream=channel["stream_id"],
                        shift=shift,
                        username=client.connection.username,
                        scheme=client.connection.scheme,
                        host=client.connection.host,
                        password=client.connection.password,
                        _external=True)
         }
        for channel in channels
    ]

    # render to a file and copy to s3
    output = render_template("playlist.m3u8.tmpl", channels=channels)

    s3 = boto3.resource("s3")
    outpath = f"m3u8/{uuid.uuid4().hex}.m3u8"
    s3.Bucket("iptv-m3u8").put_object(Key=outpath, Body="application/x-mpegURL")

    return redirect(create_presigned_url("iptv-m3u8", outpath))


@app.route("/xc/timeshift/<stream>.ts")
def timeshift_channel(stream):
    try:
        shift = int(request.args.get("shift", "1"))
    except ValueError:
        abort(400, "invalid shift value")

    client = xc_client_from_req()
    return redirect(client.timeshift_url(stream, shift))
