import time
import sys
import logging
import threading
import queue
import traceback
import statistics
import json
import re
import asyncio
from datetime import datetime
from decimal import Decimal

import requests
from requests.exceptions import Timeout
from bs4 import BeautifulSoup

from steampy.client import GameOptions, Asset
from steampy.confirmation import ConfirmationExpected
from steampy.utils import account_id_to_steam_id, update_session


logging.getLogger('requests').setLevel(logging.INFO)
logger = logging.getLogger('__main__')


def uncaught_exceptions_handler(type, value, tb):
    logger.critical("\n{0}: {1}\n{2}".format(type, value, ''.join(traceback.format_tb(tb))))
    sys.exit(1)

sys.excepthook = uncaught_exceptions_handler


def sell_on_market(steam_client, game_option):
    def confirm_items():
        logger.info('Confirming market transactions...')
        steam_client.confirm_transactions()
        logger.info('Finished confirming.')

    nameids = {}
    prices_cache = {}
    logger.info('Searching for items to sell...')
    my_skins = steam_client.get_my_inventory(game=game_option, merge=True)
    if game_option == GameOptions.CARDS:
        unpack_booster_packs(steam_client, my_skins)

    for skin_id, skin_descr in my_skins.items():
        if not skin_descr['marketable']:
            continue
        market_name = skin_descr['market_hash_name']
        nameid = nameids.get(market_name, None)
        if not nameid:
            nameid = fetch_nameid(steam_client, game_option, market_name)
            if not nameid:
                continue
            nameids[market_name] = nameid
        average_price, date = prices_cache.get(market_name, (None, None))
        if not average_price or (datetime.today() - date).days >= 1:
            prices_cache[market_name] = get_average_price(steam_client, game_option.value[0], market_name)
        listing_price = eval_listing_price(steam_client, nameid, prices_cache[market_name][0], market_name)
        if not listing_price:
            continue
        appid, context_id = game_option.value
        resp = steam_client.create_market_listing(int(skin_id), listing_price, appid, context_id)
        if 'You have too many listings pending confirmation' in resp.get('message', ''):
            confirm_items()

    confirm_items()
    logger.info('Finished putting items on sale on the market')


def cancel_items(steam_client):
    logger.info('Getting listings...')
    listings = get_listings(steam_client)
    if not listings:
        return

    logger.info('Cancelling items...')
    headers = {
        'X-Prototype-Version': '1.7',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'http://steamcommunity.com/market/',
        'Origin': 'http://steamcommunity.com',
        'Host': 'steamcommunity.com'
    }
    sessionid = steam_client.get_session_id()
    url = 'https://steamcommunity.com/market/removelisting/'
    for skin_id in listings:
        while True:
            try:
                resp = steam_client.session.post(url + skin_id, data={'sessionid': sessionid},
                                                 headers=headers, timeout=10).text
            except Timeout as err:
                logger.error("%s %s", err, url)
                continue
            if resp != '[]':
                if 'Service Unavailable - Zero size object' in resp:
                    logger.error(resp)
                    time.sleep(3)
                    continue
                logger.error('Failed to cancel the listing: %s %s', resp, skin_id)
            break

    time.sleep(10)


def unpack_booster_packs(steam_client, my_skins):
    url = 'http://steamcommunity.com/profiles/%s/ajaxunpackbooster/' % steam_client.steamid
    for skin_id, skin_descr in my_skins.items():
        if skin_descr['type'] == 'Booster Pack':
            data = {
                'appid': skin_descr['appid'],
                'communityitemid': skin_id,
                'sessionid': steam_client.get_session_id()
            }
            resp = steam_client.session.post(url, data=data).json()
            if not resp['success']:
                raise Exception(resp)


def fetch_nameid(steam_client, game_option, market_name):
    nameid_pattern = re.compile('Market_LoadOrderSpread\( ((\d)+) \)')
    nameid = None
    r = steam_client.session.get('http://steamcommunity.com/market/listings/{}/{}'.format(
        game_option.value[0], market_name.replace('?', '%3F')), timeout=10)
    try:
        nameid = nameid_pattern.search(r.text).group(1)
    except AttributeError as err:
        logger.error('%s %s %s', err, r.text, market_name)
    return nameid


