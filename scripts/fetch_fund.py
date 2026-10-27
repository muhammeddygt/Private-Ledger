#!/usr/bin/env python3
"""TEFAS'tan fon birim pay fiyatlarını çekip fund-prices.json dosyasına yazar.
GitHub Actions her iş günü akşamı (ve bu dosya değişince) çalıştırır; uygulama bu dosyayı kendi sitesinden okur."""
import json, os, sys, urllib.request, urllib.parse, datetime as dt

CODE = os.environ.get("FUND", "VFK").upper()
OUT = "fund-prices.json"
START = dt.date(2026, 5, 20)
HOSTS = ["https://www.tefas.gov.tr/api/DB/BindHistoryInfo", "https://fundturkey.com.tr/api/DB/BindHistoryInfo"]
HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": "https://www.tefas.gov.tr",
    "Referer": "https://www.tefas.gov.tr/TarihselVeriler.aspx",
}

def parse(rows):
    out = {}
    for x in rows:
        if str(x.get("FONKODU", CODE)).upper() != CODE:
            continue
        try:
            price = float(x.get("FIYAT"))
        except (TypeError, ValueError):
            continue
        t = str(x.get("TARIH", ""))
        if t.isdigit() and len(t) >= 10:      # milisaniye (Türkiye saati gece yarısı)
            d = (dt.datetime.utcfromtimestamp(int(t) / 1000) + dt.timedelta(hours=3)).date()
        elif len(t) >= 10 and t[2] == ".":
            d = dt.datetime.strptime(t[:10], "%d.%m.%Y").date()
        elif len(t) >= 10 and t[4] == "-":
            d = dt.date.fromisoformat(t[:10])
        else:
            continue
        if price > 0:
            out[d.isoformat()] = price
    return out

def fetch(a, b):
    body = urllib.parse.urlencode({
        "fontip": "YAT", "sfontur": "", "fonkod": CODE, "fongrup": "",
        "bastarih": a.strftime("%d.%m.%Y"), "bittarih": b.strftime("%d.%m.%Y"),
        "fonturkod": "", "fonunvantip": "", "kurucukod": "",
    }).encode()
    for host in HOSTS:
        try:
            req = urllib.request.Request(host, data=body, headers=HEAD, method="POST")
            with urllib.request.urlopen(req, timeout=40) as r:
                data = json.loads(r.read().decode("utf-8"))
            rows = data.get("data", []) if isinstance(data, dict) else data
            got = parse(rows)
            if got:
                return got
            print(f"{host}: boş yanıt", file=sys.stderr)
        except Exception as e:
            print(f"{host}: {e}", file=sys.stderr)
    return {}

def main():
    try:
        cur = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        cur = {}
    prices = dict(cur.get("prices", {})) if cur.get("code") == CODE else {}
    today = dt.date.today()
    start = START
    if prices:
        start = max(START, dt.date.fromisoformat(max(prices)) - dt.timedelta(days=10))
    new = 0
    a = start
    while a <= today:
        b = min(a + dt.timedelta(days=79), today)
        got = fetch(a, b)
        if not got and a == start:
            break
        for k, v in got.items():
            if prices.get(k) != v:
                prices[k] = v
                new += 1
        a = b + dt.timedelta(days=1)
    if not prices:
        print("Hiç fiyat alınamadı", file=sys.stderr)
        sys.exit(1)
    json.dump({"code": CODE, "updated": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
               "prices": dict(sorted(prices.items()))}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"{CODE}: {len(prices)} fiyat, {new} yeni/güncel")

if __name__ == "__main__":
    main()
