# Image to Facebook Auto Poster

A free, automated system that scrapes public domain images from archives, generates AI-powered descriptions and hashtags, and posts them to Facebook with proper credits and disclaimers for commercial use.

**Now with Enterprise-Grade Features:** Self-healing, intelligent scheduling, analytics, and more!

## Features

### Core Features
- **Automated Image Scraping**: Fetches images from multiple public domain archives
- **AI-Powered Content**: Uses OpenRouter API to generate engaging descriptions and hashtags
- **Smart Scheduling**: Posts at randomized human-like intervals
- **Commercial Compliance**: Automatically adds credits and disclaimers
- **Free Forever**: Runs on GitHub Actions with generous free tier
- **Multiple Archive Sources**: Supports Internet Archive, Public Domain Review, and more

### Enterprise Features (NEW!)
- **🤖 Self-Healing System**: Automatic health checks with self-recovery
- **🛡️ Content Filtering**: NSFW detection and inappropriate content blocking
- **📊 Analytics Dashboard**: Track engagement and optimize performance
- **🧠 Intelligent Scheduling**: ML-based optimal posting times
- **🔐 Token Management**: Automatic token rotation and expiry tracking
- **⚡ Rate Limiting**: Intelligent backoff strategies to prevent bans
- **🔔 Multi-Channel Notifications**: Discord, Slack, Email alerts
- **🐳 Docker Support**: Containerized deployment for easy scaling

## Archive Sources

Currently configured to scrape from:
- David Rumsey Map Collection (Internet Archive)
- Metropolitan Museum of Art Gallery (Internet Archive)
- Propix Archive (Internet Archive)
- Cleveland Museum of Art (Internet Archive)
- The Public Domain Review

## Quick Start

### Basic Mode (Simple Setup)
```bash
# Install dependencies
pip install -r requirements.txt

# Configure .env file
cp .env.example .env
# Edit .env with your credentials

# Run
cd src
python automation.py
```

### Enterprise Mode (Full Features)
```bash
# Install dependencies
pip install -r requirements.txt

# Configure .env file with enterprise settings
cp .env.example .env
# Edit .env with your credentials AND enterprise settings (Discord, Slack, etc.)

# Run enterprise automation
cd src
python automation_enterprise.py
```

### Docker Deployment
```bash
# Build and run with Docker
docker-compose up -d

# Or with monitoring stack
docker-compose --profile monitoring up -d
```

## Prerequisites

