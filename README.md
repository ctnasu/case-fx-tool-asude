# fx-tool

Bir AI agent'ının çağırabileceği, döviz çevirisi yapan küçük bir HTTP servisi;
[Frankfurter](https://frankfurter.dev) üzerinden ECB referans kurlarını
kullanıyor.

## Çalıştırma

```
pip install -r requirements.txt
./run.sh
```

`$PORT` üzerinden dinler (varsayılan `8080`). Upstream base URL'i
`$FX_UPSTREAM_BASE`'den okur (varsayılan `https://api.frankfurter.dev`) —
kodun hiçbir yerinde gerçek host hardcode edilmiyor.

Python 3.9 üzerinde test edildi (bu ortamda mevcut tek interpreter);
kodun daha yeni bir sürüme ihtiyacı yok.

## Test etme

```
pip install -r requirements.txt
./test.sh
```

Ağ bağlantısı gerektirmiyor. Her testte upstream HTTP client'ı
`httpx.MockTransport` ile değiştiriliyor, yani `FX_UPSTREAM_BASE` kapalı bir
porta işaret etse de testlerin sonucu değişmiyor.

## Endpoint

```
GET /tools/convert?amount=250&from=EUR&to=TRY&date=2026-08-28
```

`date` opsiyonel; verilmezse bugüne (UTC) düşer.

**Başarılı — 200:**

```json
{
  "amount": 250.0,
  "from": "EUR",
  "to": "TRY",
  "rate": 47.1234,
  "result": 11780.85,
  "rate_date": "2026-08-28",
  "asked_date": "2026-08-28",
  "source": "ECB via frankfurter.dev"
}
```

`rate_date`, kurun gerçekte ait olduğu tarih. `asked_date`, sorulan tarih.
Hafta sonu/tatil günlerinde bu ikisi farklı olabilir — aşağıda detaylı.

**Hata — 2xx dışı her durum:**

```json
{ "error": "<kod>", "message": "<okunabilir bir cümle>" }
```

## Hata kodları

| kod | HTTP | ne zaman |
|---|---|---|
| `invalid_amount` | 400 | eksik, sayı değil, ≤ 0, veya 2'den fazla ondalık basamak |
| `invalid_currency` | 400 | `from`/`to` eksik, veya ECB'nin yayınladığı ~30 para biriminden biri değil |
| `invalid_date` | 400 | `date` geçerli bir `YYYY-MM-DD` değil |
| `future_date` | 400 | `date` bugünden ileri — ECB henüz o tarih için kur yayınlamış olamaz |
| `date_before_series_start` | 400 | `date`, euro referans serisinin başladığı 1999-01-04'ten önce |
| `no_rate_available` | 404 | tüm girdiler geçerli, ama upstream yine de o çift/tarih için kur döndürmedi |
| `upstream_unavailable` | 502 | upstream timeout verdi, 2xx dışı bir status döndürdü, ya da JSON olmayan bir şey döndürdü |
| `internal_error` | 500 | beklenmedik bir hata — normalde olmamalı |

## Brief'teki her senaryoda ne oluyor

- **Hafta sonu / tatil** — reddedilmiyor. Frankfurter isteği zaten en son
  yayınlanan iş gününe çözüyor ve hangi tarih olduğunu bildiriyor; endpoint
  bunu okuyup `asked_date`'ten ayrı olarak `rate_date` olarak döndürüyor.
  Canlı doğrulandı: bir Cumartesi sorulduğunda, response'daki `date` alanı
  Cuma olarak dönüyor.
- **Gelecek tarih** — upstream'e hiç gitmeden reddediliyor (`future_date`);
  henüz var olmayan bir kur asla tahmin edilmiyor.
- **Seri başlangıcından önce** — upstream'e gitmeden reddediliyor
  (`date_before_series_start`).
- **Bilinmeyen para birimi kodu** — upstream'e gitmeden reddediliyor
  (`invalid_currency`), Frankfurter/ECB'nin gerçekten yayınladığı para
  birimlerinin sabit bir listesine göre kontrol ediliyor. Upstream'in kendi
  404'ü, "bilinmeyen para birimi" ile "bu tarih için veri yok" ve "gelecek
  tarih" arasında ayrım yapmıyor (canlı doğrulandı — üçü de aynı
  `{"message": "not found"}`'ı döndürüyor), o yüzden bu ayrımı kendimiz
  yapıyoruz.
- **`from == to`** — upstream'e hiç gidilmiyor; direkt `rate: 1.0` ve
  `result == amount` dönüyor. (Frankfurter'ın kendi API'si bu durumda 422
  "bad currency pair" döndürüyor — canlı doğrulandı — bu da bunu doğrudan
  geçirmek yerine kısa devre yapmak için bir sebep daha.)
- **Upstream yavaş / 500 / JSON değil** — her biri ayrı ayrı yakalanıp
  `upstream_unavailable` (502) olarak raporlanıyor. Asla bir sayı
  uydurulmuyor.
- **`amount` eksik / sıfır / negatif / çok ondalıklı** — upstream'e gitmeden
  `invalid_amount` olarak reddediliyor. "Çok ondalıklı" 2 basamaktan fazlası
  demek.

## Tasarım notları (kısa versiyon — "neden"i için NOTES.md'ye bak)

- `amount`, `Decimal` olarak parse edilip çarpılıyor, asla `float` değil —
  böylece müşteriye söylenen sayıya binary-rounding hatası karışmıyor.
- Kur cache'i in-memory, `(from, to, asked_date)` ile key'leniyor, sürecin
  ömrü boyunca tutuluyor — geçmiş bir kur asla değişmediği için. Aynı (henüz
  cache'lenmemiş) key'e gelen eşzamanlı istekler tek bir lock paylaşıyor,
  hepsi ayrı ayrı upstream'e gitmiyor (`app/cache.py`).
- Bilinçli olarak eklenmedi (brief'e göre): auth, database, UI, Docker, CI,
  ekstra endpoint.
