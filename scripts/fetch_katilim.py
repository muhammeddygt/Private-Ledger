#!/usr/bin/env python3
"""Faizsiz sekmesi için katılım fonlarının fiyatlarını TEFAS'tan çekip katilim-funds.json dosyasına yazar.

Güvenlik kuralı: bir fon listede ancak TEFAS'taki resmî unvanında "KATILIM" ibaresi geçiyorsa gösterilir
(SPK düzenlemesine göre unvanında "Katılım" geçen fonlar katılım finans ilkelerine uymak ve danışma
kurulu denetiminde olmak zorundadır). Unvanında bu ibare olmayan fon "rejected" listesine alınır, uygulamada görünmez.
TEFAS yanıtında unvan alanı hiç yoksa fon, aşağıdaki aday listesindeki unvanla "liste" doğrulamasıyla işaretlenir.
Türler: kira, hisse, altin, doviz, diger (karma/dengeli/teknoloji). Hisse/altın/döviz/karma dalgalıdır (uygulamada uyarı gösterilir)."""
import json, sys, time, datetime as dt, urllib.request

OUT = "katilim-funds.json"
KEEP_DAYS = 75          # saklanan fiyat geçmişi (günlük/aylık getiri için en az ~35 gün gerekir)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HOST = "https://www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetir"
HEAD = {"User-Agent": UA, "Content-Type": "application/json", "Accept": "*/*",
        "Origin": "https://www.tefas.gov.tr", "Referer": "https://www.tefas.gov.tr/tr/fon-verileri"}

