# Complete Workflow Guide

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     ENTERPRISE AUTOMATION SYSTEM                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   TRIGGER    │───▶│ HEALTH CHECK │───▶│ RATE LIMIT  │      │
│  │  (Scheduler) │    │  (Self-Heal) │    │   (Backoff)  │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                    │                    │              │
│         ▼                    ▼                    ▼              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ IMAGE SCRAPER │───▶│CONTENT FILTER│───▶│ APPROVAL    │      │
│  │  (PRO Mode)  │    │ (NSFW Check) │    │  WORKFLOW   │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                    │                    │              │
│         ▼                    ▼                    ▼              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ AI CONTENT   │───▶│  FACEBOOK    │───▶│ ANALYTICS   │      │
│  │  GENERATION  │    │   POSTING    │    │  TRACKING   │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                    │                    │              │
│         ▼                    ▼                    ▼              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  NOTIFICATION│    │   BACKUP     │    │  CLEANUP    │      │
│  │   SYSTEM     │    │   SYSTEM     │    │             │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Complete Workflow Step-by-Step

### Phase 1: Initialization

```
1. System Startup
   ├─ Load environment variables (.env)
   ├─ Initialize all enterprise components
   │  ├─ Health Monitor
   │  ├─ Content Filter
   │  ├─ Rate Limiter
   │  ├─ Token Manager
   │  ├─ Intelligent Scheduler
   │  ├─ Analytics Engine
   │  ├─ Notification System
   │  ├─ Backup System
   │  └─ Approval Workflow
   └─ Verify database integrity
```

### Phase 2: Pre-Flight Checks

```
2. Health Verification
   ├─ Check Facebook API connection
   ├─ Check OpenRouter API connection
   ├─ Check disk space availability
   ├─ Check token expiry (7-day warning)
   ├─ Check rate limit status
   └─ If any check fails:
      ├─ Attempt self-healing recovery
      ├─ Send alert notification
      └─ Either retry or abort based on severity
```

### Phase 3: Intelligent Scheduling

```
3. Optimal Time Calculation
   ├─ Query scheduler for optimal posting time
   ├─ Analyze historical engagement data
   ├─ Consider day of week patterns
   ├─ Consider hour-level performance
   ├─ Calculate next optimal window
   └─ Wait until optimal time (human-like delay)
```

### Phase 4: Rate Limit Verification

```
4. Rate Limit Check
   ├─ Check current request rate
   ├─ Verify within platform limits
   ├─ If rate limited:
      ├─ Calculate wait time (exponential backoff)
      ├─ Wait until allowed
      └─ Log rate limit event
   └─ Proceed if within limits
```

### Phase 5: Image Scraping (PRO Mode)

```
5. Image Discovery
   ├─ Select random archive sources
   ├─ Paginate through multiple pages (5 pages per source)
   ├─ Extract image URLs and metadata
   ├─ Download images in parallel (5 workers)
   ├─ Validate each image:
      │  ├─ Check resolution (800x600+)
      │  ├─ Check file size (50KB-10MB)
      │  ├─ Check format (JPEG/PNG preferred)
      │  └─ Calculate quality score (0-100)
   ├─ Filter by quality threshold
   ├─ Check for duplicates (database + content hash)
   ├─ Rank images by quality score
   └─ Select top images (1-3 images)
```

### Phase 6: Content Filtering

```
6. Safety Verification
   ├─ Check URL for suspicious patterns
   ├─ Scan text metadata for NSFW keywords
   ├─ Analyze image properties
   ├─ If AI filter enabled:
      │  └─ Run AI content analysis
   ├─ Calculate overall safety score
   ├─ If unsafe:
      ├─ Flag content
      ├─ Send alert notification
      └─ Skip to next image
   └─ If safe: proceed
```

### Phase 7: Content Approval (Optional)

```
7. Approval Workflow
   ├─ Submit content to approval queue
   ├─ Wait for reviewer approval
   ├─ If auto-approval enabled (score 90+):
      │  └─ Auto-approve immediately
   ├─ If manual approval:
      │  ├─ Notify reviewers
      │  ├─ Wait for decision
      │  ├─ If approved: proceed
      │  └─ If rejected: skip with reason
   └─ Mark as approved
```

### Phase 8: AI Content Generation

```
8. Caption & Hashtag Generation
   ├─ Prepare image context:
      │  ├─ Source archive
      │  ├─ Image title
      │  └─ Alt text/description
   ├─ Send to OpenRouter API
   ├─ Generate:
      │  ├─ Engaging description (2-3 sentences)
      │  ├─ 5-10 relevant hashtags
      │  └─ Short title
   ├─ Assemble full caption:
      │  ├─ Title (with emoji)
      │  ├─ Description
      │  ├─ Hashtags
      │  ├─ Credit line (source attribution)
      │  └─ Disclaimer (commercial use)
   └─ Return final caption
```

