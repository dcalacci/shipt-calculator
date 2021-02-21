from flask import Blueprint, request, jsonify, g
from twilio import twiml, base
from twilio.rest import Client
from auth import ensure_authenticated
import os

bp = Blueprint("api", __name__, url_prefix="/api")
client = Client(os.environ["TWILIO_SID"], os.environ["TWILIO_TOKEN"])
SECRET_KEY = os.environ["SECRET_KEY"]

@bp.route("/protected2")
@ensure_authenticated
def wrapped_route():
    return (jsonify(
        isError=False,
        message="SUccess!",
        phone=g.phone,
        statusCode=200),200)
