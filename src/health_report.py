"""
Self-monitoring health reporter.
- Logs each run to data/runs.jsonl
- Tracks consecutive failures
- Generates STATUS.md with system health
- All committed back to repo each run for visibility
"""
import os
import json
from datetime import datetime, timedelta
from pathlib import Path


class HealthReporter:
    def __init__(self, data_dir: str = '../data'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.runs_file = self.data_dir / 'runs.jsonl'
        self.status_file = Path('../STATUS.md')

    def log_run(self, status: str, details: dict = None):
        """Append a run record to runs.jsonl"""
        record = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'status': status,  # 'success', 'failure', 'skipped'
            'details': details or {}
        }
        try:
            with open(self.runs_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record) + '\n')
        except Exception as e:
            print(f"Failed to log run: {e}")

    def load_recent_runs(self, limit: int = 100) -> list:
        """Load the most recent N runs"""
        if not self.runs_file.exists():
            return []
        runs = []
        try:
            with open(self.runs_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            runs.append(json.loads(line))
                        except Exception:
                            continue
            return runs[-limit:]
        except Exception as e:
            print(f"Failed to load runs: {e}")
            return []

    def get_consecutive_failures(self) -> int:
        """Count consecutive recent failures (most recent first)"""
        runs = self.load_recent_runs(limit=50)
        count = 0
        for run in reversed(runs):
            if run.get('status') == 'failure':
                count += 1
            elif run.get('status') == 'success':
                break
        return count

    def generate_status_md(self):
        """Write STATUS.md summarizing system health"""
        runs = self.load_recent_runs(limit=200)
        now = datetime.utcnow()

        # Stats
        total = len(runs)
        successes = sum(1 for r in runs if r.get('status') == 'success')
        failures = sum(1 for r in runs if r.get('status') == 'failure')
        skipped = sum(1 for r in runs if r.get('status') == 'skipped')
        success_rate = (successes / total * 100) if total else 0

        consecutive_fails = self.get_consecutive_failures()

        # Last 24h
        cutoff_24h = now - timedelta(hours=24)
        last_24h = [r for r in runs if self._parse_ts(r.get('timestamp')) > cutoff_24h]
        last_24h_success = sum(1 for r in last_24h if r.get('status') == 'success')

        # Most recent run
        last_run = runs[-1] if runs else None
        last_success = next(
            (r for r in reversed(runs) if r.get('status') == 'success'), None
        )

        # Build health badge
        if consecutive_fails >= 5:
            health = "🔴 **CRITICAL** - 5+ consecutive failures"
        elif consecutive_fails >= 2:
            health = "🟠 **DEGRADED** - recent failures"
        elif success_rate >= 90:
            health = "🟢 **HEALTHY**"
        elif success_rate >= 75:
            health = "🟡 **OK**"
        else:
            health = "🟠 **NEEDS ATTENTION**"

        # Token info from last run
        token_info = ""
        if last_run and last_run.get('details', {}).get('token_days_remaining') is not None:
            days = last_run['details']['token_days_remaining']
            if days < 0:
                token_info = "✅ Long-lived (never expires)"
            elif days < 7:
                token_info = f"🚨 **EXPIRES IN {days:.1f} DAYS** - RENEW NOW"
            elif days < 14:
                token_info = f"⚠️ Expires in {days:.1f} days"
            elif days < 30:
                token_info = f"ℹ️ Expires in {days:.1f} days"
            else:
                token_info = f"✅ Valid for {days:.0f} more days"

        # Source breakdown
        source_counts = {}
        for r in runs:
            if r.get('status') == 'success':
                src = r.get('details', {}).get('source', 'unknown')
                source_counts[src] = source_counts.get(src, 0) + 1

        # Build markdown
        md = []
        md.append("# 🤖 Auto-Poster Status\n")
        md.append(f"_Last updated: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}_\n")
        md.append(f"## {health}\n")
        md.append("---\n")

        md.append("## 📊 Statistics\n")
        md.append(f"- **Total runs tracked:** {total}")
        md.append(f"- **Successes:** {successes} ({success_rate:.1f}%)")
        md.append(f"- **Failures:** {failures}")
        md.append(f"- **Skipped:** {skipped}")
        md.append(f"- **Consecutive failures:** {consecutive_fails}")
        md.append(f"- **Posts in last 24h:** {last_24h_success}")
        md.append("")

        md.append("## 🔐 Facebook Token\n")
        md.append(token_info or "_Status unknown_")
        md.append("")

        if last_success:
            md.append("## ✅ Last Successful Post\n")
            d = last_success.get('details', {})
            md.append(f"- **Time:** {last_success.get('timestamp', 'unknown')}")
            md.append(f"- **Title:** {d.get('title', 'unknown')}")
            md.append(f"- **Source:** {d.get('source', 'unknown')}")
            md.append(f"- **Image size:** {d.get('image_size', 'unknown')}")
            md.append(f"- **Post ID:** {d.get('post_id', 'unknown')}")
            md.append(f"- **AI model:** {d.get('ai_model', 'unknown')}")
            md.append("")

        if last_run and last_run.get('status') == 'failure':
            md.append("## ❌ Last Failure\n")
            d = last_run.get('details', {})
            md.append(f"- **Time:** {last_run.get('timestamp', 'unknown')}")
            md.append(f"- **Error:** `{d.get('error', 'unknown')}`")
            md.append(f"- **Stage:** {d.get('stage', 'unknown')}")
            md.append("")

        if source_counts:
            md.append("## 📚 Source Distribution\n")
            for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
                pct = count / successes * 100 if successes else 0
                md.append(f"- **{src}:** {count} posts ({pct:.1f}%)")
            md.append("")

        # Recent runs table (last 10)
        md.append("## 📜 Recent Runs (last 10)\n")
        md.append("| Time | Status | Source | Title |")
        md.append("|------|--------|--------|-------|")
        for r in runs[-10:][::-1]:
            ts = r.get('timestamp', '')[:19].replace('T', ' ')
            status_emoji = {'success': '✅', 'failure': '❌', 'skipped': '⏭️'}.get(r.get('status'), '❓')
            d = r.get('details', {})
            title = (d.get('title') or d.get('error') or '-')[:40]
            source = (d.get('source') or '-')[:20]
            md.append(f"| {ts} | {status_emoji} | {source} | {title} |")
        md.append("")

        md.append("---")
        md.append("_This file is auto-generated by the automation. Do not edit manually._")

        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(md))
            print(f"📊 Health report written to {self.status_file}")
        except Exception as e:
            print(f"Failed to write status: {e}")

    def _parse_ts(self, ts: str) -> datetime:
        try:
            if ts.endswith('Z'):
                ts = ts[:-1]
            return datetime.fromisoformat(ts)
        except Exception:
            return datetime.min
