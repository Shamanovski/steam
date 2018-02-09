const parser = new DOMParser();
let db;

setInterval($.get.bind($, "https://opskins.com/ajax/browse_scroll.php",
 {page: "1", appid: "7", contextId: "2"}, function( data, success, obj ) {
   if (!~data.indexOf("data-amount")) {
     console.log("Failed to parse: " + data + " " + success);
     return;
   page = parser.parseFromString(data, "text/html");
   let cart = parseCatalogue(page);
   for (let i = 0; i < cart.length; i++) {
     purchaseItem(cart[i]);
   }
}
}), 4000 + Math.random() * 2000);


function parseCatalogue(page) {
  let elements = document.querySelectorAll('.featured-item');
  let result = [];
  for (let i = 0; i < elements.length; i++) {
    let element = elements[i];
    let price = element.querySelector("div.item-amount").firstChild.data;
    let name = element.querySelector(".market-name.market-link").firstChild.data.trim();
    if (isItemProfitable(name, price)) {
      let id = element.querySelector("button[data-id]").getAttribute("data-id");
      result.push({id: id, price: price});
    }
  }
  return result;
}


function purchaseItem(item) {
  let url =  "https://api.opskins.com/ICart/QuickBuy/v1/";
  let csrf = $.cookie('opskins_csrf_token')

  data = {
    saleid: item.id,
    total: item.price,
    location: "shop_browse",
    internal_search: "0",
    csrf: csrf
  }

  $.ajax({
    type: "POST",
    url: url,
    xhrFields: { withCredentials:true },
    data: data
  }, function( data, success, obj ) {
    console.log(data);
  })
}


function isItemProfitable(name, price) {
  let average = findAverage(name);
  
}


function getBalance() {
  $.ajax({
    type: "GET",
    url: "https://api.opskins.com/IUser/GetBalance/v1/",
    xhrFields: { withCredentials: true }
  }, function( body, success, response ) {
    console.log(body);
  })
}


function findAverage() {
  let prices = db[name];
  let date = new Date();
  options = {
     year: 'numeric',
     month: '2-digit',
     day: '2-digit'
  }
  let weekAveragePrice = [];
  for (let i = 0; i < 7; i++) {
    day = today.toLocaleString("ru", options);
    let dayAveragePrice = prices[day]["normalized_mean"];
    weekAveragePrice.push(dayAveragePrice);
    date.setDate(date.getDate() - 1);
  }
  return weekAveragePrice;
}


function requestDb() {
  $.get("https://api.opskins.com/IPricing/GetPriceList/v2", {
    appid: "730"
      }, function(data, success) {
        db = JSON.parse(data);
        db = db.response;
      }
   )
}


// {"status":1,"time":1515260297,"balance":556,"credits":0,"response":{"order_id":7411639,"items":[{"saleid":303136036,"inventoryid":349920720}],"failed_saleids":[],"dataLayer":{"product":[{"id":303136036,"game":"CS:GO","name":"Galil AR | Sage Spray (Field-Tested)","price":"$0.04","thumb":"https://steamcommunity-a.opskins.media/economy/image/class/730/310776543/256fx256f"}]}}}
