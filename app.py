from flask import Flask, request, jsonify, render_template_string
from playwright.sync_api import sync_playwright
import threading
import requests
import time
import os

app = Flask(__name__)

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
  <title>Turnstile Çöz & Gönder</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      max-width: 440px;
      margin: 25px auto;
      padding: 0 16px;
      color: #333;
    }
    h3 {
      margin-bottom: 6px;
      text-align: center;
    }
    .subtitle {
      color: #666;
      font-size: 13px;
      margin-bottom: 14px;
      text-align: center;
    }
    iframe {
      border: 1px solid #ddd;
      border-radius: 8px;
      display: block;
      margin: 0 auto;
      box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    }
    .status-badge {
      padding: 10px 14px;
      border-radius: 6px;
      font-size: 13px;
      margin: 14px 0 12px 0;
      font-weight: 500;
      text-align: center;
      transition: all 0.3s ease;
    }
    .waiting { background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
    .ready { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    input {
      width: 100%;
      box-sizing: border-box;
      padding: 10px 12px;
      margin-bottom: 10px;
      border: 1px solid #ccc;
      border-radius: 6px;
      font-size: 14px;
    }
    button {
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
    button:disabled {
      background: #bbb;
      cursor: not-allowed;
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
  </style>
</head>
<body>
  <h3>Turnstile Çöz & Gönder</h3>
  <div class="subtitle">Aşağıdaki Turnstile kutucuğunu işaretleyin:</div>

  <!-- Yolly.ai Doğal Iframe (Kırpılmamış, Cloudflare hata vermez) -->
  <iframe id="cf" src="https://www.yolly.ai/auth/signin?callbackUrl=http%3A%2F%2Fwww.yolly.ai%2Finvite"
          width="400" height="460"></iframe>

  <div id="status" class="status-badge waiting">⏳ Captcha kutusunu işaretlemeniz bekleniyor...</div>

  <input id="email" type="email" placeholder="E-posta adresi girin">
  <button id="btn" disabled onclick="gonder()">Gönder</button>
  <pre id="out"></pre>

  <script>
    let currentToken = null;

    // Backend'de yakalanan token'ı düzenli sorgula
    setInterval(async () => {
      if (!currentToken) {
        try {
          const r = await fetch('/get-token');
          const data = await r.json();
          if (data.token) {
            currentToken = data.token;
            document.getElementById('btn').disabled = false;
            const statusEl = document.getElementById('status');
            statusEl.className = 'status-badge ready';
            statusEl.textContent = '✔ Captcha çözüldü! Token alındı.';
            document.getElementById('out').textContent = 'Token: ' + currentToken.substring(0, 45) + '...';
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

      // Yeni token için sıfırla
      currentToken = null;
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

# ---------- Token + email ile isteği at ----------
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

def playwright_monitor():
    state["browser_running"] = True
    time.sleep(1.5)
    
    os.makedirs(PROFILE_DIR, exist_ok=True)
    
    try:
        with sync_playwright() as p:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
                "--start-maximized",
            ]
            
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=PROFILE_DIR,
                    channel="chrome",
                    headless=False,
                    no_viewport=True,
                    args=launch_args,
                    ignore_default_args=["--enable-automation"],
                )
            except Exception:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=PROFILE_DIR,
                    channel="msedge",
                    headless=False,
                    no_viewport=True,
                    args=launch_args,
                    ignore_default_args=["--enable-automation"],
                )

            # Bot tespitlerini gizle
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['tr-TR', 'tr', 'en-US', 'en']
                });
            """)

            page = context.pages[0] if context.pages else context.new_page()
            page.goto("http://127.0.0.1:5001/")

            print("\n" + "="*55)
            print("[+] Tarayıcı hazır. Turnstile kutucuğunu işaretleyebilirsiniz.")
            print("="*55 + "\n")

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
                                    # input_value dinamik JS değerini alır
                                    val = el.input_value() or el.get_attribute("value")
                                    if val and len(val) > 20:
                                        found = val
                                        break
                            except Exception:
                                pass
                        if found:
                            break

                    if found and found != state["token"]:
                        print(f"\n[✔] Turnstile Token yakalandı: {found[:40]}...\n")
                        state["token"] = found
                        try:
                            for c in context.cookies():
                                session.cookies.set(c['name'], c['value'], domain=c['domain'])
                        except Exception:
                            pass
                except Exception:
                    pass
    except Exception as e:
        print("[!] Tarayıcı izleme hatası:", e)
    finally:
        state["browser_running"] = False

if __name__ == "__main__":
    t = threading.Thread(target=playwright_monitor, daemon=True)
    t.start()
    app.run(port=5001, debug=False)