1. **Facebook Page Access Token**
   - Go to [Facebook Developers](https://developers.facebook.com/)
   - Create an app and get a Page Access Token with `pages_read_engagement` and `pages_manage_posts` permissions
   - Note your Page ID

2. **OpenRouter API Key** (Free)
   - Sign up at [OpenRouter.ai](https://openrouter.ai/)
   - Get your API key (free tier available)
   - Uses free models like `mistralai/mistral-7b-instruct:free`

3. **GitHub Account** (Free)
   - Create a GitHub account if you don't have one
   - Fork this repository to your account

## Setup Instructions

### 1. Clone or Fork the Repository

```bash
git clone https://github.com/YOUR_USERNAME/ImageToFacebookAutoPoster.git
cd ImageToFacebookAutoPoster
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Facebook Configuration
FACEBOOK_ACCESS_TOKEN=your_facebook_access_token_here
FACEBOOK_PAGE_ID=your_facebook_page_id_here

# OpenRouter API Configuration
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=mistralai/mistral-7b-instruct:free

# Archive Sources (comma-separated)
ARCHIVE_SOURCES=https://archive.org/details/david-rumsey-map-collection?page=3,https://archive.org/details/metropolitanmuseumofart-gallery?page=4,https://archive.org/details/propix?page=4,https://archive.org/details/clevelandart?page=2,https://publicdomainreview.org/collections/all/

# Posting Configuration
MIN_POST_INTERVAL_HOURS=4
MAX_POST_INTERVAL_HOURS=12
MAX_IMAGES_PER_POST=3

# Credits and Disclaimer
CREDIT_TEXT=Image Source: {source}
DISCLAIMER_TEXT=Disclaimer: This image is used for commercial purposes under public domain or Creative Commons license. Source attribution provided.
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Test Locally (Optional)

Run a single post to test:

```bash
cd src
python automation.py
```

Or run continuous mode (posts at random intervals):

```bash
cd src
python automation.py
```

Press Ctrl+C to stop.

## GitHub Actions Setup (For Free Automation)

### 1. Push to GitHub

```bash
git add .
git commit -m "Initial setup"
git push origin main
```

### 2. Add Secrets to GitHub

Go to your repository on GitHub:
1. Click **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add the following secrets:

- `FACEBOOK_ACCESS_TOKEN`: Your Facebook access token
- `FACEBOOK_PAGE_ID`: Your Facebook page ID
- `OPENROUTER_API_KEY`: Your OpenRouter API key
- `ARCHIVE_SOURCES`: (Optional) Comma-separated list of archive URLs
- `OPENROUTER_MODEL`: (Optional) Model to use (default: `mistralai/mistral-7b-instruct:free`)
- `MIN_POST_INTERVAL_HOURS`: (Optional) Minimum interval (default: 4)
- `MAX_POST_INTERVAL_HOURS`: (Optional) Maximum interval (default: 12)
- `MAX_IMAGES_PER_POST`: (Optional) Max images per post (default: 3)
- `CREDIT_TEXT`: (Optional) Credit template
- `DISCLAIMER_TEXT`: (Optional) Disclaimer text

### 3. Enable GitHub Actions

The workflow is configured to run every 6 hours by default. To change this:
- Edit `.github/workflows/auto_post.yml`
- Modify the cron schedule: `cron: '0 */6 * * *'` (every 6 hours)
- Common schedules:
  - Every 4 hours: `0 */4 * * *`
  - Every 8 hours: `0 */8 * * *`
  - Twice daily: `0 0,12 * * *`
  - Once daily: `0 0 * * *`

### 4. Manual Trigger

To manually trigger a post:
- Go to **Actions** tab in your repository
- Select **Auto Post Images to Facebook**
- Click **Run workflow**

## Why GitHub Actions vs Google Apps Script?

**GitHub Actions is more reliable for this use case because:**

✅ **Generous Free Tier**: 2000 minutes/month for public repositories
✅ **Full Control**: Complete flexibility with Python and any libraries
✅ **Better Performance**: Faster execution, no quotas
✅ **More Flexible**: Can handle complex scraping and API integrations
✅ **Easier Debugging**: Better logs and error handling
✅ **No Platform Lock-in**: Move to any hosting platform anytime

Google Apps Script limitations:
❌ Quotas on execution time and API calls
❌ Limited to Google's ecosystem
❌ More restrictive for web scraping
❌ Harder to debug complex issues

## Enterprise Features Guide

### Self-Healing System
The system automatically detects and recovers from common failures:
- **Health Checks**: Monitors Facebook API, OpenRouter, disk space
- **Auto-Recovery**: Attempts to fix issues automatically
- **Incident Tracking**: Logs all incidents for review
- **Alerts**: Sends notifications when issues occur

### Content Filtering
Prevents posting inappropriate content:
- **NSFW Detection**: Keyword-based filtering
- **URL Safety**: Checks URLs for suspicious patterns
- **Image Analysis**: Validates image quality and properties
- **AI Integration**: Optional AI-based content analysis

### Intelligent Scheduling
Optimizes posting times based on engagement:
- **Learning**: Analyzes historical engagement data
- **Optimization**: Finds best posting times automatically
- **Time Zone Aware**: Considers audience location
- **Adaptive**: Adjusts based on performance

### Analytics Dashboard
Track and optimize performance:
- **Daily Summaries**: Posts, likes, comments, shares
- **Source Performance**: Which archives perform best
- **Category Analysis**: Content type performance
- **Optimization Suggestions**: Data-driven recommendations

### Token Management
Never worry about expired tokens:
- **Automatic Tracking**: Monitors token expiry
- **Rotation Alerts**: Notifies before tokens expire
- **Usage Analytics**: Tracks token usage patterns
- **Multi-Token Support**: Manage multiple tokens

### Rate Limiting
Prevent platform bans:
- **Intelligent Backoff**: Exponential backoff on failures
- **Request Tracking**: Monitors API usage
- **Automatic Throttling**: Respects platform limits
- **Recovery**: Automatically retries after backoff

### Notifications
Stay informed:
- **Discord**: Real-time alerts via webhook
- **Slack**: Integration with Slack webhooks
- **Email**: SMTP-based email notifications
- **Custom**: Support for custom webhooks

## Customization

### Adding New Archive Sources

Edit the `ARCHIVE_SOURCES` variable in `.env` or GitHub Secrets:

```env
ARCHIVE_SOURCES=https://archive.org/details/your-collection,https://your-source.com/images
```

### Changing Post Frequency

Edit `.github/workflows/auto_post.yml`:

```yaml
schedule:
  - cron: '0 */4 * * *'  # Every 4 hours
```

### Modifying AI Prompts

Edit `src/openrouter_client.py` to change the prompt for generating descriptions.

### Custom Credits/Disclaimer

Edit the `CREDIT_TEXT` and `DISCLAIMER_TEXT` in `.env`:

```env
CREDIT_TEXT=📷 Source: {source} | Public Domain
DISCLAIMER_TEXT=⚠️ Used for commercial purposes. All images are from public domain or have appropriate licenses.
```

## Project Structure

```
ImageToFacebookAutoPoster/
├── .github/
│   └── workflows/
│       └── auto_post.yml          # GitHub Actions workflow
├── src/
│   ├── __init__.py
│   ├── automation.py              # Main automation logic
│   ├── image_scraper.py           # Image scraping from archives
│   ├── openrouter_client.py       # OpenRouter API integration
│   └── facebook_poster.py         # Facebook API posting
├── .env.example                   # Environment template
├── .gitignore
├── requirements.txt               # Python dependencies
└── README.md
```

## Troubleshooting

### Facebook API Errors

- **Invalid Token**: Regenerate your access token from Facebook Developers
- **Insufficient Permissions**: Ensure your token has `pages_manage_posts` permission
- **Page Not Found**: Verify your Page ID is correct

### OpenRouter API Errors

- **Rate Limit**: Free tier has limits, consider upgrading or reducing post frequency
- **Invalid Key**: Verify your API key is correct
- **Model Not Available**: Try a different free model

### Scraping Issues

- **No Images Found**: Archive sources may have changed structure
- **Download Failed**: Check internet connectivity and image URLs
- **Rate Limited**: Add delays between requests in `image_scraper.py`

## License

This project is open source and free to use. Images posted are from public domain sources with proper attribution.

## Disclaimer

This tool is for educational purposes. Ensure you have proper rights to use images for commercial purposes. Always verify the license of each image source.

## Support

For issues and questions:
- Open an issue on GitHub
- Check the troubleshooting section above
- Review the logs in GitHub Actions

---

**Made with ❤️ for free automation**
