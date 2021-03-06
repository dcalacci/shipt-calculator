import requests
import os.path
import pandas as pd
from datetime import datetime, timedelta
from . import receipts
from . import shipt_backend
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer

KEY = os.environ['SECRET_KEY']
s = Serializer(KEY, 60*30) # 60 secs by 30 mins

def write_and_get_signed_path(phone, key, dataframe, uploads_path):
    """write a file to a path using an itsdangerous timed token
    """
    token = s.dumps({'phone': phone, 'key': key}).decode('utf-8')
    fname = "{}.csv".format(token)
    dataframe.to_csv(os.path.join(uploads_path, fname))
    return token

def export_df(df, phone, uploads_path):
    token = write_and_get_signed_path(phone, 'user_export', df, uploads_path)
    return token
