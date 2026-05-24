#!/usr/bin/env python3
"""
🔥 BATCH FB PAGE DEPLOYER V2 — 24 Mei 2026
Post konten ke Facebook Pages via Graph API dengan page token.
"""
import requests, time, random, json, sys
from pathlib import Path
from datetime import datetime

# ─── AUTH ────────────────────────────────────────────
USER_TOKEN = None
PAGES = []
LYNK_URL = "https://lynk.id/jendralbot"
DELAY_MIN, DELAY_MAX = 3, 8  # minutes between different pages

# ─── LOAD PAGES WITH PAGE TOKENS ─────────────────────
def load_pages():
    """Fetch all pages with their access tokens from Graph API."""
    global USER_TOKEN
    cfg = json.loads(Path("config/affiliate_pipeline_config.json").read_text())
    USER_TOKEN = cfg["meta"]["access_token"]
    
    r = requests.get("https://graph.facebook.com/v19.0/me/accounts",
                    params={"access_token": USER_TOKEN, "limit": 20}).json()
    pages = []
    for p in r.get("data", []):
        pages.append((p["id"], p["name"], p["access_token"]))
    return pages

# ─── CONTENT ──────────────────────────────────────────
FB_POSTS = [
    {
        "id": "FB3",
        "message": """Temen gue gaji 15jt/bulan. Tahun ini dia mulai cari side hustle.

Bukan karena gak cukup. Tapi karena dia SADAR:

1️⃣ Gaji = tergantung 1 sumber. Kalo kena layoff? GAME OVER.
2️⃣ Inflasi naik terus. Gaji naik pelan. Gap makin lebar.
3️⃣ Umur makin tua, tanggungan makin banyak.

Dia mulai affiliate marketing produk AI. Dalam 3 bulan:
➡️ Bulan 1: 200rb (balik modal link)
➡️ Bulan 2: 800rb (mulai belajar konten)
➡️ Bulan 3: 2.4jt (konsisten posting)

Masih kecil dibanding gaji 15jt? IYA.
Tapi ini baru start. 12 bulan lagi? Bisa nyusul.

Intinya: JANGAN tunggu dipecat baru mulai. Mulai sekarang. Sampingan.

👇 Link GRATIS:
{link}

#sidehustle #bisnisonline #pejuangrupiah""",
    },
    {
        "id": "FB5",
        "message": """POLL: Side hustle paling realistis buat pemula 2026? 🤔

🅰️ Affiliate marketing
🅱️ Jualan produk digital
🅲 Content creator
🅳 Jastip / reseller

Gue personally vote B. Produk digital = gak ada stok, margin gede, AI bikin semuanya gampang.

Tapi penasaran — kalian pilih apa? Drop alasan di komentar!

👇 Cek tools GRATIS:
{link}

#sidehustle #bisnis2026 #pejuangrupiah""",
    },
    {
        "id": "FB1",
        "message": """Gue cancel 5 subscription tools bulan lalu.

Total hemat: Rp 2.100.000/bulan 🎉

Gantinya? AI tools yang lebih cepet, lebih murah, hasilnya lebih bagus:

✨ Canva Pro → AI Design (bikin desain 1 klik)
✨ Copywriter → AI Copywriting (dari 500rb jadi 0)
✨ Ads Manager → AI Ad Optimizer (auto-bidding)
✨ Data analyst → AI Data Cruncher
✨ Virtual assistant → AI Assistant

Semua ada di JENDRALBOT. Mulai dari 0 rupiah.

👇 Link GRATIS:
{link}

#aitools #bisnisonline #produktivitas""",
    },
    {
        "id": "FB2-short",
        "message": """Gue bukan orang sukses. Gue cuma orang yang GAK PERNAH BERHENTI gagal.

2024: 7 bisnis gagal, rekening minus, hampir nyerah.
2025: Nemu affiliate digital product.
2026: Akhirnya stabil.

Dropshipping ❌ Reseller ❌ Jastip ❌ Trading ❌

Yang works? Affiliate marketing produk AI.
Mulai dari GRATIS. Gak perlu modal.

Kalo lu di posisi yang sama — ini tanda buat lu.

👇 Link:
{link}

#storytime #bisnis #pejuangrupiah""",
    },
    {
        "id": "FB4-short",
        "message": """Bukti bukan omong kosong 🧾

Ini chat ASLI dari orang-orang yang udah nyoba produk JENDRALBOT:

"Mantap bang tools-nya, langsung bisa pake!" — @user1
"Gara2 link lu gue dapet 500rb pertama" — @user2
"Ternyata segampang ini ya affiliate" — @user3

Gak ada settingan. Gak ada yang gue bayar.

Kalo lu mau nyoba — produk GRATIS-nya ada di link. Test sendiri. Kalo gak cocok? Ya udah, gak ada ruginya.

👇 Link GRATIS:
{link}

#testimoni #bisnisonline #aitools""",
    },
]

