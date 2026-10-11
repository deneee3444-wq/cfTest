from flask import Flask, request, jsonify, render_template_string
from cloakbrowser import launch_persistent_context
import threading
import requests
import time
import os

app = Flask(__name__)

# CORS Desteği
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

TARGET = "https://www.yolly.ai"
SIGNIN = TARGET + "/auth/signin?callbackUrl=http%3A%2F%2Fwww.yolly.ai%2Finvite"
PROFILE_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "browser_profile_cloak")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9",
})

state = {
    "token": None,
    "browser_running": False,
    "last_updated": 0,
    "page_ref": None,
}

INDEX = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Cloudflare Turnstile Token (CloakBrowser)</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      max-width: 500px;
      margin: 40px auto;
      padding: 0 16px;
      color: #333;
      background: #f8fafc;
    }
    .card {
      background: #fff;
      padding: 24px;
      border-radius: 12px;
      box-shadow: 0 4px 14px rgba(0,0,0,0.06);
      border: 1px solid #e2e8f0;
    }
    h2 {
      margin-top: 0;
      margin-bottom: 8px;
      text-align: center;
      font-size: 20px;
      color: #0f172a;
    }
    .subtitle {
      color: #64748b;
      font-size: 13px;
      margin-bottom: 20px;
      text-align: center;
    }
    .status-badge {
      padding: 12px 16px;
      border-radius: 8px;
      font-size: 14px;
      margin: 16px 0;
      font-weight: 600;
      text-align: center;
      transition: all 0.3s ease;
    }
    .waiting {
      background: #fef3c7;
      color: #92400e;
      border: 1px solid #fde68a;
      animation: pulse 1.5s infinite;
    }
    .ready {
      background: #dcfce7;
      color: #166534;
      border: 1px solid #bbf7d0;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.7; }
    }
    label {
      display: block;
      font-size: 13px;
      font-weight: 600;
      color: #475569;
      margin-bottom: 6px;
    }
    textarea {
      width: 100%;
      box-sizing: border-box;
      height: 120px;
      padding: 10px;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      font-family: monospace;
      font-size: 12px;
      resize: vertical;
      background: #f8fafc;
      word-break: break-all;
    }
    input {
      width: 100%;
      box-sizing: border-box;
      padding: 10px 12px;
      margin-bottom: 10px;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      font-size: 14px;
    }
    .btn-group {
      display: flex;
      gap: 10px;
      margin-top: 10px;
      margin-bottom: 20px;
    }
    button {
      flex: 1;
      padding: 12px;
      border: none;
      border-radius: 6px;
      font-size: 14px;
      font-weight: bold;
      cursor: pointer;
      transition: background 0.2s;
    }
    button.copy-btn {
      background: #2563eb;
      color: #fff;
    }
    button.copy-btn:hover {
      background: #1d4ed8;
    }
    button.refresh-btn {
      background: #f1f5f9;
      color: #334155;
      border: 1px solid #cbd5e1;
    }
    button.refresh-btn:hover {
      background: #e2e8f0;
    }
    button.send-btn {
      background: #10b981;
      color: #fff;
      width: 100%;
    }
    button.send-btn:hover {
      background: #059669;
    }
    button:disabled {
      background: #e2e8f0 !important;
      color: #94a3b8 !important;
      cursor: not-allowed;
      border: none;
    }
    .divider {
      height: 1px;
      background: #e2e8f0;
      margin: 20px 0;
    }
    pre {
      margin-top: 15px;
      background: #f1f5f9;
      padding: 10px;
      border-radius: 6px;
      font-size: 12px;
      white-space: pre-wrap;
      word-break: break-all;
      border: 1px solid #e2e8f0;
      min-height: 20px;
      display: none;
    }
  </style>
</head>
<body>
  <div class="card">
    <h2>Cloudflare Turnstile Token</h2>
    <div class="subtitle">CloakBrowser ile arka planda otomatik üretilir</div>

    <div id="status" class="status-badge waiting">⏳ Token alınıyor, lütfen bekleyin...</div>

    <label for="tokenBox">Yakalanan Token:</label>
    <textarea id="tokenBox" readonly placeholder="Token bekleniyor..."></textarea>

    <div class="btn-group">
      <button id="copyBtn" class="copy-btn" disabled onclick="copyToken()">📋 Token'ı Kopyala</button>
      <button id="refreshBtn" class="refresh-btn" onclick="refreshToken()">🔄 Yeni Token Al</button>
    </div>

    <div class="divider"></div>

    <label for="email">E-posta ile Doğrulama Kodu Gönder:</label>
    <input id="email" type="email" placeholder="ornek@domain.com">
    <button id="sendBtn" class="send-btn" disabled onclick="sendCode()">Doğrulama Kodu Gönder</button>
    <pre id="out"></pre>
  </div>

  <script>
    let currentToken = null;

    function applyToken(token) {
      if (!token) return;
      currentToken = token;
      document.getElementById('tokenBox').value = token;
      document.getElementById('copyBtn').disabled = false;
      document.getElementById('sendBtn').disabled = false;
      
      const statusEl = document.getElementById('status');
      statusEl.className = 'status-badge ready';
      statusEl.textContent = '✔ Token Başarıyla Alındı!';
    }

    // Backend'de yakalanan token'ı her saniye sorgula
    setInterval(async () => {
      if (!currentToken) {
        try {
          const r = await fetch('/get-token');
          const data = await r.json();
          if (data.token) {
            applyToken(data.token);
          }
        } catch(e) {}
      }
    }, 1000);

    async function copyToken() {
      if (!currentToken) return;
      await navigator.clipboard.writeText(currentToken);
      const copyBtn = document.getElementById('copyBtn');
      const oldText = copyBtn.textContent;
      copyBtn.textContent = '✔ Kopyalandı!';
      setTimeout(() => { copyBtn.textContent = oldText; }, 2000);
    }

    async function refreshToken() {
      currentToken = null;
      document.getElementById('tokenBox').value = '';
      document.getElementById('copyBtn').disabled = true;
      document.getElementById('sendBtn').disabled = true;
      
      const statusEl = document.getElementById('status');
      statusEl.className = 'status-badge waiting';
      statusEl.textContent = '⏳ Yeni token alınıyor, lütfen bekleyin...';

      await fetch('/reset-token');
    }

    async function sendCode() {
      const email = document.getElementById('email').value.trim();
      if (!email) {
        alert("Lütfen e-posta adresi girin!");
        return;
      }
      if (!currentToken) {
        alert("Token henüz hazır değil!");
        return;
      }

      const sendBtn = document.getElementById('sendBtn');
      const out = document.getElementById('out');
      sendBtn.disabled = true;
      out.style.display = 'block';
      out.textContent = "Kod gönderiliyor...";

      try {
        const r = await fetch('/send', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({email: email, token: currentToken})
        });
        const res = await r.json();
        out.textContent = JSON.stringify(res, null, 2);
      } catch (err) {
        out.textContent = "Hata: " + err;
      } finally {
        sendBtn.disabled = false;
      }
    }
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX)

