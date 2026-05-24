#!/usr/bin/env python3
"""
🔥 AFFILIATE CONTENT PIPELINE — End-to-End Auto-Distributor
===========================================================
Download TikTok/IG videos → FFmpeg hash mod → AI Niche Detect → FB/IG Upload

Stack:
  TikTokDownloader (JoeanAmier) / yt-dlp  → Download no-watermark
  FFmpeg                                  → MD5 hash modification
  Omniroute Gemini API                    → Niche detection
  Meta Graph API                          → Upload to FB Pages & IG

Author: Vilona · BerkahKarya Digital
Version: 1.1.0 · 2026-05-24
"""

import os
import sys
import json
import time
import random
import hashlib
import subprocess
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Literal
from dataclasses import dataclass, field, asdict
import logging

# ─── CONFIG ────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config" / "affiliate_pipeline_config.json"
DB_PATH = BASE_DIR / "data" / "pipeline.db"
LOG_PATH = BASE_DIR / "logs" / "pipeline.log"
DOWNLOAD_DIR = BASE_DIR / "temp" / "downloads"
PROCESSED_DIR = BASE_DIR / "temp" / "processed"
AFFILIATE_DB = BASE_DIR / "data" / "affiliate_links"

# Niche folders → affiliate links
NICHE_FOLDERS = {
    "ootd_hijab":         "ootd_hijab/links.txt",
    "handphone":          "handphone/links.txt",
    "parfum":             "parfum/links.txt",
    "skincare":           "skincare/links.txt",
    "health":             "health/links.txt",
    "sepatu_sneakers":    "sepatu_sneakers/links.txt",
    "tas_wanita":         "tas_wanita/links.txt",
    "atasan_pria":        "atasan_pria/links.txt",
    "general_fashion":    "general_fashion/links.txt",
}

# Default config
DEFAULT_CONFIG = {
    "downloader": {
        "method": "tikwm_api",  # tiktokdownloader | ytdlp | direct
        "tiktokdownloader_api": "http://127.0.0.1:5555",
        "max_retries": 3,
    },
    "ffmpeg": {
        "video_codec": "copy",
        "audio_volume_db": -0.05,
        "audio_codec": "aac",
        "audio_bitrate": "128k",
        "add_noise_pct": 0.3,  # subtle noise for hash mod
    },
    "niche_detection": {
        "api_url": "http://127.0.0.1:20128/v1/chat/completions",
        "model": "gemini-2.5-flash",
        "temperature": 0.0,
        "max_tokens": 10,
    },
    "meta": {
        "access_token": "",
        "fb_page_ids": [],   # ["page_id_1", "page_id_2"]
        "ig_account_ids": [], # ["ig_user_id_1"]
        "upload_endpoint_fb": "https://graph.facebook.com/v19.0/{page_id}/videos",
        "upload_endpoint_ig": "https://graph.facebook.com/v19.0/{ig_user_id}/media",
    },
    "anti_spam": {
        "same_account_delay_min": 45,
        "same_account_delay_max": 120,
        "cross_account_delay_min": 10,
        "cross_account_delay_max": 25,
        "max_videos_per_account_per_day": 4,
        "organic_ratio": 5,  # 1:5 = every 5th post has NO affiliate link
    },
    "queue": {
        "max_daily_total": 50,
        "processing_hours_start": 6,
        "processing_hours_end": 23,
    },
}

# ─── LOGGING ───────────────────────────────────────────────────────
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("pipeline")