def worker(items, steam_client):
    while not items.empty():
        offer = items.get()
        partner_id = account_id_to_steam_id(str(offer['accountid_other']))
        trade_id = offer['tradeofferid']
        resp = steam_client.accept_trade_offer(trade_id, partner_id)
        logger.info(resp)
        items.task_done()


def process_offers(steam_client):
    items = queue.Queue()
    offers = steam_client.get_trade_offers(
        merge=False, get_descriptions=0)['response']['trade_offers_received']
    for item in offers:
        if item.get('items_to_give', None):
            continue
        items.put(item)
    if items.empty():
        logger.info('No offers found')
        return
    logger.info('Found offers. Accepting...')
    for _ in range(5):
        t = threading.Thread(target=worker, args=(items, steam_client))
        t.daemon = True
        t.start()
    items.join()


def sell_on_opskins(steam_client, ops, game_option):
    items = []
    my_skins = steam_client.get_my_inventory(game=game_option)
    current_prices = ops.get_lowest_sale_price()
    for skin_id, skin_descr in my_skins.items():
        if not skin_descr['tradable']:
            continue
        skin_name = skin_descr['market_hash_name']
        logger.info("putting on sale skin: %s", skin_name)
        avg_price = ops.get_average_price(skin_name)[0]
        if not avg_price:
            continue
        current_price = current_prices[skin_name]['price']
        price = max((avg_price, current_price))
        if price > 2:  # lowest price on opskins is 2 cents
            price -= 1
        else:
            continue  # skip item if too cheap
        logger.info("average price of the skin on OPSkins: %s", price / 100)
        item = {
            'appid': game_option.app_id,
            'assetid': skin_id,
            'contextid': 2,
            'price': price
        }
        items.append(item)

    if not items:
        return

    logger.info(items)
    logger.info('Selling items for appid: %s', game_option.app_id)
    start = 0
    end = limit = ops.get_listing_limit()
    tradeoffers = []
    while True:
        resp = ops.list_items(items[start:end])
        if resp['tradeoffer_error']:
            time.sleep(10)
            continue
        logger.info(resp)
        tradeoffers.append((resp['tradeoffer_id'], str(resp['bot_id64'])))
        start, end = end, end + limit
        if start >= len(items):
            break

    for offer_id, bot_id in tradeoffers:
        while True:
            try:
                resp = steam_client.accept_trade_offer(offer_id, bot_id)
                logger.info('Accept trade offer response: %s', resp)
                # It seems like the offer is unaccepted only if success value is false
                if resp.get('success', True):
                    break
            except ConfirmationExpected:
                print('Failed to confirm the trade')


def get_listings(steam_client):
    # if 'marketWalletBalanceAmount' not in r.text:
    #     logger.info("couldn't find the purse element, the session has expired")
    #     update_session(steam_client)
    #     r = steam_client.session.get('http://steamcommunity.com/market/')
    start = 0
    total_count = 1
    listings_total = set()
    while start < total_count:
        resp = steam_client.session.get(
            'http://steamcommunity.com/market/mylistings/render/?query=&start=%s&count=100' % start).json()
        if not resp['success']:
            raise Exception(resp)
        listings_total.update(set(re.findall(r'mylisting_(\d+)', str(resp))))
        total_count = resp['total_count']
        start += 100

    return listings_total


def get_wallet_balance(steam_client):
    resp = steam_client.session.get('http://steamcommunity.com/market/')
    if 'marketWalletBalanceAmount' not in resp.text:
        logger.info("couldn't find the purse element, the session has expired")
        update_session(steam_client)
        resp = steam_client.session.get('http://steamcommunity.com/market/')
    s = BeautifulSoup(resp.text, 'html.parser')
    purse_element = s.find(id='marketWalletBalanceAmount').text.split()
    amount = float(purse_element[0].replace('.', '').replace(',', '.'))
    return amount


