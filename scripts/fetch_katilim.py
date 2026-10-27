#!/usr/bin/env python3
"""Faizsiz sekmesi için katılım fonlarının fiyatlarını TEFAS'tan çekip katilim-funds.json dosyasına yazar.

Güvenlik kuralı: bir fon listede ancak TEFAS'taki resmî unvanında "KATILIM" ibaresi geçiyorsa gösterilir
(SPK düzenlemesine göre unvanında "Katılım" geçen fonlar katılım finans ilkelerine uymak ve danışma
kurulu denetiminde olmak zorundadır). Unvanında bu ibare olmayan fon "rejected" listesine alınır, uygulamada görünmez.
TEFAS yanıtında unvan alanı hiç yoksa fon, aşağıdaki aday listesindeki unvanla "liste" doğrulamasıyla işaretlenir."""
import json, sys, datetime as dt, urllib.request

OUT = "katilim-funds.json"
KEEP_DAYS = 75          # saklanan fiyat geçmişi (günlük/aylık getiri için en az ~35 gün gerekir)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HOST = "https://www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetir"
HEAD = {"User-Agent": UA, "Content-Type": "application/json", "Accept": "*/*",
        "Origin": "https://www.tefas.gov.tr", "Referer": "https://www.tefas.gov.tr/tr/fon-verileri"}

# Aday listesi: yalnızca TL cinsi kira sertifikası ve para piyasası katılım fonları (hisse/altın/döviz/serbest yok).
# kod: (tür, kurucu, beklenen unvan)
CANDIDATES = {
    "VFK": ("kira", "Ziraat Portföy", "ZİRAAT PORTFÖY İKİNCİ KISA VADELİ KİRA SERTİFİKALARI KATILIM (TL) FONU"),
    "ZPG": ("kira", "Ziraat Portföy", "ZİRAAT PORTFÖY KİRA SERTİFİKALARI (SUKUK) KATILIM FONU"),
    "VKK": ("kira", "Vakıf Katılım Portföy", "VAKIF KATILIM PORTFÖY KİRA SERTİFİKALARI KATILIM FONU"),
    "VKV": ("kira", "Vakıf Katılım Portföy", "VAKIF KATILIM PORTFÖY KISA VADELİ KİRA SERTİFİKALARI KATILIM FONU"),
    "KTN": ("kira", "Kuveyt Türk Portföy", "KUVEYT TÜRK PORTFÖY KİRA SERTİFİKALARI KATILIM (TL) FONU"),
    "KTV": ("kira", "Kuveyt Türk Portföy", "KUVEYT TÜRK PORTFÖY KISA VADELİ KİRA SERTİFİKALARI KATILIM (TL) FONU"),
    "RBT": ("kira", "Albaraka Portföy", "ALBARAKA PORTFÖY KİRA SERTİFİKALARI KATILIM FONU"),
    "RBV": ("kira", "Albaraka Portföy", "ALBARAKA PORTFÖY KISA VADELİ KİRA SERTİFİKALARI KATILIM (TL) FONU"),
    "ZPO": ("pp", "Ziraat Portföy", "ZİRAAT PORTFÖY PARA PİYASASI KATILIM FONU"),
    "VPA": ("pp", "Vakıf Katılım Portföy", "VAKIF KATILIM PORTFÖY PARA PİYASASI KATILIM FONU"),
    "KLU": ("pp", "Kuveyt Türk Portföy", "KUVEYT TÜRK PORTFÖY PARA PİYASASI KATILIM (TL) FONU"),
    "PPG": ("pp", "Albaraka Portföy", "ALBARAKA PORTFÖY PARA PİYASASI KATILIM FONU"),
}
# Bunlar unvanda geçerse (katılım olsa bile) listeye alınmaz: kullanıcı altın/döviz/hisse istemiyor.
BLOCK_WORDS = ["ALTIN", "DÖVİZ", "DOVIZ", "HİSSE", "HISSE", "SERBEST", "KAR PAYI", "KIYMETLİ", "KIYMETLI", "EUROBOND", "BORÇLANMA"]
LOG = []


def log(x):
    print(x, file=sys.stderr)
    LOG.append(x)


def norm(s):
    """Türkçe büyük/küçük harf farklarından bağımsız karşılaştırma için."""
    return str(s or "").replace("İ", "I").replace("ı", "i").upper().replace("Ö", "O").replace("Ü", "U").replace("Ş", "S").replace("Ç", "C").replace("Ğ", "G")


