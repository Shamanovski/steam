import statistics
import logging
import json
import threading
import time
from datetime import datetime

import requests


class OpSkins:

    def __init__(self, api_key, appid=None):
        self.api_key = api_key
        self.api_base = 'https://api.opskins.com/{0}/{1}/{2}/'
        self._pricehistory_average = None
        self._appid = appid

    def get_average_price(self, skin_name):
        average_price, volume = None, None
        try:
            stats = self._pricehistory_average[skin_name]
        except KeyError:
            logging.info('no history for: %s', skin_name)
            return average_price, volume

        average_price, volume = self._calculate_average_price(stats, skin_name)
        return average_price, volume

    @property
    def appid(self):
        return self._appid

    @appid.setter
    def appid(self, value):
        self._appid = value
        self._update_pricehistory()

    def _calculate_average_price(self, stats, skin_name):
        volume = 0
        nearest_prices = {}
        current_day = datetime.today()
        for date, item in stats.items():
            date = datetime.strptime(date, '%Y-%m-%d')
            # subtract 1 to align with the usa time zone
            # subtract 1 because the last timestamp is the day before yesterday
            delta_days = (current_day - date).days
            if delta_days <= 9:
                nearest_prices[delta_days] = item['normalized_mean']
                volume += 1

        if not nearest_prices:
            logging.error("The item has poor price history: %s", skin_name)
            return None, None

        average_price = statistics.mean(nearest_prices.values())
        for delta_days, price in list(nearest_prices.items()):
            coef = price / average_price
            if coef <= 0.5 or coef >= 2:
                del nearest_prices[delta_days]
        average_price = statistics.mean(nearest_prices.values())
        # average_trend = self._determine_trend(nearest_prices, average_price)
        # logging.info('average trend: %s for %s', average_trend, skin_name)
        # if average_trend > 1 and average_price > 2:
        #     average_price *= average_trend

        return int(average_price), volume

    @staticmethod
    def _determine_trend(nearest_prices, average_price):
        average_trend = 1
        trend_prices = []
        trend_days = 3
        while not trend_prices:
            trend_prices = [price for delta_days, price in nearest_prices.items()
                            if delta_days < trend_days]
            trend_days += 3

        if trend_prices:
            average_trend = statistics.mean(
                (price / average_price for price in trend_prices))

        return average_trend

    def _update_pricehistory(self):
        current_time = datetime.today()
        try:
            with open("common/database/opskins_pricehistory.json", "r", encoding="utf-8") as f:
                db = json.load(f)
        except FileNotFoundError:
            db = {}
        try:
            days_delta = (current_time - datetime.fromtimestamp(db[self.appid]['time'])).days
        except (KeyError, AttributeError):
            days_delta = 1

        if days_delta >= 1:
            resp = self.get_pricelist()
            db[self.appid] = resp
            with open("common/database/opskins_pricehistory.json", "w", encoding="utf-8") as f:
                json.dump(resp, f)

        self._pricehistory_average = db[self.appid]['response']
        # the prices database is updated nightly on opskins
        update_time = 24 - datetime.fromtimestamp(db[self.appid]['time']).hour + 2 * 60
        return update_time

    def daemonize_price_update(self):
        def worker():
            while True:
                update_time = self._update_pricehistory()
                time.sleep(update_time)

        t = threading.Thread(target=worker)
        t.daemon = True
        t.start()

    def get_pricelist(self):
        resp = requests.get(self.api_base.format('IPricing', 'GetPriceList', 'v2'),
                            params={'appid': self.appid})
        return resp.json()

    def list_items(self, items):
        data = {
            'key': self.api_key,
            'items': json.dumps(items)
        }
        resp = requests.post(self.api_base.format('ISales', 'ListItems', 'v1'),
                             data=data).json()
        if resp['status'] != 1:
            raise Exception(resp)
        return resp['response']

    def get_listing_limit(self):
        resp = requests.get(self.api_base.format('ISales', 'GetListingLimit', 'v1'),
                            params={'key': self.api_key})
        return resp.json()['response']['listing_limit']

    def resend_offer(self, item_id):
        url = self.api_base.format(USER_ENDPOINT, self.api_key, 'ResendTrade')
        resp = requests.get(url + '&item_id=%s' % item_id)
        logging.info('resend offer response: %s', resp.text)

    def bump_items(self, items):
        resp = requests.post(self.api_base.format('ISales', 'BumpItems', 'v1'),
                             data={'key': self.api_key, 'items': items})
        logging.info('bump item response: %s', resp.text)

    def get_sales(self, type_='2'):
        resp = requests.get(self.api_base.format('ISales', 'GetSales', 'v1'),
                            params={'key': self.api_key, 'type': type_})
        return resp.json()['response']

    def edit_price_multi(self, items):
        resp = requests.post(self.api_base.format('ISales', 'EditPriceMulti', 'v1'),
                             data={'key': self.api_key, 'items': items})
        logging.info('edit item response: %s', resp.text)

    def get_lowest_sale_price(self):
        return requests.get(self.api_base.format('IPricing', 'GetAllLowestListPrices', 'v1'),
                            params={'appid': self.appid}).json()['response']

    def search_items(self, appid, context_id, search_item):
        app = appid + '_' + context_id
        resp = requests.post(self.api_base.format('ISales', 'Search', 'v1'),
                             data={'app': app, 'search_item': '"' + search_item + '"'}).json()
        return resp['response']['sales']

    def buy_items(self, saleids , total):
        resp = requests.post(self.api_base.format('ISales', 'Buyitems', 'v1'),
                             data=json.loads({'saleids': saleids, 'total': total})).json()
        return resp['response']['items']

if __name__ == '__main__':
    ops = OpSkins('e4f2d89cdbac56b132b68cef2c53e5')
    ops.appid = "730"
    # steam_client = SteamClient()
    # steam_client.login('immunepzw', 'arigold4172409', r'C:\Users\sham\Desktop\sda\maFiles\76561198177211015.maFile')
    # my_skins = steam_client.get_my_inventory(game=GameOptions.CS)
    # items = []
    # lowest_prices = ops.get_lowest_sale_price(skin_name)
    # box_classids = (
    #     '520025252', '2048553988', '1544067968',
    #     '1432174707', '1293508920', '926978479',
    #     '1690096482', '991959905', '1797256701',
    #     '1923037342'
    # )
    # for skin_id, skin_descr in my_skins.items():
    #     if not skin_descr['tradable'] or skin_descr['classid'] in box_classids:
    #         continue
    #     skin_name = skin_descr['market_hash_name']
    #     lowest_price = lowest_prices[skin_name]['price']
    #     if lowest_price != 2: # lowest price on opskins is 2 cents
    #         lowest_price -= 1
    #     # average_price = prices_db[skin_name][0]
    #     # if lowest_price / average_price < 0.99:
    #     #     lowest_prices = average_price * 0.99
    #     #     logging.info('lowest price is 1 perc. and more less than purchase one: %s', skin_name)
    #     item = {
    #         'appid': 730,
    #         'assetid': skin_id,
    #         'contextid': 2,
    #         'price': lowest_price
    #     }
    #     items.append(item)
    # prices_db.close()
    # end = ops.get_listing_limit()
    # start = 0
    # while True:
    #     items_slice = items[start:end]
    #     resp = ops.list_items(items)
    #     if resp['tradeoffer_error']:
    #         time.sleep(10)
    #         continue
    #     resp = steam_client.accept_trade_offer(resp['tradeoffer_id'], resp['bot_id64'])
    #     start, end = end, end + 50