async def purchase_skins(steam_client):
    skin_name, appid = request_skin_to_buy()
    nameid_pattern = re.compile('Market_LoadOrderSpread\( ((\d)+) \)')
    wallet_balance = get_wallet_balance(steam_client)
    r = steam_client.session.get('http://steamcommunity.com/market/listings/{}/{}'.format(appid, skin_name))
    nameid = nameid_pattern.search(r.text).group(1)
    headers = {'Referer': "http://steamcommunity.com/market/listings/%s/%s" % (appid, skin_name)}
    data = {
        "sessionid": steam_client.get_session_id(),
        "currency": 5,
        "appid": appid,
        "market_hash_name": skin_name
    }

    average_price = get_average_price(steam_client, appid, skin_name)[0]
    skin_price, quantity = eval_purchase_price(steam_client, nameid)
    while wallet_balance > skin_price:
        while True:
            skin_price, quantity = eval_purchase_price(steam_client, nameid)
            if skin_price / average_price > 1.5:
                logger.info('the current price is 50% more than the average one, waiting...')
                await asyncio.sleep(300)
                skin_name, appid = request_skin_to_buy()
                average_price = get_average_price(steam_client, appid, skin_name)[0]
                continue

            amount_to_buy = wallet_balance // skin_price
            if amount_to_buy > quantity:
                amount_to_buy = quantity

            data["price_total"] = skin_price * 100 * amount_to_buy
            data["quantity"] = amount_to_buy
            response = steam_client.session.post("https://steamcommunity.com/market/createbuyorder/", data=data,
                                                 headers=headers).json()
            try:
                success = response['success']
            except TypeError:
                logger.error('createbuyorder error: %s', response)
                await asyncio.sleep(300)
                continue
            if success != 1:
                if ('You already have an active buy order' in response.get('message', '')
                        or 'The listing may have been removed' in response.get('message', '')
                        or 'servers are currently too busy' in response.get('message', '')
                        or 'You cannot buy any items until' in response.get('message', '')):
                    logger.error(response)
                    time.sleep(15)
                    continue
                else:
                    raise Exception(response)
            logger.info('Item bought. Name: %s, Price: %s, Quantity: %s', skin_name, skin_price, amount_to_buy)
            break

        wallet_balance -= skin_price * amount_to_buy
        time.sleep(5)  # wait until the order is fully complete


def deliver_items(steam_client, token='GzpZvCSv', steamid='76561198177211015'):
    appids = fetch_inventory_appids(steam_client)
    for appid in appids:
        game_option = GameOptions.appid_to_option(appid)
        logger.info('Searching for items to deliver for appid: %s...', appid)
        inventory = steam_client.get_my_inventory(game_option)
        assets = [Asset(item, game_option) for item, item_descr in inventory.items() if item_descr['tradable']]
        if assets:
            logger.info('Found items. Delivering...')
            resp = steam_client.make_offer(token, assets, [], steamid)
            logger.info('Response: %s', resp)
        else:
            logger.info('No items found to deliver.')


def request_skin_to_buy():
    url = 'http://shamanovski.pythonanywhere.com/skin-to-buy'
    while True:
        try:
            resp = requests.get(url, timeout=3)
            skin_name, appid = resp.text.split(':')
            return skin_name, appid
        except (ValueError, requests.exceptions.Timeout) as err:
            print(err, url)
            time.sleep(3)


def fetch_inventory_appids(steam_client):
    resp = steam_client.session.get('http://steamcommunity.com/profiles/%s/inventory/' % steam_client.steamid)
    appids = re.findall(r'inventory_link_(\d+)"', resp.text)
    for farm_appid in ('753', '218620'):
        if farm_appid in appids:
            appids.remove(farm_appid)
    return appids


def get_itemorderhistogram(steam_client, nameid, market_name=None):
    params = {
        'language': 'english',
        'currency': '5',
        'item_nameid': nameid,
        'two_factor': '0'
    }
    url = 'http://steamcommunity.com/market/itemordershistogram'
    r = steam_client.session.get(url, params=params, timeout=10)
    try:
        return r.json()['sell_order_graph']
    except (json.decoder.JSONDecodeError, KeyError) as err:
        logger.error('%s %s %s %s', err, r.text, url, market_name)
        return None