### Phase 9: Facebook Posting

```
9. Post to Facebook
   ├─ Verify Facebook token (check expiry)
   ├─ Upload image(s) to Facebook
   ├─ Add caption with metadata
   ├─ Publish post
   ├─ Record rate limit usage
   ├─ If successful:
      │  ├─ Get post ID
      │  ├─ Mark as posted in database
      │  ├─ Send success notification
      │  └─ Clear rate limit backoff
   └─ If failed:
      ├─ Trigger rate limit backoff
      ├─ Send failure notification
      └─ Log error for analysis
```

### Phase 10: Analytics Tracking

```
10. Performance Tracking
    ├─ Record post in analytics database:
    │  ├─ Post ID
    │  ├─ Platform (Facebook)
    │  ├─ Image URL
    │  ├─ Caption
    │  ├─ Posted timestamp
    │  ├─ Source archive
    │  ├─ Category
    │  └─ Quality score
    ├─ Record in scheduler for learning
    └─ Update token usage statistics
```

### Phase 11: Notifications

```
11. Alert System
    ├─ Send success notification:
    │  ├─ Discord webhook (if configured)
    │  ├─ Slack webhook (if configured)
    │  └─ Email (if configured)
    ├─ If any issues:
    │  ├─ Send failure notification
    │  ├─ Include error details
    │  └─ Alert relevant channels
    └─ Weekly analytics report (scheduled)
```

### Phase 12: Cleanup & Maintenance

```
12. Post-Processing
    ├─ Delete temporary image files
    ├─ Clean up cache (older than 24 hours)
    ├─ Record performance metrics
    ├─ Run database optimization
    └─ Calculate next optimal posting time
```

### Phase 13: Backup (Scheduled)

```
13. Automated Backup (Daily)
    ├─ Create backup directory with timestamp
    ├─ Backup all databases (6 databases):
    │  ├─ image_database.db
    │  ├─ health_monitor.db
    │  ├─ rate_limiter.db
    │  ├─ token_manager.db
    │  ├─ scheduler.db
    │  └─ analytics.db
    ├─ Backup directories:
    │  ├─ image_cache/
    │  └─ logs/
    ├─ Compress with GZIP
    ├─ Generate manifest with metadata
    ├─ Calculate SHA256 checksum
    ├─ Upload to cloud storage (if configured):
    │  ├─ AWS S3 (with encryption)
    │  └─ Google Cloud Storage
    ├─ Cleanup old backups (30-day retention)
    └─ Verify backup integrity
```

## Workflow Variations

### Basic Mode (Without Enterprise Features)

```
Trigger → Scrape → Download → Generate Caption → Post → Cleanup
```

### Enterprise Mode (Full Features)

```
Trigger → Health Check → Rate Limit → PRO Scraping → Content Filter → 
Approval Workflow → AI Generation → Post → Analytics → Notifications → 
Backup (scheduled) → Cleanup
```

### GitHub Actions Mode (Scheduled)

```
GitHub Trigger → Health Check → PRO Scraping → Content Filter → 
AI Generation → Post → Analytics → Cleanup → End
```

### Docker Mode (Containerized)

```
Container Start → Health Check → Continuous Loop → All Enterprise Features → 
Auto-restart on failure
```

## Data Flow Diagram

```
┌─────────────┐
│  SCHEDULER  │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ HEALTH CHECK│────▶│ RATE LIMITER │────▶│ IMAGE SCRAPER│
└──────┬──────┘     └──────┬───────┘     └──────┬──────┘
       │                   │                     │
       │                   ▼                     ▼
       │           ┌──────────────┐     ┌──────────────┐
       │           │ CONTENT      │────▶│ APPROVAL     │
       │           │ FILTER       │     │ WORKFLOW     │
       │           └──────┬───────┘     └──────┬──────┘
       │                  │                     │
       │                  ▼                     ▼
       │           ┌──────────────┐     ┌──────────────┐
       │           │ AI CONTENT   │────▶│ FACEBOOK     │
       │           │ GENERATOR    │     │ POSTER       │
       │           └──────┬───────┘     └──────┬──────┘
       │                  │                     │
       │                  ▼                     ▼
       │           ┌──────────────┐     ┌──────────────┐
       │           │ ANALYTICS    │────▶│ NOTIFICATION │
       │           │ ENGINE       │     │ SYSTEM       │
       │           └──────┬───────┘     └──────┬──────┘
       │                  │                     │
       │                  ▼                     ▼
       │           ┌──────────────┐     ┌──────────────┐
       └──────────▶│ BACKUP       │     │ CLEANUP      │
                   │ SYSTEM       │     │              │
                   └──────────────┘     └──────────────┘
```