def to_date(t):
    t = str(t)
    if t.isdigit() and len(t) >= 12:
        return (dt.datetime.utcfromtimestamp(int(t) / 1000) + dt.timedelta(hours=3)).date()
    if t.isdigit() and len(t) == 8:
        return dt.datetime.strptime(t, "%Y%m%d").date()
    if len(t) >= 10 and t[4] == "-":
        return dt.date.fromisoformat(t[:10])
    if len(t) >= 10 and t[2] == ".":
        return dt.datetime.strptime(t[:10], "%d.%m.%Y").date()
    return None


def tefas(code, a, b):
    """(fiyatlar, unvan) döndürür; hata olursa ({}, '')."""
    body = json.dumps({"fonTipi": "YAT", "fonKodu": code, "aramaMetni": None, "fonTurKod": None, "fonGrubu": None,
                       "sfonTurKod": None, "fonTurAciklama": None, "kurucuKod": None,
                       "basTarih": a.strftime("%Y%m%d"), "bitTarih": b.strftime("%Y%m%d"), "basSira": 1, "bitSira": 100000,
                       "dil": "TR", "sFonTurKod": "", "fonKod": "", "fonGrup": "", "fonUnvanTip": ""}).encode()
    try:
        req = urllib.request.Request(HOST, data=body, headers=HEAD, method="POST")
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read().decode("utf-8", "replace")
        data = json.loads(raw)
        rows = (data.get("resultList") or []) if isinstance(data, dict) else data
    except Exception as e:
        log(f"{code}: TEFAS {type(e).__name__} {getattr(e, 'code', '')} {str(e)[:80]}")
        return {}, ""
    prices, unvan = {}, ""
    for x in rows:
        if str(x.get("fonKodu", x.get("FONKODU", code))).upper() != code:
            continue
        unvan = unvan or str(x.get("fonUnvan") or x.get("FONUNVAN") or x.get("fonAdi") or x.get("FONADI") or "")
        try:
            price = float(x.get("fiyat", x.get("FIYAT")))
        except (TypeError, ValueError):
            continue
        d = to_date(x.get("tarih", x.get("TARIH", "")))
        if d and price > 0:
            prices[d.isoformat()] = price
    if not prices:
        log(f"{code}: TEFAS boş yanıt ({raw[:100]!r})")
    return prices, unvan


def main():
    try:
        cur = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        cur = {}
    old = cur.get("funds", {}) if isinstance(cur, dict) else {}
    today = dt.date.today()
    funds, rejected = {}, []
    for code, (tur, kurucu, beklenen) in CANDIDATES.items():
        prev = old.get(code, {}).get("prices", {})
        prices = dict(prev)
        start = today - dt.timedelta(days=KEEP_DAYS)
        if prices:  # sadece eksik kısmı çek (son tarihten 10 gün geriden)
            start = max(start, dt.date.fromisoformat(max(prices)) - dt.timedelta(days=10))
        unvan = ""
        a = start
        while a <= today:
            b = min(a + dt.timedelta(days=27), today)
            got, u = tefas(code, a, b)
            unvan = unvan or u
            prices.update(got)
            a = b + dt.timedelta(days=1)
        # --- doğrulama ---
        if unvan:
            if "KATILIM" not in norm(unvan):
                rejected.append({"kod": code, "unvan": unvan, "neden": "TEFAS unvanında 'Katılım' yok"})
                log(f"{code}: REDDEDİLDİ, unvan '{unvan}'")
                continue
            blocked = [w for w in BLOCK_WORDS if norm(w) in norm(unvan)]
            if blocked:
                rejected.append({"kod": code, "unvan": unvan, "neden": "istenmeyen tür: " + ", ".join(blocked)})
                log(f"{code}: REDDEDİLDİ, tür {blocked}")
                continue
            dogrulama = "tefas"
        else:
            # Unvan alınamadı (ör. TEFAS ulaşılamadı): önceki doğrulamayı koru, yoksa aday listesindeki unvanla "liste"
            unvan = old.get(code, {}).get("unvan") or beklenen
            dogrulama = old.get(code, {}).get("dogrulama") or "liste"
        if not prices:
            log(f"{code}: fiyat yok, atlandı")
            continue
        cut = (today - dt.timedelta(days=KEEP_DAYS)).isoformat()
        prices = {k: v for k, v in prices.items() if k >= cut}
        funds[code] = {"unvan": unvan, "tur": tur, "kurucu": kurucu, "dogrulama": dogrulama,
                       "prices": dict(sorted(prices.items()))}
    if not funds and old:
        log("Hiç fon alınamadı; mevcut dosya korunuyor")
        return
    out = {"updated": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z", "funds": funds, "rejected": rejected, "log": LOG[-30:]}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"katılım: {len(funds)} fon, {len(rejected)} reddedildi")


if __name__ == "__main__":
    main()
