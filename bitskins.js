const fs = require('fs');

// const SteamUser = require('steam-user');
const SteamCommunity = require('steamcommunity');
const SteamTotp = require('steam-totp');

const community = new SteamCommunity();
// const client = new SteamUser();

fs.readFile("common/database/ops_bot.maFile", (err, data) => {
  const mafile = JSON.parse(data);
  community.login({
    accountName: mafile.account_name,
    password: mafile.account_password,
    twoFactorCode: SteamTotp.generateAuthCode(mafile.shared_secret)
  }, function(err, sessionID, cookies, steamguard) {
    community.getUserInventoryContents("76561198177211015", "730", "2", true, "english", (err, inventory) => {
      console.log(inventory);
    });
  });
})


// community.getInventoryContents(730, 2, true, "english", (err, inventory) => {
//   console.log(inventory);
// });
