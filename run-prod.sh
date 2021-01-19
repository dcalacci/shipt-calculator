#!/usr/bin/env bash
# service account and other details are specific to your install
gcloud builds submit --tag $GCLOUD_PROJECT
gcloud run deploy --image $GCLOUD_PROJECT --platform managed --service-account $SERVICE_ACCT -memory 2G --cpu 2 --set-env-vars EXPORT_PASSWORD=exportpass
