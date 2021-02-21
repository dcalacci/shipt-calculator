import requests
import os.path
from flask import Flask, request, redirect, session, send_from_directory, url_for
from twilio.twiml.messaging_response import Message, MessagingResponse
from twilio import twiml, base
from twilio.rest import Client
from datetime import datetime
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
import pandas as pd
import bcrypt
import gspread
from . import receipts
from . import shipt_backend
from . import export
from . import api
from . import auth

SECRET_KEY = os.environ['SECRET_KEY']
prefix = '' if os.environ['CONFIG'] == 'production' else 'test_'
print("setting database prefix:", prefix)
SB = shipt_backend.FirestoreBackend(prefix=prefix)
client = Client(os.environ["TWILIO_SID"], os.environ['TWILIO_TOKEN'])

def create_app():
    # for sessions
    app = Flask(__name__, static_folder=os.path.abspath('/tmp'))
    app.config.from_object(__name__)
    app.secret_key = SECRET_KEY
    uploads_dir = os.path.join(app.root_path, 'uploads')
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    print("created app:", app)
    print("Connected to firestore backend...")

    @app.route("/get_signed_file/<token>", methods=['GET'])
    def get_signed_file(token):
        """ get signed file using a token request. The serializer resets every N minutes (see export.py),
        so a request using an old token should not be able to find the same file. 

        Always send from the uploads directory.

        """
        s = Serializer(os.environ['SECRET_KEY'])
        phone = s.loads(token)['phone']
        print("got a phone from the token:", token, phone)
        return send_from_directory(uploads_dir, '{}.csv'.format(token), as_attachment = True)

    # download directory for images
    DOWNLOAD_DIRECTORY = "/tmp"

    def command_options_text():
        response = "\n'delete' - delete all the shops you've sent, and clear your history completely."
        response += "\n'about' - learn more about this project."
        response += "\n'contact' - puts you in touch with the team responsible for creating this tool"
        response += "\n'more' - to display this message."
        response += "\n'stop' - to stop all texts from this number."
        response += "\n\n"
        response += "If you've sent me at least 10 shops, you can text:"
        response += "\n'pay' - give you the low-down on how changes in Shipt's algorithm may be affecting your pay."
        response += "\n'tips' - let you know your average tip rate, and how much of your pay comes from tips"
        response += "\n'metro' - tell you the average pay per shop in your metro area."
        response += "\n'export' - export your data as a CSV file"
        return response

    def send_help_text(resp):
        response = "I'm a bot that scans screenshots from your shipt shopping history."
        response += " I use your anonymous data to help all the shoppers using this tool."
        response += " You can always text:"
        response += command_options_text()
        resp.message(response)
        return str(resp)

    def send_contact_text(resp):
        response = "Have questions or need help? Contact drew@coworker.org or request to join"
        response += " 'the SHIpT list' on Facebook - an unofficial group for like-minded shoppers: "
        response += "\nhttps://www.facebook.com/groups/theshiptlist/"
        resp.message(response)
        return str(resp)

    def send_about_text(resp):
        response = "This project is part of an effort to learn how changes to Shipt's pay"
        response += " structure are effecting the take home pay of shoppers." 
        response += " Shipt’s original algorithm (which we call 'V1') was clear: "
        response += " Shoppers received 7.5% of the total order amount, plus $5."
        response += " Shipt’s new algorithm, 'V2', is NOT clear."
        response += " We don’t know exactly how payment is calculated, and it often"
        response += " pays workers much less than they would have received under V1."
        response += " As Shipt rolls out the new algorithm in cities across the country,"
        response += " we’re gathering data determine the extent to which the new"
        response += " algorithm reduces overall pay and to support efforts for transparency and fairness."
        resp.message(response)
        return str(resp)

    def send_delete_confirmation(resp):
        response = "Are you sure? The data you've sent can help other shoppers!"
        response += " If you really want to delete the data you've sent, send 'delete' again."
        resp.message(response)
        return str(resp)

    def usd_format(str):
        return '${:,.2f}'.format(str)

    def send_pay_text(resp, phone):
        n_v2, mean_v2_pay = SB.average_pay_v2(phone)

        if (n_v2 == 0):
            response = "On average, you get paid {} per shop & deliver order from Shipt,excluding tips.".format(SB.average_pay_true(phone))
            response += "Based on your shop data, you're in an area that's still using the V1 algorithm, so we can't say for sure how your pay would change under the new V2 algorithm"

            resp.message(response)
            return str(resp)

        mean_v2_pay = usd_format(mean_v2_pay)
        mean_if_v1 = usd_format(SB.average_pay_if_v1(phone))
        mean_pay_true = usd_format(SB.average_pay_true(phone))
        n_shops = SB.n_records(phone)

        delta = SB.v1_v2_total_pay_difference(phone)
        v1_v2_diff = usd_format(abs(delta))
        if (delta > 0):
            post = "more"
        elif (delta == 0):
            v1_v2_diff = ""
            post = "the same"
        else:
            post = "less"

        is_V1 = SB.is_likely_v1_algo_p(phone)

        response = "On average, you get paid {} per shop & deliver order from Shipt, excluding tips.".format(
            mean_pay_true)
        if (is_V1):
            response += " Based on your shop data, you're in an area that's still using the V1 algorithm, so we can't say for sure how your pay would change under the new 'V2' algorithm."
        else:
            response += " Shipt used the new payment algorithm in {} out of {} of the shops you sent us.".format(
                n_v2, n_shops)
            response += " If Shipt never changed their algorithm, you would have been paid {} per shop (on average) instead".format(
                mean_if_v1)
            response += ", and {} {} in total.".format(v1_v2_diff, post)
        response += " These numbers ignore Delivery Only shops, because their pay is fixed."

        resp.message(response)
        return str(resp)

    def send_tips_text(resp, phone):
        tip_info = SB.average_tips(phone)
        tip_pct = "{:.0%}".format(tip_info['mean_pct'])
        if tip_info['mean_pct'] > 1:
            print("TIP ERROR: Tips are over 100% for shopper {}".format(phone))
            response = "Hmm, something's wrong. From your shops, we calculated that about \
{} of your total pay is from tips, but that can't be right. Try emailing drew@coworker.org \
to report it :(".format(tip_pct)
            resp.message(response)
            return str(resp)
        response = "On average, you make {} in tips on each Shop & Deliver order. That's about {} of your total pay!".format(
            usd_format(tip_info['mean_amt']), tip_pct)
        resp.message(response)
        return str(resp)

    def send_metro_text(resp, phone):
        # TODO make the minimum records dependent on unique # of shoppers
        metro = SB.get_phone_metro(phone)
        stats = SB.get_metro_stats(metro)
        print("metro stats:", stats)
        response = ""
        if stats is None or stats['n_records'] < 20:
            response += "We don't have enough data about your area yet. Try again after we've had a chance to collect more."
        else:
            response += "In the '{}' metro area, shoppers generally make about {} every shop, earn {} in tips on average per shop, and about {} of the shops we've collected were paid out using the V1 algorithm.".format(
                metro, usd_format(stats['avg_pay_true']), usd_format(stats['avg_tips']), "{:.0%}".format(stats['pct_v1']))
        resp.message(response)
        return str(resp)

    def intro_no_receipt_text(response):
        response += "Hi! I'm a bot that scans screenshots from your shipt shopping history."
        response += " I use your anonymous data to help all the shoppers using this tool."
        response += "\n\nTo get started, what city do you mainly shop in?"
        return response

    def intro_with_receipt_text(response):
        response += "Thanks for the screenshots! First, to get started, what city do you mainly shop in?"
        return response

    def first_image_response(response, df_added, records_so_far, likely_v1):
        likely_pay_text = ""
        if likely_v1 is None:
            likely_pay_text = " We need more shop + deliver orders or more shops to figure out what algorithm your pay rate is based on."
        elif likely_v1:
            likely_pay_text = " Your pay rate appears to be based on the V1 algorithm."
        else:
            likely_pay_text = ' Your pay rate appears to be based on the V2 algorithm.'

        total_pay = df_added['total_pay'].sum()

        if len(df_added) == 0:
            print("No new shops. returning...")
            response += "Thanks for the screenshot, but we didn't find any new shops in that image. Try sending another? If you think this is an error, type 'contact' to report it."
            print("returning resp:", response)
            return response
        response += "Great, and thanks for the screenshot! We found {} new shops in that \
image, totaling {} (including tips)".format(
            len(df_added), usd_format(total_pay))
        response += " and you've shared {} shops in total.".format(
            records_so_far)
        response += likely_pay_text
        if int(session.get("n_submissions_total", 0)) > 10:
            response += "\n You've send over 10 shops - great work!"
        else:
            response += " Once you give me at least 10 shops, I can also tell you how your pay has changed over time,"
            response += " what earnings look like in your area, and more. Text MORE to learn more."
        return response

    def no_image_response(response):
        response += ("This bot needs images! I scan screenshots from your Shipt shopping history and" +
                     " use your anonymous data to help shoppers. Try submitting a screenshot of your shipping history" +
                     " from the Shipt app. Type MORE to learn more")
        return response

    def cant_find_receipt_response(response):
        response += "Oh no! We didn't find any shops in that screenshot -- I'm just a dumb bot, after all. Try sending another?"
        return response

    def general_error_response(response):
        response += ("I scan screenshots from your Shipt shopping history and" +
                     " use your anonymous data to help shoppers. Try submitting a screenshot of your shipping history" +
                     " from the Shipt app. Type MORE to learn more")
        return response

    def send_command_not_found_text(resp):
        response = "Sorry, I need screenshots, or a command I know! Try one of the below commands, or sending me a screenshot from your Shipt shopping history."
        response += command_options_text()
        resp.message(response)
        return str(resp)

    def has_min_shops(phone):
        records = SB.get_phone_shops(phone)
        return len(records) >= 10

    @app.route("/sms", methods=['POST'])
    def incoming_sms():
        """Send a dynamic reply to an incoming text message"""
        message_body = request.form['Body'].lower().strip()

        # form base response
        resp = MessagingResponse()
        response = ""

        # get phone and zip code if we can
        phone, fromZip = None, None
        if 'From' in request.form:
            phone = request.form['From']
        else:
            resp.message("Sorry, something went wrong, and we couldn't process your request.")
            return str(resp)
        phone = phone.strip("+")

        if 'fromZip' in request.form:
            fromZip = request.form['FromZip']

        def sync_phone_session():
            """ all we're doing is pushing the session every time, unless its empty, which
            means our instance has been reset.
            """
            if not session.get('synced', False):
                firebase_session = SB.get_phone_session(phone)
                if firebase_session is None:
                    session['synced'] = True
                else:
                    for k, v in firebase_session.items():
                        session[k] = v
                    session['synced'] = True
            else:
                print("Pushing local session to firebase")
                SB.set_phone_session(phone, dict(session))

        sync_phone_session()
        if 'reset' in message_body:
            session.clear()
            resp.message("Session reset!")
            return str(resp)

        print("Received message from {} with {} images: {}".format(phone,
                                                                   request.values['NumMedia'], message_body))

        # if has_sent_receipts:
        #    session['did_intro'] = True

        def process_text_command():
            if 'send_all' in message_body or 'sendall' in message_body:
                if session.get("started_send_all", False):
                    ## send message to all numbers
                    counter = 0
                    for phone_record in SB.get_all_phones():
                        print(phone_record)
                        if 'phone' in phone_record:
                            try:
                                number = phone_record["phone"]
                                message = client.messages.create(
                                        body=session["send_all_message"],
                                        from_=os.environ["TWILIO_NUMBER"],
                                        to='+' + number)
                                session['started_send_all'] = False
                                counter += 1
                            except base.exceptions.TwilioRestException:
                                print("ERR: invalid phone number", phone_record, ". Skipping...")
                    session['started_send_all'] = False
                    resp.message("Sent {} messages".format(counter))
                    return str(resp)
                else:
                    password = request.form['Body'].strip().split(":")[1].encode('utf-8')
                    pw = os.environ['EXPORT_PASSWORD'].encode('utf-8')
                    hashed = bcrypt.hashpw(pw, bcrypt.gensalt())
                    if bcrypt.checkpw(password, hashed):
                        message = request.form["Body"].strip().split(":")[2]
                        session["started_send_all"] = True
                        session["send_all_message"] = message
                        session["send_all_message"] = message
                        sync_phone_session()
                        resp.message("Authentication succeeded. Sending the following message: \n" + message + ".\nType 'send_all' to confirm, anything else to cancel.")
                        return str(resp)
                    else:
                        resp.message("Authentication failed.")
                        return str(resp)

            elif 'more' in message_body:
                return send_help_text(resp)
            elif 'contact' in message_body:
                return send_contact_text(resp)
            elif 'about' == message_body:
                return send_about_text(resp)
            elif 'metro' == message_body:
                return send_metro_text(resp, phone)
            elif 'delete' in message_body:
                if session.get('started_delete', False):
                    SB.delete_phone_records(phone)
                    session.clear()
                    resp.message(
                        "Beep boop, poof! All your data has been deleted!")
                    session['started_delete'] = False
                    sync_phone_session()
                    return str(resp)
                else:
                    session['started_delete'] = True
                    sync_phone_session() 
                    return send_delete_confirmation(resp)
            elif 'pay' in message_body:
                if has_min_shops(phone):
                    return send_pay_text(resp, phone)
                else:
                    session['n_submissions_total'] = len(SB.get_phone_shops(phone))
                    resp.message("To calculate your average pay, I need at least 10 shops! You've sent me {}. Try sending more screenshots.".format(
                        session['n_submissions_total']))
                    sync_phone_session()
                    return str(resp)
            elif 'tips' in message_body:
                if has_min_shops(phone):
                    return send_tips_text(resp, phone)
                else:
                    session['n_submissions_total'] = len(SB.get_phone_shops(phone))
                    resp.message("To calculate tip details, I need at least 10 shops! You've sent me {}. Try sending more screenshots.".format(
                        session['n_submissions_total']))
                    return str(resp)
            elif 'export_all' in message_body:
                password = request.form['Body'].strip().split(":")[1].encode('utf-8')
                pw = os.environ['EXPORT_PASSWORD'].encode('utf-8')
                hashed = bcrypt.hashpw(pw, bcrypt.gensalt())
                if bcrypt.checkpw(password, hashed):
                    print("Password matched. Exporting...")
                    df_all = SB.get_all_shops()
                    df_phones = pd.DataFrame(SB.get_all_phones())
                    fname = "shipt_all_shops_{}.csv".format(datetime.now().strftime("%m-%d-%Y"))
                    phonename = "shipt_all_phones_{}.csv".format(datetime.now().strftime("%m-%d-%Y"))
                    fpath = os.path.join("/tmp", fname)
                    phonepath = os.path.join("/tmp", phonename)
                    shops_token = export.write_and_get_signed_path(phone, 'shops', df_all, uploads_dir)
                    phones_token = export.write_and_get_signed_path(phone, 'phones', df_phones, uploads_dir)
                    URL_SHOPS = url_for('get_signed_file', token=shops_token, _external=True)
                    URL_PHONES = url_for('get_signed_file', token=phones_token, _external=True)
                    print("phone URL:", URL_PHONES)
                    resp.message("Authentication succeeded! Export of all data will be available for the next 2 hours. Shops:  {}\n".format(URL_SHOPS))
                    # Send second message
                    message = client.messages.create(
                            body="Phones: {}".format(URL_PHONES),
                                from_=os.environ["TWILIO_NUMBER"],
                                to=phone)
 
                    return str(resp)
                else:
                    resp.message("Authentication failed. Send a message in the format 'export_all:password' to continue.")
                    return str(resp)


            elif 'export' in message_body:
                shop_df = SB.get_phone_shops(phone)
                token = export.export_df(shop_df, phone, uploads_dir)
                url = url_for('get_signed_file', token=token, _external=True)
                resp.message(
                    "Data exported! You can download it here: {}".format(url))
                return str(resp)
            else:
                return send_command_not_found_text(resp)

        def send_response(text):
            sync_phone_session()
            resp = MessagingResponse()
            resp.message(text)
            return str(resp)

        # reset delete counter if they do anything else
        if 'delete' not in message_body:
            session['started_delete'] = False

        if 'send_all' not in message_body and 'sendall' not in message_body:
            session['started_send_all'] = False

        commands = ['more', 'pay', 'tips', 'metro',
                    'contact', 'delete', 'export', 'about']
        has_command = any([c == message_body for c in commands])
        has_command = (has_command or 'export_all' in message_body or 'send_all' in
        message_body or 'sendall' in message_body)
        if (has_command):
            print("processing command...")
            return process_text_command()

        n_images = int(request.values['NumMedia'])
        sent_image = n_images > 0
        df_arr = []
        # if there's an attachment, check if it's a screenshot
        if sent_image:
            for idx in range(n_images):
                df = pd.DataFrame()
                # Use the message SID as a filename.
                print("Found an image, processing...")
                filename = request.values['MessageSid'] + \
                    '_{}'.format(idx) + '.png'
                filepath = '{}/{}'.format(DOWNLOAD_DIRECTORY, filename)
                with open(filepath, 'wb') as f:
                    image_url = request.values['MediaUrl{}'.format(idx)]
                    print("Downloading image from:", image_url)
                    f.write(requests.get(image_url).content)
                try:
                    df = receipts.receipt_to_df(filepath)
                except Exception as e:
                    print("Error parsing receipt:")
                    print(e)
                    df = pd.DataFrame()
                df["phone"] = phone
                df['media_url'] = image_url
                df["from_zip"] = fromZip
                df_arr.append(df)

        if len(df_arr) > 0:
            df = pd.concat(df_arr)
        else:
            df = pd.DataFrame()

        records_from_phone = SB.get_phone_shops(phone)
        is_new_phone = SB.is_new_phone(phone)
        print("records from phone", records_from_phone)
        first_text_had_receipt = session.get("first_text_receipt", False)
        waiting_for_metro = session.get("waiting_for_metro", not is_new_phone)
        did_intro = session.get('did_intro', not is_new_phone)

        # True if the image includes a receipt (shop)
        found_receipt = len(df) > 0
        print("found shops?", len(df))

        if found_receipt:
            records_from_phone = SB.get_phone_shops(phone)
            df_added = SB.add_shops(df, phone)
            records_so_far = len(records_from_phone) + len(df_added)
            rows_dropped = len(df) - len(df_added)
            likely_v1 = SB.is_likely_v1_algo_p(phone)
            session["first_image_response_saved"] = first_image_response(
                "", df_added, records_so_far, likely_v1)
            print("Dropped {} duplicate rows.".format(rows_dropped))
            print("Adding: {}".format(df_added))

        session['n_submissions_total'] = len(SB.get_phone_shops(phone))
        has_sent_receipts = int(session['n_submissions_total']) > 0
        print("Found {} records from phone {}".format(
            session['n_submissions_total'], phone))
        if not did_intro:
            if sent_image and found_receipt:
                likely_v1 = SB.is_likely_v1_algo_p(phone)
                session["first_image_response_saved"] = first_image_response(
                     "", df_added, records_so_far, likely_v1)
                response = intro_with_receipt_text(response)
                session["did_intro"] = True
                session["first_text_receipt"] = True
                session["waiting_for_metro"] = True
                return send_response(response)
            else:
                print("asking for metro")
                response = intro_no_receipt_text(response)
                session["did_intro"] = True
                session["first_text_receipt"] = False
                session["waiting_for_metro"] = True
                return send_response(response)
        elif did_intro and (not (first_text_had_receipt or has_sent_receipts)):
            print("did intro but no receipt yet")
            if waiting_for_metro and not sent_image:
                print("I think I got a metro:", message_body)
                metro = message_body
                session["metro"] = metro
                SB.set_phone_metro(phone, metro)
                session["waiting_for_metro"] = False
                response = session.get("first_image_response_saved", None)
                if response is None:
                    session["first_text_receipt"] = False
                    session["first_image_response_saved"] = None
                    return send_response("Great! Try submitting a screenshot of your shopping history from the Shipt app to get started.")
                else:
                    return send_response(response)
            elif waiting_for_metro and sent_image:
                response += "Sorry! I think I asked you for your metro area. Just reply with what city or town you mainly shop in. If this seems wrong, send 'reset' and try again."
                return send_response(response)
            elif not waiting_for_metro and sent_image:
                # expecting image with receipt.
                if found_receipt:
                    response = first_image_response(
                        response, df_added, records_so_far, likely_v1)
                    print("sending response:", response)
                    return send_response(response)
                else:  # no receipt
                    response = cant_find_receipt_response(response)
                    return send_response(response)
            elif not waiting_for_metro and not sent_image:
                if int(session['n_submissions_total']) < 1:
                    response = no_image_response(response)
                    return send_response(response)
                else:
                    return process_text_command()

            else:
                response = general_error_response(response)
                return send_response(response)
        elif did_intro and (first_text_had_receipt or has_sent_receipts):
            print("did intro but have receipts")
            if waiting_for_metro:
                print("expecting metro response")
                if not sent_image:
                    metro = message_body
                    session["metro"] = metro
                    SB.set_phone_metro(phone, metro)
                    session["waiting_for_metro"] = False
                    print("session metro:", session['metro'])
                    response = session.get("first_image_response_saved", None)
                    if response is None:
                        # something wrong with state - no saved receipt response, but we got an
                        # image. Ask for an image now and change state accordingly.
                        session["first_text_receipt"] = False
                        return send_response("Great! Try submitting a screenshot of your shopping history from the Shipt app to get started.")
                    else:
                        return send_response(response)
                else:
                    response += "Sorry! I think I asked you for your metro area. Just reply with what city or town you mainly shop in. If this seems wrong, send 'reset' and try again."
                    return send_response(response)
            elif sent_image and found_receipt:
                print("sending an image response")
                likely_v1 = SB.is_likely_v1_algo_p(phone)
                response = first_image_response(
                    response, df_added, records_so_far, likely_v1)
                print("sending response:", response)
                return send_response(response)
            elif sent_image and not found_receipt:
                print("sending a not-found response")
                response = cant_find_receipt_response(response)
                return send_response(response)
            elif not sent_image:
                return process_text_command()
            else:
                response = general_error_response(response)
                return send_response(response)
        else:
            response = general_error_response(response)
            return send_response(response)

        return send_response(response)

    app.register_blueprint(api.bp)
    app.register_blueprint(auth.bp)
    print("Registered blueprint.")

    return app
