const fs = require('fs');

// const SteamUser = require('steam-user');
const SteamCommunity = require('steamcommunity');
const SteamTotp = require('steam-totp');

const community = new SteamCommunity();
// const client = new SteamUser();

var totp = require('notp').totp;
var base32 = require('thirty-two');
var request = require('request');
let apiKey = "74315789-5f2a-4d84-8a47-cd362ee51c8b";
let secret = "BHZIQUFOTQVX7BLK";
let code, pricelist;

// print out a code that's valid right now
function generateCode() {
  code = totp.gen(base32.decode(secret));
}

community.getUserInventoryContents("76561198177211015", "730", "2", true, "english", (err, inventory) => {

})

function getPrices() {
  request({
    uri: "https://bitskins.com/api/v1/get_all_item_prices",
    qs: {
      api_key: apiKey,
      code: code,
      app_id: "730"
    }
  }, function(error, response, body) {
    pricelist = JSON.parse(body).prices;
    console.log(pricelist[0]);
    console.log(pricelist[0].market_hash_name);
  })
}

generateCode();
// setInterval(generateCode, 28000);
getPrices();

// fs.readFile("common/database/ops_bot.maFile", (err, data) => {
//   const mafile = JSON.parse(data);
//   community.login({
//     accountName: mafile.account_name,
//     password: mafile.account_password,
//     twoFactorCode: SteamTotp.generateAuthCode(mafile.shared_secret)
//   }, function(err, sessionID, cookies, steamguard) {
//     });
//   });
// })


// community.getInventoryContents(730, 2, true, "english", (err, inventory) => {
//   console.log(inventory);
// });
