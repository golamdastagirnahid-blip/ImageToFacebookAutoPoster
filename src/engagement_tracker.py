"""
Engagement analytics: fetch likes/comments/shares for past posts via FB Graph API.
Tracks which sources, eras, and topics get the best engagement.
Stores data in data/engagement.jsonl for trend analysis.
"""
import os
import json
import time
import requests
from datetime import datetime
from pathlib import Path


class EngagementTracker:
    def __init__(self, page_id: str, access_token: str, data_dir: str = '../data'):
        self.page_id = page_id
        self.access_token = access_token
        self.base_url = "https://graph.facebook.com/v22.0"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.engagement_file = self.data_dir / 'engagement.jsonl'

    def fetch_recent_posts(self, limit: int = 25) -> list:
        """Get recent posts with engagement metrics."""
        try:
            url = f"{self.base_url}/{self.page_id}/posts"
            params = {
                'access_token': self.access_token,
                'fields': 'id,message,created_time,permalink_url,'
                          'reactions.summary(total_count),'
                          'comments.summary(total_count),'
                          'shares',
                'limit': limit
            }
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json().get('data', [])
        except Exception as e:
            print(f"Engagement fetch failed: {e}")
            return []

    def update_engagement_log(self, runs_jsonl_path: str = '../data/runs.jsonl'):
        """
        Cross-reference recent FB posts with our run log to track per-source/per-AI engagement.
        Appends to engagement.jsonl with engagement deltas.
        """
        posts = self.fetch_recent_posts(limit=25)
        if not posts:
            print("No posts retrieved")
            return

        # Load run log to map post_id -> source/title metadata
        run_meta_by_post_id = {}
        try:
            if Path(runs_jsonl_path).exists():
                with open(runs_jsonl_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            r = json.loads(line.strip())
                            pid = r.get('details', {}).get('post_id')
                            if pid and pid != 'unknown':
                                run_meta_by_post_id[str(pid)] = r.get('details', {})
                        except Exception:
                            continue
        except Exception as e:
            print(f"Run log read error: {e}")

        snapshot_time = datetime.utcnow().isoformat() + 'Z'
        records = []
        for p in posts:
            pid = str(p.get('id', ''))
            reactions = (p.get('reactions') or {}).get('summary', {}).get('total_count', 0)
            comments = (p.get('comments') or {}).get('summary', {}).get('total_count', 0)
            shares = (p.get('shares') or {}).get('count', 0)
            engagement_score = reactions + (comments * 3) + (shares * 5)

            run_info = run_meta_by_post_id.get(pid, {})
            
            record = {
                'snapshot_time': snapshot_time,
                'post_id': pid,
                'created_time': p.get('created_time', ''),
                'reactions': reactions,
                'comments': comments,
                'shares': shares,
                'engagement_score': engagement_score,
                'source': run_info.get('source', 'unknown'),
                'title': (run_info.get('title') or p.get('message', '')[:100]),
                'permalink': p.get('permalink_url', ''),
            }
            records.append(record)

        # Append to engagement log
        try:
            with open(self.engagement_file, 'a', encoding='utf-8') as f:
                for r in records:
                    f.write(json.dumps(r) + '\n')
            print(f"📊 Engagement: logged {len(records)} posts")
        except Exception as e:
            print(f"Engagement write error: {e}")

        # Print summary
        if records:
            top = sorted(records, key=lambda x: x['engagement_score'], reverse=True)[:3]
            print("\n🏆 Top 3 posts by engagement:")
            for r in top:
                print(f"   {r['engagement_score']} pts: {r['title'][:60]} ({r['source']})")
            
            # Per-source averages
            from collections import defaultdict
            by_source = defaultdict(list)
            for r in records:
                if r['source'] != 'unknown':
                    by_source[r['source']].append(r['engagement_score'])
            if by_source:
                print("\n📈 Avg engagement by source:")
                for src, scores in sorted(by_source.items(), key=lambda x: -sum(x[1])/len(x[1])):
                    avg = sum(scores) / len(scores)
                    print(f"   {avg:.1f}: {src} ({len(scores)} posts)")

        return records

    def get_top_sources(self, lookback_days: int = 30) -> dict:
        """Return engagement-weighted source rankings for smart prioritization."""
        if not self.engagement_file.exists():
            return {}
        
        from collections import defaultdict
        from datetime import timedelta
        
        cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).isoformat()
        
        # Take most recent snapshot per post
        latest_by_post = {}
        try:
            with open(self.engagement_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        r = json.loads(line.strip())
                        if r.get('created_time', '') < cutoff:
                            continue
                        pid = r.get('post_id')
                        if pid:
                            latest_by_post[pid] = r
                    except Exception:
                        continue
        except Exception as e:
            print(f"Engagement read error: {e}")
            return {}
        
        by_source = defaultdict(list)
        for r in latest_by_post.values():
            src = r.get('source', 'unknown')
            if src != 'unknown':
                by_source[src].append(r['engagement_score'])
        
        return {src: sum(scores) / len(scores) for src, scores in by_source.items()}
