# shipt-calculator

This is an SMS bot and OCR tool to help Shipt shoppers keep track of their pay more easily. Shoppers can text the
bot screenshots of their pay history, and then export parsed data as a CSV file, compare their pay
to others who have reported pay in their metro area, and get basic statistics on their pay.

It was used in [a 2020 report](https://gigbox.media.mit.edu/posts/2020-10-13-bargaining-with-the-algorithm-shipt-shopper-pay/) that found that 41% of shoppers that contributed data have made _less_ after Shipt changed their payment algorithm.

## Some notes

- note that this is a _research_ repository. The core, dirty OCR script that lives at
  `shipt/receipts.py` can be used as a base for other services. It's not perfect, but it got the job
  done for a few hundred workers in the summer-fall of 2020.

# Install & Setup

This project uses the following external services:

- [Twilio](https://www.twilio.com/) for SMS capability
- [Firebase](https://firebase.google.com/) to store user data

Once you enable Twilio and Firebase, you need to define the following env variables:

```
# service account key needed for running firebase in-container
GOOGLE_APPLICATION_CREDENTIALS=/app/service_account.json
# used for generating temporary links
SECRET_KEY=dev
# password you give to anyone who should be able to export all the data
EXPORT_PASSWORD=mysecretpass
# SID & account token & phone for twilio
TWILIO_SID=twiliosid
TWILIO_TOKEN=twiliotoken
TWILIO_NUMBER=+5555555555
# need this for production flask deployment
FLASK_APP=shipt:create_app
```

## Quick set-up

If you already have a twilio account + number, and a firebase account, fill in the env variables and
[download your google service account key](https://console.cloud.google.com/iam-admin/serviceaccounts), and build + run the docker container in development mode:

```bash
docker build -t "shipt-calculator-dev" -f Dockerfile.dev .
docker run -e CONFIG='development' --env-file .env -p 5000:5000 -v $PWD:/app shipt-calculator-dev:latest
```

Make sure to set your SMS endpoint in twilio to wherever you have the container running:

![twilio setup](screenshots/twilio.png | width=300)

Then, you should be able to interact over SMS:

![sms shot](screenshots/img-commands.png | width=200)

If you submit a screenshot of the Shipt pay screen, you should see something like the following:

![image_submit](screenshots/img-submit.png | width=200)

## Install and Setup

To run the service locally on your development machine, you really just need to get twilio set up.
This means making an account with a phone number you can text.

Once twilio is set up, you can assign the endpoint to your SMS service. I use [ngrok](https://ngrok.com/) to tunnel requests from my dev environment to twilio, but you can use whatever you want. The endpoint for receiving sms is `http://your-hostname/sms`

### Twilio

This project uses the Twilio messaging API to send and receive text messages. To run and test the
code, you need to [sign up for a twilio account](https://www.twilio.com/try-twilio), and [create a
messaging service](https://www.twilio.com/docs/messaging/services). I recommend making two, each with a different phone number attached: one for development and one for deployment.

If you are developing locally, I recommend using [ngrok](https://ngrok.com) to get a public URL you
can use to send twilio web requests. For example, if my docker container is running at
`localhost:5000`, I create a tunnel with `ngrok http 5000 --subdomain shipt-calculator`, and set
`shipt-calculator.ngrok.io/sms` to my Twilio endpoint.

### Google cloud for firebase and exports

This project uses firebase to store user data.

To get up and running, [create a firestore
instance](https://firebase.google.com/docs/firestore/quickstart), and [download the service account
key](https://console.cloud.google.com/iam-admin/serviceaccounts). Generate a private key for the
service account with access to the firestore, and _save it as `shipt-calculator/service_account.json`_.

### Building and running the container

First, make sure that you have a `.env` file (for development) and a `.env.prod` file (for production), as discussed above.

To run in development, and have local changes appear in the container:

```bash
docker build -t "shipt-calculator-dev" -f Dockerfile.dev .
docker run -e CONFIG='development' --env-file .env -p 5000:5000 -v $PWD:/app shipt-calculator-dev:latest
```

And to run in production:

```
docker run -e CONFIG='production' --env-file .env.prod -p 8080:8080 shipt-calculator:latest
```

# Tests

To test this project, I use a bunch of test images that workers have shared. Because these images
include actual pay data and order numbers, I am not making them public, and the test code will
remain in a private repository. If you're interested in testing changes you've made to this repo,
please [contact me](mailto:dcalacci@media.mit.edu) and I can share access.
