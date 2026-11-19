"""Run with `python -m unittest discover -s tests -v` (no external deps)."""
import csv
import io
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT=pathlib.Path(__file__).resolve().parents[1]

class SiteTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory()
  sock=socket.socket();sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1];sock.close()
  cls.url=f'http://127.0.0.1:{cls.port}'
  env=dict(os.environ,DATA_DIR=cls.temp.name,HOST='127.0.0.1',PORT=str(cls.port),ADMIN_TOKEN='super-secret-test-token',INVITE_ACCESS_CODE='')
  cls.proc=subprocess.Popen([sys.executable,str(ROOT/'server.py')],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(50):
   try:
    urlopen(cls.url+'/api/health',timeout=.4).close()
    break
   except (OSError,URLError):time.sleep(.08)
  else:raise RuntimeError('Server did not start')
 @classmethod
 def tearDownClass(cls):
  cls.proc.terminate();cls.proc.wait(timeout=5);cls.temp.cleanup()
 def call(self,path,body=None,token=None):
  data=json.dumps(body).encode() if body is not None else None
  headers={}
  if body is not None:headers['Content-Type']='application/json'
  if token:headers['Authorization']='Bearer '+token
  req=Request(self.url+path,data=data,headers=headers)
  try:
   r=urlopen(req,timeout=3)
   return r.status,r.read(),r.headers
  except HTTPError as e:return e.code,e.read(),e.headers
 def test_01_content_and_security(self):
  code,content,headers=self.call('/')
  self.assertEqual(code,200)
  self.assertIn(b'OFFICE OSCARS',content)
  self.assertIn('noindex',headers['X-Robots-Tag'])
  self.assertEqual(self.call('/data/rsvp.sqlite3')[0],404)
  self.assertEqual(self.call('/api/admin/export.csv')[0],401)
 def test_02_save_and_dedupe_and_csv(self):
  name={'fullName':'Иван Проверочный','department':'Тестовая команда','attendance':'yes','requestId':'test-test-0001'}
  code,body,_=self.call('/api/rsvp',name)
  self.assertEqual(code,201,body)
  self.assertTrue(json.loads(body)['saved'])
  code,body,_=self.call('/api/rsvp',name)
  self.assertEqual(code,200,body)
  self.assertTrue(json.loads(body)['alreadySaved'])
  code,body,_=self.call('/api/rsvp',{**name,'requestId':'test-test-0002'})
  self.assertEqual(code,409,body)
  self.assertEqual(self.call('/api/admin/export.csv',token='bad')[0],401)
  code,body,headers=self.call('/api/admin/export.csv',token='super-secret-test-token')
  self.assertEqual(code,200,body)
  self.assertTrue(body.startswith(b'\xef\xbb\xbf'))
  rows=list(csv.reader(io.StringIO(body.decode('utf-8-sig'))))
  self.assertEqual(len(rows),2)
  self.assertEqual(rows[1][1],'Иван Проверочный')
  self.assertEqual(rows[1][3],'Да')
  self.assertIn('+03:00',rows[1][4])
 def test_03_validation(self):
  invalid={'fullName':'X','department':'T','attendance':'maybe','requestId':'test-test-0003'}
  self.assertEqual(self.call('/api/rsvp',invalid)[0],422)
  self.assertEqual(self.call('/api/rsvp',{'fullName':'Тест Тестов','department':'Тест','attendance':'yes','requestId':'k'})[0],422)
 def test_04_static(self):
  for asset in ['/styles.css','/app.js','/og-preview.png','/favicon.svg','/statuette.svg','/robots.txt']:
   self.assertEqual(self.call(asset)[0],200,asset)

if __name__=='__main__':unittest.main()
