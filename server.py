#!/usr/bin/env python3
"""OFFICE OSCARS 2026: dependency-free invite server, SQLite RSVP, private CSV.

Run: python server.py
Environment: PORT, HOST, DATA_DIR, ADMIN_TOKEN, PUBLIC_BASE_URL,
             INVITE_ACCESS_CODE (optional).
Deploy behind HTTPS reverse proxy with a persistent writable DATA_DIR.
"""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import logging
import mimetypes
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'
DATA_DIR = Path(os.environ.get('DATA_DIR', str(ROOT / 'data'))).resolve()
DATA_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
DB_FILE = DATA_DIR / 'rsvp.sqlite3'
PORT = int(os.environ.get('PORT', '8000'))
HOST = os.environ.get('HOST', '127.0.0.1')
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '').strip().rstrip('/')
INVITE_ACCESS_CODE = os.environ.get('INVITE_ACCESS_CODE', '').strip()
MOSCOW = timezone(timedelta(hours=3))
MAX_BODY_BYTES = 4096
LIMIT_LOCK = threading.Lock()
ATTEMPTS: dict[str, list[float]] = {}


def read_secret(env_key: str, filename: str) -> str:
    if os.environ.get(env_key):
        return os.environ[env_key]
    filepath = DATA_DIR / filename
    if filepath.exists():
        return filepath.read_text(encoding='utf-8').strip()
    token = secrets.token_urlsafe(36)
    fd = os.open(filepath, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write(token + '\n')
    return token


ADMIN_TOKEN = read_secret('ADMIN_TOKEN', 'admin_token.txt')
SESSION_SECRET = read_secret('SESSION_SECRET', 'session_secret.txt')
SESSION_COOKIE = hmac.new(SESSION_SECRET.encode('utf-8'), b'office-oscars-2026-access', hashlib.sha256).hexdigest()


@contextmanager
def database():
    connection = sqlite3.connect(DB_FILE, timeout=10)
    try:
        connection.execute('PRAGMA busy_timeout=10000')
        connection.execute('PRAGMA journal_mode=WAL')
        with connection:
            yield connection
    finally:
        connection.close()


def initialize():
    with database() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                name_normalized TEXT NOT NULL,
                department TEXT NOT NULL,
                department_normalized TEXT NOT NULL,
                attendance TEXT NOT NULL CHECK (attendance IN ('yes', 'no')),
                request_id TEXT NOT NULL UNIQUE,
                created_at_utc TEXT NOT NULL,
                created_at_moscow TEXT NOT NULL,
                UNIQUE(name_normalized, department_normalized)
            );
            CREATE INDEX IF NOT EXISTS idx_responses_created ON responses(created_at_utc);
        ''')
    os.chmod(DB_FILE, 0o600)


def too_many(key: str, max_attempts: int, window: int) -> bool:
    now = time.monotonic()
    with LIMIT_LOCK:
        events = ATTEMPTS.setdefault(key, [])
        events[:] = [old for old in events if now - old <= window]
        if len(events) >= max_attempts:
            return True
        events.append(now)
        if len(ATTEMPTS) > 5000:
            for k, values in list(ATTEMPTS.items())[:1000]:
                if not values or now - values[-1] > window:
                    ATTEMPTS.pop(k, None)
        return False


def clean(value: object) -> str:
    if not isinstance(value, str):
        return ''
    return re.sub(r'\s+', ' ', value).strip()


def export_safe(value: object) -> str:
    """Avoid Excel/Sheets interpreting user text as a formula."""
    text = str(value)
    if text.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')):
        return "'" + text
    return text


class Handler(BaseHTTPRequestHandler):
    server_version = 'OfficeOscars/1.0'

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Robots-Tag', 'noindex, nofollow, noarchive')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        self.send_header('Content-Security-Policy', "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; img-src 'self' data: https://images.unsplash.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self'; upgrade-insecure-requests")
        super().end_headers()

    def log_message(self, format, *args):
        logging.info('%s %s', self.address_string(), format % args)

    def respond(self, status: int, data: bytes, mime: str, *, headers: dict[str, str] | None = None):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store' if mime.startswith('application/json') or mime.startswith('text/csv') or mime.startswith('text/html') else 'public, max-age=86400')
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def json_response(self, status: int, payload: dict):
        self.respond(status, json.dumps(payload, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')

    def get_json_body(self) -> dict:
        raw_length = self.headers.get('Content-Length', '')
        if not raw_length.isdigit() or int(raw_length) > MAX_BODY_BYTES:
            raise ValueError('Слишком большой или некорректный запрос.')
        if not self.headers.get('Content-Type', '').lower().startswith('application/json'):
            raise ValueError('Неверный тип данных.')
        raw = self.rfile.read(int(raw_length))
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError('Неверный формат данных.')
        return value

    def ip(self):
        # Do not trust X-Forwarded-For by default (spoofable outside a trusted proxy).
        return self.client_address[0]

    def same_origin(self) -> bool:
        origin = self.headers.get('Origin')
        if not origin:
            return True  # Non-browser clients; protected by rate limits and validation.
        parsed = urlsplit(origin)
        return parsed.scheme in ('http', 'https') and parsed.netloc.lower() == self.headers.get('Host', '').lower()

    def is_unlocked(self):
        if not INVITE_ACCESS_CODE:
            return True
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            return 'office_access' in cookie and hmac.compare_digest(cookie['office_access'].value, SESSION_COOKIE)
        except Exception:
            return False

    def serve_file(self, name: str, mime: str | None = None):
        path = (STATIC / name).resolve()
        if not path.is_relative_to(STATIC.resolve()) or not path.is_file():
            return self.send_error(404)
        content = path.read_bytes()
        if name in ('index.html', 'unlock.html') and PUBLIC_BASE_URL:
            html = content.decode('utf-8').replace('content="/og-preview.png"', f'content="{PUBLIC_BASE_URL}/og-preview.png"')
            html = html.replace('<meta property="og:type"', f'<meta property="og:url" content="{PUBLIC_BASE_URL}/">\n  <meta property="og:type"')
            content = html.encode('utf-8')
        self.respond(200, content, mime or mimetypes.guess_type(name)[0] or 'application/octet-stream')

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/health':
            return self.json_response(200, {'ok': True})
        if path in ('/', '/index.html'):
            if not self.is_unlocked():
                return self.serve_file('unlock.html', 'text/html; charset=utf-8')
            return self.serve_file('index.html', 'text/html; charset=utf-8')
        if path == '/admin':
            return self.serve_file('admin.html', 'text/html; charset=utf-8')
        if path == '/api/admin/export.csv':
            if too_many('admin:' + self.ip(), 30, 60):
                return self.json_response(429, {'error': 'Слишком много запросов.'})
            supplied = self.headers.get('Authorization', '')
            if not supplied.startswith('Bearer ') or not hmac.compare_digest(supplied[7:], ADMIN_TOKEN):
                return self.json_response(401, {'error': 'Неверный административный ключ.'})
            output = io.StringIO(newline='')
            writer = csv.writer(output, dialect='excel', lineterminator='\r\n')
            writer.writerow(['ID', 'Имя и фамилия', 'Отдел / команда', 'Присутствие', 'Дата и время (Москва, UTC+3)', 'Дата и время (UTC)'])
            with database() as conn:
                for row in conn.execute('SELECT id, full_name, department, attendance, created_at_moscow, created_at_utc FROM responses ORDER BY created_at_utc'):
                    writer.writerow([row[0], export_safe(row[1]), export_safe(row[2]), 'Да' if row[3] == 'yes' else 'Нет', row[4], row[5]])
            body = ('\ufeff' + output.getvalue()).encode('utf-8')
            return self.respond(200, body, 'text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="office-oscars-rsvp.csv"'})
        if path == '/robots.txt':
            return self.respond(200, b'User-agent: *\nDisallow: /\n', 'text/plain; charset=utf-8')
        # Only allow explicit public assets. Keep data and server files private.
        allowed = {'styles.css','app.js','favicon.svg','statuette.svg','champagne.svg','og-preview.png','unlock.js','unlock.css','admin.js','admin.css'}
        if path.startswith('/') and path[1:] in allowed:
            return self.serve_file(path[1:])
        self.send_error(404)

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in ('/api/rsvp', '/api/unlock'):
            return self.json_response(404, {'error': 'Неизвестный адрес.'})
        if not self.same_origin():
            return self.json_response(403, {'error': 'Недопустимый источник запроса.'})
        if too_many(f'{path}:{self.ip()}', 10 if path == '/api/rsvp' else 8, 300):
            return self.json_response(429, {'error': 'Слишком много попыток. Попробуйте позднее.'})
        try:
            data = self.get_json_body()
        except (ValueError, json.JSONDecodeError):
            return self.json_response(400, {'error': 'Проверьте введённые данные и повторите попытку.'})
        if path == '/api/unlock':
            return self.unlock(data)
        if not self.is_unlocked():
            return self.json_response(403, {'error': 'Для отправки ответа необходимо открыть приглашение.'})
        return self.rsvp(data)

    def unlock(self, data):
        if not INVITE_ACCESS_CODE:
            return self.json_response(200, {'ok': True})
        supplied = data.get('code', '')
        if not isinstance(supplied, str) or not hmac.compare_digest(supplied, INVITE_ACCESS_CODE):
            return self.json_response(403, {'error': 'Неверный код приглашения.'})
        is_https = PUBLIC_BASE_URL.startswith('https://') or self.headers.get('X-Forwarded-Proto', '') == 'https'
        secure = '; Secure' if is_https else ''
        payload = json.dumps({'ok': True}).encode('utf-8')
        return self.respond(200, payload, 'application/json; charset=utf-8', headers={'Set-Cookie': f'office_access={SESSION_COOKIE}; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000{secure}'})

    def rsvp(self, data):
        full_name = clean(data.get('fullName'))
        department = clean(data.get('department'))
        attendance = data.get('attendance')
        request_id = data.get('requestId')
        if not (3 <= len(full_name) <= 120 and len(full_name.split(' ')) >= 2):
            return self.json_response(422, {'error': 'Укажите имя и фамилию (от 3 до 120 символов).'})
        if not (2 <= len(department) <= 120):
            return self.json_response(422, {'error': 'Укажите отдел или команду (от 2 до 120 символов).'})
        if attendance not in ('yes', 'no'):
            return self.json_response(422, {'error': 'Выберите, планируете ли вы присутствовать.'})
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 100 or not re.fullmatch(r'[\w-]+', request_id, re.ASCII):
            return self.json_response(422, {'error': 'Не удалось проверить отправку. Обновите страницу и повторите попытку.'})
        if any(c in full_name + department for c in '\x00\r\n'):
            return self.json_response(422, {'error': 'Недопустимые символы в полях.'})
        now_utc = datetime.now(timezone.utc)
        now_msk = now_utc.astimezone(MOSCOW)
        try:
            with database() as conn:
                existing = conn.execute('SELECT full_name, department, attendance FROM responses WHERE request_id = ?', (request_id,)).fetchone()
                if existing is not None:
                    if existing == (full_name, department, attendance):
                        return self.json_response(200, {'saved': True, 'alreadySaved': True})
                    return self.json_response(409, {'error': 'Этот запрос уже использован для другого ответа. Обновите страницу.'})
                conn.execute('''INSERT INTO responses (full_name, name_normalized, department, department_normalized, attendance, request_id, created_at_utc, created_at_moscow)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (full_name, full_name.casefold(), department, department.casefold(), attendance,
                     request_id, now_utc.isoformat(timespec='seconds'), now_msk.isoformat(timespec='seconds')))
            return self.json_response(201, {'saved': True})
        except sqlite3.IntegrityError:
            # A duplicate staff entry with a new request key is not silently accepted.
            with database() as conn:
                prior = conn.execute('SELECT full_name, department, attendance FROM responses WHERE request_id = ?', (request_id,)).fetchone()
            if prior == (full_name, department, attendance):
                return self.json_response(200, {'saved': True, 'alreadySaved': True})
            return self.json_response(409, {'error': 'Ответ от сотрудника с таким именем и отделом уже сохранён. Если нужно его изменить, свяжитесь с организаторами.'})
        except sqlite3.Error:
            logging.exception('Failed to persist RSVP')
            return self.json_response(503, {'error': 'Сейчас не удалось сохранить ответ. Попробуйте отправить его ещё раз.'})


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    initialize()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    logging.info('OFFICE OSCARS running at http://%s:%d', HOST, PORT)
    logging.info('SQLite responses file: %s', DB_FILE)
    logging.info('Admin CSV export: http://%s:%d/admin', HOST, PORT)
    logging.info('Admin key: %s (keep private)', 'set via ADMIN_TOKEN' if os.environ.get('ADMIN_TOKEN') else str(DATA_DIR / 'admin_token.txt'))
    if INVITE_ACCESS_CODE:
        logging.info('Private access code is enabled')
    try:
        server.serve_forever(poll_interval=.4)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
