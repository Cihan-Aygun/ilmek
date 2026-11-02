# HTTP API

Yerel taban adresi: `http://127.0.0.1:8000`. Tüm yazma isteklerinde `Content-Type: application/json` gerekir. Başarılı yazma `201`, doğrulama hatası `400`, kaynak kontrolü hatası `403`, desteklenmeyen içerik `415`, bulunamayan yol `404` döner. Hatalar `{"error":"Açıklama"}` biçimindedir.

| Metot | Yol | İşlev |
|---|---|---|
| GET | `/api/state` | İlanlar, talepler, rezervasyonlar, eşleştirmeler, seçenekler, son 15 hareket |
| POST | `/api/listings` | İlan oluştur |
| POST | `/api/requests` | Talep oluştur |
| POST | `/api/reservations` | Stok ve talep kapasitesinden ayır |
| POST | `/api/reservations/status` | Teslim et veya iptal et |
| GET | `/api/report.csv` | Tüm rezervasyon durumlarını içeren UTF-8 BOM CSV |

## İlan oluşturma

```json
{
  "title": "Ekru pamuk parçaları",
  "organization": "Örnek Atölye",
  "material": "Pamuk",
  "color": "Ekru",
  "city": "Bursa",
  "kind": "Kesim artığı",
  "kg": "75.500",
  "price": "25.00",
  "gsm": 180,
  "composition": "%100 pamuk",
  "description": "40–80 cm parçalar, alıcı teslim alır."
}
```

## Talep oluşturma

```json
{
  "title": "Bez çanta projesi",
  "organization": "Örnek Tasarımcı",
  "material": "Pamuk",
  "color": "Fark etmez",
  "city": "Bursa",
  "kg": "20",
  "budget": "30"
}
```

`kg` en çok üç ondalık, `price`/`budget` en çok iki ondalık kabul eder. Gramaj tam sayıdır. Fiyat ve bütçe sıfır olabilir; miktar ve gramaj pozitif olmalıdır. Sayısal giriş üst sınırı 1.000.000'dur. Enum değerleri `/api/state` içindeki `options` alanından alınır. Talep renginde ayrıca `Fark etmez` kabul edilir.

## Rezervasyon

```json
{"listing_id": 1, "request_id": 1, "kg": "25.125"}
```

Yanıt: `{"id":1}`. Yetersiz stok, aşılmış talep, renk/malzeme uyuşmazlığı veya birim bütçe aşımı hata döner; kısmi yazma yapılmaz.

## Durum geçişi

```json
{"id": 1, "status": "completed"}
```

`reserved → completed` ve `reserved → cancelled` geçerlidir. İptal, ayrılan miktarı stoğa iade eder. Son durumlar değiştirilemez.

`state` yanıtındaki `grams`/`remaining` gram, `price`/`budget` kuruştur. Tarihler UTC ISO 8601 biçimindedir. CSV tutarı TL'dir ve rezervasyon fiyatı × kilogram olarak hesaplanır. CSV tüm durumları kapsar; yeniden kullanım analizinde yalnızca `completed` satırlarını kullanın.
