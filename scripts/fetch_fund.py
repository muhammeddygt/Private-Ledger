#!/usr/bin/env python3
"""Fon birim pay fiyatlarını çekip fund-prices.json dosyasına yazar (GitHub Actions: iş günleri akşamı ve bu dosya değişince).
Kaynaklar sırayla: TEFAS API -> fon sayfaları (marketvisuals + ekofin). Sonuç/hata nedenleri fund-status.json'a yazılır."""
import json, os, re, sys, urllib.request, urllib.parse, datetime as dt

CODE = os.environ.get("FUND", "VFK").upper()
OUT, STATUS = "fund-prices.json", "fund-status.json"
START = dt.date(2026, 5, 20)
HOSTS = ["https://www.tefas.gov.tr/api/DB/BindHistoryInfo", "https://fundturkey.com.tr/api/DB/BindHistoryInfo"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HEAD = {"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01", "Origin": "https://www.tefas.gov.tr",
        "Referer": "https://www.tefas.gov.tr/TarihselVeriler.aspx"}
LOG = []

def log(x):
    print(x, file=sys.stderr); LOG.append(x)

def tr_num(s):
    return float(s.replace(".", "").replace(",", "."))

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
        if t.isdigit() and len(t) >= 10:
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

def tefas(a, b):
    body = urllib.parse.urlencode({"fontip": "YAT", "sfontur": "", "fonkod": CODE, "fongrup": "",
        "bastarih": a.strftime("%d.%m.%Y"), "bittarih": b.strftime("%d.%m.%Y"),
        "fonturkod": "", "fonunvantip": "", "kurucukod": ""}).encode()
    for host in HOSTS:
        try:
            req = urllib.request.Request(host, data=body, headers=HEAD, method="POST")
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode("utf-8", "replace")
            data = json.loads(raw)
            got = parse(data.get("data", []) if isinstance(data, dict) else data)
            if got:
                return got
            log(f"{host.split('/')[2]}: boş yanıt ({raw[:80]!r})")
        except Exception as e:
            log(f"{host.split('/')[2]}: {type(e).__name__} {getattr(e, 'code', '')} {str(e)[:80]}")
    return {}

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def text(html):
    html = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html, flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace("&nbsp;", " ")

def scrape():
    """marketvisuals: fiyat (3 hane) + tarih; ekofin: 4 haneli fiyat. İkisi uyuşuyorsa ekofin'in hassas fiyatı marketvisuals tarihine yazılır."""
    mv = ek = None
    try:
        h = get(f"https://marketvisuals.net/tefas-fon/{CODE.lower()}.html")
        t = text(h)
        m = re.search(r"Fiyat:?\s*(\d{1,3}(?:\.\d{3})*,\d{2,6})", t); d = re.search(r"Tarih:?\s*(\d{2})\.(\d{2})\.(\d{4})", t)
        if m and d:
            mv = (f"{d.group(3)}-{d.group(2)}-{d.group(1)}", tr_num(m.group(1)))
            log(f"marketvisuals: {mv[0]} {mv[1]}")
        else:
            log("marketvisuals: fiyat/tarih bulunamadı")
        # sayfada gömülü geçmiş veri var mı (tarih-fiyat çiftleri)?
        pairs = {}
        for dd, pp in re.findall(r"(\d{4}-\d{2}-\d{2})[^0-9]{1,12}?(\d\.\d{3,8})", h):
            v = float(pp)
            if mv and abs(v / mv[1] - 1) < 0.25:
                pairs[dd] = v
        if len(pairs) >= 10:
            log(f"marketvisuals: gömülü geçmiş {len(pairs)} fiyat")
            return pairs, mv
    except Exception as e:
        log(f"marketvisuals: {type(e).__name__} {str(e)[:80]}")
    try:
        t = text(get(f"https://ekofin.net/fonlar/detay/{CODE}/fiyat-endeks-degisimi"))
        m = re.search(r"(\d{1,2},\d{4,6})\s*\(\s*[+-]?%", t)
        if m:
            ek = tr_num(m.group(1)); log(f"ekofin: {ek}")
        else:
            log("ekofin: fiyat bulunamadı")
    except Exception as e:
        log(f"ekofin: {type(e).__name__} {str(e)[:80]}")
    out = {}
    if mv and ek and abs(round(ek, 3) - mv[1]) < 0.0015:
        out[mv[0]] = ek
    elif mv:
        out[mv[0]] = mv[1]
    return out, mv

def main():
    try:
        cur = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        cur = {}
    prices = dict(cur.get("prices", {})) if cur.get("code") == CODE else {}
    today = dt.date.today()
    start = max(START, dt.date.fromisoformat(max(prices)) - dt.timedelta(days=10)) if prices else START
    new = 0; src = ""
    a = start
    while a <= today:
        b = min(a + dt.timedelta(days=79), today)
        got = tefas(a, b)
        if not got:
            break
        src = "TEFAS"
        for k, v in got.items():
            if prices.get(k) != v:
                prices[k] = v; new += 1
        a = b + dt.timedelta(days=1)
    if not src:
        got, _ = scrape()
        if got:
            src = "fon sayfası"
            for k, v in got.items():
                if prices.get(k) != v:
                    prices[k] = v; new += 1
    status = {"code": CODE, "source": src or "yok", "count": len(prices), "last": max(prices) if prices else "", "log": LOG}
    if prices and new:
        json.dump({"code": CODE, "updated": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                   "prices": dict(sorted(prices.items()))}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump(status, open(STATUS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{CODE}: {len(prices)} fiyat, {new} yeni; kaynak: {src or 'yok'}")

if __name__ == "__main__":
    main()
