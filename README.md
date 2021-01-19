# shipt-calculator

This is an SMS bot to help Shipt shoppers keep track of their pay more easily. Shoppers can text the
bot screenshots of their pay history, and then export parsed data as a CSV file, compare their pay
to others who have reported pay in their metro area, and get basic statistics on their pay. It was
used in [a 2020 report](https://gigbox.media.mit.edu/posts/2020-10-13-bargaining-with-the-algorithm-shipt-shopper-pay/) that found that 41% of shoppers that contributed data have made _less_ after Shipt changed their payment algorithm.

Quick note that this is a _research_ repository. The core, dirty OCR script that lives at
`shipt/receipts.py` can be used as a base for other services. It's not perfect, but it got the job
done for a few hundred workers in the summer-fall of 2020.

Deploying this is a little tricky, because it requires public URLs to share data exports (those CSVs
that workers can download) and integration with Twilio and Firebase. I'd like to be able to reduce
the dependencies it has on these services, so if anyone would like to help on that front please feel
welcome.

The deployment setup to Google Cloud Run is a work in progress. If you're trying to set this all up
yourself and run into issues, please [send me an email](mailto:dcalacci@media.mit.edu) or open an
issue here!

# Install & Setup

As much as I like locally-hosted services, this project makes heavy use of external services to get
everything working:

- [Twilio](https://www.twilio.com/) for SMS capability
- [Firebase](https://firebase.google.com/) to store user info and quickly iterate.
- Google cloud buckets to create (temporary) publicly accessible URLs for exports and data
- [Google cloud run](https://cloud.google.com/run/) to quickly deploy the dockerized app for cheap production

Instructions for setting up all of these services to work with this project can be found below. If
you have an idea of how to get this project to stop relying on these services, please feel free to
open a PR!

Once you follow all the instructions below, or if you already happen to have a google service
account and a twilio account, you can add your env variables to a `.env` file in the root of the
project, and add your google `service_account.json` to the root directory of the repo, too. The env
file should define all of these variables:

```
SECRET_KEY=dev
EXPORT_PASSWORD=mysecretpass
TWILIO_SID=twiliosid
TWILIO_TOKEN=twiliotoken
TWILIO_NUMBER=+5555555555
TEST_IMAGE_BUCKET_NAME=test-images
```

## Getting things running locally first

To run the service locally on your development machine, you really just need to get twilio set up.
This means making an account with a phone number you can text.

Once twilio is set up, you can assign the endpoint to your SMS service. I use [ngrok](https://ngrok.com/) to tunnel requests from my dev environment to twilio, but you can use whatever you want. The endpoint for receiving sms is `http://your-hostname/sms`

### Twilio

This project uses the Twilio messaging API to send and receive text messages. To run and test the
code, you need to [sign up for a twilio account](https://www.twilio.com/try-twilio), and [create a
messaging service](https://www.twilio.com/docs/messaging/services). I recommend making two, each with a different phone number attached: one for development and one for deployment.

Once you do this, you can add your twilio account SID and token to your `.env` file:

```
TWILIO_SID=twiliosid
TWILIO_TOKEN=twiliotoken
```

### Google cloud for firebase and exports

This project uses firebase to store and access user data, and google cloud buckets to store data
exports and create temporarily available links that users can access and share.

To enable both of these, you need [a service account keyfile](https://console.cloud.google.com/iam-admin/serviceaccounts). Then, you need to [create a cloud bucket](https://cloud.google.com/storage/docs/creating-buckets), and [a cloud firestore instance](https://console.firebase.google.com/u/0/). My Google App Engine default service account has worked for both access to Firestore and cloud buckets made in the same project.

Once you do both of these, add the relevant pieces to your `.env` file:

```
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json
BUCKET_NAME=shipt-calculator
```

## Deploying to google cloud run

This section is a work-in-progress. I found the process of setting all of this up pretty complicated
and annoying, but **extremely smooth** once it was up and running.

### Google & Firebase

1. create a new google cloud project.
2. [enable the cloud build API, create the cloud build service account](https://console.cloud.google.com/cloud-build/settings?_ga=2.243706114.606237968.1611076241-555423138.1611076241)
3. enable the cloud run API (you might end up doing this in the above step)
4. This project uses your [service key file](https://console.cloud.google.com/iam-admin/serviceaccounts), so download the `.json` file, and authenticate your google cloud console with it
   using the command:

   ```
   gcloud authenticate --keyfile=service-account-file.json
   ```

   This file also needs to be in the root of your project directory while the service runs,
   since the backend makes heavy use of firebase and google cloud buckets for storage.

5. Finish your env vars
   Once you've done all the above, you need to add the right info to your `.env` file:

```
SERVICE_ACCT=shipt-calculator@shipt-calculator.iam.gserviceaccount.com
GCP_BUILD_TAG=gcr.io/shipt-calculator/shipt-calculator
```

Once you do the above, you should be able to follow along with the instructions [here](https://cloud.google.com/run/docs/quickstarts/build-and-deploy):

1. Submit docker build
   Submit the docker build to the google cloud registry. This uses the `Dockerfile` at the root
   of the repo by default. When you submit a build, the tag is of the form
   `hostname/project-name/some-tag-id`. If you're only building this container in your
   project, I recommend just making your tag and the project name the same for simplicity:

```
gcloud builds submit --tag gcr.io/shipt-calculator/shipt-calculator
```

**IMPORTANT** After you submit this build, make sure to add this URI to your .env file

```
GCP_BUILD_TAG=gcr.io/shipt-calculator/shipt-calculator
```

2. Run the built container:
   I run this project with 2G of ram and 2 cores, so it can reply to texts reasonably fast and
   process images.

```
gcloud run deploy --image gcr.io/shipt-calculator/shipt-calculator --platform managed
--service-account $SERVICE_ACCT -memory 2G -cpu 2 --set-env-vars
EXPORT_PASSWORD=${EXPORT_PASSWORD}
```

# Tests

To test this project, I use a bunch of test images that workers have shared. Because these images
include actual pay data and order numbers, I am not making them public, and the test code will
remain in a private repository. If you're interested in testing changes you've made to this repo,
please [contact me](mailto:dcalacci@media.mit.edu) and I can share access.
