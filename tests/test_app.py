import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from pathlib import Path
from http.server import ThreadingHTTPServer

from app import DomainError, Store, make_handler


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name)/'test.db')
        self.store.seed()

    def reserve(self, amount=25, lid=1, rid=1):
        return self.store.reserve({'listing_id': lid, 'request_id': rid, 'kg': amount})

    def test_seed_is_idempotent(self):
        self.store.seed()
        self.assertEqual(len(self.store.state()['listings']), 6)

    def test_matching_explains_and_orders_scores(self):
        state = self.store.state()
        match = next(x for x in state['matches'] if x['listing_id']==1 and x['request_id']==1)
        self.assertEqual(match['score'], 100)
        self.assertEqual(match['grams'], 100000)
        self.assertEqual(len(match['reasons']), 4)

    def test_reserve_cancel_restores_stock_and_demand(self):
        key = self.reserve()['id']
        state = self.store.state()
        self.assertEqual(next(x for x in state['listings'] if x['id']==1)['grams'], 215000)
        self.assertEqual(next(x for x in state['requests'] if x['id']==1)['remaining'], 75000)
        self.store.transition({'id': key, 'status':'cancelled'})
        state = self.store.state()
        self.assertEqual(next(x for x in state['listings'] if x['id']==1)['grams'], 240000)
        self.assertEqual(next(x for x in state['requests'] if x['id']==1)['remaining'], 100000)

    def test_completed_is_terminal(self):
        key = self.reserve()['id']
        self.store.transition({'id':key,'status':'completed'})
        with self.assertRaises(DomainError):
            self.store.transition({'id':key,'status':'cancelled'})
        self.assertEqual(self.store.state()['reservations'][0]['status'],'completed')

    def test_rejects_overbooking_and_rolls_back(self):
        self.reserve(80)
        with self.assertRaises(DomainError):
            self.reserve(30)
        self.assertEqual(len(self.store.state()['reservations']),1)

    def test_concurrent_reservations_cannot_overbook(self):
        def reserve():
            try:
                self.reserve(70)
                return True
            except DomainError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(lambda _:reserve(), range(2))),[False,True])
        self.assertEqual(self.store.state()['reservations'][0]['grams'],70000)

    def test_rejects_incompatible_material(self):
        with self.assertRaises(DomainError):
            self.reserve(1, lid=2, rid=1)

    def test_rejects_color_mismatch(self):
        with self.assertRaises(DomainError):
            self.reserve(1, lid=5, rid=1)

    def test_rejects_over_budget(self):
        with self.store.connection() as db:
            db.execute('UPDATE requests SET budget=100 WHERE id=1')
        with self.assertRaises(DomainError):
            self.reserve(1)
        self.assertFalse(any(x['request_id']==1 for x in self.store.state()['matches']))

    def test_invalid_quantities(self):
        for value in [0,-1,'NaN','Infinity','0.0001',None,True,[],1000001]:
            with self.subTest(value=value),self.assertRaises(DomainError):
                self.reserve(value)

    def test_grams_are_exact(self):
        self.reserve('0.001')
        self.assertEqual(self.store.state()['reservations'][0]['grams'],1)

    def test_full_demand_removed_from_matches(self):
        self.reserve(100)
        self.assertFalse(any(x['request_id']==1 for x in self.store.state()['matches']))

    def test_state_survives_reopen(self):
        self.reserve(12)
        self.assertEqual(len(Store(self.store.path).state()['reservations']),1)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.store = Store(Path(cls.temp.name)/'api.db')
        cls.store.seed()
        cls.server = ThreadingHTTPServer(('127.0.0.1',0),make_handler(cls.store))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def call(self,path,method='GET',data=None,extra=None):
        connection=HTTPConnection('127.0.0.1',self.server.server_port)
        headers={'Content-Type':'application/json'}
        headers.update(extra or {})
        connection.request(method,path,json.dumps(data) if data is not None else None,headers)
        response=connection.getresponse()
        body=response.read()
        status=response.status
        connection.close()
        return status,body

    def test_static_and_api(self):
        for path in ['/','/app.js','/style.css','/api/state','/api/report.csv']:
            self.assertEqual(self.call(path)[0],200)
        self.assertEqual(self.call('/../app.py')[0],404)

    def test_invalid_payload_and_cross_origin(self):
        self.assertEqual(self.call('/api/listings','POST',[])[0],400)
        self.assertEqual(self.call('/api/reservations','POST',{}, {'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.call('/api/listings','POST',{}, {'Content-Type':'text/plain'})[0],415)

    def test_full_api_lifecycle_and_csv(self):
        status, body=self.call('/api/reservations','POST',{'listing_id':1,'request_id':1,'kg':10})
        self.assertEqual(status,201)
        key=json.loads(body)['id']
        self.assertEqual(self.call('/api/reservations/status','POST',{'id':key,'status':'completed'})[0],201)
        self.assertIn('completed',self.call('/api/report.csv')[1].decode('utf-8-sig'))


if __name__ == '__main__':
    unittest.main()