# Aday listesi: kod: (tür, kurucu, beklenen unvan). Unvanda "Katılım" yoksa script fonu reddeder.
CANDIDATES = {
    # --- Kira sertifikası (TL) ---
    "VFK": ("kira", "Ziraat Portföy", "ZİRAAT PORTFÖY İKİNCİ KISA VADELİ KİRA SERTİFİKALARI KATILIM (TL) FONU"),
    "ZPG": ("kira", "Ziraat Portföy", "ZİRAAT PORTFÖY KİRA SERTİFİKALARI (SUKUK) KATILIM FONU"),
    "VKK": ("kira", "Vakıf Katılım Portföy", "VAKIF KATILIM PORTFÖY KİRA SERTİFİKALARI KATILIM FONU"),
    "VKV": ("kira", "Vakıf Katılım Portföy", "VAKIF KATILIM PORTFÖY KISA VADELİ KİRA SERTİFİKALARI KATILIM FONU"),
    "KTN": ("kira", "Kuveyt Türk Portföy", "KUVEYT TÜRK PORTFÖY KİRA SERTİFİKALARI KATILIM (TL) FONU"),
    "KTV": ("kira", "Kuveyt Türk Portföy", "KUVEYT TÜRK PORTFÖY KISA VADELİ KİRA SERTİFİKALARI KATILIM (TL) FONU"),
    "RBT": ("kira", "Albaraka Portföy", "ALBARAKA PORTFÖY KİRA SERTİFİKALARI KATILIM FONU"),
    "RBV": ("kira", "Albaraka Portföy", "ALBARAKA PORTFÖY KISA VADELİ KİRA SERTİFİKALARI KATILIM (TL) FONU"),
    # Para piyasası fonları (ZPO, VPA, KLU, PPG) bilerek yok: portföyleri ağırlıkla satım vaadiyle alım (taahhütlü işlem) ile tutuluyor.
    # --- Katılım hisse senedi fonları ---
    "ZPE": ("hisse", "Ziraat Portföy", "ZİRAAT PORTFÖY KATILIM HİSSE SENEDİ FONU (HİSSE SENEDİ YOĞUN FON)"),
    "VHS": ("hisse", "Vakıf Katılım Portföy", "VAKIF KATILIM PORTFÖY KATILIM HİSSE SENEDİ FONU (HİSSE SENEDİ YOĞUN FON)"),
    "KPC": ("hisse", "Kuveyt Türk Portföy", "KUVEYT TÜRK PORTFÖY KATILIM HİSSE SENEDİ (TL) FONU (HİSSE SENEDİ YOĞUN FON)"),
    "RBH": ("hisse", "Albaraka Portföy", "ALBARAKA PORTFÖY KATILIM HİSSE SENEDİ FONU (HİSSE SENEDİ YOĞUN FON)"),
    "TIL": ("hisse", "İş Portföy", "İŞ PORTFÖY KATILIM HİSSE SENEDİ (TL) FONU (HİSSE SENEDİ YOĞUN FON)"),
    "KH1": ("hisse", "AK Portföy", "AK PORTFÖY KATILIM HİSSE SENEDİ FONU (HİSSE SENEDİ YOĞUN FON)"),
    "GKV": ("hisse", "Garanti Portföy", "GARANTİ PORTFÖY KATILIM HİSSE SENEDİ (TL) FONU (HİSSE SENEDİ YOĞUN FON)"),
    "YHK": ("hisse", "Yapı Kredi Portföy", "YAPI KREDİ PORTFÖY KATILIM HİSSE SENEDİ FONU (HİSSE SENEDİ YOĞUN FON)"),
    # --- Altın katılım fonları ---
    "TCA": ("altin", "Ziraat Portföy", "ZİRAAT PORTFÖY ALTIN KATILIM FONU"),
    "VLT": ("altin", "Vakıf Katılım Portföy", "VAKIF KATILIM PORTFÖY ALTIN KATILIM FONU"),
    "KZL": ("altin", "Kuveyt Türk Portföy", "KUVEYT TÜRK PORTFÖY ALTIN KATILIM FONU"),
    "LKF": ("altin", "İş Portföy", "İŞ PORTFÖY ALTIN KATILIM FONU"),
    "GOL": ("altin", "Garanti Portföy", "GARANTİ PORTFÖY ALTIN KATILIM FONU"),
    "KCR": ("altin", "AK Portföy", "AK PORTFÖY KÜLÇE ALTIN KATILIM FONU"),
    # --- Döviz katılım fonları ---
    "ZPF": ("doviz", "Ziraat Portföy", "ZİRAAT PORTFÖY KATILIM FONU (DÖVİZ)"),
    "ZP6": ("doviz", "Ziraat Portföy", "ZİRAAT PORTFÖY SEDEF KATILIM SERBEST (DÖVİZ-AMERİKAN DOLARI) FON"),
    "ZP9": ("doviz", "Ziraat Portföy", "ZİRAAT PORTFÖY AKİK KATILIM SERBEST (DÖVİZ-AVRO) FON"),
    "KDL": ("doviz", "Kuveyt Türk Portföy", "KUVEYT TÜRK PORTFÖY BEŞİNCİ KATILIM SERBEST (DÖVİZ) FON"),
    "KTT": ("doviz", "Kuveyt Türk Portföy", "KUVEYT TÜRK PORTFÖY DÖRDÜNCÜ KATILIM SERBEST (DÖVİZ) FON"),
    "CKS": ("doviz", "İş Portföy", "İŞ PORTFÖY BİRİNCİ KATILIM SERBEST (DÖVİZ) FON"),
    # --- Karma / dengeli / teknoloji katılım fonları ---
    "ZBI": ("diger", "Ziraat Portföy", "ZİRAAT PORTFÖY TEMKİNLİ KATILIM FONU"),
    "ZCK": ("diger", "Ziraat Portföy", "ZİRAAT PORTFÖY AGRESİF KATILIM FONU"),
    "KDE": ("diger", "Kuveyt Türk Portföy", "KUVEYT TÜRK PORTFÖY DENGELİ KATILIM FONU"),
    "KCV": ("diger", "Kuveyt Türk Portföy", "KUVEYT TÜRK PORTFÖY ÇOKLU VARLIK KATILIM FONU"),
    "GPF": ("diger", "Garanti Portföy", "GARANTİ PORTFÖY ÇOKLU VARLIK KATILIM FONU"),
    "KTJ": ("diger", "Kuveyt Türk Portföy", "KUVEYT TÜRK PORTFÖY TEKNOLOJİ KATILIM FONU"),
}
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
    rows = None
    for attempt in range(5):            # TEFAS hız sınırı (429) / zaman aşımı: bekleyip yeniden dene
        time.sleep(2.5 if attempt == 0 else 8 * attempt)
        try:
            req = urllib.request.Request(HOST, data=body, headers=HEAD, method="POST")
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = r.read().decode("utf-8", "replace")
            data = json.loads(raw)
            rows = (data.get("resultList") or []) if isinstance(data, dict) else data
            break
        except Exception as e:
            if attempt == 4:
                log(f"{code}: TEFAS {type(e).__name__} {getattr(e, 'code', '')} {str(e)[:80]}")
    if rows is None:
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
        # Geçmiş yeterliyse sadece eksik kısmı çek (son tarihten 10 gün geriden); kısaysa (30 günlük getiri için) baştan çek
        if prices and dt.date.fromisoformat(min(prices)) <= today - dt.timedelta(days=60):
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
