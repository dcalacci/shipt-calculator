from xml.etree import ElementTree
import pandas as pd
import os
import pytest
import requests
from flask import Flask, session
from shipt.receipts import receipt_to_df
from shipt.shipt_backend import FirestoreBackend
from shipt import create_app, SB

test_number = "+15555555555"


@pytest.fixture(scope="session")
def client():
    app = create_app()
    with app.test_client() as client:
        SB.delete_phone_records(test_number)
        yield client


def test_new_phone(client):
    assert SB.is_new_phone(test_number)

def test_asks_for_city_first_message_text_only(client):
    res = client.post('/sms',
                      data=dict(
                          Body="hi",
                          From=test_number,
                          MessageSid="aaa000",
                          NumMedia=0))
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    assert root.tag == 'Response'
    assert 'To get started, what city do you mainly shop in?' in message.text


def test_asks_for_city_first_message_image_only(client):
    res = client.post('/sms',
                      data=dict(
                          Body="",
                          MessageSid="aaa000",
                          From=test_number,
                          NumMedia=1,
                          MediaUrl0="https://storage.googleapis.com/shipt-test-images/test_receipt_1.jpeg"
                      ))
    assert session['waiting_for_metro']
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    assert root.tag == 'Response'
    assert "Sorry! I think I asked you for your metro area." in message.text
    assert SB.is_new_phone(test_number)

def test_sending_metro(client):
    res = client.post('/sms',
                      data=dict(
                          Body="B City",
                          MessageSid="aaa000",
                          NumMedia=0,
                          From=test_number,
                      ))
    assert session['waiting_for_metro'] == False
    metro = SB.get_phone_metro(test_number)
    assert metro == 'b city'
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    assert "we found 2 new shops" in message.text.lower()
    assert "2 shops in total" in message.text.lower()
    assert not SB.is_new_phone(test_number)

def test_sending_same_image(client):
    res = client.post('/sms',
                      data=dict(
                          Body="",
                          MessageSid="aaa000",
                          From=test_number,
                          NumMedia=1,
                          MediaUrl0="https://storage.googleapis.com/shipt-test-images/test_receipt_1.jpeg"
                      ))
    assert session['n_submissions_total'] == 2
    print(res.data)
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    assert root.tag == 'Response'
    assert "Try sending another?" in message.text


def test_pay_under_10(client):
    res = client.post("/sms",
            data=dict(
                Body="pay",
                MessageSid="aaa001",
                From=test_number,
                NumMedia=0
                ))
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    assert "To calculate your average pay, I need at least 10 shops!" in message.text
    assert "sent me 2" in message.text

def test_multiple_shops(client):

    res = client.post('/sms',
                      data=dict(
                          Body="",
                          MessageSid="aaa000",
                          From=test_number,
                          NumMedia=3,
                          MediaUrl0="https://storage.googleapis.com/shipt-test-images/93875339_10158244832554660_702422526663327744_n.jpg",
                          MediaUrl1="https://storage.googleapis.com/shipt-test-images/93859025_10158244833509660_4173780932567760896_n.jpg",
                          MediaUrl2="https://storage.googleapis.com/shipt-test-images/IMG_1250.PNG"
                      ))
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    assert "8 new shops" in message.text


def test_pay_over_10(client):
    res = client.post("/sms",
            data=dict(
                Body="pay",
                MessageSid="aaa001",
                From=test_number,
                NumMedia=0
                ))
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    assert 'paid $18.81 per shop' in message.text
    assert "Shipt used the new payment algorithm in 7 out of 10" in message.text
    assert "$12.01 per shop" in message.text

def test_export(client):
    res = client.post("/sms",
            data=dict(
                Body="export",
                MessageSid="eee001",
                From=test_number,
                NumMedia=0
                ))
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    print(message.text)
    assert 'exported!' in message.text.lower()
    url = message.text.split("here:")[1].strip()


    r = client.get(url, follow_redirects=True)
    # r = requests.get(url)
    print("request response:", r)
    #retrieving data from the URL using get method
    with open("/tmp/export.csv", 'wb') as f:
        f.write(r.content) 
    df = pd.read_csv('/tmp/export.csv')
    assert len(df) == SB.n_records(test_number)
