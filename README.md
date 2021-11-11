# steam

### The repository consists of several useful scripts related to Steam

##### bitskins.js - written in javascript, the  daeamon script can be used for consistent listing of your Steam items on Bitskins.com. The servise's API is used.
##### market_bot.py and ops_bot.py asynchronously list your steam items for sale on the steam market or opskins.com respectevely. The price is determined at an average price.
    The average price is calculated with the mean statistics during a period from one day to one month depending on the rarity of the item.
    Dramatic spikes in the value are removed.
    trades_handler.py library allows to buy items as well. The algorithm of purchasing prevents from buying skins at a price 50% more than the average one. Thus, you will be saving your money
##### sniper.js - snipes skins which are too cheap on opskins.com. You can resell them to earn money.
      ! The script is deprecated. Opskins.com is not skins marketplace anymore.
