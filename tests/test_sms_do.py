from xml.etree import ElementTree
import pandas as pd
import os
import pytest
from flask import Flask, session
from shipt.receipts import receipt_to_df
from shipt.shipt_backend import FirestoreBackend
from shipt import create_app, SB

test_number = "+17777777777"

@pytest.fixture(scope="session")
def client():
    app = create_app()
    with app.test_client() as client:
        SB.delete_phone_records(test_number)
        yield client


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

def test_sending_delivery_only_instead_of_city(client):
    res = client.post('/sms',
                      data=dict(
                          Body="",
                          MessageSid="aaa000",
                          From=test_number,
                          NumMedia=1,
                          MediaUrl0="https://storage.googleapis.com/shipt-test-images/IMG_1264.PNG"))
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    assert root.tag == 'Response'
    assert "Sorry! I think I asked you for your metro area." in message.text

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

def test_sending_delivery_only(client):
    res = client.post('/sms',
                      data=dict(
                          Body="",
                          MessageSid="aaa000",
                          From=test_number,
                          NumMedia=1,
                          MediaUrl0="https://storage.googleapis.com/shipt-test-images/IMG_1264.PNG"))
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    print(message)
    assert "didn't find any new shops" in message.text.lower()
