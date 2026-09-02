# Notlar

## Kararlar

ECB'nin sorulan tarih için kur yayınlamadığı durumda ne olacağı, iki farklı
senaryoya ayrılıyor:

- **Hafta sonu/tatil**: hata değil. Frankfurter'ın bunu kendi çözdüğünü
  canlı doğruladım (bir Cumartesi sorulduğunda Cuma'nın kuru dönüyor, `date`
  alanı Cuma olarak set ediliyor) — endpoint bunu okuyup `asked_date`'in
  yanında `rate_date` olarak sunuyor.
- **Gelecek tarih / seri başlangıcından önce / bilinmeyen para birimi**:
  upstream'e gitmeden reddediliyor. Canlı doğruladım ki upstream üçü için
  de aynı 404'ü döndürüyor, yani bunu olduğu gibi geçirmek güvenli değil —
  para birimi ve tarih aralığı önce bilinen-geçerli değerlere göre kontrol
  ediliyor.

Ayrıca: `amount`, `Decimal` olarak parse edilip çarpılıyor, `float` değil —
müşteriye söylenen bir rakamda binary-rounding hatası olmamalı. Cache,
`(from, to, asked_date)` ile key'leniyor ve sürecin ömrü boyunca tutuluyor;
aynı (henüz cache'lenmemiş) key'e gelen eşzamanlı istekler tek bir
`asyncio.Lock` paylaşıyor, böylece cache senkronize olmayan paylaşılan bir
state haline gelmiyor — bitirme projemdeki paylaşılan mutable state
sorunuyla aynı türden bir mesele, sadece daha küçük ölçekte. Bu ortamda
mevcut tek interpreter olan Python 3.9 üzerinde geliştirildi.

## Bir gün daha olsaydı

- "Bugün" sorguları için gerçek bir TTL — ECB günün ortasında bir kere
  yayın yapıyor, yani yayından önce cache'lenen bir cevap yayından sonra da
  kullanılabilir. Takvim günü bazlı bir kontrol bunu yakalamıyor (aşağıya
  bak), kısa bir wall-clock TTL yakalardı, ama ECB'nin tam yayın saatini
  tahmin etmek istemedim.
- Para birimine özel yuvarlama — şu an herkesi 2 ondalığa yuvarlıyorum, ama
  JPY/HUF gerçekte sıfır ondalıklı.
- Temel structured logging, ve `amount` parse için property-based testler.

## AI araçları

Baştan sona Claude Code — iskelet kurma ve kendi validasyon mantığıma
ikinci bir göz olarak. Bu mantığı yazmadan önce, brief'teki her edge case
için gerçek Frankfurter API'sine canlı `curl` attım, davranışını
dokümantasyondan varsaymak yerine gerçekte ne döndüğüne göre kod yazdım.

## AI'ın yanlış yaptığı bir şey

İlk cache versiyonu, `cached_on` diye bir alan tutarak "bugün"ün kaydını
gün değişince eskitmeye çalışıyordu. Cache için doğrudan bir test yazmak,
bu kontrolün ne zaman gerçekten tetiklenebileceğini takip etmemi
gerektirdi — hiçbir zaman tetiklenemiyordu: sadece `asked_date == today`
olduğunda kontrol ediliyordu, ve yazma anında bu her zaman doğru olduğu
için karşılaştırma da her zaman doğru çıkıyordu. Bir tarih "bugün" olmaktan
çıktığı anda geçmiş olarak işlem görüyor ve kontrol hiç çalışmadan kısa
devre yapıyor. Yamamak yerine kaldırdım, ve gerçek eksikliği sessizce atmak
yerine yukarıda yazılı bıraktım.

Ayrıca, gerçek bir bug: `RateCache.__init__` içinde `asyncio.Lock()`
oluşturmak, Python 3.9'da bir test ikinci kez `asyncio.run()` çağırdığı
anda bozuluyordu. Testleri çalıştırınca yakaladım, lock'ları async metodun
içinde tembel (lazy) oluşturarak düzelttim.
