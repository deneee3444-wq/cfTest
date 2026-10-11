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
      max-width: 420px;
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
      margin-bottom: 16px;
      text-align: center;
    }
    /* Sadece Cloudflare Turnstile kutucuğunu çerçeveleyen kırpılmış alan */
    .cf-wrapper {
      width: 300px;
      height: 65px;
      overflow: hidden;
      position: relative;
      border-radius: 6px;
      border: 1px solid #e2e8f0;
      background: #fff;
      margin: 15px auto;
      box-shadow: 0 2px 6px rgba(0,0,0,0.06);
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
  <div class="subtitle">Aşağıdaki Turnstile kutucuğuna tıklayın:</div>

  <!-- SADECE CAPTCHA KISMI GÖRÜNÜR -->
  <div class="cf-wrapper">
    <iframe id="cf" src="https://www.yolly.ai/auth/signin?callbackUrl=http%3A%2F%2Fwww.yolly.ai%2Finvite"></iframe>
  </div>

  <div id="status" class="status-badge waiting">⏳ Captcha kutusunu işaretlemeniz bekleniyor...</div>

  <input id="email" type="email" placeholder="E-posta adresi girin">
  <button id="btn" disabled onclick="gonder()">Gönder</button>
  <pre id="out"></pre>

  <script>
    let currentToken = null;

    function applyToken(token) {
      if (!token) return;
      currentToken = token;
      document.getElementById('btn').disabled = false;
      const statusEl = document.getElementById('status');
      statusEl.className = 'status-badge ready';
      statusEl.textContent = '✔ Captcha çözüldü! Token alındı.';
      document.getElementById('out').textContent = 'Token: ' + token.substring(0, 45) + '...';
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
    }, 500);

    // Cross-frame mesajlarını da dinle
    window.addEventListener('message', (e) => {
      if (e.data) {
        let t = null;
        if (typeof e.data === 'string' && e.data.length > 30) t = e.data;
        else if (e.data.token && typeof e.data.token === 'string') t = e.data.token;
        else if (e.data.turnstileToken && typeof e.data.turnstileToken === 'string') t = e.data.turnstileToken;
        if (t) {
          applyToken(t);
          fetch('/set-token', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({token: t})
          }).catch(() => {});
        }
      }
    });

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

# Manuel token yükleme endpoint'i (uzaktan kullanım için)
@app.route("/set-token", methods=["POST"])
def set_token():
    data = request.get_json(force=True)
    state["token"] = data.get("token")
    return jsonify({"ok": True, "token": state["token"]})

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

def playwright_monitor(port=5001):
    state["browser_running"] = True
    time.sleep(2.0)
    
    is_render = os.environ.get("RENDER") is not None
    os.makedirs(PROFILE_DIR, exist_ok=True)
    
    try:
        with sync_playwright() as p:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
            ]
            if not is_render:
                launch_args.append("--start-maximized")

            headless_mode = True if is_render else False

            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=PROFILE_DIR,
                    channel="chrome" if not is_render else None,
                    headless=headless_mode,
                    no_viewport=True if not is_render else False,
                    args=launch_args,
                    ignore_default_args=["--enable-automation"],
                )
            except Exception:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=PROFILE_DIR,
                    headless=headless_mode,
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

            target_url = f"http://127.0.0.1:{port}/"
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(target_url)

            print("\n" + "="*55)
            print(f"[+] Tarayıcı hazır ({'Headless/Render' if is_render else 'Pencere'}). Hedef: {target_url}")
            print("[+] Turnstile kutucuğunu işaretleyebilirsiniz.")
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
                                # DOM property'si olarak dynamic value'yu çek
                                val = frame.evaluate("""
                                    () => {
                                        const el = document.querySelector('[name="cf-turnstile-response"]') || 
                                                   document.querySelector('input[name*="turnstile"]');
                                        if (el && el.value && el.value.length > 20) return el.value;
                                        if (window.turnstile && typeof window.turnstile.getResponse === 'function') {
                                            try {
                                                const resp = window.turnstile.getResponse();
                                                if (resp && resp.length > 20) return resp;
                                            } catch(e) {}
                                        }
                                        return null;
                                    }
                                """)
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
    port = int(os.environ.get("PORT", 5001))
    t = threading.Thread(target=playwright_monitor, args=(port,), daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=port, debug=False)
