from xml.etree import ElementTree
import pandas as pd
import os
import pytest
from flask import Flask, session
from shipt.receipts import receipt_to_df
from shipt.shipt_backend import FirestoreBackend
from shipt import create_app, SB

test_number = "+16666666666"


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


def test_tips_delivery_only1(client):
    res = client.post("/sms",
            data=dict(
                Body="tips",
                From=test_number,
                MessageSid='bbb000',
                NumMedia=0,
                ))
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    print(message.text)
    assert '$5.73 in tips' in message.text

def test_delivery_only(client):
    res = client.post("/sms",
            data=dict(
                Body="",
                MessageSid='bbb000',
                From=test_number,
                NumMedia=1,
                MediaUrl0="https://storage.googleapis.com/shipt-test-images/test_receipt_delivery_only.PNG"
                ))
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    assert "2 new shops" in message.text

    res = client.post("/sms",
            data=dict(
                Body="pay",
                From=test_number,
                MessageSid='bbb000',
                NumMedia=0,
                ))
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    print(message)
    # if it included delivery_only, it would be $16.83
    assert 'paid $18.04 per shop' in message.text

def test_tips_delivery_only(client):
    res = client.post("/sms",
            data=dict(
                Body="tips",
                From=test_number,
                MessageSid='bbb000',
                NumMedia=0,
                ))
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    print(message.text)
    # would be higher if it included delivery_only
    assert "$5.67 in message.text"

def test_session_gets_restored(client):
    assert session['did_intro']
    # clear the session, then send a text command request
    session.clear()
    res = client.post("/sms",
            data=dict(
                Body="tips",
                From=test_number,
                MessageSid='bbb000',
                NumMedia=0,
                ))
    # make sure session is set
    print(session)
    # request should come back as normal
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    assert "$5.67 in message.text"

def test_delete(client):
    res = client.post("/sms",
            data=dict(
                Body="delete",
                From=test_number,
                MessageSid='bbb000',
                NumMedia=0,
                ))
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    assert 'delete' in message.text

    res = client.post("/sms",
            data=dict(
                Body="delete",
                From=test_number,
                MessageSid='bbb000',
                NumMedia=0,
                ))
    root = ElementTree.fromstring(res.data)
    message = root.findall('Message')[0]
    assert 'deleted' in message.text


