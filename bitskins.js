const fs = require('fs');
const EventEmitter = require('events');

const SteamCommunity = require('steamcommunity');
const SteamTotp = require('steam-totp');
const TradeOfferManager = require('steam-tradeoffer-manager');

const community = new SteamCommunity();

var totp = require('notp').totp;
var base32 = require('thirty-two');
var request = require('request');
let manager = new TradeOfferManager();
const apiKey = "74315789-5f2a-4d84-8a47-cd362ee51c8b";
const secret = "BHZIQUFOTQVX7BLK";
let code;
let pricelist = {
  "Twitch Prime Balaclava": "",
  "Mann Co. Supply Crate Key": 2.09,
  "Gamma 2 Case Key": 2.05
};

// print out a code that's valid right now
function generateCode() {
  code = totp.gen(base32.decode(secret));
}

function listItems(itemids, prices) {
  request({
    uri: "https://bitskins.com/api/v1/list_item_for_sale",
    qs: {
      api_key: apiKey,
      code: code,
      item_ids: itemids,
      prices: prices,
      app_id: "440"
    }
  }, function(error, response, body) {
      response = JSON.parse(response.body);
      try {
        let botid = response["data"]["bot_info"]["uid"];
      } catch (err) {
        console.log(err + '\n');
        console.log(response);
        process.exit();
      }
      let token = response["data"]["trade_tokens"][0];
      bitskinsOffers.push(token);
  });
}

let promises = [
  new Promise((resolve, reject) => {
    community.getUserInventoryContents("76561198177211015", "440", "2", true, "english", (err, inventory) => {
    let item;
    let result = [];
    for (let i = 0; i < inventory.length; i++) {
      item = inventory[i];
      if (item.tradable) {
        result.push([item.market_hash_name, item.assetid]);
        resolve(result);
      }
    }
  })
}),

  new Promise((resolve, reject) => {
    fs.readFile("common/database/ops_bot.maFile", (err, data) => {
      const mafile = JSON.parse(data);
      community.login({
        accountName: mafile.account_name,
        password: mafile.account_password,
        twoFactorCode: SteamTotp.generateAuthCode(mafile.shared_secret)
      }, function(err, sessionID, cookies, steamguard) {
          manager.setCookies(cookies, (err) => {
            if (err) throw new Error(err);
            resolve();
          });
        });
    });
  })
];

let bitskinsOffers = [];

manager.on('newOffer', function(offer) {
  console.log("New offer #" + offer.id + " from " + offer.partner.getSteam3RenderedID());
  let tokenIndex = bitskinsOffers.findIndex(function(element) {
    let regexp = new RegExp(`BitSkins Trade Token: (${element}),.+`, "i");
    return !!offer.message.match(regexp);
  });

  if (!~tokenIndex) {
    return;
  }

  bitskinsOffers.splice(tokenIndex, 1);
  offer.accept(function(err, status) {
    if (err) {
      console.log("Unable to accept offer: " + err.message);
    } else {
      console.log("Offer accepted: " + status);
      if (status == "pending") {
        community.acceptConfirmationForObject("Y6uDbFkE92y9rcYBRLqNK9+2ax0=",
          offer.id, function(err) {
            if (err) {
              console.log("Can't confirm trade offer: " + err.message);
            } else {
              console.log("Trade offer " + offer.id + " confirmed");
            }
            console.log("offers left: " + bitskinsOffers.length);
            if (!bitskinsOffers.length) {
              process.exit();
            }
        });
      }
    }
  });
});

generateCode();
setInterval(generateCode, 28000);

Promise.all(promises)

  .then(results => {
    let inventory = results[0];
    let itemName, assetid;
    let prices = [];
    let itemids = [];
    for (let i = 0; i < 100; i++) {
      [itemName, assetid] = [inventory[i][0], inventory[i][1]];

      if (!pricelist[itemName]) {
        continue;
      }
      prices.push(pricelist[itemName]);
      itemids.push(assetid);

      if (i > 0 && i % 99 == 0 || i == inventory.length - 1) {
        console.log("listing items: " + i);
        console.log(itemids.length, prices.length);
        listItems(itemids.join(","), prices.join(","));
        prices = [];
        itemids = [];
      }
    }
  })

  .catch(error => {
    console.log(error)
    process.exit();
  })
