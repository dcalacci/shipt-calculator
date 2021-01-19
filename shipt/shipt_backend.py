from google.cloud import firestore
from fuzzywuzzy import fuzz
import pandas as pd
import numpy as np
from . import receipts

class FirestoreBackend():
    def __init__(self, prefix=""):
        self.db = firestore.Client()
        self.shops_collection = lambda: self.db.collection(
            "{}shops".format(prefix))
        self.phones_collection = lambda: self.db.collection(
            "{}phones".format(prefix))
        self.n_added = 0

    def get_all_shops(self):
        phone_records = self.shops_collection().stream()
        return pd.DataFrame([r.to_dict() for r in phone_records])

    def get_all_phones(self):
        phone_records = self.phones_collection().stream()
        return [r.to_dict() for r in phone_records]

    def get_phone_session(self, phone):
        ref = self.phones_collection().document(phone)
        doc = ref.get()
        if doc.exists:
            if 'session' in doc.to_dict():
                return doc.to_dict()['session']
        return None

    def set_phone_session(self, phone, session_dict):
        ref = self.phones_collection().document(phone)
        data = {'session': session_dict}
        ref.set(data, merge=True)

    def set_phone_metro(self, phone, metro):
        phone = phone.strip("+")
        data = {
            'phone': phone,
            'metro': metro
        }
        ref = self.phones_collection().document(phone)
        ref.set(data, merge=True)

    def get_phone_metro(self, phone):
        phone = phone.strip("+")
        print("finding metro for phone:", phone)
        ref = self.phones_collection().document(phone)
        return ref.get().to_dict()['metro']

    def add_shops(self, df, phone, trim_dupes=True):
        """adds a dataframe of shops to the database.
        """
        phone = phone.strip("+")
        shops_ref = self.shops_collection()
        past_shops = shops_ref.where('phone', '==', phone).stream()
        past_order_numbers = [shop.to_dict()['order_number']
                              for shop in past_shops]

        batch = self.db.batch()
        if trim_dupes:
            order_numbers_keep = [on for on in df.order_number if on not in
                                  past_order_numbers]
            trimmed_df = df[df['order_number'].isin(order_numbers_keep)]
            trimmed_df = trimmed_df.drop_duplicates(subset='order_number',
                                                    keep='first', inplace=False)
        else:
            trimmed_df = df

        # drop any with no order number
        trimmed_df = trimmed_df[trimmed_df["order_number"] != ""]

        trimmed_df['order_pay'] = pd.to_numeric(trimmed_df['order_pay'])
        trimmed_df['order_total'] = pd.to_numeric(trimmed_df['order_total'])
        trimmed_df['tip'] = pd.to_numeric(trimmed_df['tip'])
        trimmed_df['total_pay'] = pd.to_numeric(trimmed_df['total_pay'])
        # add 'is_v1' column
        v1_pay = (trimmed_df["order_total"] * 0.075 + 5)
        trimmed_df['is_v1'] = abs(v1_pay - trimmed_df["order_pay"]) < 0.05

        records = trimmed_df.to_dict(orient='records')
        for r in records:
            if 'order_number' in r and r['order_number'] != "":
                ref = self.shops_collection().document(r['order_number'])
                ref.set(r, merge=True)

        batch.commit()
        return trimmed_df

    def is_new_phone(self, phone):
        phone = phone.strip("+")
        phone_ref = self.phones_collection()
        phones = phone_ref.where('phone', '==', phone).stream()
        phones = [r.to_dict() for r in phones]
        if len(phones) == 0:
            return True
        else:
            return False

    def n_records(self, phone):
        recs = self.get_phone_shops(phone)
        return len(recs)

    def get_phone_shops(self, phone):
        phone = phone.strip("+")
        phone_ref = self.shops_collection()
        # ignore delivery_only shops (for now)
        phone_records = phone_ref.where('phone', '==', phone).where('delivery_only', '==',
                                                                    False).stream()
        return pd.DataFrame([r.to_dict() for r in phone_records])

    def delete_phone_records(self, phone):
        phone = phone.strip("+")
        print("deleting all records with phone:", phone)
        shop_records = self.shops_collection().where("phone", "==",
                                                     phone).stream()
        for record in shop_records:
            record.reference.delete()
        phone_records = self.phones_collection().where("phone", "==",
                                                       phone).stream()
        for record in phone_records:
            record.reference.delete()

    def get_v1_shops(self, phone):
        v1_shops = self.shops_collection().where('phone', '==',
                                                 phone).where('is_v1', '==',
                                                              True).where('delivery_only',
                                                                          '==', False).stream()
        return pd.DataFrame([r.to_dict() for r in v1_shops])

    def get_v2_shops(self, phone):
        v2_shops = self.shops_collection().where('phone', '==',
                                                 phone).where('is_v1', '==',
                                                              False).where('delivery_only',
                                                                           '==', False).stream()
        return pd.DataFrame([r.to_dict() for r in v2_shops])

    def average_pay_v1(self, phone):
        """calculates average pay for a given phone if they had only the v1 algorithm.
        """
        v1_shops = self.get_v1_shops(phone)
        if len(v1_shops) != 0:
            return (len(v1_shops), v1_shops['order_pay'].mean())
        else:
            return (0, None)

    def is_likely_v1_algo_p(self, phone):
        """Returns true if over 3/4 of this phone's shops are from the v1 algo
        """
        v1_shops = self.get_v1_shops(phone)
        if self.n_records(phone) == 0:
            return None
        else:
            pct_v1 = len(v1_shops) / self.n_records(phone)
            return pct_v1 > 0.75

    def average_pay_v2(self, phone):
        """calculates average pay for a given phone using only shops that aren't consistent
        with the v1 pay algorithm.
        does not include delivery_only shops.
        """
        v2_shops = self.get_v2_shops(phone)
        if len(v2_shops) != 0:
            return (len(v2_shops), v2_shops['order_pay'].mean())
        else:
            return (0, None)

    def average_pay_if_v1(self, phone):
        """calculates average pay for a given phone if all their shops were under v1.
        does not include delivery_only shops.
        """
        shops = self.get_phone_shops(phone)
        return (shops["order_total"] * 0.075 + 5).mean()

    def average_pay_true(self, phone):
        """calculates "true" average pay for a given phone #, from 
        all actual given shops.
        """
        mean_pay = self.get_phone_shops(phone)["order_pay"].mean()
        return mean_pay

    def average_tips(self, phone):
        """calculate average tips for each shop
        """
        records = self.get_phone_shops(phone)
        avg_tips = records["tip"].mean()
        tip_pct = (records["tip"] / records["total_pay"]).mean()
        return {"mean_amt": avg_tips, "mean_pct": tip_pct}

    def v1_v2_total_pay_difference(self, phone):
        records = self.get_phone_shops(phone)
        v1_pay = ((records["order_total"] * 0.075) + 5).sum()
        true_pay = records["order_pay"].sum()
        return v1_pay - true_pay

    def get_metro_stats(self, metro):
        metro_records = self.phones_collection().stream()
        metro_records = [r.to_dict() for r in metro_records]
        metro_records = [r for r in metro_records if 'metro' in r]
        metro_phones = [str(r['phone']) for r in metro_records if
                        fuzz.partial_ratio(r['metro'], metro) > 75]
        print(">>> metro phones:", metro_phones)
        if len(metro_phones) < 3:
            print("not enough other shoppers with that metro")
            return None
        metro_shops = self.shops_collection().where('phone', 'in',
                                                    metro_phones).stream()
        metro_shops = pd.DataFrame([r.to_dict() for r in metro_shops])
        if len(metro_shops) < 5:
            print("not enough other shops in that metro")
            return None
        avg_metro_pay = metro_shops['order_pay'].mean()

        v1_shops = metro_shops[metro_shops['is_v1']]['order_pay']
        avg_pay_v1 = v1_shops.mean()

        pct_v1 = len(v1_shops) / len(metro_shops)

        avg_tips = metro_shops['tip'].mean()
        tip_pct = (metro_shops['tip'] / metro_shops['total_pay']).mean()

        return {"n_records": len(metro_shops), "avg_pay_true": avg_metro_pay, "avg_pay_v1": avg_pay_v1, 'pct_v1': pct_v1, "avg_tips": avg_tips, "tip_pct": tip_pct}