# ─── DATA STRUCTURES ───────────────────────────────────────────────
@dataclass
class VideoItem:
    source_url: str
    local_path: str = ""
    caption_original: str = ""
    niche: str = "general_fashion"
    affiliate_link: str = ""
    hash_before: str = ""
    hash_after: str = ""
    status: str = "pending"  # pending | downloaded | processed | uploaded | failed
    platform: str = ""        # tiktok | instagram
    uploaded_url: str = ""
    uploaded_platform: str = ""  # facebook | instagram
    uploaded_account: str = ""
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ─── DATABASE ──────────────────────────────────────────────────────
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT UNIQUE,
            local_path TEXT,
            caption_original TEXT,
            niche TEXT DEFAULT 'general_fashion',
            affiliate_link TEXT,
            hash_before TEXT,
            hash_after TEXT,
            status TEXT DEFAULT 'pending',
            platform TEXT,
            uploaded_url TEXT,
            uploaded_platform TEXT,
            uploaded_account TEXT,
            error TEXT,
            created_at TEXT,
            processed_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS upload_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT,
            platform TEXT,
            video_source TEXT,
            upload_url TEXT,
            niche TEXT,
            has_affiliate BOOLEAN,
            uploaded_at TEXT DEFAULT (datetime('now')),
            status TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_counters (
            date TEXT PRIMARY KEY,
            account_id TEXT,
            count INTEGER DEFAULT 0,
            UNIQUE(date, account_id)
        )
    """)
    conn.commit()
    return conn


# ─── CONFIG MANAGEMENT ─────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return DEFAULT_CONFIG


# ─── 1. DOWNLOADER ─────────────────────────────────────────────────
class VideoDownloader:
    """Download TikTok/IG videos without watermark."""

    def __init__(self, config: dict):
        self.config = config
        self.method = config["downloader"]["method"]
        self.max_retries = config["downloader"]["max_retries"]
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    def download(self, url: str) -> Optional[Path]:
        """Download video, return local path or None."""
        for attempt in range(self.max_retries):
            try:
                if self.method == "tiktokdownloader":
                    return self._download_via_tiktokdownloader(url)
                elif self.method == "ytdlp":
                    return self._download_via_ytdlp(url)
                else:
                    return self._download_direct(url)
            except Exception as e:
                log.warning(f"Download attempt {attempt+1}/{self.max_retries} failed: {e}")
                time.sleep(2 ** attempt)
        return None

    def _download_via_tiktokdownloader(self, url: str) -> Optional[Path]:
        """Use JoeanAmier/TikTokDownloader Web API (port 5555)."""
        import requests
        api = self.config["downloader"]["tiktokdownloader_api"]
        resp = requests.post(f"{api}/download", json={"url": url}, timeout=60)
        if resp.status_code != 200:
            raise Exception(f"TikTokDownloader API error: {resp.status_code}")

        data = resp.json()
        video_url = data.get("video_url") or data.get("download_url")
        if not video_url:
            raise Exception("No video URL in response")

        # Download the actual file
        video_resp = requests.get(video_url, timeout=120, stream=True)
        ext = ".mp4"
        local_path = DOWNLOAD_DIR / f"tt_{int(time.time())}_{random.randint(1000,9999)}{ext}"
        with open(local_path, "wb") as f:
            for chunk in video_resp.iter_content(chunk_size=8192):
                f.write(chunk)

        log.info(f"Downloaded via TikTokDownloader: {local_path.name}")
        return local_path

    def _download_via_ytdlp(self, url: str) -> Optional[Path]:
        """Use yt-dlp as fallback."""
        output_template = str(DOWNLOAD_DIR / "%(id)s.%(ext)s")
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--no-warnings",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "-o", output_template,
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise Exception(f"yt-dlp failed: {result.stderr[:200]}")

        # Find downloaded file
        video_id = self._extract_video_id(url)
        candidates = sorted(DOWNLOAD_DIR.glob(f"{video_id}*"), key=os.path.getmtime, reverse=True)
        if not candidates:
            candidates = sorted(DOWNLOAD_DIR.glob("*.mp4"), key=os.path.getmtime, reverse=True)

        if candidates:
            log.info(f"Downloaded via yt-dlp: {candidates[0].name}")
            return candidates[0]
        raise Exception("Downloaded file not found")

    def _download_direct(self, url: str) -> Optional[Path]:
        """Direct download fallback."""
        import requests
        resp = requests.get(url, timeout=60, stream=True)
        local_path = DOWNLOAD_DIR / f"dl_{int(time.time())}.mp4"
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return local_path

    @staticmethod
    def _extract_video_id(url: str) -> str:
        """Extract video ID from TikTok/IG URL."""
        import re
        # TikTok: /video/123456789
        m = re.search(r'/video/(\d+)', url)
        if m: return m.group(1)
        # Instagram: /reel/XXXXX or /p/XXXXX
        m = re.search(r'/(?:reel|p)/([^/?]+)', url)
        if m: return m.group(1)
        return hashlib.md5(url.encode()).hexdigest()[:12]


# ─── 2. FFMPEG HASH MODIFIER ───────────────────────────────────────
class HashModifier:
    """Modify MD5 hash without visible quality loss."""

    def __init__(self, config: dict):
        self.cfg = config["ffmpeg"]
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_hash(filepath: Path) -> str:
        return hashlib.md5(filepath.read_bytes()).hexdigest()

    def modify(self, input_path: Path) -> Optional[Path]:
        """Apply FFmpeg tweaks to change MD5 hash."""
        output_path = PROCESSED_DIR / f"mod_{int(time.time())}_{input_path.name}"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-c:v", self.cfg["video_codec"],
            "-af", f"volume={self.cfg['audio_volume_db']}dB",
            "-c:a", self.cfg["audio_codec"],
            "-b:a", self.cfg["audio_bitrate"],
            "-movflags", "+faststart",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            log.error(f"FFmpeg error: {result.stderr[:300]}")
            return None

        hash_before = self.get_hash(input_path)
        hash_after = self.get_hash(output_path)

        if hash_before == hash_after:
            log.warning("Hash unchanged, applying noise injection...")
            return self._inject_noise(output_path)

        log.info(f"Hash modified: {hash_before[:12]}... → {hash_after[:12]}...")
        return output_path

    def _inject_noise(self, filepath: Path) -> Path:
        """Fallback: inject imperceptible noise to change hash."""
        tmp = filepath.with_suffix(".tmp.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", str(filepath),
            "-vf", "noise=alls=1:allf=t",
            "-c:v", "libx264", "-crf", "18",
            "-c:a", "copy",
            str(tmp),
        ]
        subprocess.run(cmd, capture_output=True, timeout=120)
        tmp.replace(filepath)
        return filepath


# ─── 3. AI NICHE DETECTION ─────────────────────────────────────────
class NicheDetector:
    """Detect product niche from video caption using Omniroute/Gemini."""

    VALID_NICHES = list(NICHE_FOLDERS.keys())

    def __init__(self, config: dict):
        self.cfg = config["niche_detection"]
        self.api_url = self.cfg["api_url"]

    def detect(self, caption: str) -> str:
        """Classify caption into a niche folder."""
        if not caption or len(caption.strip()) < 5:
            return "general_fashion"

        prompt = (
            f"Classify this TikTok caption into EXACTLY ONE category.\n"
            f"Categories: {', '.join(self.VALID_NICHES)}\n"
            f"Reply ONLY with the category name, nothing else.\n\n"
            f"Caption: {caption[:500]}"
        )

        try:
            import requests
            resp = requests.post(
                self.api_url,
                json={
                    "model": self.cfg["model"],
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.cfg["temperature"],
                    "max_tokens": self.cfg["max_tokens"],
                },
                timeout=15,
            )
            if resp.status_code == 200:
                niche = resp.json()["choices"][0]["message"]["content"].strip().lower()
                if niche in self.VALID_NICHES:
                    log.info(f"Niche detected: {niche}")
                    return niche
        except Exception as e:
            log.warning(f"Niche detection failed: {e}")

        log.info(f"Niche: general_fashion (fallback)")
        return "general_fashion"

    def detect_local(self, caption: str) -> str:
        """Local keyword-based fallback (no API call needed)."""
        c = caption.lower()
        keywords = {
            "sepatu_sneakers": ["sepatu", "sneakers", "sepatu", "sneaker", "sepatu sneakers", "nike", "adidas", "vans", "converse"],
            "ootd_hijab": ["hijab", "hijaber", "kerudung", "jilbab", "pashmina", "ootd hijab", "gamishijab"],
            "tas_wanita": ["tas", "handbag", "sling bag", "tote bag", "backpack wanita", "dompet"],
            "atasan_pria": ["kemeja", "kaos pria", "jaket pria", "celana pria", "atasan pria", "polo"],
        }
        for niche, kws in keywords.items():
            if any(kw in c for kw in kws):
                return niche
        return "general_fashion"


# ─── 4. AFFILIATE LINK ASSIGNER ────────────────────────────────────
class LinkAssigner:
    """Assign random affiliate link based on detected niche."""

    def __init__(self):
        AFFILIATE_DB.mkdir(parents=True, exist_ok=True)
        # Auto-create folders if missing
        for niche in NICHE_FOLDERS:
            folder = AFFILIATE_DB / niche
            folder.mkdir(parents=True, exist_ok=True)
            links_file = folder / "links.txt"
            if not links_file.exists():
                links_file.write_text("# Add affiliate links here, one per line\n")

    def get_link(self, niche: str) -> str:
        """Get random affiliate link from niche folder."""
        links_file = AFFILIATE_DB / NICHE_FOLDERS.get(niche, "general_fashion/links.txt")
        fallback = AFFILIATE_DB / "general_fashion/links.txt"

        for path in [links_file, fallback]:
            if path.exists():
                lines = [l.strip() for l in path.read_text().splitlines()
                        if l.strip() and not l.strip().startswith("#")]
                if lines:
                    return random.choice(lines)

        return "https://lynk.id/jendralbot"  # ultimate fallback

    def list_links(self, niche: str) -> list:
        links_file = AFFILIATE_DB / NICHE_FOLDERS.get(niche, "general_fashion/links.txt")
        if links_file.exists():
            return [l.strip() for l in links_file.read_text().splitlines()
                   if l.strip() and not l.strip().startswith("#")]
        return []


# ─── 5. CAPTION GENERATOR ──────────────────────────────────────────
class CaptionGenerator:
    """Generate organic and affiliate captions."""

    CLICKBAIT_HOOKS = [
        "Wah ini keren banget sih! 🔥",
        "Ngeliat ini langsung pengen beli 😭",
        "Gila... ini game changer banget",
        "Buat yang nanya-nanya, ini link-nya 👇",
        "Akhirnya ketemu juga yang kayak gini",
        "Gak nyangka sebagus ini...",
        "Rekomendasi banget nih buat kalian ✨",
        "Jujurly ini worth it banget",
        "Udah nyobain sendiri dan emang oke",
        "Kalau kalian cari yang model gini, ini ⬇️",
    ]

    ENGAGEMENT_PROMPTS = [
        "Menurut kalian gimana nih? 👀",
        "Ada yang udah pernah coba?",
        "Kira-kira cocok gak ya?",
        "Rate 1-10 dong! 🔥",
        "Mana yang lebih cocok menurut kalian?",
        "Comment dong pendapat kalian!",
        "Ada yang suka model gini juga? 🙋",
        "Spill dong pengalaman kalian!",
    ]

    def generate_affiliate(self, niche: str, link: str) -> str:
        """Generate caption WITH affiliate link."""
        hook = random.choice(self.CLICKBAIT_HOOKS)
        niche_hashtags = {
            "sepatu_sneakers": "#sepatu #sneakers #fashion #ootd #sepatumurah #sepatukeren",
            "ootd_hijab": "#hijab #ootdhijab #fashionhijab #hijabers #kerudung #stylehijab",
            "tas_wanita": "#tas #fashion #taswanita #handbag #totebag #aksesoris",
            "atasan_pria": "#fashionpria #kaos #kemeja #ootdpria #stylepria",
            "general_fashion": "#fashion #ootd #style #trending #viral",
        }
        hashtags = niche_hashtags.get(niche, "#fashion #trending #viral")
        return f"{hook}\n\n{link}\n\n{hashtags}"

    def generate_organic(self, niche: str) -> str:
        """Generate caption WITHOUT affiliate link (engagement bait)."""
        prompt = random.choice(self.ENGAGEMENT_PROMPTS)
        return f"{prompt}\n\n#fyp #foryou #trending #viral"


# ─── 6. META UPLOADER ──────────────────────────────────────────────
class MetaUploader:
    """Upload videos to Facebook Pages and Instagram."""

    def __init__(self, config: dict):
        self.cfg = config["meta"]
        self.token = self.cfg["access_token"]
        self.fb_pages = self.cfg.get("fb_page_ids", [])
        self.ig_accounts = self.cfg.get("ig_account_ids", [])

    def upload_to_facebook(self, video_path: Path, caption: str, page_id: str) -> dict:
        """Upload video to Facebook Page."""
        import requests
        url = self.cfg["upload_endpoint_fb"].format(page_id=page_id)
        with open(video_path, "rb") as f:
            resp = requests.post(
                url,
                params={
                    "access_token": self.token,
                    "description": caption,
                },
                files={"source": f},
                timeout=180,
            )
        return resp.json()

    def upload_to_instagram(self, video_path: Path, caption: str, ig_user_id: str) -> dict:
        """Upload video to Instagram (via Graph API)."""
        import requests

        # Step 1: Create media container
        create_url = self.cfg["upload_endpoint_ig"].format(ig_user_id=ig_user_id)
        resp1 = requests.post(
            create_url,
            params={
                "access_token": self.token,
                "media_type": "REELS",
                "video_url": str(video_path),  # Must be publicly accessible URL
                "caption": caption,
            },
            timeout=30,
        )
        data1 = resp1.json()
        if "id" not in data1:
            return {"error": data1}

        # Step 2: Publish
        container_id = data1["id"]
        publish_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
        resp2 = requests.post(
            publish_url,
            params={
                "access_token": self.token,
                "creation_id": container_id,
            },
            timeout=30,
        )
        return resp2.json()

    def upload_all(self, video_path: Path, caption: str,
                   platforms: list = None) -> list:
        """Upload to all configured accounts, return results."""
        results = []
        targets = platforms or (self.fb_pages + self.ig_accounts)

        for account_id in targets:
            try:
                if account_id in self.ig_accounts:
                    result = self.upload_to_instagram(video_path, caption, account_id)
                    platform = "instagram"
                else:
                    result = self.upload_to_facebook(video_path, caption, account_id)
                    platform = "facebook"

                if "id" in result:
                    video_id = result["id"]
                    permalink = self._build_permalink(platform, account_id, video_id)
                    results.append({
                        "success": True,
                        "platform": platform,
                        "account": account_id,
                        "video_id": video_id,
                        "permalink": permalink,
                    })
                    log.info(f"✅ Uploaded to {platform}/{account_id}: {permalink}")
                else:
                    results.append({
                        "success": False,
                        "platform": platform,
                        "account": account_id,
                        "error": str(result),
                    })
                    log.error(f"❌ Failed {platform}/{account_id}: {result}")
            except Exception as e:
                results.append({"success": False, "platform": "unknown", "account": account_id, "error": str(e)})
                log.error(f"❌ Exception {account_id}: {e}")

        return results

    @staticmethod
    def _build_permalink(platform: str, account_id: str, video_id: str) -> str:
        if platform == "facebook":
            return f"https://facebook.com/{video_id}"
        elif platform == "instagram":
            return f"https://instagram.com/reel/{video_id}"
        return f"https://{platform}.com/{video_id}"


# ─── 7. ANTI-SPAM SCHEDULER ────────────────────────────────────────
class AntiSpamScheduler:
    """Manage upload timing to avoid Meta spam detection."""

    def __init__(self, config: dict, db_conn):
        self.cfg = config["anti_spam"]
        self.queue_cfg = config["queue"]
        self.conn = db_conn

    def get_delay(self, same_account: bool) -> int:
        """Get random delay in minutes."""
        if same_account:
            return random.randint(
                self.cfg["same_account_delay_min"],
                self.cfg["same_account_delay_max"],
            )
        return random.randint(
            self.cfg["cross_account_delay_min"],
            self.cfg["cross_account_delay_max"],
        )

    def can_upload(self, account_id: str) -> bool:
        """Check if account hasn't hit daily limit."""
        today = datetime.now().strftime("%Y-%m-%d")
        cursor = self.conn.execute(
            "SELECT count FROM daily_counters WHERE date=? AND account_id=?",
            (today, account_id),
        )
        row = cursor.fetchone()
        current = row[0] if row else 0
        return current < self.cfg["max_videos_per_account_per_day"]

    def record_upload(self, account_id: str):
        """Increment daily counter for account."""
        today = datetime.now().strftime("%Y-%m-%d")
        self.conn.execute("""
            INSERT INTO daily_counters (date, account_id, count)
            VALUES (?, ?, 1)
            ON CONFLICT(date, account_id) DO UPDATE SET count = count + 1
        """, (today, account_id))
        self.conn.commit()

    def is_in_processing_hours(self) -> bool:
        hour = datetime.now().hour
        return self.queue_cfg["processing_hours_start"] <= hour <= self.queue_cfg["processing_hours_end"]

    def should_use_organic(self, account_id: str) -> bool:
        """Check if this post should be organic (1:N ratio)."""
        today = datetime.now().strftime("%Y-%m-%d")
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM upload_log WHERE date(uploaded_at)=? AND account_id=? AND has_affiliate=1",
            (today, account_id),
        )
        affiliate_count = cursor.fetchone()[0]
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM upload_log WHERE date(uploaded_at)=? AND account_id=? AND has_affiliate=0",
            (today, account_id),
        )
        organic_count = cursor.fetchone()[0]

        total = affiliate_count + organic_count
        if total == 0:
            return False

        expected_organic = max(1, total // self.cfg["organic_ratio"])
        return organic_count < expected_organic


# ─── 8. MAIN PIPELINE ──────────────────────────────────────────────
class AffiliatePipeline:
    """End-to-end TikTok → FB/IG affiliate content pipeline."""

    def __init__(self, config_path: Path = None):
        self.config = load_config()
        self.db = init_db()
        self.downloader = VideoDownloader(self.config)
        self.hash_mod = HashModifier(self.config)
        self.niche_detector = NicheDetector(self.config)
        self.link_assigner = LinkAssigner()
        self.caption_gen = CaptionGenerator()
        self.uploader = MetaUploader(self.config)
        self.scheduler = AntiSpamScheduler(self.config, self.db)

    def process_url(self, url: str, caption: str = "") -> VideoItem:
        """Process a single TikTok/IG URL through the full pipeline."""
        item = VideoItem(source_url=url, caption_original=caption)
        item.platform = "tiktok" if "tiktok.com" in url else "instagram"

        log.info(f"🚀 Processing: {url[:80]}")

        # Step 1: Download
        log.info("📥 Downloading...")
        local_path = self.downloader.download(url)
        if not local_path:
            item.status = "failed"
            item.error = "Download failed"
            self._save_item(item)
            return item
        item.local_path = str(local_path)
        item.hash_before = HashModifier.get_hash(local_path)
        item.status = "downloaded"

        # Step 2: FFmpeg hash modification
        log.info("🔧 Modifying hash...")
        processed_path = self.hash_mod.modify(local_path)
        if processed_path:
            item.local_path = str(processed_path)
            item.hash_after = HashModifier.get_hash(processed_path)
        else:
            item.hash_after = item.hash_before  # fallback to original

        # Step 3: Niche detection
        log.info("🧠 Detecting niche...")
        try:
            item.niche = self.niche_detector.detect(caption)
        except Exception:
            item.niche = self.niche_detector.detect_local(caption)

        # Step 4: Affiliate link
        item.affiliate_link = self.link_assigner.get_link(item.niche)
        item.status = "processed"
        log.info(f"✅ Processed: niche={item.niche}, link={item.affiliate_link[:50]}...")
        self._save_item(item)
        return item

    def distribute(self, item: VideoItem, accounts: list = None) -> list:
        """Upload processed video to FB/IG accounts with anti-spam rules."""
        results = []
        video_path = Path(item.local_path)
        if not video_path.exists():
            return [{"success": False, "error": "Video file not found"}]

        target_accounts = accounts or (self.uploader.fb_pages + self.uploader.ig_accounts)
        last_account = None

        for account_id in target_accounts:
            # Anti-spam checks
            if not self.scheduler.can_upload(account_id):
                log.info(f"⏭️ Skipping {account_id} — daily limit reached")
                continue

            # Determine organic vs affiliate
            is_organic = self.scheduler.should_use_organic(account_id)
            if is_organic:
                caption = self.caption_gen.generate_organic(item.niche)
                log.info(f"🌿 Organic post for {account_id}")
            else:
                caption = self.caption_gen.generate_affiliate(item.niche, item.affiliate_link)

            # Delay
            same = (account_id == last_account)
            delay_min = self.scheduler.get_delay(same)
            log.info(f"⏳ Waiting {delay_min}min before uploading to {account_id}...")
            time.sleep(delay_min * 60)

            # Upload
            log.info(f"📤 Uploading to {account_id}...")
            if account_id in self.uploader.ig_accounts:
                upload_result = self.uploader.upload_to_instagram(video_path, caption, account_id)
                platform = "instagram"
            else:
                upload_result = self.uploader.upload_to_facebook(video_path, caption, account_id)
                platform = "facebook"

            if "id" in upload_result:
                permalink = MetaUploader._build_permalink(platform, account_id, upload_result["id"])
                results.append({
                    "success": True,
                    "platform": platform,
                    "account": account_id,
                    "permalink": permalink,
                    "organic": is_organic,
                })
                self.scheduler.record_upload(account_id)
                item.uploaded_url = permalink
                item.uploaded_platform = platform
                item.uploaded_account = account_id
                item.status = "uploaded"
                self._save_item(item)
                self._log_upload(account_id, platform, item.source_url, permalink, item.niche, not is_organic, "success")
            else:
                results.append({
                    "success": False,
                    "platform": platform,
                    "account": account_id,
                    "error": str(upload_result),
                })
                self._log_upload(account_id, platform, item.source_url, "", item.niche, not is_organic, "failed")

            last_account = account_id

        return results

    def process_batch(self, urls: list, captions: dict = None) -> list:
        """Process multiple URLs and distribute."""
        results = []
        captions = captions or {}

        for i, url in enumerate(urls):
            if not self.scheduler.is_in_processing_hours():
                log.info("Outside processing hours, queuing remaining...")
                self._save_to_queue(urls[i:], captions)
                break

            caption = captions.get(url, "")
            item = self.process_url(url, caption)
            if item.status == "processed":
                dist_results = self.distribute(item)
                results.append({"url": url, "item": item, "upload": dist_results})
            else:
                results.append({"url": url, "item": item, "upload": [], "error": item.error})

        return results

    def generate_report(self) -> str:
        """Generate upload report."""
        today = datetime.now().strftime("%Y-%m-%d")
        cursor = self.db.execute(
            "SELECT uploaded_at, account_id, platform, uploaded_url, niche, has_affiliate, status "
            "FROM upload_log WHERE date(uploaded_at)=? ORDER BY uploaded_at DESC",
            (today,),
        )
        rows = cursor.fetchall()

        report = ["📊 AFFILIATE PIPELINE REPORT", f"📅 {today}", "=" * 50, ""]
        report.append("✅ BERHASIL DIPOSTING:")
        success_count = 0
        for row in rows:
            if row[6] == "success":
                success_count += 1
                report.append(
                    f"{success_count}. [{row[0]}] - {row[2].upper()} {row[1]} - "
                    f"{row[4]} - {'🔗' if row[5] else '🌿'} {row[3]}"
                )

        report.append("")
        report.append("⚠️ GAGAL/ERROR:")
        for row in rows:
            if row[6] != "success":
                report.append(f"  [{row[0]}] - {row[2]}/{row[1]} - {row[6]}")

        report.append("")
        report.append(f"Total berhasil: {success_count} | Gagal: {len(rows)-success_count}")
        return "\n".join(report)

    def _save_item(self, item: VideoItem):
        self.db.execute("""
            INSERT OR REPLACE INTO videos
            (source_url, local_path, caption_original, niche, affiliate_link,
             hash_before, hash_after, status, platform, uploaded_url,
             uploaded_platform, uploaded_account, error, created_at, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.source_url, item.local_path, item.caption_original,
            item.niche, item.affiliate_link, item.hash_before, item.hash_after,
            item.status, item.platform, item.uploaded_url,
            item.uploaded_platform, item.uploaded_account,
            item.error, item.created_at, datetime.now().isoformat(),
        ))
        self.db.commit()

    def _save_to_queue(self, urls: list, captions: dict):
        queue_file = BASE_DIR / "data" / "queue.json"
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if queue_file.exists():
            existing = json.loads(queue_file.read_text())
        for url in urls:
            existing.append({"url": url, "caption": captions.get(url, ""), "queued_at": datetime.now().isoformat()})
        queue_file.write_text(json.dumps(existing, indent=2))
        log.info(f"Queued {len(urls)} URLs for next processing window")

    def _log_upload(self, account_id, platform, source, upload_url, niche, has_affiliate, status):
        self.db.execute(
            "INSERT INTO upload_log (account_id, platform, video_source, upload_url, niche, has_affiliate, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (account_id, platform, source, upload_url, niche, has_affiliate, status),
        )
        self.db.commit()


# ─── CLI ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="🔥 Affiliate Content Pipeline")
    parser.add_argument("--url", help="Single TikTok/IG URL to process")
    parser.add_argument("--batch", help="File with URLs (one per line)")
    parser.add_argument("--report", action="store_true", help="Generate today's report")
    parser.add_argument("--init", action="store_true", help="Initialize config + DB")
    parser.add_argument("--add-links", nargs=2, metavar=("NICHE", "LINK"),
                       help="Add affiliate link to niche folder")
    parser.add_argument("--list-links", metavar="NICHE", help="List links for a niche")
    parser.add_argument("--capek", action="store_true", help="Turu dulu (quit)")

    args = parser.parse_args()
    pipeline = AffiliatePipeline()

    if args.init:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        init_db()
        LinkAssigner()
        print("✅ Pipeline initialized!")
        print(f"   Config: {CONFIG_PATH}")
        print(f"   DB: {DB_PATH}")
        print(f"   Affiliate DB: {AFFILIATE_DB}")
        print(f"\nEdit {CONFIG_PATH} to set Meta access token + account IDs")
        print(f"Add affiliate links to {AFFILIATE_DB}/*/links.txt")

    elif args.report:
        print(pipeline.generate_report())

    elif args.add_links:
        niche, link = args.add_links
        if niche not in NICHE_FOLDERS:
            print(f"❌ Invalid niche. Choose: {list(NICHE_FOLDERS.keys())}")
            sys.exit(1)
        links_file = AFFILIATE_DB / NICHE_FOLDERS[niche]
        links_file.parent.mkdir(parents=True, exist_ok=True)
        with open(links_file, "a") as f:
            f.write(f"{link}\n")
        print(f"✅ Added to {niche}: {link}")

    elif args.list_links:
        la = LinkAssigner()
        links = la.list_links(args.list_links)
        print(f"Links for {args.list_links}:")
        for link in links:
            print(f"  • {link}")

    elif args.batch:
        urls = [l.strip() for l in Path(args.batch).read_text().splitlines() if l.strip()]
        print(f"📦 Processing {len(urls)} URLs...")
        results = pipeline.process_batch(urls)
        print(pipeline.generate_report())

    elif args.url:
        item = pipeline.process_url(args.url)
        print(f"Status: {item.status}")
        print(f"Niche: {item.niche}")
        print(f"Link: {item.affiliate_link}")
        if item.status == "processed":
            results = pipeline.distribute(item)
            for r in results:
                if r["success"]:
                    print(f"✅ {r['platform']}: {r['permalink']}")
                else:
                    print(f"❌ {r['platform']}: {r['error']}")

    elif args.capek:
        print("😴 Turu dulu...")
        sys.exit(0)

    else:
        parser.print_help()

    log.info("Pipeline finished.")