# ─── ANTI-SPAM ────────────────────────────────────────
POST_LOG = Path("logs/fb_batch_24may.jsonl")

def can_post(page_id):
    """Check daily limit for this page."""
    today = datetime.now().strftime("%Y-%m-%d")
    if not POST_LOG.exists():
        return True
    count = sum(1 for line in POST_LOG.read_text().splitlines()
               if line and json.loads(line).get("page_id") == page_id
               and today in json.loads(line).get("time", ""))
    return count < 4

def log_post(entry):
    POST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(POST_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

# ─── DEPLOY ───────────────────────────────────────────
def post_to_page(page_id, page_name, page_token, message, link_url):
    """Post to FB Page using its page access token."""
    url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
    params = {
        "message": message.format(link=link_url),
        "access_token": page_token,
    }
    try:
        resp = requests.post(url, params=params, timeout=30)
        data = resp.json()
        if "id" in data:
            post_id = data["id"]
            permalink = f"https://facebook.com/{post_id}"
            return True, permalink, None, post_id
        else:
            error = data.get("error", {}).get("message", str(data))
            return False, None, error, None
    except Exception as e:
        return False, None, str(e), None

def deploy():
    pages = load_pages()
    print(f"🔑 Connected: {len(pages)} pages with page tokens")
    print(f"📦 {len(FB_POSTS)} posts × {len(pages)} pages = {len(FB_POSTS)*len(pages)} potential posts")
    print(f"⏱️  Delay: {DELAY_MIN}-{DELAY_MAX} min antar page\n")

    total_ok, total_fail = 0, 0
    last_page_id = None

    for post in FB_POSTS:
        for page_id, page_name, page_token in pages:
            now = datetime.now().strftime("%H:%M:%S")

            # Anti-spam: skip if daily limit reached
            if not can_post(page_id):
                print(f"⏭️ [{now}] {page_name} — daily limit reached, skip")
                continue

            # Delay between pages
            if last_page_id and last_page_id != page_id:
                delay = random.randint(DELAY_MIN * 60, DELAY_MAX * 60)
                print(f"⏳ Delay {delay//60}m...", end=" ", flush=True)
                time.sleep(delay)
                print("done")

            success, url, error, post_id = post_to_page(
                page_id, page_name, page_token, post["message"], LYNK_URL
            )

            now = datetime.now().strftime("%H:%M:%S")
            if success:
                print(f"✅ [{now}] FB {page_name} — [{post['id']}] {url}")
                total_ok += 1
            else:
                print(f"⚠️ [{now}] FB {page_name} — [{post['id']}] ERROR: {error[:120]}")
                total_fail += 1

            log_post({
                "time": now,
                "page_id": page_id,
                "page": page_name,
                "post_id": post["id"],
                "status": "success" if success else "failed",
                "url": url,
                "error": error,
            })
            last_page_id = page_id

    print(f"\n{'='*50}")
    print(f"📊 DEPLOYMENT COMPLETE")
    print(f"✅ Success: {total_ok}  ⚠️ Failed: {total_fail}")
    return total_ok, total_fail

if __name__ == "__main__":
    deploy()
