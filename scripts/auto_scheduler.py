#!/usr/bin/env python3
"""
🔥 AUTO-SCHEDULER — Maintain momentum 24/7
Runs every 2 hours: scrape → download → hash mod → deploy → log
"""
import requests, json, time, random, re, subprocess
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent
CONFIG = BASE / "config/affiliate_pipeline_config.json"
PROFILE_DB = BASE / "data/known_profiles.json"
LOG_FILE = BASE / "logs/autoscheduler.log"
DOWNLOAD_DIR = BASE / "temp/downloads"
PROCESSED_DIR = BASE / "temp/processed"

# ─── Known TikTok fashion profiles ───
KNOWN_PROFILES = [
    "trendsandang.idn",
    "shankara_adw",
    "outfitgadiss",
    "sannii_94",
    "habsahstore",
    "affclip2",
    "darmawan9860",
    "ika.shop24",
    "cyra_sachi",
    "mariaibad",
    "sudartiindraaa",
]

SHOPEE_LINKS = [
    'https://s.shopee.co.id/AUqwO9d3kZ',
    'https://s.shopee.co.id/20sOGX9Q0f',
    'https://s.shopee.co.id/1Vw7fcBK1c',
    'https://s.shopee.co.id/7AaUQ1pkWF',
    'https://s.shopee.co.id/2VoerS7Vzm',
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}

def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def scrape_profile(profile):
    """Scrape video IDs from TikTok profile page."""
    try:
        r = requests.get(f"https://www.tiktok.com/@{profile}", headers=HEADERS, timeout=15)
        return list(set(re.findall(r'/video/(\d+)', r.text)))
    except:
        return []

def download_video(vid, profile):
    """Download via tikwm API + hash modify."""
    proc_path = PROCESSED_DIR / f"mod_{profile}_{vid}.mp4"
    if proc_path.exists():
        return str(proc_path)
    
    try:
        tik = requests.get("https://www.tikwm.com/api/",
                         params={"url": f"https://www.tiktok.com/@{profile}/video/{vid}"},
                         timeout=15).json()
        if tik.get("code") != 0 or not tik.get("data", {}).get("play"):
            return None
        
        dl_path = DOWNLOAD_DIR / f"{profile}_{vid}.mp4"
        dl_path.write_bytes(requests.get(tik["data"]["play"], timeout=60).content)
        
        subprocess.run(["ffmpeg","-y","-i",str(dl_path),"-c:v","copy",
                       "-af","volume=-0.05dB","-c:a","aac","-b:a","128k",
                       "-movflags","+faststart",str(proc_path)],
                      capture_output=True, timeout=60)
        return str(proc_path)
    except Exception as e:
        log(f"  Download error: {e}")
        return None

def deploy_to_fb(video_path, caption, pages):
    """Upload video to random subset of Facebook Pages."""
    ok, bad = 0, 0
    for p in random.sample(pages, min(3, len(pages))):
        try:
            r = requests.post(f"https://graph.facebook.com/v19.0/{p['id']}/videos",
                params={"access_token": p["access_token"], "description": caption},
                files={"source": open(video_path, "rb")}, timeout=120).json()
            if "id" in r:
                log(f"  ✅ {p['name']} — {p['id']} — facebook.com/{r['id']}")
                ok += 1
            else:
                log(f"  ⚠️ {p['name']} — {r.get('error',{}).get('message','?')[:80]}")
                bad += 1
        except Exception as e:
            log(f"  ⚠️ {p['name']} — {e}")
            bad += 1
        time.sleep(3)
    return ok, bad

def run_cycle():
    """One complete pipeline cycle."""
    log("🔄 AUTO-SCHEDULER CYCLE START")
    
    # Load config
    cfg = json.loads(open(CONFIG).read())
    
    # Get Facebook Pages
    r = requests.get("https://graph.facebook.com/v19.0/me/accounts",
                    params={"access_token": cfg["meta"]["access_token"], "limit": 16}).json()
    pages = r.get("data", [])
    log(f"📄 {len(pages)} pages loaded")
    
    total_downloaded = 0
    total_posted = 0
    
    # Process profiles (shuffle for variety)
    profiles = random.sample(KNOWN_PROFILES, min(5, len(KNOWN_PROFILES)))
    
    for profile in profiles:
        vids = scrape_profile(profile)
        if not vids:
            log(f"⏭️ @{profile} — 0 videos (TikTok block)")
            continue
        
        log(f"📥 @{profile} — {len(vids)} videos")
        
        for vid in vids[:5]:
            video_path = download_video(vid, profile)
            if not video_path:
                continue
            total_downloaded += 1
            
            # Generate caption
            link = random.choice(SHOPEE_LINKS)
            caption = f"Fashion viral dari @{profile}! 🔥\n\nRekomendasi outfit kekinian.\n\n👇 Cek Shopee:\n{link}\n\n#fashion #daster #viral #ootd"
            
            ok, bad = deploy_to_fb(video_path, caption, pages)
            total_posted += ok
    
    log(f"✅ CYCLE DONE — {total_downloaded} downloaded, {total_posted} posted")
    return total_posted

if __name__ == "__main__":
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    run_cycle()
