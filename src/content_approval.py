import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
import json


class ApprovalStatus(Enum):
    """Content approval status"""
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    POSTED = 'posted'


class ContentApprovalWorkflow:
    """Content approval workflow with staging queue"""
    
    def __init__(self, db_path: str = 'approval_queue.db'):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize approval queue database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS approval_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_url TEXT,
                image_path TEXT,
                caption TEXT,
                source TEXT,
                quality_score REAL,
                category TEXT,
                submitted_by TEXT DEFAULT 'system',
                submitted_at TIMESTAMP,
                status TEXT DEFAULT 'pending',
                reviewed_by TEXT,
                reviewed_at TIMESTAMP,
                rejection_reason TEXT,
                metadata TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS approval_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                queue_id INTEGER,
                action TEXT,
                performed_by TEXT,
                performed_at TIMESTAMP,
                notes TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviewers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                role TEXT DEFAULT 'reviewer',
                active BOOLEAN DEFAULT 1
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def submit_for_approval(self, content_data: Dict) -> int:
        """Submit content for approval"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO approval_queue 
            (image_url, image_path, caption, source, quality_score, category, submitted_by, submitted_at, status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            content_data.get('image_url'),
            content_data.get('image_path'),
            content_data.get('caption'),
            content_data.get('source'),
            content_data.get('quality_score'),
            content_data.get('category'),
            content_data.get('submitted_by', 'system'),
            datetime.now(),
            ApprovalStatus.PENDING.value,
            json.dumps(content_data.get('metadata', {}))
        ))
        
        queue_id = cursor.lastrowid
        
        # Log submission
        cursor.execute('''
            INSERT INTO approval_history (queue_id, action, performed_by, performed_at, notes)
            VALUES (?, 'submitted', ?, datetime('now'), ?)
        ''', (queue_id, content_data.get('submitted_by', 'system'), 'Content submitted for approval'))
        
        conn.commit()
        conn.close()
        
        return queue_id
    
    def get_pending_approvals(self, limit: int = 50) -> List[Dict]:
        """Get all pending approvals"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM approval_queue
            WHERE status = 'pending'
            ORDER BY submitted_at DESC
            LIMIT ?
        ''', (limit,))
        
        pending = []
        for row in cursor.fetchall():
            pending.append({
                'id': row[0],
                'image_url': row[1],
                'image_path': row[2],
                'caption': row[3],
                'source': row[4],
                'quality_score': row[5],
                'category': row[6],
                'submitted_by': row[7],
                'submitted_at': row[8],
                'status': row[9],
                'metadata': json.loads(row[12]) if row[12] else {}
            })
        
        conn.close()
        return pending
    
    def approve_content(self, queue_id: int, reviewer: str, notes: str = '') -> bool:
        """Approve content for posting"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE approval_queue
                SET status = 'approved', reviewed_by = ?, reviewed_at = datetime('now')
                WHERE id = ? AND status = 'pending'
            ''', (reviewer, queue_id))
            
            if cursor.rowcount == 0:
                conn.close()
                return False
            
            # Log approval
            cursor.execute('''
                INSERT INTO approval_history (queue_id, action, performed_by, performed_at, notes)
                VALUES (?, 'approved', ?, datetime('now'), ?)
            ''', (queue_id, reviewer, notes))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            conn.close()
            print(f"Approval failed: {e}")
            return False
    
    def reject_content(self, queue_id: int, reviewer: str, reason: str) -> bool:
        """Reject content with reason"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE approval_queue
                SET status = 'rejected', reviewed_by = ?, reviewed_at = datetime('now'), rejection_reason = ?
                WHERE id = ? AND status = 'pending'
            ''', (reviewer, reason, queue_id))
            
            if cursor.rowcount == 0:
                conn.close()
                return False
            
            # Log rejection
            cursor.execute('''
                INSERT INTO approval_history (queue_id, action, performed_by, performed_at, notes)
                VALUES (?, 'rejected', ?, datetime('now'), ?)
            ''', (queue_id, reviewer, reason))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            conn.close()
            print(f"Rejection failed: {e}")
            return False
    
    def mark_as_posted(self, queue_id: int) -> bool:
        """Mark approved content as posted"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE approval_queue
                SET status = 'posted'
                WHERE id = ? AND status = 'approved'
            ''', (queue_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            conn.close()
            print(f"Failed to mark as posted: {e}")
            return False
    
    def get_approved_content(self, limit: int = 10) -> List[Dict]:
        """Get approved content ready for posting"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM approval_queue
            WHERE status = 'approved'
            ORDER BY reviewed_at ASC
            LIMIT ?
        ''', (limit,))
        
        approved = []
        for row in cursor.fetchall():
            approved.append({
                'id': row[0],
                'image_url': row[1],
                'image_path': row[2],
                'caption': row[3],
                'source': row[4],
                'quality_score': row[5],
                'category': row[6],
                'submitted_by': row[7],
                'submitted_at': row[8],
                'status': row[9],
                'reviewed_by': row[10],
                'reviewed_at': row[11]
            })
        
        conn.close()
        return approved
    
    def get_content_history(self, queue_id: int) -> List[Dict]:
        """Get approval history for content"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT action, performed_by, performed_at, notes
            FROM approval_history
            WHERE queue_id = ?
            ORDER BY performed_at ASC
        ''', (queue_id,))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'action': row[0],
                'performed_by': row[1],
                'performed_at': row[2],
                'notes': row[3]
            })
        
        conn.close()
        return history
    
    def add_reviewer(self, username: str, role: str = 'reviewer') -> bool:
        """Add a reviewer to the system"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO reviewers (username, role, active)
                VALUES (?, ?, 1)
            ''', (username, role))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            conn.close()
            print(f"Failed to add reviewer: {e}")
            return False
    
    def get_reviewers(self) -> List[Dict]:
        """Get all active reviewers"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT username, role FROM reviewers WHERE active = 1
        ''')
        
        reviewers = []
        for row in cursor.fetchall():
            reviewers.append({
                'username': row[0],
                'role': row[1]
            })
        
        conn.close()
        return reviewers
    
    def get_statistics(self) -> Dict:
        """Get approval workflow statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Count by status
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM approval_queue
            GROUP BY status
        ''')
        
        status_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Average approval time
        cursor.execute('''
            SELECT AVG(julianday(reviewed_at) - julianday(submitted_at)) * 24 as avg_hours
            FROM approval_queue
            WHERE status IN ('approved', 'rejected') AND reviewed_at IS NOT NULL
        ''')
        
        avg_approval_time = cursor.fetchone()[0] or 0
        
        # Top submitters
        cursor.execute('''
            SELECT submitted_by, COUNT(*) as count
            FROM approval_queue
            GROUP BY submitted_by
            ORDER BY count DESC
            LIMIT 5
        ''')
        
        top_submitters = [
            {'submitter': row[0], 'count': row[1]}
            for row in cursor.fetchall()
        ]
        
        conn.close()
        
        return {
            'status_counts': status_counts,
            'avg_approval_hours': avg_approval_time,
            'top_submitters': top_submitters,
            'total_reviewers': len(self.get_reviewers())
        }
    
    def auto_approve_high_quality(self, min_score: float = 90.0) -> int:
        """Auto-approve content above quality threshold"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE approval_queue
            SET status = 'approved', reviewed_by = 'auto-approve', reviewed_at = datetime('now')
            WHERE status = 'pending' AND quality_score >= ?
        ''', (min_score,))
        
        count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return count
    
    def cleanup_old_pending(self, days: int = 7) -> int:
        """Remove pending items older than specified days"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(days=days)
        
        cursor.execute('''
            DELETE FROM approval_queue
            WHERE status = 'pending' AND submitted_at < ?
        ''', (cutoff,))
        
        count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return count