## Timeline Example

### Single Post Cycle (Enterprise Mode)

```
Time 00:00 - Trigger fired by scheduler
Time 00:01 - Health checks completed (all healthy)
Time 00:02 - Rate limit verified (within limits)
Time 00:03 - Started scraping 5 sources
Time 00:15 - Scraped 250 images, downloaded in parallel
Time 00:16 - Quality filtering completed (50 images pass)
Time 00:17 - Duplicate check completed (45 unique)
Time 00:18 - Content filtering completed (43 safe)
Time 00:19 - Ranked by quality score
Time 00:20 - Selected top 3 images
Time 00:21 - Submitted to approval queue
Time 00:22 - Auto-approved (all scores 90+)
Time 00:23 - AI content generation completed
Time 00:24 - Posted to Facebook successfully
Time 00:25 - Analytics recorded
Time 00:26 - Success notifications sent
Time 00:27 - Cleanup completed
Time 00:28 - Next optimal time calculated (4 hours 37 minutes)
Time 00:29 - Cycle complete, waiting for next trigger
```

## Error Handling Workflow

```
Error Detected
    │
    ├─► Is it a known error type?
    │   ├─ Yes → Use specific recovery
    │   │   ├─ Network error → Retry with backoff
    │   │   ├─ API error → Check token, refresh if needed
    │   │   ├─ Rate limit → Wait and retry
    │   │   └─ Disk space → Cleanup and retry
    │   │
    │   └─ No → Log error, send alert
    │
    ├─► Recovery attempt successful?
    │   ├─ Yes → Continue workflow
    │   └─ No →
    │       ├─ Retry (max 3 attempts)
    │       └─ If still failed →
    │           ├─ Mark incident in database
    │           ├─ Send critical alert
    │           └─ Skip to next cycle
    │
    └─► Self-healing system monitors
        ├─ If recurring error → Escalate
        └─ If pattern detected → Preventive action
```

## Configuration Options

### Workflow Modes

**1. Basic Mode** (Simple, no enterprise features)
```bash
python src/automation.py
```

**2. Enterprise Mode** (Full features, self-healing)
```bash
python src/automation_enterprise.py
```

**3. GitHub Actions** (Scheduled, single post)
```yaml
# Runs automatically every 6 hours
# Single post per execution
# Uses enterprise features
```

**4. Docker** (Containerized, continuous)
```bash
docker-compose up -d
# Runs continuously with health checks
# Auto-restart on failure
```

### Approval Modes

**1. Auto-Post** (No approval)
```env
USE_APPROVAL_WORKFLOW=false
```

**2. Auto-Approve High Quality** (Score 90+)
```env
USE_APPROVAL_WORKFLOW=true
AUTO_APPROVE_THRESHOLD=90
```

**3. Manual Approval** (All content)
```env
USE_APPROVAL_WORKFLOW=true
AUTO_APPROVE_THRESHOLD=100  # Disable auto-approve
```

### Backup Modes

**1. Local Only**
```env
CLOUD_BACKUP_PROVIDER=local
```

**2. AWS S3**
```env
CLOUD_BACKUP_PROVIDER=s3
AWS_S3_BUCKET=your-bucket
```

**3. Google Cloud Storage**
```env
CLOUD_BACKUP_PROVIDER=gcs
GCS_BUCKET=your-bucket
```

## Monitoring & Observability

### Health Check Endpoints

The system continuously monitors:
- Facebook API connectivity
- OpenRouter API connectivity
- Disk space availability
- Database integrity
- Token expiry status
- Rate limit status

### Metrics Tracked

- Post success/failure rate
- Average post duration
- Image quality scores
- Scraping performance
- API response times
- Rate limit hits
- Token usage patterns

### Alerts Generated

- Health check failures
- Post failures
- Token expiry warnings
- Rate limit alerts
- Content flagging
- Backup failures
- System errors

## Summary

The workflow is designed to be:

1. **Self-Healing** - Automatically recovers from failures
2. **Self-Monitoring** - Continuous health checks
3. **Self-Optimizing** - Learns optimal posting times
4. **Self-Protecting** - Rate limiting prevents bans
5. **Quality-Focused** - Content filtering and approval
6. **Data-Safe** - Automated backups with verification
7. **Notified** - Multi-channel alert system

**Result:** A production-ready, enterprise-grade automation system that can run indefinitely with minimal human intervention while maintaining quality, safety, and reliability.
