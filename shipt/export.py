import requests
import os.path
import pandas as pd
from datetime import datetime, timedelta
from . import receipts
from . import shipt_backend
from google.cloud import storage

BUCKET_NAME = os.environ['BUCKET_NAME']
def upload_to_bucket(blob_name, path_to_file, bucket_name):
    """ Upload data to a bucket"""

    # Explicitly use service account credentials by specifying the private key
    # file.
    storage_client = storage.Client()

    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(path_to_file)

    #returns a public url
    blob.make_public()
    return blob.public_url

def upload_to_bucket_signed(blob_name, path_to_file, bucket_name):
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(path_to_file)
    return blob.generate_signed_url(expiration=timedelta(hours=2), version='v4')


def export_df(df, phone):
    filename = "{}_{}.csv".format(phone, datetime.now().strftime("%m-%d-%Y"))
    df.to_csv(os.path.join("/tmp", filename))
    return upload_to_bucket(blob_name=filename, path_to_file=os.path.join("/tmp",
        filename), bucket_name=BUCKET_NAME)


def upload_image(filename, filepath):

    storage_client = storage.Client()

    bucket = storage_client.get_bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_filename(filepath)

    #returns a public url
    return blob.public_url
