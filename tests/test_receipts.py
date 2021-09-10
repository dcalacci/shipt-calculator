from twilio.rest import Client
import pandas as pd
import os
import pytest

from shipt.receipts import receipt_to_df
from google.cloud import storage


client = storage.Client()
bucket_name = os.environ['TEST_BUCKET_NAME']
folder='tests/images'
delimiter='/'

import os
if not os.path.exists(folder):
    os.makedirs(folder)

def retrieve_test_images():
    """retrieve all blobs from env['TEST_BUCKET_NAME'] with a test_ prefix, saving to local volume"""
# Retrieve all blobs with a prefix matching the file.
    bucket=client.get_bucket(bucket_name)
    # List blobs iterate in folder 
    blobs=bucket.list_blobs(prefix='test_', delimiter=delimiter) # Excluding folder inside bucket
    for blob in blobs:
       print(blob.name)
       destination_uri = '{}/{}'.format(folder, blob.name) 
       blob.download_to_filename(destination_uri)

retrieve_test_images()


headers = "order_number,order_total,late,delivery_only,delivery_window_start,delivery_window_end,delivery_date,delivered_date,delivered_time,order_pay,tip,total_pay,filename,date_submitted,phone,from_zip,is_v1"


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
               }],
               "test_receipt_cards.png":
               [{
                   "order_number": "50859325",
                   "order_total": 56.00,
                   "order_pay": 9.43,
                   "tip": 0,
                   "total_pay": 9.43},
                   {
                   "order_number": "50490162",
                   "order_total": 69.44,
                   "order_pay": 10.21,
                   "tip": 6.48,
                   "total_pay": 16.69}
                ],
               "test_receipt_redacted.jpeg":
               [{
                   "order_total": 69.83,
                   "tip": 5.0,
                   "order_pay": 11.82},
                {
                   "order_total": 131.52,
                   "tip": 25.0,
                   "order_pay": 12.63},
                {
                    "order_total": 181.35,
                    "tip": 0.0,
                    "order_pay": 14.40}
                ]
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


def test_parses_cards(example_receipts):
    fname = "test_receipt_cards.png"
    res = receipt_to_df(os.path.join("tests/images", fname), verbose=True)
    res_dict = res.to_dict(orient='records')
    data = parsed_data[fname]
    for n, shop in enumerate(res_dict):
        for k, v in data[n].items():
            assert data[n][k] == shop[k]


def test_parses_redacted_order_numbers(example_receipts):
    fname = "test_receipt_redacted.jpeg"
    res = receipt_to_df(os.path.join("tests/images", fname), verbose=True)
    res_dict = res.to_dict(orient='records')
    data = parsed_data[fname]
    for n, shop in enumerate(res_dict):
        for k, v in data[n].items():
            assert data[n][k] == shop[k]


def generates_order_number_if_redacted(example_receipts):
    fname = "test_receipt_redacted.jpeg"
    res = receipt_to_df(os.path.join("tests/images", fname), verbose=True)
    res_dict = res.to_dict(orient='records')
    data = parsed_data[fname]
    for n, shop in enumerate(res_dict):
        new_ordernum = "{}{}{}".format(
                int(shop['tip']),
                int(shop['total_pay']),
                shop['delivery_date'].split('/')[1])
        assert shop['order_number'] == new_ordernum

def test_finds_shops_in_receipt(example_receipts):
    for receipt in example_receipts:
        res = receipt_to_df(receipt['filename'])
        print(res)
        assert len(res) > 0


def test_parsing_easy(example_receipts):
    fname = "test_receipt_1.jpeg"
    res = receipt_to_df(os.path.join("tests/images", fname), verbose=True)
    res_dict = res.to_dict(orient='records')
    data = parsed_data[fname]
    for n, shop in enumerate(res_dict):
        for k, v in data[n].items():
            assert data[n][k] == shop[k]


def test_parsing_bad_image(example_receipts):
    fname = "test_receipt_1_bad.png"
    res = receipt_to_df(os.path.join("tests/images", fname), verbose=True)
    res_dict = res.to_dict(orient='records')
    data = parsed_data[fname]
    for n, shop in enumerate(res_dict):
        for k, v in data[n].items():
            assert data[n][k] == shop[k]
    assert(len(res) == 1)


def test_parsing_missing_field(example_receipts):
    fname = "test_receipt_1_bad_nopay.png"
    res = receipt_to_df(os.path.join("tests/images", fname), verbose=True)
    res_dict = res.to_dict(orient='records')
    assert res_dict[0]['total_pay'] == ''
    assert len(res_dict) == 1


def test_parsing_promo(example_receipts):
    fname = "test_receipt_promo_pay.jpeg"
    res = receipt_to_df(os.path.join("tests/images", fname), verbose=True)
    res_dict = res.to_dict(orient="records")
    print(res_dict)
    assert res_dict[0]['promo_pay'] == 4
    assert res_dict[2]['promo_pay'] == 1


def test_parsing_delivery_window_newline(example_receipts):
    res = receipt_to_df("tests/images/test_receipt_window_2lines.png")
    res_dict = res.to_dict(orient='records')
    assert res_dict[0]['delivery_window_start'] == '9AM'
    assert res_dict[1]['delivery_window_start'] == '8AM'
    assert res_dict[0]['delivery_window_end'] == '10AM'


def test_normal_delivery_window(example_receipts):
    res = receipt_to_df(os.path.join(
        "tests/images", "test_receipt_1.jpeg"), verbose=True)
    res_dict = res.to_dict(orient="records")
    assert res_dict[0]['delivery_window_start'] == '4PM'
    assert res_dict[0]['delivery_window_end'] == '5PM'


def test_receipt_small_text(example_receipts):
    res = receipt_to_df(os.path.join(
        "tests/images", "test_receipt_big_parse.png"), verbose=True)
    res_dict = res.to_dict(orient="records")
    assert res_dict[0]['order_pay'] == 10.5
    assert res_dict[1]['order_pay'] == 11.13
    assert res_dict[2]['order_pay'] == 14.49
    assert res_dict[2]['order_total'] == 126.51
    assert res_dict[2]['tip'] == 0.0


def test_big_pay(example_receipts):
    res = receipt_to_df(os.path.join(
        "tests/images", "test_big_pay.jpeg"), verbose=True)
    res_dict = res.to_dict(orient='records')
    assert res_dict[0]['order_pay'] == 75.14


def test_orderpay_toobig(example_receipts):
    res = receipt_to_df(os.path.join(
        "tests/images", "test_receipt_bad_orderpay.png"), verbose=True)
    res_dict = res.to_dict(orient='records')
    assert res_dict[0]['order_pay'] == 11.17


def test_receipt_cutoff_ordernumber(example_receipts):
    res = receipt_to_df(os.path.join("tests/images", "test_receipt_long_3.jpg"),
                        verbose=True)
    res_dict = res.to_dict(orient='records')
    # make sure we don't include an order w/ a cut-off order number
    assert res_dict[1]["order_number"] != ''
    # make sure we get all shops in the long screenshot
    assert len(res_dict) == 7
