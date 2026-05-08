# 🛠️ Operations Manual

This document contains everything you need to operate, maintain, and recover the auto-poster system.

---

## 📋 Daily / Weekly Checks

### Quick Health Check
1. View `STATUS.md` (auto-updated each run) — should show 🟢 HEALTHY
2. View latest GitHub Actions run → Job Summary tab shows full report
3. Check Facebook page — recent posts should look quality

### Weekly
- Skim engagement data in `data/engagement.jsonl`
- Verify no consecutive failures in STATUS.md
- Check token expiry warning (if < 14 days, renew)

---

## 🔐 Facebook Token Management

### How Long Tokens Last
- **User Access Token**: 1 hour (don't use)
- **Long-lived User Token**: 60 days
- **Page Access Token (long-lived)**: Never expires (recommended!)

### Renewing Token (when STATUS.md warns)

#### Method 1: Get a Never-Expiring Page Token (RECOMMENDED)
1. Go to https://developers.facebook.com/tools/explorer/
2. Select your app from the dropdown
3. Click **"Get Token"** → **"Get User Access Token"**
4. Check permissions: `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`
5. Click **Generate Access Token**
6. Copy the user token, then:
   ```
   curl "https://graph.facebook.com/v22.0/oauth/access_token?grant_type=fb_exchange_token&client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET&fb_exchange_token=USER_TOKEN"
   ```
7. With the long-lived user token, get the page token:
   ```
   curl "https://graph.facebook.com/v22.0/me/accounts?access_token=LONG_LIVED_USER_TOKEN"
   ```
8. Copy `access_token` from your page entry — **this never expires**
9. Update GitHub secret `FACEBOOK_ACCESS_TOKEN`

---

## 🌐 Configuring Content Sources

### `ARCHIVE_SOURCES` Secret Format

Comma-separated list. Mix and match:

**Archive.org collections (full URLs):**
- `https://archive.org/details/clevelandart`
- `https://archive.org/details/metropolitanmuseumofart-gallery`
- `https://archive.org/details/david-rumsey-map-collection`
- `https://archive.org/details/propix`
- `https://publicdomainreview.org/collections/all/`

**Special keywords (no URL needed):**
- `loc` — Library of Congress (16M+ items)
- `nasa` — NASA Image Library (140K+ items)
- `met` — Metropolitan Museum direct API (492K+ public domain)
- `smithsonian` — Smithsonian Open Access (4.5M+, needs API key)

**Recommended setup (10 sources for maximum variety):**
```
https://archive.org/details/clevelandart,https://archive.org/details/metropolitanmuseumofart-gallery,https://archive.org/details/david-rumsey-map-collection,https://archive.org/details/propix,https://publicdomainreview.org/collections/all/,loc,nasa,met,smithsonian
```

### Optional: Smithsonian API Key (free)
1. Sign up at https://api.data.gov/signup/
2. Add as GitHub secret `SMITHSONIAN_API_KEY`
3. Without it, Smithsonian uses heavily rate-limited DEMO_KEY (still works for low volume)

---

## 🤖 AI Provider Setup

### Groq (Primary, Recommended)
- Get key at https://console.groq.com/keys (free, no card)
- Add as GitHub secret `GROQ_API_KEY`
- Free tier: 14,400 requests/day

### OpenRouter (Fallback)
- Get key at https://openrouter.ai/keys
- Add as GitHub secret `OPENROUTER_API_KEY`
- Free tier: ~50 requests/day per model (8 models in chain = 400/day)

---

## 🚨 Troubleshooting

### "All AI providers failed - using fallback caption"
- Both Groq AND all 7 OpenRouter models hit rate limits or are down
- Usually transient — next run will recover
- If persistent: regenerate API keys

### "Facebook connection failed"
1. Token expired (check STATUS.md)
2. Page ID incorrect
3. App permissions revoked
- **Fix:** Renew token using procedure above

### "Validated 0 images" from a source
- Source may be blocking the bot's User-Agent
- Source's API may be temporarily down
- Other sources will compensate

### Posts have wrong/generic captions
- AI is using fallback because metadata was poor
- Check that source is providing rich titles/descriptions
- Some archive items have minimal metadata — system will skip these on next pick

### Workflow runs but doesn't post
- Check Actions tab → click latest run → expand "Run automation"
- Look for the specific error in logs
- STATUS.md will also show last failure reason

### Database conflicts
- If you see "git push rejected" repeatedly, manually:
  ```
  git pull --rebase origin master
  git push
  ```

---

## 🔄 Backup & Recovery

### Database Files (in repo)
- `data/image_database.db` — posted URLs (deduplication)
- `data/nsfw_detector.db` — NSFW history
- `data/runs.jsonl` — every run logged
- `data/engagement.jsonl` — FB engagement metrics
- `STATUS.md` — current health snapshot

### Disaster Recovery
If repo gets corrupted or DB is lost:
1. Clone fresh from GitHub
2. Database state will be restored from latest commit
3. Rotation/dedup will resume normally

### Manual DB Inspection
```sql
sqlite3 data/image_database.db
.schema images
SELECT source, COUNT(*) FROM images WHERE post_count > 0 GROUP BY source;
```

---

## ⚙️ Tunable Parameters (env vars in workflow)

| Variable | Default | Effect |
|----------|---------|--------|
| `ENABLE_WATERMARK` | `true` | Add credit overlay to images |
| `ENABLE_ENHANCE` | `true` | Auto-contrast/sharpen old scans |
| `WATERMARK_TEXT` | source name | Default watermark text |
| `MIN_POST_INTERVAL_HOURS` | `4` | Min hours between posts (continuous mode) |
| `MAX_POST_INTERVAL_HOURS` | `12` | Max hours between posts |
| `MAX_IMAGES_PER_POST` | `1` | Single image per post (carousel disabled) |
| `BLOCK_ON_MEDIUM_RISK` | `true` | NSFW: block borderline content |
| `NSFW_STRICT_MODE` | `true` | Use strict NSFW detection |

---

## 📈 Performance Expectations

- **Time per post:** 60-120 seconds
- **Storage growth:** ~1MB/month (databases)
- **API quota usage:**
  - Groq: ~3% of free daily (8 posts × 1 request)
  - FB Graph: ~0.1% of rate limit
  - Archive.org: well within fair-use
- **Success rate target:** 95%+ (failures are usually rate limits or transient)

---

## 🔮 Future Enhancements (TODO)

- [ ] Instagram cross-posting (uses same FB token)
- [ ] Telegram failure alerts
- [ ] Web admin UI (Flask/Streamlit)
- [ ] Comment auto-response with LLM
- [ ] A/B caption testing
- [ ] Carousel posts (5 thematic images weekly)
- [ ] Content variety enforcement (topic rotation)

---

_Last updated: 2026-05-08_
