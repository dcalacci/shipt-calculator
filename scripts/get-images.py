from google.cloud import storage
import shipt
from datetime import datetime
import pandas as pd
import os

BUCKET_NAME = os.environ['BUCKET_NAME']
SB = shipt.shipt_backend.FirestoreBackend()
if __name__ == "__main__":
    # download all images
    storage_client = storage.Client()
    blobs = storage_client.list_blobs(BUCKET_NAME)
    images = [b for b in blobs if '.csv' not in b.name]
    print("> Downloading images...")
    os.makedirs("export/images", exist_ok=True)
    for i in images:
        print(i.name)
        i.download_to_filename(os.path.join("export/images", i.name))

    print("> Downloading parsed data...")
    df_all = SB.get_all_shops()
    df_phones = pd.DataFrame(SB.get_all_phones())
    fname = "shipt_all_shops_{}.csv".format(datetime.now().strftime("%m-%d-%Y"))
    phonename = "shipt_all_phones_{}.csv".format(
        datetime.now().strftime("%m-%d-%Y"))
    fpath = os.path.join("export", fname)
    phonepath = os.path.join("export", phonename)
    print("> Saving dataframes...")
    df_all.to_csv(fpath)
    df_phones.to_csv(phonepath)
