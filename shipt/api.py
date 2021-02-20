from flask import Blueprint, request, jsonify
from twilio import twiml, base
from twilio.rest import Client
import base64
import os
import pyotp
import bcrypt

bp = Blueprint("api", __name__, url_prefix="/api")
client = Client(os.environ["TWILIO_SID"], os.environ["TWILIO_TOKEN"])
SECRET_KEY = os.environ["SECRET_KEY"]

print("Registered api blueprint")


@bp.route("/")
def index():
    return "urls2 index route"


def encode_base32(str):
    """encode input as base32 string using input and a secret key"""
    return base64.b32encode(bytearray(str + SECRET_KEY, "ascii")).decode("utf-8")


def get_otp(phone):
    """create OTP for a phone, using phone as base32 secret"""
    totp = pyotp.TOTP(encode_base32(phone))
    return totp.now()


@bp.route("/auth_otp")
def auth_phone():
    """creates (and sends, through twilio) an OTP code for a phone"""
    phone = request.form["phone"]
    # create one-time password with phone as secret
    message = client.messages.create(
        body="Your one-time code from Shipt Calculator: {}".format(get_otp(phone)),
        from_=os.environ["TWILIO_NUMBER"],
        to=phone,
    )
    return jsonify(isError=False, message="Success", statusCode=200), 200


@bp.route("/verify_otp", methods=["POST"])
def verify_otp():
    """returns 200 if the code matches the current OTP for the phone in the form"""
    code = request.form.get("otp")
    phone = request.form.get("phone")
    authenticated = get_otp(phone) == code
    if not authenticated:
        return (
            jsonify(isError=True, message="Authentication Failed", statusCode=400),
            400,
        )
    else:
        return jsonify(isError=False, message="Success", statusCode=200), 200
