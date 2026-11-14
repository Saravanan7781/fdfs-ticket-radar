"""Local Web Dashboard for FDFS Ticket Radar (Zero Extra Dependencies)."""

import json
import logging
import os
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.settings import Settings
from notifiers.ntfy_notifier import NtfyNotifier

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FDFS Ticket Radar Dashboard</title>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --border: #334155;
      --primary: #e11d48;
      --primary-hover: #be123c;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --success: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); padding: 24px; min-height: 100vh; }
    .container { max-width: 860px; margin: 0 auto; }
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
    .title { font-size: 24px; font-weight: 800; display: flex; align-items: center; gap: 8px; }
    .title span { color: var(--primary); }
    .btn { background: var(--primary); color: white; border: none; padding: 10px 18px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: 0.2s; display: inline-flex; align-items: center; gap: 6px; font-size: 14px; }
    .btn:hover { background: var(--primary-hover); transform: translateY(-1px); }
    .btn-secondary { background: #334155; }
    .btn-secondary:hover { background: #475569; }
    .btn-danger { background: #ef4444; }
    .btn-danger:hover { background: #dc2626; }
    .btn-sm { padding: 6px 12px; font-size: 13px; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.2); }
    .card-title { font-size: 18px; font-weight: 700; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .full-width { grid-column: span 2; }
    .form-group { display: flex; flex-direction: column; gap: 6px; }
    label { font-size: 13px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
    input, select, textarea { background: #0f172a; border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; color: white; font-size: 15px; outline: none; transition: 0.2s; }
    input:focus, select:focus, textarea:focus { border-color: var(--primary); }
    .toggle-container { display: flex; align-items: center; gap: 12px; margin-top: 8px; }
    .toggle { position: relative; width: 48px; height: 26px; }
    .toggle input { opacity: 0; width: 0; height: 0; }
    .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background: #334155; border-radius: 26px; transition: 0.3s; }
    .slider:before { position: absolute; content: ""; height: 20px; width: 20px; left: 3px; bottom: 3px; background: white; border-radius: 50%; transition: 0.3s; }
    input:checked + .slider { background: var(--success); }
    input:checked + .slider:before { transform: translateX(22px); }
    .tag-help { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
    .toast { position: fixed; bottom: 24px; right: 24px; background: var(--success); color: white; padding: 12px 20px; border-radius: 8px; font-weight: 600; display: none; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3); }
    .badge { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; text-transform: uppercase; background: rgba(225, 29, 72, 0.2); color: #fda4af; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="title">🎟️ <span>FDFS</span> Ticket Radar</div>
      <div style="display: flex; gap: 10px;">
        <button class="btn btn-secondary" onclick="testSiren()">🚨 Test Siren</button>
        <button class="btn" onclick="saveAll()">💾 Save Watchlist</button>
      </div>
    </div>

    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
      <h2 style="font-size: 18px; font-weight: 700;">Tracked Movies</h2>
      <button class="btn btn-sm" onclick="addMovieCard()">➕ Add Movie</button>
    </div>

    <div id="movies-list"></div>
  </div>

  <div id="toast" class="toast">Saved successfully!</div>

  <script>
    let watchlist = [];

    async function loadWatchlist() {
      const res = await fetch('/api/watchlist');
      const data = await res.json();
      watchlist = data.watchlist || [];
      render();
    }

    function render() {
      const container = document.getElementById('movies-list');
      if (watchlist.length === 0) {
        container.innerHTML = '<div class="card" style="text-align: center; color: var(--text-muted); padding: 40px;">No movies in watchlist. Click "Add Movie" to start!</div>';
        return;
      }

      container.innerHTML = watchlist.map((item, index) => `
        <div class="card">
          <div class="card-title">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 20px;">🎬</span>
              <span style="font-weight: 800;">${item.movie_name || 'Untitled Movie'}</span>
              <span class="badge">${item.district || 'All Districts'}</span>
            </div>
            <button class="btn btn-danger btn-sm" onclick="deleteMovie(${index})">🗑️ Delete</button>
          </div>

          <div class="grid">
            <div class="form-group">
              <label>Movie Name</label>
              <input type="text" value="${item.movie_name || ''}" onchange="updateItem(${index}, 'movie_name', this.value)" placeholder="e.g. Coolie, Thalapathy 69">
            </div>

            <div class="form-group">
              <label>District / City</label>
              <input type="text" value="${item.district || ''}" onchange="updateItem(${index}, 'district', this.value)" placeholder="e.g. Chennai, Coimbatore, Madurai">
            </div>

            <div class="form-group full-width">
              <label>Target Theatres</label>
              <input type="text" value="${(item.target_theatres || []).join(', ')}" onchange="updateTheatres(${index}, this.value)" placeholder="e.g. Rohini, Vettri, AGS, KG Cinemas">
              <div class="tag-help">💡 Leave blank or type 'all' to monitor ALL theatres across the entire district.</div>
            </div>

            <div class="form-group">
              <label>Target Release Date (Optional)</label>
              <input type="text" value="${item.target_date || ''}" onchange="updateItem(${index}, 'target_date', this.value)" placeholder="YYYY-MM-DD or leave blank">
            </div>

            <div class="form-group">
              <label>FDFS Only Filter</label>
              <div class="toggle-container">
                <label class="toggle">
                  <input type="checkbox" ${item.fdfs_only !== false ? 'checked' : ''} onchange="updateItem(${index}, 'fdfs_only', this.checked)">
                  <span class="slider"></span>
                </label>
                <span style="font-size: 14px; font-weight: 600;">Early Morning Shows (≤ 08:00 AM)</span>
              </div>
            </div>

            <div class="form-group">
              <label>Direct BookMyShow URL (Optional)</label>
              <input type="text" value="${item.bms_url || ''}" onchange="updateItem(${index}, 'bms_url', this.value)" placeholder="https://in.bookmyshow.com/movies/...">
            </div>

            <div class="form-group">
              <label>Direct District URL (Optional)</label>
              <input type="text" value="${item.district_url || ''}" onchange="updateItem(${index}, 'district_url', this.value)" placeholder="https://www.district.in/movies/...">
            </div>
          </div>
        </div>
      `).join('');
    }

    function updateItem(index, key, value) {
      watchlist[index][key] = value;
      if (key === 'movie_name' || key === 'district') {
        render();
      }
    }

    function updateTheatres(index, text) {
      if (!text || text.trim().toLowerCase() === 'all') {
        watchlist[index].target_theatres = [];
      } else {
        watchlist[index].target_theatres = text.split(',').map(s => s.trim()).filter(Boolean);
      }
    }

    function addMovieCard() {
      watchlist.unshift({
        id: 'movie_' + Date.now(),
        movie_name: '',
        district: 'Chennai',
        target_theatres: [],
        target_date: null,
        fdfs_only: true,
        fdfs_max_time: '08:00',
        enabled: true
      });
      render();
    }

    function deleteMovie(index) {
      watchlist.splice(index, 1);
      render();
    }

    async function saveAll() {
      await fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ watchlist })
      });
      showToast('Watchlist updated! The radar will use these new filters immediately.');
    }

    async function testSiren() {
      await fetch('/api/test-siren', { method: 'POST' });
      showToast('🚨 Test Siren sent! Check your phone.');
    }

    function showToast(msg) {
      const toast = document.getElementById('toast');
      toast.innerText = msg;
      toast.style.display = 'block';
      setTimeout(() => { toast.style.display = 'none'; }, 3000);
    }

    loadWatchlist();
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    """Handles web UI requests and watchlist API."""

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))

        elif self.path == "/api/watchlist":
            data = {"watchlist": []}
            if Settings.WATCHLIST_PATH.exists():
                with open(Settings.WATCHLIST_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else ""

        if self.path == "/api/watchlist":
            try:
                payload = json.loads(body)
                Settings.WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(Settings.WATCHLIST_PATH, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())

        elif self.path == "/api/test-siren":
            notifier = NtfyNotifier(Settings.NTFY_TOPIC)
            notifier.send_test_alert()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Quiet logging


def start_server(port: int = 5055):
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    url = f"http://localhost:{port}"
    print("=" * 60)
    print("  🎟️  FDFS TICKET RADAR — WEB DASHBOARD")
    print("=" * 60)
    print(f"👉 Opening Dashboard at: {url}")
    print("   (You can also open this link on your phone if on same Wi-Fi)")
    print("=" * 60)
    print("Press Ctrl+C to stop the dashboard server.\n")

    # Open user's default browser automatically
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")


if __name__ == "__main__":
    start_server()
