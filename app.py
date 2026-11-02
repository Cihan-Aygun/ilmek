"""İlmek — dependency-free, local textile circularity prototype."""
import argparse
import csv
import io
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
MATERIALS = ['Pamuk', 'Keten', 'Denim', 'Viskon', 'Polyester', 'Yün']
COLORS = ['Ekru', 'Mavi', 'Siyah', 'Yeşil', 'Karışık']
CITIES = ['İstanbul', 'Bursa', 'Denizli', 'İzmir', 'Gaziantep', 'Ankara']
KINDS = ['Top sonu', 'Kesim artığı', 'Numune kumaş']


class DomainError(ValueError):
    pass


def number(value, label, scale=1, allow_zero=False):
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n < 0 or (not allow_zero and n == 0) or n > 1000000:
            raise InvalidOperation
        scaled = n * scale
        if scaled != scaled.to_integral_value():
            raise InvalidOperation
        return int(scaled)
    except (InvalidOperation, ValueError, TypeError):
        raise DomainError(f'{label}: geçerli bir pozitif sayı girin; en fazla {scale} ölçek hassasiyeti.')


def text(data, key, maximum=120):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise DomainError(f'{key}: 1–{maximum} karakter gerekli.')
    return value.strip()


def choice(data, key, values):
    value = data.get(key)
    if value not in values:
        raise DomainError(f'{key}: desteklenmeyen değer.')
    return value


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS listings (
              id INTEGER PRIMARY KEY, title TEXT NOT NULL, organization TEXT NOT NULL,
              material TEXT NOT NULL, color TEXT NOT NULL, city TEXT NOT NULL,
              kind TEXT NOT NULL, grams INTEGER NOT NULL CHECK(grams>=0),
              price INTEGER NOT NULL CHECK(price>=0), gsm INTEGER NOT NULL,
              composition TEXT NOT NULL, description TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS requests (
              id INTEGER PRIMARY KEY, title TEXT NOT NULL, organization TEXT NOT NULL,
              material TEXT NOT NULL, color TEXT NOT NULL, city TEXT NOT NULL,
              grams INTEGER NOT NULL CHECK(grams>0), budget INTEGER NOT NULL CHECK(budget>=0),
              created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reservations (
              id INTEGER PRIMARY KEY, listing_id INTEGER NOT NULL REFERENCES listings(id),
              request_id INTEGER NOT NULL REFERENCES requests(id), grams INTEGER NOT NULL CHECK(grams>0),
              price INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('reserved','completed','cancelled')),
              created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY, action TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat(timespec='seconds')

    def event(self, db, action, detail):
        db.execute('INSERT INTO events(action,detail,created_at) VALUES (?,?,?)', (action, detail, self.now()))

    def add_listing(self, data):
        values = [text(data, 'title'), text(data, 'organization'), choice(data, 'material', MATERIALS),
                  choice(data, 'color', COLORS), choice(data, 'city', CITIES), choice(data, 'kind', KINDS),
                  number(data.get('kg'), 'Miktar', 1000), number(data.get('price'), 'Fiyat', 100, True),
                  number(data.get('gsm'), 'Gramaj'), text(data, 'composition'), text(data, 'description', 1000), self.now()]
        with self.connection() as db:
            key = db.execute('INSERT INTO listings(title,organization,material,color,city,kind,grams,price,gsm,composition,description,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', values).lastrowid
            self.event(db, 'İlan', values[0])
        return {'id': key}

    def add_request(self, data):
        values = [text(data, 'title'), text(data, 'organization'), choice(data, 'material', MATERIALS),
                  choice(data, 'color', COLORS + ['Fark etmez']), choice(data, 'city', CITIES),
                  number(data.get('kg'), 'Miktar', 1000), number(data.get('budget'), 'Bütçe', 100, True), self.now()]
        with self.connection() as db:
            key = db.execute('INSERT INTO requests(title,organization,material,color,city,grams,budget,created_at) VALUES (?,?,?,?,?,?,?,?)', values).lastrowid
            self.event(db, 'Talep', values[0])
        return {'id': key}

    def reserve(self, data):
        listing_id = number(data.get('listing_id'), 'İlan ID')
        request_id = number(data.get('request_id'), 'Talep ID')
        grams = number(data.get('kg'), 'Miktar', 1000)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            listing = db.execute('SELECT * FROM listings WHERE id=?', (listing_id,)).fetchone()
            request = db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
            if not listing or not request:
                raise DomainError('İlan veya talep bulunamadı.')
            committed = db.execute("SELECT COALESCE(SUM(grams),0) FROM reservations WHERE request_id=? AND status!='cancelled'", (request_id,)).fetchone()[0]
            if grams > listing['grams'] or grams > request['grams'] - committed:
                raise DomainError('Kullanılabilir stok veya kalan talep miktarı yetersiz.')
            if listing['material'] != request['material'] or request['color'] not in ['Fark etmez', listing['color']]:
                raise DomainError('Malzeme veya renk talep ile uyuşmuyor.')
            if listing['price'] > request['budget']:
                raise DomainError('Birim fiyat talep bütçesini aşıyor.')
            db.execute('UPDATE listings SET grams=grams-? WHERE id=?', (grams, listing_id))
            key = db.execute("INSERT INTO reservations(listing_id,request_id,grams,price,status,created_at) VALUES (?,?,?,?,'reserved',?)", (listing_id, request_id, grams, listing['price'], self.now())).lastrowid
            self.event(db, 'Rezervasyon', f"{listing['title']} · {grams / 1000:g} kg")
        return {'id': key}

    def transition(self, data):
        key = number(data.get('id'), 'Rezervasyon ID')
        status = choice(data, 'status', ['completed', 'cancelled'])
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM reservations WHERE id=?', (key,)).fetchone()
            if not row or row['status'] != 'reserved':
                raise DomainError('Yalnızca bekleyen rezervasyon güncellenebilir.')
            if status == 'cancelled':
                db.execute('UPDATE listings SET grams=grams+? WHERE id=?', (row['grams'], row['listing_id']))
            db.execute('UPDATE reservations SET status=? WHERE id=?', (status, key))
            self.event(db, 'Teslimat' if status == 'completed' else 'İptal', f"Rezervasyon #{key} · {row['grams']/1000:g} kg")
        return {'id': key, 'status': status}

    def state(self):
        with self.connection() as db:
            listings = [dict(x) for x in db.execute('SELECT * FROM listings ORDER BY id DESC')]
            requests = [dict(x) for x in db.execute("SELECT r.*, r.grams-COALESCE((SELECT SUM(grams) FROM reservations WHERE request_id=r.id AND status!='cancelled'),0) AS remaining FROM requests r ORDER BY id DESC")]
            reservations = [dict(x) for x in db.execute('SELECT r.*,l.title,l.material,l.color,q.organization AS buyer FROM reservations r JOIN listings l ON l.id=r.listing_id JOIN requests q ON q.id=r.request_id ORDER BY r.id DESC')]
            events = [dict(x) for x in db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 15')]
        matches = []
        for request in requests:
            for listing in listings:
                if request['remaining'] <= 0 or listing['grams'] <= 0 or listing['material'] != request['material']:
                    continue
                if request['color'] not in ['Fark etmez', listing['color']] or listing['price'] > request['budget']:
                    continue
                coverage = min(listing['grams'] / request['remaining'], 1)
                same_city = listing['city'] == request['city']
                score = round(50 + coverage * 30 + (20 if same_city else 0))
                matches.append({'listing_id': listing['id'], 'request_id': request['id'], 'grams': min(listing['grams'], request['remaining']), 'score': score, 'reasons': ['Malzeme ve renk uyumlu', f'Talebin %{round(coverage*100)} karşılanabilir', 'Aynı şehir' if same_city else 'Şehirler arası teslimat', 'Bütçe içinde']})
        return {'listings': listings, 'requests': requests, 'reservations': reservations, 'events': events,
                'matches': sorted(matches, key=lambda x: (-x['score'], x['listing_id'], x['request_id'])),
                'options': {'material': MATERIALS, 'color': COLORS, 'city': CITIES, 'kind': KINDS}}

    def seed(self):
        with self.connection() as db:
            if db.execute('SELECT COUNT(*) FROM listings').fetchone()[0]:
                return
        samples = [
            ('Ekru pamuk dokuma', 'Marmara Dokuma · Demo', 'Pamuk', 'Ekru', 'Bursa', 'Top sonu', 240, 32, 180, '%100 pamuk', 'Çanta ve aksesuar üretimine uygun. 120–150 cm en; 3–12 metre arası parçalar.'),
            ('İndigo denim parçaları', 'Ege Denim · Demo', 'Denim', 'Mavi', 'İzmir', 'Kesim artığı', 185, 24, 320, '%98 pamuk, %2 elastan', 'Patchwork ve ileri dönüşüm koleksiyonları için ayrıştırılmış kesim artıkları.'),
            ('Doğal keten numuneler', 'Lif Atölye · Demo', 'Keten', 'Ekru', 'İstanbul', 'Numune kumaş', 62, 55, 210, '%100 keten', 'Ev tekstili ve küçük aksesuarlar için 40–80 cm numune parçaları.'),
            ('Siyah viskon top sonu', 'Güney Tekstil · Demo', 'Viskon', 'Siyah', 'Denizli', 'Top sonu', 120, 28, 140, '%100 viskon', 'Hafif ve dökümlü dokuma. 140 cm en; her parça en az 4 metre.'),
            ('Adaçayı pamuk süprem', 'Yeşil İplik · Demo', 'Pamuk', 'Yeşil', 'İstanbul', 'Kesim artığı', 90, 18, 160, '%100 pamuk', 'Renge göre ayrılmış örme parçalar. Oyuncak dolgusu ve aksesuar için uygun.'),
            ('Karışık yün seçkisi', 'Anadolu Yün · Demo', 'Yün', 'Karışık', 'Ankara', 'Numune kumaş', 45, 42, 280, '%80 yün, %20 polyester', 'Dokulu numune kartelaları. Renkler karışık; küçük el işi projeleri için.')]
        for row in samples:
            self.add_listing(dict(zip(['title','organization','material','color','city','kind','kg','price','gsm','composition','description'], row)))
        for row in [('Bez çanta koleksiyonu', 'Döngü Tasarım · Demo', 'Pamuk', 'Ekru', 'Bursa', 100, 40), ('Denim aksesuar serisi', 'Yama Stüdyo · Demo', 'Denim', 'Mavi', 'İstanbul', 80, 30), ('Doğal ev tekstili', 'Kök Tasarım · Demo', 'Keten', 'Fark etmez', 'İstanbul', 40, 60)]:
            self.add_request(dict(zip(['title','organization','material','color','city','kg','budget'], row)))


def make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body, content_type='application/json; charset=utf-8'):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/api/state':
                return self.send(200, store.state())
            if path == '/api/report.csv':
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(['Rezervasyon','Malzeme','Miktar (kg)','Tutar (TL)','Durum'])
                for r in store.state()['reservations']:
                    writer.writerow([r['id'], r['material'], r['grams']/1000, round(r['price']*r['grams']/100000, 2), r['status']])
                return self.send(200, '\ufeff'+output.getvalue(), 'text/csv; charset=utf-8')
            files = {'/': ('index.html','text/html'), '/app.js': ('app.js','text/javascript'), '/style.css': ('style.css','text/css')}
            if path not in files:
                return self.send(404, {'error': 'Bulunamadı.'})
            name, mime = files[path]
            self.send(200, (ROOT/'static'/name).read_bytes(), mime+'; charset=utf-8')

        def do_POST(self):
            # Local demo: reject cross-origin form/fetch writes and DNS rebinding.
            host = self.headers.get('Host', '')
            origin = self.headers.get('Origin')
            if host not in [f'localhost:{self.server.server_port}', f'127.0.0.1:{self.server.server_port}'] or (origin and origin not in [f'http://{host}']):
                return self.send(403, {'error': 'Kaynak adresi reddedildi.'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send(415, {'error': 'JSON gerekli.'})
            routes = {'/api/listings': store.add_listing, '/api/requests': store.add_request,
                      '/api/reservations': store.reserve, '/api/reservations/status': store.transition}
            path = urlsplit(self.path).path
            if path not in routes:
                return self.send(404, {'error': 'Bulunamadı.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384:
                    raise DomainError('İstek boyutu geçersiz.')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise DomainError('JSON nesnesi gerekli.')
                self.send(201, routes[path](data))
            except (ValueError, UnicodeError) as exc:
                self.send(400, {'error': str(exc) if isinstance(exc, DomainError) else 'Geçersiz istek.'})
            except sqlite3.Error:
                self.send(503, {'error': 'Veritabanı işlemi tamamlanamadı. Tekrar deneyin.'})

    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='İlmek yerel demo sunucusu')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--db', default=str(ROOT/'data'/'ilmek.db'))
    parser.add_argument('--empty', action='store_true', help='Örnek veri ekleme')
    args = parser.parse_args()
    store = Store(args.db)
    if not args.empty:
        store.seed()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(store))
    print(f'İlmek hazır: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
