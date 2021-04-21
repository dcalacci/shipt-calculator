from twilio.rest import Client
import pandas as pd
import os
import pytest

from shipt.receipts import receipt_to_df
from shipt.shipt_backend import FirestoreBackend

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'service_account.json'

SB = FirestoreBackend(prefix="")

parsed_data = {"test_receipt_1.jpeg": 
        [
            {
                "order_number": "27852647",
                "order_total": 124.37,
                "order_pay": 14.58,
                "tip": 0

                },
            {
                "order_number": "27815758",
                "order_total": 192.05,
                "order_pay": 19.40,
                "tip": 25.00
                }
            ],
        "test_receipt_1_bad.png":
        [{
            "order_number": "27852647",
            "order_total": 124.37,
            "order_pay": 14.58,
            "tip": 0
            }]
        }

@pytest.fixture
def example_receipts():
    test_data = []
    for fname in os.listdir("tests/images"):
        if fname in parsed_data:
            test_data.append({
                "filename": os.path.join("tests/images", fname),
                "data": parsed_data[fname]})
    return test_data


