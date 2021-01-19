from PIL import Image, ImageEnhance, ImageFilter
from datetime import datetime
import pytesseract
import argparse
import cv2
import os
import glob
import pandas as pd
import numpy as np
import string
import random
import math


def strip_punc(s): return s.translate(
    str.maketrans('', '', string.punctuation))


def image_to_text(image_filename):
    image = cv2.imread(image_filename)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # scale 1.5x
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    # enhancer = ImageEnhance.Contrast(gray)
    # gray = enhancer.enhance(2)
    # gray = gray.convert('1')
    # random filename
    filename = "/tmp/{}.png".format(os.getpid() + random.randint(1, 100))
    cv2.imwrite(filename, gray)
    text = pytesseract.image_to_string(Image.open(filename),
                                       config='--psm 6')
    os.remove(filename)
    return text


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def bad_entries_to_na(data):
    for k, v in data.items():
        if k in ['delivery_window_start', 'delivery_window_end',
                 'order_pay', 'order_total', 'tip', 'total_pay']:

            test_str = str(v).replace("PM", "").replace("AM", "")
            if not is_number(test_str):
                data[k] = np.nan
    return data


def to_number_or_none(x):
    try:
        return pd.to_numeric(x)
    except:
        return None


def guess_better_numbers(data):
    """ Guesses better numbers if the order pay, tip, promo pay, and total pay don't add up.
    also creates a new order number from the pay #s if it's been parsed wrong. We check if the order 
    number has been parsed wrong by testing if it's parse-able into a number.
    new order # is: <tip><totalpay><delivery day-of-month>
    """
    if 'tip' not in data or 'order_pay' not in data or 'promo_pay' not in data:
        return data
    data['tip'] = to_number_or_none(data['tip'])
    data['total_pay'] = to_number_or_none(data['total_pay'])
    data['order_pay'] = to_number_or_none(data['order_pay'])
    data['promo_pay'] = to_number_or_none(data['promo_pay'])
    if (data['order_pay'] == None or data['total_pay'] == None):
        return data
    while data['order_pay'] > data['total_pay']:
        data['order_pay'] = round(data['order_pay'] / 10, 2)

    while data['tip'] > data['total_pay']:
        data['tip'] = round(data['tip'] / 10, 2)

    if data['tip'] + data['order_pay'] + data['promo_pay'] != data['total_pay']:
        # the order pay is *always* a decimal, basically. if it's not,
        # it almost definitely means it was parsed incorrectly.
        # breaks, obviously, when tip is greater than promo pay, but that
        # rarely happens.
        if data['order_pay'] > data['total_pay']:
            data['order_pay'] == data['total_pay'] - \
                data['promo_pay'] - data['tip']
        elif data['total_pay'] > data['order_pay'] + data['tip'] + data['promo_pay']:
            data['total_pay'] = data['order_pay'] + \
                data['tip'] + data['promo_pay']
        elif data['tip'] > data['total_pay']:
            data['tip'] = data['total_pay'] - \
                data['order_pay'] - data['promo_pay']

    # order number
    new_ordernum = "{}{}{}".format(
                int(data['tip']), 
                int(data['total_pay']),
                data['delivery_date'].split('/')[1])
    if 'order_number' not in data:
        data['order_number'] = new_ordernum
    else:
        try:
            ordernum = int(data['order_number'])
        except ValueError:
            data['order_number'] = new_ordernum
    return data

