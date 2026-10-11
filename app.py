from flask import Flask, request, jsonify, render_template_string
from playwright.sync_api import sync_playwright
import threading
import requests
import time
import os

app = Flask(__name__)

# CORS Desteği (Bookmarklet veya harici scriptlerden gelen /set-token istekleri için)
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

TARGET = "https://www.yolly.ai"
SIGNIN = TARGET + "/auth/signin?callbackUrl=http%3A%2F%2Fwww.yolly.ai%2Finvite"
PROFILE_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "browser_profile")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9",
})

state = {
    "token": None,
    "browser_running": False
}

INDEX = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Turnstile Çöz & Gönder (Render)</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      max-width: 420px;
      margin: 30px auto;
      padding: 0 16px;
      color: #333;
      background: #fafafa;
    }
    .card {
      background: #fff;
      padding: 24px 20px;
      border-radius: 12px;
      box-shadow: 0 4px 14px rgba(0,0,0,0.08);
      border: 1px solid #eaeaea;
    }
    h3 {
      margin-top: 0;
      margin-bottom: 6px;
      text-align: center;
      font-size: 20px;
    }
    .subtitle {
      color: #666;
      font-size: 13px;
      margin-bottom: 16px;
      text-align: center;
    }
    
    /* SADECE Turnstile kutucuğunu gösteren kırpılmış çerçeve */
    .cf-wrapper {
      width: 300px;
      height: 65px;
      overflow: hidden;
      position: relative;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      margin: 15px auto;
      background: #fff;
      box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .cf-wrapper iframe {
      width: 400px;
      height: 500px;
      position: absolute;
      top: -326px;
      left: -50px;
      border: none;
    }

    .status-badge {
      padding: 10px 14px;
      border-radius: 6px;
      font-size: 13px;
      margin: 14px 0;
      font-weight: 500;
      text-align: center;
      transition: all 0.3s ease;
    }
    .waiting { background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
    .ready { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }

    input {
      width: 100%;
      box-sizing: border-box;
      padding: 11px 12px;
      margin-bottom: 12px;
      border: 1px solid #ccc;
      border-radius: 6px;
      font-size: 14px;
    }
    input:focus {
      outline: none;
      border-color: #0070f3;
    }

    button.primary {
      width: 100%;
      padding: 12px;
      background: #0070f3;
      color: #fff;
      border: none;
      border-radius: 6px;
      font-size: 15px;
      font-weight: bold;
      cursor: pointer;
      transition: background 0.2s;
    }
    button.primary:disabled {
      background: #ccc;
      cursor: not-allowed;
    }
    button.secondary {
      width: 100%;
      padding: 8px;
      background: #f0f2f5;
      color: #333;
      border: 1px solid #ccc;
      border-radius: 6px;
      font-size: 12px;
      cursor: pointer;
      margin-top: 6px;
    }

    .token-manual-box {
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px dashed #ddd;
    }

    pre {
      margin-top: 15px;
      background: #f6f8fa;
      padding: 12px;
      border-radius: 6px;
      font-size: 12px;
      white-space: pre-wrap;
      word-break: break-all;
      border: 1px solid #eaecef;
      min-height: 20px;
    }
    .tip-box {
      background: #f0f7ff;
      border: 1px solid #cce3ff;
      border-radius: 6px;
      padding: 10px 12px;
      font-size: 12px;
      color: #0052cc;
      margin-top: 14px;
      line-height: 1.4;
    }
  </style>
</head>
<body>
  <div class="card">
    <h3>Turnstile Çöz & Gönder</h3>
    <div class="subtitle">Aşağıdaki kutucuğu doğrulayın:</div>

    <!-- SADECE CLOUDFLARE TURNSTILE KUTUCUĞU GÖRÜNÜR -->
    <div class="cf-wrapper">
      <iframe id="cf" src="https://www.yolly.ai/auth/signin?callbackUrl=http%3A%2F%2Fwww.yolly.ai%2Finvite"></iframe>
    </div>

    <div id="status" class="status-badge waiting">⏳ Captcha kutusunu işaretlemeniz bekleniyor...</div>

    <input id="email" type="email" placeholder="E-posta adresi girin">
    <button id="btn" class="primary" disabled onclick="gonder()">Gönder</button>

    <!-- Manuel / Panodan Yapıştırma Seçeneği -->
    <div class="token-manual-box">
      <input id="manual_token" type="text" placeholder="Token kopyaladıysanız buraya yapıştırın" oninput="manualTokenInput(this.value)">
      <button class="secondary" onclick="pasteFromClipboard()">📋 Panodan Token Yapıştır</button>
    </div>

    <pre id="out"></pre>

    <div class="tip-box">
      <strong>💡 İpucu:</strong> Kutucukta ✔ Başarılı olduktan sonra buton otomatik açılmazsa, sağ tık &rarr; İncele (DevTools) ile <code>cf-turnstile-response</code> değerini kopyalayıp yukarıdaki kutuya yapıştırabilir ya da "Panodan Token Yapıştır" diyebilirsiniz.
    </div>
  </div>

  <script>
    let currentToken = null;

    function applyToken(token) {
      if (!token) return;
      currentToken = token;
      document.getElementById('btn').disabled = false;
      const statusEl = document.getElementById('status');
      statusEl.className = 'status-badge ready';
      statusEl.textContent = '✔ Captcha çözüldü! Token hazır.';
      document.getElementById('out').textContent = 'Aktif Token: ' + token.substring(0, 45) + '...';
    }

    function manualTokenInput(val) {
      val = val.trim();
      if (val.length > 20) {
        applyToken(val);
        // Sunucuya da bildir
        fetch('/set-token', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({token: val})
        }).catch(()=>{});
      }
    }

    async function pasteFromClipboard() {
      try {
        const text = await navigator.clipboard.readText();
        if (text && text.trim().length > 20) {
          document.getElementById('manual_token').value = text.trim();
          manualTokenInput(text.trim());
        } else {
          alert("Panoda geçerli bir token bulunamadı!");
        }
      } catch(e) {
        alert("Pano erişim izni verilmedi. Lütfen token'ı kutuya doğrudan yapıştırın.");
      }
    }

    // Tampermonkey veya eklentiden gelen postMessage dinleyicisi
    window.addEventListener('message', (e) => {
      if (e.data && (e.data.token || e.data.cfToken)) {
        const t = e.data.token || e.data.cfToken;
        applyToken(t);
      }
    });

    // Sunucu tarafında (Playwright vb.) yakalanan token'ı düzenli sorgula
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
    }, 500);

    async function gonder() {
      const email = document.getElementById('email').value.trim();
      if (!email) {
        alert("Lütfen e-posta adresi girin!");
        return;
      }
      if (!currentToken) {
        alert("Lütfen önce captchayı çözün!");
        return;
      }

      document.getElementById('btn').disabled = true;
      document.getElementById('out').textContent = "Kod gönderiliyor...";

      try {
        const r = await fetch('/send', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({email: email, token: currentToken})
        });
        const res = await r.json();
        document.getElementById('out').textContent = JSON.stringify(res, null, 2);
      } catch (err) {
        document.getElementById('out').textContent = "Hata: " + err;
      }

      // Yeni istek için sıfırla
      currentToken = null;
      document.getElementById('manual_token').value = "";
      document.getElementById('status').className = 'status-badge waiting';
      document.getElementById('status').textContent = '⏳ Yeni captcha bekleniyor...';
      document.getElementById('cf').src = 'https://www.yolly.ai/auth/signin?callbackUrl=http%3A%2F%2Fwww.yolly.ai%2Finvite&t=' + Date.now();
      await fetch('/reset-token');
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
    return jsonify({"ok": True})

