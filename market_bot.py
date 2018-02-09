import logging
import json
import asyncio

from steampy.client import SteamClient, GameOptions
from common.trades_handler import process_offers, sell_on_market, purchase_skins, deliver_items, cancel_items


PATH = 'steamfarm/itemsfarm/database/payday2_storage.maFile'
GAME_OPTION = GameOptions.PAYDAY2

logging.getLogger('requests').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)
filelog = logging.FileHandler('steamfarm/itemsfarm/database/market_bot.log', encoding='utf-8', mode='w')
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
filelog.setFormatter(formatter)
logger.setLevel(logging.INFO)
logger.addHandler(filelog)


def main():
    with open(PATH, 'r') as f:
        account_data = json.load(f)
    steam_client = SteamClient(account_data['api_key'])
    steam_client.login(account_data['account_name'], account_data['account_password'], account_data)
    run_market_loop(steam_client)


def run_market_loop(steam_client):
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(process_offers_loop(steam_client))
    asyncio.ensure_future(sell_on_market_loop(steam_client, GAME_OPTION))
    asyncio.ensure_future(purchase_skins_loop(steam_client))
    asyncio.ensure_future(deliver_items_loop(steam_client))
    loop.set_debug(enabled=True)
    loop.run_forever()


async def sell_on_market_loop(steam_client, game_option):
    while True:
        sell_on_market(steam_client, game_option)
        await asyncio.sleep(3600 * 6)
        cancel_items(steam_client)


async def process_offers_loop(steam_client):
    while True:
        logger.info('Searching for offers...')
        process_offers(steam_client)
        await asyncio.sleep(1800)


async def purchase_skins_loop(steam_client):
    while True:
        logger.info('Purchasing skins...')
        await purchase_skins(steam_client)
        await asyncio.sleep(3600 * 6)


async def deliver_items_loop(steam_client):
    while True:
        deliver_items(steam_client)
        await asyncio.sleep(3600 * 24)

main()