def receipt_to_df(image_filename, verbose=False):
    text = image_to_text(image_filename)
    def fword(s): return s.split(" ")[0]
    def line_items(s): return s.split(" ")
    all_data = []
    data = {}
    if verbose:
        print("-----------------")
        print(image_filename)
    lines = text.split("\n")
    for n, line in enumerate(lines):
        first_word = fword(line)
        if verbose:
            print(line_items(line))
            print('window' in line.lower())
            print(line.lower())
            print(first_word)

        if (first_word == 'Window'):
            if (verbose):
                print("new delivery window parsing...")
            lm = line_items(line)
            month = lm[1]
            day = lm[2]
            times = lm[3].split("-")
            # assume current year
            year = datetime.today().year
            date = datetime.strptime("{} {} {}".format(
                month, day, year), "%b %d, %Y")
            datestr = datetime.strftime(date, "%m/%d/%Y")
            data['delivery_window_start'] = times[0]
            data['delivery_window_end'] = times[1]
            data['delivery_date'] = datestr
            data['delivered_date'] = datestr

        elif (first_word == 'Delivery'):
            if line_items(line)[1] == "Only":
                data["delivery_only"] = True
                continue
            elif "delivery_only" not in data:
                data["delivery_only"] = False

            if 'window' in line.lower():
                if (verbose):
                    print("delivery window parsing...", line, lines[n+1])
                if len(line_items(line)) == 2:
                    line = " ".join([line, lines[n+1]])
                delivery_window = line.split(":")[-1]  # gets the XX to XX
                data["delivery_date"] = line_items(line)[2].split(":")[
                    0].strip()  # removes colon
                data["delivery_window_start"] = strip_punc(
                    delivery_window.split("to")[0].strip())
                data["delivery_window_end"] = strip_punc(
                    delivery_window.split("to")[1].strip())
        elif (first_word == 'Delivered'):
            data["delivered_date"] = line_items(line)[1][:-1]  # removes comma
            if data["delivered_date"] == "Today":
                data["delivered_date"] = datetime.now().strftime("%m/%d/%Y")
            data["delivered_time"] = " ".join(
                line_items(line)[2:])  # merges time and AM/PM
        elif (first_word == 'Order' and line_items(line)[1] == 'Pay'):
            data["order_pay"] = line_items(
                line)[2][1:].strip().replace(",", "")
        elif (first_word == 'Order'):

            # new cards only have 4 on this line
            data["order_number"] = strip_punc(
                line_items(line)[1])  # remove hash

            # Some of them don't have an order total
            if len(line_items(line)) >= 4:

                # sometimes it picks up the dot between total and the amount as a plus
                # or an arrow but sometimes, it doesn't. If it has this, it's pretty
                # likely there's an order total.
                if (any(c in line_items(line)[2].strip() for c in ["+", "*", "-", "»", "«"]) or
                        len(line_items(line)[2]) == 1):
                    print("ORDER TOTAL")
                    data["order_total"] = line_items(
                        line)[3][1:].strip().replace(",", "")
                    print(data['order_total'])
                else:
                    print("ORDER total 2222")
                    data["order_total"] = line_items(
                        line)[2][1:].strip().replace(",", "")
                    print(data['order_total'])
            else:
                data["order_total"] = np.nan
            if "Time" in line_items(line)[-1]:
                data["late"] = False
            elif "Late" in line_items(line)[-1]:
                data["late"] = True
        elif (first_word == "Tip"):
            data["tip"] = line_items(line)[-1][1:]
        elif (first_word == 'Promo'):
            data["promo_pay"] = line_items(line)[2][1:].strip()
        elif (first_word == "Total"):
            data["total_pay"] = line_items(
                line)[2][1:].strip().replace(",", "")
            if 'promo_pay' not in data:
                data['promo_pay'] = 0
            data["filename"] = image_filename
            data = guess_better_numbers(data)
            ## make sure order_total is in there too -- if it's not, we can't use it as data.
            if 'order_number' in data and data['order_number'] != '' and 'order_total' in data:
                if verbose:
                   print("Adding", data, "to all_data...")
                all_data.append(data)
            data = {}
        else:
            continue
    df = pd.DataFrame(all_data)
    df["date_submitted"] = datetime.now().strftime("%m/%d/%Y")
    df[["order_pay", "tip", "order_total", "total_pay", "promo_pay"]] = df[["order_pay", "tip",
                                                                            "order_total", "total_pay", "promo_pay"]].apply(to_number_or_none)
    return df.fillna("")
