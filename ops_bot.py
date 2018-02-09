import logging
import json

from steampy.client import SteamClient, GameOptions
from common.trades_handler import process_offers, sell_on_opskins, fetch_inventory_appids
from common.opskins_utils import OpSkins

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO,
                    filename='steamfarm/database/ops_sell_log.txt', filemode='w')

api_key = 'e4f2d89cdbac56b132b68cef2c53e5'
seller = OpSkins(api_key)
with open('steamfarm/database/ops_bot.maFile', 'r') as f:
    account_data = json.load(f)


def main():
    steam_client = SteamClient(account_data['api_key'])
    steam_client.login(account_data['account_name'], account_data['account_password'], account_data)
    logging.info('Starting to process offers...')
    process_offers(steam_client)
    appids = fetch_inventory_appids(steam_client)
    appids.remove('578080')  # TEMP
    for appid in appids:
        game_option = GameOptions.appid_to_option(appid)
        seller.appid = appid
        sell_on_opskins(steam_client, seller, game_option)

main()