def eval_listing_price(steam_client, nameid, average_price, market_name):
    order_graph = get_itemorderhistogram(steam_client, nameid, market_name)
    if order_graph:
        ctr = 0
        price_init = None
        while True:
            try:
                price_init = order_graph[ctr][0]
            except IndexError:
                break
            if average_price / price_init > 1.2 and price_init > 1:
                ctr += 1
                continue
            break
        if not price_init:
            price_init = average_price
    else:
        price_init = average_price

    subtract = Decimal(price_init) - Decimal(price_init * 0.01)
    price_final = int((float(subtract) * 86.95))
    return price_final


def eval_purchase_price(steam_client, nameid):
    order_graph = get_itemorderhistogram(steam_client, nameid)
    if not order_graph:
        raise Exception("Failed to get sell order graph. See logs...")
    # Increase index by 1 to reduce time of waiting for the appropriate price
    price, quantity = order_graph[1][0], order_graph[1][1]
    return price, quantity


def get_average_price(steam_client, appid, skin_name):
    params = {
        'country': 'RU',
        'currency': '1',
        'appid': appid,
        'market_hash_name': skin_name
    }
    url = 'http://steamcommunity.com/market/pricehistory'
    while True:
        resp = steam_client.session.get(url, params=params, timeout=10)
        try:
            resp = resp.json()
            break
        except json.decoder.JSONDecodeError as err:
            logger.error('%s %s %s', err, url, resp.text)
            time.sleep(3)

    if not resp['success']:
        raise Exception('The steam pricehistory server responded with failure: %s %s' % (resp, skin_name))
    elif resp['price_prefix'] == '$':
        raise Exception('Prices are in USD: %s', params)

    today = datetime.today()
    stats = sort_statistics(resp['prices'], today)
    default_timespan = '7'
    for timespan, value in sorted(stats.items()):
        total_volume = sum((int(element[2]) for element in value))
        if total_volume >= 5:
            default_timespan = timespan
            break
    prices = [price for element in stats[default_timespan] for price in [element[1]] * int(element[2])]
    # prices might not exist for some unpopular items within the timespan of a week
    if not prices:
        logger.info("Couldn't evaluate the average price for %s. The items is unpopular", skin_name)
        return 0, today

    average_price = statistics.mean(prices)
    for price in prices:
        ratio = price / average_price
        if ratio <= 0.5 or ratio >= 2:
            prices.remove(price)
    average_price = statistics.mean(prices)
    # average_trend = determine_trend(today, timespan, stats, average_price)  # the function is not correct
    # average_price *= average_trend
    logger.info('Steam Marketplace stats: %s %s %s' % (average_price, default_timespan, skin_name))
    return average_price, today


def sort_statistics(stats, current_day):
    result = {'1': [], '3': [], '7': []}
    for item in stats:
        date, price = item[:2]
        date = datetime.strptime(date.replace(': +0', ''), '%b %d %Y %H')
        delta_days = (current_day - date).days
        if delta_days < 1:
            result['1'].append(item)
        if delta_days < 3:
            result['3'].append(item)
        if delta_days < 7:
            result['7'].append(item)

    return result


def determine_trend(current_day, timespan, stats, average_price):
    trend_timespan = {'1': 6, '3': 24, '7': 72}
    trend_hours = trend_timespan[timespan]
    trend_prices = []
    while not trend_prices:
        for item in stats:
            date, price, volume = item
            date = datetime.strptime(date.replace(': +0', ''), '%b %d %Y %H')
            delta_hours = (current_day - date).total_seconds() // 3600
            if delta_hours < trend_hours:
                for _ in range(int(volume)):
                    trend_prices.append(price)
        trend_hours += trend_hours

    average_trend = statistics.mean((price / average_price for price in trend_prices))
    return average_trend