@app.route("/get-token")
def get_token():
    return jsonify({"token": state["token"]})

@app.route("/reset-token")
def reset_token():
    state["token"] = None
    if state["page_ref"]:
        try:
            state["page_ref"].reload()
        except Exception:
            pass
    return jsonify({"ok": True})

@app.route("/set-token", methods=["POST", "OPTIONS"])
def set_token():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})
    data = request.get_json(force=True, silent=True) or {}
    token = data.get("token") or request.form.get("token")
    if token:
        state["token"] = token
        print("\n" + "="*60, flush=True)
        print("[SUCCESS] SET-TOKEN ILE TOKEN ALINDI:", flush=True)
        print(token, flush=True)
        print("="*60 + "\n", flush=True)
        return jsonify({"ok": True, "token": state["token"]})
    return jsonify({"ok": False, "error": "No token"}), 400

@app.route("/send", methods=["POST"])
def send():
    data = request.get_json(force=True)
    token = data.get("token") or state["token"]
    email = data.get("email")

    print("\n" + "="*60, flush=True)
    print(f"[+] /send cagirildi: Email: {email}", flush=True)
    print(f"[+] Token: {token[:35] if token else 'None'}...", flush=True)
    print("="*60 + "\n", flush=True)

    r = session.post(
        TARGET + "/api/auth/send-code",
        headers={
            "accept": "*/*",
            "content-type": "application/json",
            "origin": TARGET,
            "referer": SIGNIN,
        },
        json={"email": email, "turnstileToken": token},
        timeout=15,
    )
    return jsonify({"status": r.status_code, "body": r.text})

def cloak_monitor():
    state["browser_running"] = True
    time.sleep(1.0)
    
    os.makedirs(PROFILE_DIR, exist_ok=True)
    
    try:
        print("[*] CloakBrowser headless olarak baslatiliyor...", flush=True)
        context = launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=True,
            humanize=True,
            stealth_args=True,
            args=[
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
                "--window-size=1920,1080",
            ],
        )

        page = context.pages[0] if context.pages else context.new_page()
        state["page_ref"] = page

        print(f"[*] CloakBrowser yolly.ai giris sayfasina gidiyor: {SIGNIN}", flush=True)
        page.goto(SIGNIN)

        while True:
            time.sleep(1.0)
            
            # Eger token zaten varsa ve resetlenmediyse bekle
            if state["token"]:
                continue

            try:
                found = None
                for p_item in context.pages:
                    if p_item.is_closed():
                        continue
                    for frame in p_item.frames:
                        try:
                            el = frame.query_selector('[name="cf-turnstile-response"]')
                            if el:
                                val = el.input_value() or el.get_attribute("value")
                                if val and len(val) > 20:
                                    found = val
                                    break
                        except Exception:
                            pass
                    if found:
                        break

                if found and found != state["token"]:
                    print("\n" + "="*60, flush=True)
                    print("[SUCCESS] RENDER CLOAKBROWSER TOKEN YAKALADI VE BASILDI:", flush=True)
                    print(found, flush=True)
                    print("="*60 + "\n", flush=True)
                    state["token"] = found
                    try:
                        for c in context.cookies():
                            session.cookies.set(c['name'], c['value'], domain=c['domain'])
                    except Exception:
                        pass
            except Exception as e:
                pass
    except Exception as e:
        print("[!] CloakBrowser izleme hatasi:", e, flush=True)
    finally:
        state["browser_running"] = False

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    
    # CloakBrowser arka plan tarayicisini baslat
    t = threading.Thread(target=cloak_monitor, daemon=True)
    t.start()
    
    print(f"[*] Flask sunucusu baslatiliyor: 0.0.0.0:{port}", flush=True)
    app.run(host="0.0.0.0", port=port, debug=False)
