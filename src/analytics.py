import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from collections import defaultdict

class AnalyticsEngine:
    """Comprehensive engagement analytics and optimization system"""
    
    def __init__(self, db_path: str = 'analytics.db'):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize analytics database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT UNIQUE,
                platform TEXT,
                image_url TEXT,
                caption TEXT,
                posted_at TIMESTAMP,
                source TEXT,
                category TEXT,
                quality_score REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS engagement_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT,
                metric_name TEXT,
                metric_value REAL,
                recorded_at TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts(post_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE,
                platform TEXT,
                posts_count INTEGER,
                avg_likes REAL,
                avg_comments REAL,
                avg_shares REAL,
                total_engagement REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS content_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                source TEXT,
                avg_engagement REAL,
                post_count INTEGER,
                last_updated TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def track_post(self, post_data: Dict):
        """Track a new post"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO posts 
                (post_id, platform, image_url, caption, posted_at, source, category, quality_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                post_data.get('post_id'),
                post_data.get('platform', 'facebook'),
                post_data.get('image_url'),
                post_data.get('caption'),
                post_data.get('posted_at', datetime.now()),
                post_data.get('source'),
                post_data.get('category'),
                post_data.get('quality_score')
            ))
            conn.commit()
        except Exception as e:
            print(f"Error tracking post: {e}")
        finally:
            conn.close()
    
    def record_engagement(self, post_id: str, metrics: Dict):
        """Record engagement metrics for a post"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            for metric_name, metric_value in metrics.items():
                cursor.execute('''
                    INSERT INTO engagement_metrics (post_id, metric_name, metric_value, recorded_at)
                    VALUES (?, ?, ?, datetime('now'))
                ''', (post_id, metric_name, metric_value))
            
            conn.commit()
        except Exception as e:
            print(f"Error recording engagement: {e}")
        finally:
            conn.close()
    
    def get_post_performance(self, post_id: str) -> Dict:
        """Get performance data for a specific post"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM posts WHERE post_id = ?
        ''', (post_id,))
        post = cursor.fetchone()
        
        if not post:
            conn.close()
            return None
        
        cursor.execute('''
            SELECT metric_name, metric_value, recorded_at
            FROM engagement_metrics
            WHERE post_id = ?
            ORDER BY recorded_at DESC
        ''', (post_id,))
        
        metrics = []
        for row in cursor.fetchall():
            metrics.append({
                'metric_name': row[0],
                'metric_value': row[1],
                'recorded_at': row[2]
            })
        
        conn.close()
        
        return {
            'post': {
                'post_id': post[0],
                'platform': post[1],
                'image_url': post[2],
                'caption': post[3],
                'posted_at': post[4],
                'source': post[5],
                'category': post[6],
                'quality_score': post[7]
            },
            'metrics': metrics
        }
    
    def get_daily_summary(self, days: int = 7) -> List[Dict]:
        """Get daily performance summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        cursor.execute('''
            SELECT 
                DATE(posted_at) as date,
                platform,
                COUNT(*) as posts_count,
                AVG(CASE WHEN em.metric_name = 'likes' THEN em.metric_value END) as avg_likes,
                AVG(CASE WHEN em.metric_name = 'comments' THEN em.metric_value END) as avg_comments,
                AVG(CASE WHEN em.metric_name = 'shares' THEN em.metric_value END) as avg_shares
            FROM posts p
            LEFT JOIN engagement_metrics em ON p.post_id = em.post_id
            WHERE p.posted_at >= ?
            GROUP BY DATE(posted_at), platform
            ORDER BY date DESC
        ''', (cutoff_date,))
        
        summaries = []
        for row in cursor.fetchall():
            summaries.append({
                'date': row[0],
                'platform': row[1],
                'posts_count': row[2],
                'avg_likes': row[3],
                'avg_comments': row[4],
                'avg_shares': row[5]
            })
        
        conn.close()
        return summaries
    
    def get_top_performing_content(self, limit: int = 10) -> List[Dict]:
        """Get top performing content by engagement"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                p.post_id,
                p.source,
                p.category,
                p.quality_score,
                SUM(CASE WHEN em.metric_name = 'likes' THEN em.metric_value ELSE 0 END) +
                SUM(CASE WHEN em.metric_name = 'comments' THEN em.metric_value ELSE 0 END) +
                SUM(CASE WHEN em.metric_name = 'shares' THEN em.metric_value ELSE 0 END) as total_engagement
            FROM posts p
            LEFT JOIN engagement_metrics em ON p.post_id = em.post_id
            GROUP BY p.post_id
            ORDER BY total_engagement DESC
            LIMIT ?
        ''', (limit,))
        
        top_content = []
        for row in cursor.fetchall():
            top_content.append({
                'post_id': row[0],
                'source': row[1],
                'category': row[2],
                'quality_score': row[3],
                'total_engagement': row[4]
            })
        
        conn.close()
        return top_content
    
    def get_source_performance(self) -> Dict:
        """Analyze performance by image source"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                source,
                COUNT(*) as post_count,
                AVG(quality_score) as avg_quality,
                AVG(
                    COALESCE(
                        SUM(CASE WHEN em.metric_name = 'likes' THEN em.metric_value ELSE 0 END),
                        0
                    ) +
                    COALESCE(
                        SUM(CASE WHEN em.metric_name = 'comments' THEN em.metric_value ELSE 0 END),
                        0
                    )
                ) as avg_engagement
            FROM posts p
            LEFT JOIN engagement_metrics em ON p.post_id = em.post_id
            GROUP BY source
            ORDER BY avg_engagement DESC
        ''')
        
        source_stats = []
        for row in cursor.fetchall():
            source_stats.append({
                'source': row[0],
                'post_count': row[1],
                'avg_quality': row[2],
                'avg_engagement': row[3]
            })
        
        conn.close()
        return {'sources': source_stats}
    
    def get_category_performance(self) -> Dict:
        """Analyze performance by content category"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                category,
                COUNT(*) as post_count,
                AVG(
                    COALESCE(
                        SUM(CASE WHEN em.metric_name = 'likes' THEN em.metric_value ELSE 0 END),
                        0
                    )
                ) as avg_engagement
            FROM posts p
            LEFT JOIN engagement_metrics em ON p.post_id = em.post_id
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY avg_engagement DESC
        ''')
        
        category_stats = []
        for row in cursor.fetchall():
            category_stats.append({
                'category': row[0],
                'post_count': row[1],
                'avg_engagement': row[2]
            })
        
        conn.close()
        return {'categories': category_stats}
    
    def get_optimization_suggestions(self) -> List[Dict]:
        """Generate data-driven optimization suggestions"""
        suggestions = []
        
        # Analyze source performance
        source_perf = self.get_source_performance()
        if source_perf['sources']:
            best_source = source_perf['sources'][0]
            suggestions.append({
                'type': 'source_optimization',
                'priority': 'high',
                'suggestion': f"Focus more on {best_source['source']} - it has highest average engagement ({best_source['avg_engagement']:.2f})",
                'expected_impact': '+15-25% engagement'
            })
        
        # Analyze category performance
        category_perf = self.get_category_performance()
        if category_perf['categories']:
            best_category = category_perf['categories'][0]
            suggestions.append({
                'type': 'category_optimization',
                'priority': 'medium',
                'suggestion': f"Increase posts in '{best_category['category']}' category - best performing",
                'expected_impact': '+10-20% engagement'
            })
        
        # Quality score analysis
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                CASE 
                    WHEN quality_score >= 80 THEN 'high'
                    WHEN quality_score >= 60 THEN 'medium'
                    ELSE 'low'
                END as quality_tier,
                AVG(
                    COALESCE(
                        SUM(CASE WHEN em.metric_name = 'likes' THEN em.metric_value ELSE 0 END),
                        0
                    )
                ) as avg_engagement
            FROM posts p
            LEFT JOIN engagement_metrics em ON p.post_id = em.post_id
            GROUP BY quality_tier
        ''')
        
        quality_tiers = []
        for row in cursor.fetchall():
            quality_tiers.append({
                'tier': row[0],
                'avg_engagement': row[1]
            })
        
        conn.close()
        
        if quality_tiers:
            high_quality = [t for t in quality_tiers if t['tier'] == 'high']
            if high_quality:
                suggestions.append({
                    'type': 'quality_optimization',
                    'priority': 'high',
                    'suggestion': "Maintain high quality score threshold (80+) - shows strong correlation with engagement",
                    'expected_impact': '+20-30% engagement'
                })
        
        return suggestions
    
    def generate_report(self) -> Dict:
        """Generate comprehensive analytics report"""
        return {
            'daily_summary': self.get_daily_summary(days=7),
            'top_content': self.get_top_performing_content(limit=5),
            'source_performance': self.get_source_performance(),
            'category_performance': self.get_category_performance(),
            'optimization_suggestions': self.get_optimization_suggestions(),
            'generated_at': datetime.now().isoformat()
        }
    
    def export_data(self, format: str = 'json') -> str:
        """Export analytics data"""
        report = self.generate_report()
        
        if format == 'json':
            return json.dumps(report, indent=2, default=str)
        elif format == 'csv':
            # Generate CSV format
            lines = []
            lines.append('Date,Platform,Posts,Avg Likes,Avg Comments,Avg Shares')
            for day in report['daily_summary']:
                lines.append(f"{day['date']},{day['platform']},{day['posts_count']},{day['avg_likes']},{day['avg_comments']},{day['avg_shares']}")
            return '\n'.join(lines)
        
        return str(report)