# Manuel veya harici betikten gelen token'ı kabul eden endpoint
@app.route("/set-token", methods=["POST", "OPTIONS"])
def set_token():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})
    data = request.get_json(force=True, silent=True) or {}
    token = data.get("token") or request.form.get("token")
    if token:
        state["token"] = token
        print(f"[✔] set-token ile yeni token kaydedildi: {token[:35]}...")
        return jsonify({"ok": True, "token": state["token"]})
    return jsonify({"ok": False, "error": "No token provided"}), 400

# ---------- Token + email ile yolly.ai'ye kod gönderme ----------
@app.route("/send", methods=["POST"])
def send():
    data = request.get_json(force=True)
    r = session.post(
        TARGET + "/api/auth/send-code",
        headers={
            "accept": "*/*",
            "content-type": "application/json",
            "origin": TARGET,
            "referer": SIGNIN,
        },
        json={"email": data["email"], "turnstileToken": data["token"]},
        timeout=15,
    )
    state["token"] = None
    return jsonify({"status": r.status_code, "body": r.text})

# Sunucu tarafında doğrudan yolly.ai'yi izleyen Playwright motoru
def server_playwright_monitor():
    state["browser_running"] = True
    time.sleep(2.0)
    
    os.makedirs(PROFILE_DIR, exist_ok=True)
    
    try:
        with sync_playwright() as p:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
            ]

            # Render Linux ortamında doğrudan Chromium headless
            context = p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                headless=True,
                args=launch_args,
                ignore_default_args=["--enable-automation"],
            )

            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['tr-TR', 'tr', 'en-US', 'en'] });
            """)

            # Sunucu tarafında doğrudan yolly.ai giriş sayfasına git
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(SIGNIN)

            print("\n[+] Render arka plan tarayıcısı yolly.ai'yi dinliyor...\n")

            while True:
                time.sleep(0.5)
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
                        print(f"\n[✔] Sunucu Playwright Token yakaladı: {found[:40]}...\n")
                        state["token"] = found
                except Exception:
                    pass
    except Exception as e:
        print("[!] Render arka plan tarayıcı hatası (Normal olabilir):", e)
    finally:
        state["browser_running"] = False

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    
    # Arka plan tarayıcısını isteğe bağlı başlat
    if os.environ.get("ENABLE_SERVER_PLAYWRIGHT") == "true":
        t = threading.Thread(target=server_playwright_monitor, daemon=True)
        t.start()

    app.run(host="0.0.0.0", port=port, debug=False)
