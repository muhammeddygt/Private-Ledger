var CACHE_NAME = 'private-ledger-v37';
var SHELL = ['./', './index.html', './manifest.json', './icon-192.png', './icon-512.png'];

self.addEventListener('install', function(e){
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE_NAME).then(function(cache){ return cache.addAll(SHELL); }));
});

self.addEventListener('activate', function(e){
  e.waitUntil(
    caches.keys().then(function(keys){
      return Promise.all(keys.filter(function(k){ return k!==CACHE_NAME; }).map(function(k){ return caches.delete(k); }));
    }).then(function(){ return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function(e){
  var url = e.request.url;
  // Supabase ve diğer uzak API çağrılarına dokunma, direkt ağa bırak
  if(url.indexOf('supabase.co') !== -1 || url.indexOf('malatyakuyumcular') !== -1 || url.indexOf('allorigins') !== -1 || url.indexOf('truncgil') !== -1 || url.indexOf('doviz.com') !== -1 || url.indexOf('tefas') !== -1 || url.indexOf('fundturkey') !== -1 || url.indexOf('corsproxy') !== -1 || url.indexOf('ekofin') !== -1 || url.indexOf('marketvisuals') !== -1 || url.indexOf('fund-prices.json') !== -1 || url.indexOf('katilim-funds.json') !== -1 || e.request.method !== 'GET'){ return; }
  e.respondWith(
    caches.match(e.request).then(function(cached){
      var network = fetch(e.request).then(function(resp){
        if(resp && resp.status===200){
          var copy = resp.clone();
          caches.open(CACHE_NAME).then(function(cache){ cache.put(e.request, copy); });
        }
        return resp;
      }).catch(function(){ return cached; });
      return cached || network;
    })
  );
});
