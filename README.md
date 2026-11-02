# İlmek — Malzemenin ikinci hikâyesi

Tekstil üretiminden kalan kumaşları, bu malzemeleri kullanabilecek tasarımcı ve atölyelerin ihtiyaçlarıyla eşleştiren Türkçe bir web uygulaması.

**Python 3.11+ · SQLite · Vanilla JavaScript · Harici bağımlılık yok**

## Hızlı başlangıç

```bash
git clone https://github.com/Cihan-Aygun/ilmek.git
cd ilmek
python3 app.py
```

Tarayıcıda **http://127.0.0.1:8000** adresini açın. İlk çalıştırmada altı kurgusal malzeme ilanı ve üç talep eklenir. Sonraki değişiklikler `data/ilmek.db` dosyasında kalıcıdır.

```bash
# Farklı port
python3 app.py --port 8080
# Örnek verisiz, ayrı veritabanı
python3 app.py --empty --db data/atolye.db
# Testler
python3 -m unittest discover -s tests -v
```

## Neler yapılabilir?

- **Malzeme pazarı:** kumaş içeriği, renk, gramaj, parça türü, şehir, miktar ve kilogram fiyatı ile ilan oluşturma; arama ve filtreleme.
- **İhtiyaç talepleri:** proje, atölye, malzeme, renk, miktar ve azami birim bütçe tanımlama.
- **Açıklanabilir eşleştirme:** zorunlu uyum koşulları ve puan gerekçeleriyle uygun ilan/talep çiftlerini sıralama.
- **Kısmi rezervasyon:** uygun stoktan ihtiyaç kadar ayırma; hem stoğun hem kalan talebin aynı işlemde güncellenmesi.
- **Teslimat ve iptal:** teslimatı tamamlayarak yeniden kullanım raporuna işleme; iptalde stoğu ve talep kapasitesini geri açma.
- **Döngü raporu:** malzeme bazlı teslim edilen kilogram, işlem sayısı, CSV dışa aktarımı ve hareket günlüğü.

## 2 dakikalık demo

1. Malzeme pazarında **Pamuk** filtresini seçin, ekru pamuk ilanını inceleyin.
2. **Eşleştirmeler** bölümünde bez çanta talebiyle eşleşen ilanı bulun.
3. **Malzemeyi ayır** ile 25 kg rezervasyon oluşturun.
4. **Rezervasyonlar** bölümünden teslimatı tamamlayın.
5. **Döngü raporu** bölümünde 25 kg pamuk yeniden kullanımını görün ve CSV indirin.
6. Başka bir rezervasyonu iptal ederek stok miktarının geri geldiğini kontrol edin.

## Eşleştirme nasıl çalışır?

Malzeme birebir aynı olmalı; renk aynı olmalı veya talepte “Fark etmez” seçilmeli. İlanın kilogram fiyatı talebin azami birim bütçesini aşamaz. Kullanılabilir stok ve kalan ihtiyaç sıfırdan büyük olmalıdır.

```text
Puan = 50 + 30 × min(kullanılabilir stok / kalan ihtiyaç, 1)
          + (aynı şehir ise 20)
```

Bu puan bir öneri sıralamasıdır; olasılık veya çevresel performans ölçümü değildir. Şehirler arası seçenekler kabul edilir, kargo dahil değildir. Her eşleşme bağımsız bir alternatiftir; rezervasyonlar sonrasında seçenekler yeniden hesaplanır.

## Veri tutarlılığı

Miktarlar tam sayı gram, fiyatlar tam sayı kuruş olarak saklanır. Rezervasyon ve durum geçişleri SQLite `BEGIN IMMEDIATE` işlemleriyle yapılır; eşzamanlı istekler aynı stoğu veya talep kapasitesini aşamaz. Tamamlanmış/iptal edilmiş rezervasyonlar tekrar değiştirilemez. CSV tutarları rezervasyon anındaki fiyatı kullanır.

## Mimari

```text
app.py                  HTTP API, iş kuralları, SQLite, demo verileri
static/index.html       Erişilebilir Türkçe uygulama kabuğu
static/style.css        Duyarlı tasarım ve temsili kumaş dokuları
static/app.js           Ekranlar, formlar, filtreleme ve API bağlantısı
tests/test_app.py       İş kuralları, eşzamanlılık ve HTTP testleri
docs/API.md             Uç noktalar ve istek örnekleri
docs/ROADMAP.md         Üretim sürümüne geçiş planı
.github/workflows/      Python sürümleriyle otomatik test
```

## Kapsam ve sınırlar

Bu sürüm **tek kullanıcılı yerel prototiptir**. Kimlik doğrulama, firma yetkilendirmesi, ödeme, gerçek mesajlaşma, fotoğraf yükleme, lojistik ve sertifika doğrulaması içermez. Sunucu yalnızca `127.0.0.1` üzerinde dinler; internete açık üretim sunucusu olarak kullanılmamalıdır. Paylaşılan bir servis için [yol haritasındaki](docs/ROADMAP.md) erişim ve dağıtım gereksinimleri uygulanmalıdır.

Başlangıç firmaları ve kayıtlar kurgusaldır. Kumaş görselleri CSS ile çizilmiş temsili dokulardır. Raporlar teslim edilen kilogramı ölçer; karbon/su tasarrufu ya da doğrulanmış sürdürülebilirlik sertifikası iddiası içermez. İlan içeriği satıcı beyanıdır. Para tutarları örnek kayıt değerleridir; ticari teklif değildir.

## Lisans

[MIT](LICENSE)
