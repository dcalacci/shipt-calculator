#!/usr/bin/env bash
# service account and other details are specific to your install
export $(cat .env.prod | xargs)
gcloud builds submit --tag $GCLOUD_PROJECT
gcloud run deploy --image $GCLOUD_PROJECT --platform managed --service-account $SERVICE_ACCT --memory 2G --cpu 2 --set-env-vars EXPORT_PASSWORD=${EXPORT_PASSWORD} TWILIO_SID=${TWILIO_SID} TWILIO_TOKEN=${TWILIO_TOKEN} TWILIO_NUMBER=${TWILIO_NUMBER} TEST_IMAGE_BUCKET_NAME=${TEST_IMAGE_BUCKET_NAME} SECRET_KEY=${SECRET_KEY} SERVICE_ACCT=${SERVICE_ACCT} GCLOUD_PROJECT=${GCLOUD_PROJECT} GCP_PROJECT_NAME=${GCP_PROJECT_NAME} GCP_PROJECT_ID=${GCP_PROJECT_ID}
