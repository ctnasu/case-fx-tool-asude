# tool.py İncelemesi

Bulgular, müşteriye verdiği zarara göre sıralı. Her biri kod okuyarak değil,
mock'lu (ağsız) bir upstream ile çalıştırarak doğrulandı.

## 1. Endpoint, brief'in belirttiği `from` ve `date` parametrelerini hiç kabul etmiyor

Python parametre adları `from_` ve `on`, ama `alias` tanımlanmamış. `from`
Python'da rezerve kelime olduğu için değişken `from_` yazılmış — doğru, ama
query string'de gerçekten `from` olarak kabul edilmesi için ek olarak
`Query(alias="from")` gerekir; bu adım atlanmış. Aynı şey tarih için de
geçerli: parametre `date` değil, `on`.

**Müşteriye etkisi:** Brief'in kendi örnek isteğiyle
(`?amount=250&from=USD&to=TRY&date=1999-01-04`) çağırdığımda, `from` ve
`date` sessizce yok sayıldı; yanıt `"from": "EUR"` ve bugünün tarihiyle
geldi — hata yok, 200 OK. Brief'te yazılan formatla çağıran hiç kimse
gerçekte istediği para birimini ya da tarihi alamıyor, hep "EUR'dan, en
güncel kur" cevabı alıyor.

**Doğrulama:** `TestClient` ile `from=USD&date=1999-01-04` gönderip
yanıtın bunları hiç yansıtmadığını gördüm.

## 2. Cache para birimi çiftine göre key'leniyor ama tarihe göre değil — bir kere cache'lenen kur sonsuza kadar donuyor

`_cache` key'i `f"{base}-{target}"`, tarih hiç yok. `EUR-TRY` bir kere
sorgulandıktan sonra, süreç ayakta kaldığı sürece **sonraki her istek**,
gerçek kur değişmiş olsa bile, ilk cache'lenen donmuş kuru döndürüyor —
`rate_date` da hep sorulan/bugünün tarihini yansıttığı için (upstream'in
gerçek `date` alanı hiç okunmuyor), bu donmuş kur her seferinde
"güncelmiş" gibi etiketleniyor.

**Müşteriye etkisi:** Sunucu günler/haftalarca ayakta kalırsa, TRY gibi
oynak bir para biriminde müşteriler çok sonra bile ilk günün kuruyla
işlem görür — sessizce, hatasız.

**Doğrulama:** Sahte upstream'de iki farklı tarih için iki farklı gerçek
kur simüle ettim (50.0 ve 56.17); ikinci çağrı, kendi sorduğum tarihe
etiketlenmiş halde, birincinin kuru olan 50.0'ı döndürdü.

## 3. Herhangi bir hata, sahte bir "başarılı" 200 yanıtına dönüşüyor

`except Exception` bloğu her türlü hatayı (geçersiz para birimi, upstream
çökmesi, JSON bozukluğu) yakalayıp `rate: 0.0, result: 0.0` ile 200 OK
dönüyor; tek iz sunucu konsoluna düşen bir `print()`.

**Müşteriye etkisi:** Sistem başarısız olduğunda bile müşteriye "250
EUR'un karşılığı 0.00" gibi sahte bir başarı gösteriliyor; gerçek bir hata
hiçbir zaman çağırana ulaşmıyor.

**Doğrulama:** Upstream'i "bad currency pair" (422) döndürecek şekilde
mock'ladım — `from == to` durumunda gerçek Frankfurter'ın verdiği yanıt
bu. `tool.convert(...)`'i doğrudan çağırdığımda `{'rate': 0.0, 'result':
0.0, ...}` ile 200 döndüğünü gördüm.

## 4. `date | None` sözdizimi, Python 3.10 öncesinde uygulamayı hiç başlatmıyor

`from __future__ import annotations` bunu çözmüyor, çünkü FastAPI route'u
kaydederken tip belirtimini gerçekten değerlendirmek zorunda kalıyor.

**Müşteriye etkisi:** Deployment ortamı Python 3.10'dan eskiyse, servis
hiç ayağa kalkmıyor.

**Doğrulama:** Part A'yı geliştirdiğim ortamdaki tek interpreter olan
Python 3.9'da doğrudan denedim — `import tool` anında `TypeError` ile
çöktü.

## Bu gece önce hangisini düzeltirdim

**1 numarayı.** En temel olanı bu — diğer üçü bile kısmen bunun gölgesinde
kalıyor (örneğin `on` zaten hiç gerçek bir değer almadığı için cache'in
tarih sorunu pratikte hep "latest" senaryosuna indirgeniyor). Düzeltmesi
de ucuz: `Query(alias="from")` ve `Query(alias="date")` eklemek birkaç
dakikalık bir değişiklik, ama brief'in kendi örnek isteğini bile çalışır
hale getiriyor.

4 numarayı (Python sürüm çökmesi) bilerek en sona koydum: brief'in kendi
mantığına göre — "yanlış sayı, sayı vermemekten kötüdür" — bir çökme en
azından sessizce yanlış bir rakam vermiyor; ilk üç bulgu ise tam olarak
bunu yapıyor.

## Şüpheli görünüp aslında sorunsuz olanlar

- `httpx.AsyncClient()` timeout'suz görünüyor ama varsayılan 5 saniyelik
  timeout'u var (doğruladım).
- `_cache: dict[str, float]` — `date | None` ile aynı "yeni sözdizimi"
  şüphesini uyandırabilir, ama `dict[str, float]` (PEP 585) Python 3.9'da
  da çalışıyor; sorun `|` operatörü (PEP 604), `dict[...]` değil
  (doğruladım).
