# 🔥 BerkahKarya Affiliate Pipeline

> TikTok → Download No-WM → FFmpeg Hash Mod → AI Niche → Shopee Link → FB/IG Upload

**Production-ready end-to-end affiliate content automation.**

---

## 🚀 Features

| Module | Description |
|--------|-------------|
| 📥 TikTok Scraper | Download videos without watermark via tikwm API |
| 🔧 Hash Modifier | FFmpeg-based MD5 hash modification (Meta-safe) |
| 🧠 Niche Detector | AI-powered (Omniroute) + local keyword fallback |
| 🔗 Link Assigner | Auto-pick from 27 Shopee affiliate links (5 niches) |
| ✍️ Caption Generator | Clickbait hooks + organic engagement (1:5 ratio) |
| 📤 Meta Uploader | 16 FB Pages + 5 IG via Graph API v19.0 |
| ⏱️ Anti-Spam | 45-120min delay, 4 posts/acct/day, random jitter |
| 📊 Reporter | Daily upload reports with permalink URLs |

---

## 📦 Quick Start

```bash
# Init
python3 scripts/affiliate_content_pipeline.py --init

# Add affiliate links
python3 scripts/affiliate_content_pipeline.py --add-links ootd_hijab "https://s.shopee.co.id/xxx"

# Deploy single TikTok video
python3 scripts/affiliate_content_pipeline.py --url "https://vt.tiktok.com/xxx"

# Deploy batch from file
python3 scripts/affiliate_content_pipeline.py --batch urls.txt

# Daily report
python3 scripts/affiliate_content_pipeline.py --report
```

---

## 🏗️ Architecture

```
TikTok Profile → Web Search (URLs) → tikwm API (download no-WM)
    ↓
FFmpeg (-c:v copy -af volume=-0.05dB) → unique MD5 hash
    ↓
Niche Detection → ootd_hijab / sepatu / tas / atasan_pria / general
    ↓
Random Shopee Link from niche folder (27 products, 3%-16.5% commission)
    ↓
Graph API v19.0 → 16 Facebook Pages + 5 Instagram Accounts
```

---

## 📊 Deployments

| Date | Videos | Posts | Success Rate |
|------|--------|-------|-------------|
| 2026-05-24 | 15+ | 128+ | 96%+ |

---

## ⚙️ Config

Edit `config/config.example.json`:
- Set Meta access token
- Add Facebook Page IDs
- Add Instagram account IDs
- Configure anti-spam delays

---

## 📁 Structure

```
berkahkarya-affiliate-pipeline/
├── config/
│   └── config.example.json
├── data/
│   └── affiliate_links/
│       ├── ootd_hijab/
│       ├── sepatu_sneakers/
│       ├── tas_wanita/
│       ├── atasan_pria/
│       └── general_fashion/
├── scripts/
│   ├── affiliate_content_pipeline.py
│   ├── fb_batch_deployer_v2.py
│   ├── batch_deploy_now.py
│   └── deploy_remaining_videos.py
├── docs/
└── README.md
```

---

*Built by Vilona · BerkahKarya Digital · 2026*
