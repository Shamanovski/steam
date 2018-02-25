const fs = require('fs');
const EventEmitter = require('events');

const SteamCommunity = require('steamcommunity');
const SteamTotp = require('steam-totp');

const community = new SteamCommunity();

var totp = require('notp').totp;
var base32 = require('thirty-two');
var request = require('request');
let emitter = new EventEmitter();
let apiKey = "74315789-5f2a-4d84-8a47-cd362ee51c8b";
let secret = "BHZIQUFOTQVX7BLK";
let code;
let pricelist = {
  "Twitch Prime Balaclava": "",
  "Mann Co. Supply Crate Key": "",
  "Gamma 2 Case Key": 1.98
}

// print out a code that's valid right now
function generateCode() {
  code = totp.gen(base32.decode(secret));
}

community.getUserInventoryContents("76561198177211015", "730", "2", true, "english", (err, inventory) => {
  let item;
  let result = [];
  for (let i = 0; i < inventory.length; i++) {
    item = inventory[i];
    if (item.tradable) {
      result.push([item.market_hash_name, item.assetid]);
    }
  }
  emitter.on("logged", sell.bind(null, result));
})

fs.readFile("common/database/ops_bot.maFile", (err, data) => {
  const mafile = JSON.parse(data);
  community.login({
    accountName: mafile.account_name,
    password: mafile.account_password,
    twoFactorCode: SteamTotp.generateAuthCode(mafile.shared_secret)
  }, function(err, sessionID, cookies, steamguard) {
      console.log("emitting");
      emitter.emit("logged");
    })
})

function sell(inventory) {
  let itemPrice, itemName;
  let prices = [];
  let itemids = [];
  for (let i = 0; i < 1; i++) {
    [itemName, assetid] = [inventory[i][0], inventory[i][1]];
    prices.push(pricelist[itemName]);
    itemids.push(assetid);
  }
  put(itemids, prices);
}

function put(itemids, prices) {
  [itemids, prices] = [itemids.join(","), prices.join(",")];
  console.log("putting")
  request({
    uri: "https://bitskins.com/api/v1/list_item_for_sale",
    qs: {
      api_key: apiKey,
      code: code,
      item_ids: itemids,
      prices: prices,
      app_id: "730"
    }
  }, function(error, response, body)  {
      console.log(body);
      // community.acceptConfirmationForObject();
      process.exit();
    }
  )}

// function sortPriceList() {
//   let priceListSorted = {};
//   let item;
//   for (let i = 0; i < pricelist.length; i++) {
//     item = pricelist[i];
//     priceListSorted[item.market_hash_name] = item;
//   }
//   return priceListSorted;
// }

// function getPrices(inventory) {
//   request({
//     uri: "https://bitskins.com/api/v1/get_all_item_prices",
//     qs: {
//       api_key: apiKey,
//       code: code,
//       app_id: "730"
//     }
//   }

generateCode();
setInterval(generateCode, 28000);
