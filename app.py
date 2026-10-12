from flask import Flask, request, jsonify, render_template_string, Response
from cloakbrowser import launch_persistent_context
import threading
import requests
import time
import os
import io

app = Flask(__name__)

# CORS Desteği
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

TARGET = "https://apixo.ai"
SIGNIN = TARGET + "/tr/login"
PROFILE_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "browser_profile_cloak")

# Webshare Proxy Bilgileri
DEFAULT_PROXY = "http://plasthjw-1:vh917rfhzcxi@p.webshare.io:80"
PROXY = os.environ.get("PROXY", DEFAULT_PROXY)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9",
})
if PROXY:
    session.proxies = {"http": PROXY, "https": PROXY}

state = {
    "token": None,
    "browser_running": False,
    "last_screenshot": None,
    "screenshot_requested": False,
    "reload_requested": False,
    "last_ss_time": 0,
}

INDEX = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Cloudflare Turnstile Token & Ekran (CloakBrowser)</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      max-width: 560px;
      margin: 30px auto;
      padding: 0 16px;
      color: #1e293b;
      background: #f8fafc;
    }
    .card {
      background: #fff;
      padding: 24px;
      border-radius: 12px;
      box-shadow: 0 4px 14px rgba(0,0,0,0.06);
      border: 1px solid #e2e8f0;
      margin-bottom: 20px;
    }
    h2 {
      margin-top: 0;
      margin-bottom: 6px;
      text-align: center;
      font-size: 20px;
      color: #0f172a;
    }
    .subtitle {
      color: #64748b;
      font-size: 13px;
      margin-bottom: 18px;
      text-align: center;
    }
    .badge {
      display: inline-block;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: bold;
      background: #e2e8f0;
      color: #475569;
    }
    .proxy-info {
      text-align: center;
      margin-bottom: 14px;
      font-size: 12px;
      color: #475569;
    }
    .status-badge {
      padding: 12px 16px;
      border-radius: 8px;
      font-size: 14px;
      margin: 14px 0;
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
      height: 100px;
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
      gap: 8px;
      margin-top: 10px;
      margin-bottom: 16px;
    }
    button {
      flex: 1;
      padding: 10px;
      border: none;
      border-radius: 6px;
      font-size: 13px;
      font-weight: bold;
      cursor: pointer;
      transition: all 0.2s;
    }
    button.copy-btn {
      background: #2563eb;
      color: #fff;
    }
    button.copy-btn:hover { background: #1d4ed8; }
    button.refresh-btn {
      background: #f1f5f9;
      color: #334155;
      border: 1px solid #cbd5e1;
    }
    button.refresh-btn:hover { background: #e2e8f0; }
    button.ss-btn {
      background: #6366f1;
      color: #fff;
      margin-bottom: 12px;
    }
    button.ss-btn:hover { background: #4f46e5; }
    button.send-btn {
      background: #10b981;
      color: #fff;
      width: 100%;
    }
    button.send-btn:hover { background: #059669; }
    button:disabled {
      background: #e2e8f0 !important;
      color: #94a3b8 !important;
      cursor: not-allowed;
      border: none;
    }
    .divider {
      height: 1px;
      background: #e2e8f0;
      margin: 18px 0;
    }
    .screenshot-box {
      margin-top: 10px;
      text-align: center;
      background: #0f172a;
      border-radius: 8px;
      overflow: hidden;
      border: 1px solid #334155;
      min-height: 180px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .screenshot-box img {
      max-width: 100%;
      height: auto;
      display: block;
    }
    pre {
      margin-top: 12px;
      background: #f1f5f9;
      padding: 10px;
      border-radius: 6px;
      font-size: 12px;
      white-space: pre-wrap;
      word-break: break-all;
      border: 1px solid #e2e8f0;
      display: none;
    }
  </style>
</head>
<body>
  <div class="card">
    <h2>Cloudflare Turnstile Token</h2>
    <div class="subtitle">CloakBrowser + Proxy ile Otomatik Yakalama</div>

    <div class="proxy-info">
      <span class="badge">Proxy Aktif</span> <code>p.webshare.io:80</code>
    </div>

    <div id="status" class="status-badge waiting">⏳ Token alınıyor, lütfen bekleyin...</div>

    <label for="tokenBox">Yakalanan Token:</label>
    <textarea id="tokenBox" readonly placeholder="Token bekleniyor..."></textarea>

    <div class="btn-group">
      <button id="copyBtn" class="copy-btn" disabled onclick="copyToken()">📋 Token'ı Kopyala</button>
      <button id="refreshBtn" class="refresh-btn" onclick="refreshToken()">🔄 Yeni Token Al</button>
    </div>

    <div class="divider"></div>

    <!-- EKRAN GÖRÜNTÜSÜ BÖLÜMÜ -->
    <button class="ss-btn" onclick="takeScreenshot()">📸 Canlı Tarayıcı Ekran Görüntüsü Al</button>
    
    <div id="ssContainer" class="screenshot-box">
      <span style="color:#94a3b8; font-size:12px;">Ekran görüntüsü almak için yukarıdaki butona tıklayın</span>
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

    // Backend'de yakalanan token'ı düzenli sorgula
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
      // Otomatik yeni ekran görüntüsü de al
      setTimeout(takeScreenshot, 2000);
    }

    async function takeScreenshot() {
      const container = document.getElementById('ssContainer');
      container.innerHTML = '<span style="color:#94a3b8; font-size:12px;">📸 Ekran görüntüsü alınıyor...</span>';
      
      const url = '/screenshot?t=' + Date.now();
      const img = new Image();
      img.onload = () => {
        container.innerHTML = '';
        container.appendChild(img);
      };
      img.onerror = () => {
        container.innerHTML = '<span style="color:#ef4444; font-size:12px;">Ekran görüntüsü henüz hazır değil, tekrar deneyin.</span>';
      };
      img.src = url;
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

@app.route("/screenshot")
def screenshot():
    state["screenshot_requested"] = True
    # Arka plan tarayıcısının ekran görüntüsü alması için 1.5 saniyeye kadar bekle
    for _ in range(15):
        time.sleep(0.1)
        if not state["screenshot_requested"] and state["last_screenshot"]:
            break
    if state["last_screenshot"]:
        return Response(state["last_screenshot"], mimetype="image/png")
    return "Tarayici henuz ilk ekran goruntusunu almadi, lutfen 3 saniye sonra tekrar deneyin.", 503

@app.route("/reset-token")
def reset_token():
    state["token"] = None
    state["reload_requested"] = True
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
        print(f"[*] CloakBrowser headless olarak baslatiliyor (Proxy: {PROXY})...", flush=True)
        context = launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=True,
            proxy=PROXY,
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

        # Ilk ekran goruntusunu hemen al
        try:
            state["last_screenshot"] = page.screenshot()
            state["last_ss_time"] = time.time()
        except Exception:
            pass

        while True:
            time.sleep(1.0)
            
            # Sayfa yenileme istegi varsa kendi thread'inde yenile
            if state["reload_requested"]:
                try:
                    page.reload()
                except Exception:
                    pass
                state["reload_requested"] = False

            # Ekran goruntusu istendiyse veya her 3 saniyede bir guncelle
            if state["screenshot_requested"] or (time.time() - state["last_ss_time"] > 3):
                try:
                    state["last_screenshot"] = page.screenshot()
                    state["last_ss_time"] = time.time()
                except Exception:
                    pass
                state["screenshot_requested"] = False

            # Eger token zaten varsa bekle
            if state["token"]:
                continue

            try:
                # 1. Turnstile kutucugu varsa otomatik tiklamayi dene
                for frame in page.frames:
                    if "challenges.cloudflare.com" in frame.url:
                        try:
                            # Frame body'sine tikla
                            frame.locator('body').click(timeout=1500)
                        except Exception:
                            pass

                # 2. Token degeri uretilmis mi kontrol et
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
            except Exception:
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
