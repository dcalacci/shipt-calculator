from flask import Blueprint, request, jsonify
from twilio import twiml, base
from twilio.rest import Client
import datetime
import base64
import os
import pyotp
import jwt
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


def create_jwt(phone):
    """generates a token from successful authentication"""
    try:
        payload = {
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7),
            "iat": datetime.datetime.utcnow(),
            "sub": phone,
        }
        return jwt.encode(payload, SECRET_KEY, algorithm="HS256").decode("utf-8")
    except Exception as e:
        print("Could not create JWT token for phone")


def decode_jwt(token):
    """decodes a token and returns ID associated (subject) if valid"""
    try:
        payload = jwt.decode(token.encode(), SECRET_KEY)
        return payload["sub"]
    except jwt.ExpiredSignatureError as e:
        return "Signature expired"
    except jwt.InvalidTokenError as e:
        return "Invalid token: {}".format(e) 


# flow is:
# user requests OTP
# user enters OTP
# user session recieves JWT for associated phone
# user uses this token for all subsequent API requests.


@bp.route("/otp", methods=["GET"])
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
    print("Recieved OTP {} from phone: {}".format(code, phone))
    authenticated = get_otp(phone) == code
    if not authenticated:
        return (
            jsonify(isError=True, message="Authentication Failed", statusCode=400),
            400,
        )
    else:
        token = create_jwt(phone),
        print("Created token:", token)
        return (
            jsonify(
                isError=False,
                message="Success",
                token=token,
                statusCode=200,
            ),
            200,
        )

@bp.route("/protected")
def protected_route():
    """verifies if a token is valid"""
    token = request.form.get("token")
    phone = request.form.get("phone")
    decoded_phone = decode_jwt(token)
    print("Decoded token to phone: {}".format(decoded_phone))
    assert phone == decoded_phone
    return (jsonify(
            isError=False,
            message="Successfully validated",
            phone=decoded_phone,
            statusCode=200
            ), 200)
