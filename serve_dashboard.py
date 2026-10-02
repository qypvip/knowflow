#!/usr/bin/env python3
"""Serve the KnowFlow dashboard locally with Gaokao API."""
import http.server
import json
import socketserver
import sys
import webbrowser
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = 8080
DIR = Path(__file__).parent / 'docs'
GAOKAO_DIR = Path(__file__).parent / 'data' / 'gaokao' / 'hebei'

# Add gaokao analyzer path
sys.path.insert(0, str(Path(__file__).parent / 'tools'))
from gaokao.analyzer import GaokaoAnalyzer

analyzer = GaokaoAnalyzer()

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/gaokao':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            with open(Path(__file__).parent / 'templates' / 'gaokao_dashboard.html', 'rb') as f:
                self.wfile.write(f.read())
            return
        return super().do_GET()

    def do_POST(self):
        if self.path == '/api/gaokao/analyze':
            length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(length).decode('utf-8'))
            try:
                result = analyzer.analyze(
                    group=body.get('group', '物理组'),
                    score=body.get('score', 580),
                    rank=body.get('rank', 12000),
                    subjects=body.get('subjects', '物化生'),
                    year=body.get('year', '2025')
                )
                self.send_json(result)
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
            return
        self.send_error(404)

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format, *args):
        pass  # Quiet

print(f"📊 KnowFlow Dashboard: http://localhost:{PORT}/gaokao")
print(f"🔐 Password: qian8985831")
print(f"Press Ctrl+C to stop")
webbrowser.open(f'http://localhost:{PORT}/gaokao')
with socketserver.TCPServer(('', PORT), Handler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
