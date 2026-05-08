import os
import sqlite3
import shutil
import gzip
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import hashlib
from pathlib import Path


class BackupSystem:
    """Automated backup and disaster recovery system"""
    
    def __init__(self, backup_dir: str = 'backups', retention_days: int = 30):
        self.backup_dir = backup_dir
        self.retention_days = retention_days
        os.makedirs(backup_dir, exist_ok=True)
        
        # Databases to backup
        self.databases = [
            'image_database.db',
            'health_monitor.db',
            'rate_limiter.db',
            'token_manager.db',
            'scheduler.db',
            'analytics.db'
        ]
        
        # Directories to backup
        self.directories = [
            'image_cache',
            'logs'
        ]
    
    def create_backup(self, backup_name: Optional[str] = None) -> Dict:
        """Create a full backup of all databases and directories"""
        if not backup_name:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_path = os.path.join(self.backup_dir, backup_name)
        os.makedirs(backup_path, exist_ok=True)
        
        results = {
            'backup_name': backup_name,
            'backup_path': backup_path,
            'timestamp': datetime.now().isoformat(),
            'databases': [],
            'directories': [],
            'total_size_mb': 0,
            'success': True,
            'errors': []
        }
        
        # Backup databases
        for db_file in self.databases:
            if os.path.exists(db_file):
                try:
                    db_backup_path = os.path.join(backup_path, f"{db_file}.gz")
                    self._backup_database(db_file, db_backup_path)
                    size_mb = os.path.getsize(db_backup_path) / (1024 * 1024)
                    results['databases'].append({
                        'file': db_file,
                        'backup_path': db_backup_path,
                        'size_mb': size_mb
                    })
                    results['total_size_mb'] += size_mb
                except Exception as e:
                    results['errors'].append(f"Database backup failed for {db_file}: {e}")
                    results['success'] = False
        
        # Backup directories
        for dir_name in self.directories:
            if os.path.exists(dir_name):
                try:
                    dir_backup_path = os.path.join(backup_path, f"{dir_name}.tar.gz")
                    self._backup_directory(dir_name, dir_backup_path)
                    size_mb = os.path.getsize(dir_backup_path) / (1024 * 1024)
                    results['directories'].append({
                        'directory': dir_name,
                        'backup_path': dir_backup_path,
                        'size_mb': size_mb
                    })
                    results['total_size_mb'] += size_mb
                except Exception as e:
                    results['errors'].append(f"Directory backup failed for {dir_name}: {e}")
                    results['success'] = False
        
        # Create backup manifest
        manifest_path = os.path.join(backup_path, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Calculate checksum
        results['checksum'] = self._calculate_backup_checksum(backup_path)
        
        return results
    
    def _backup_database(self, db_file: str, backup_path: str):
        """Backup a single database with compression"""
        # Use SQLite backup API for consistent backup
        source = sqlite3.connect(db_file)
        backup = sqlite3.connect(':memory:')
        
        try:
            # Backup to memory
            source.backup(backup)
            
            # Dump to file
            with gzip.open(backup_path, 'wb') as f:
                for line in backup.iterdump():
                    f.write(line.encode('utf-8') + b'\n')
        finally:
            source.close()
            backup.close()
    
    def _backup_directory(self, dir_name: str, backup_path: str):
        """Backup a directory with compression"""
        import tarfile
        with tarfile.open(backup_path, "w:gz") as tar:
            tar.add(dir_name, arcname=os.path.basename(dir_name))
    
    def _calculate_backup_checksum(self, backup_path: str) -> str:
        """Calculate SHA256 checksum of backup"""
        checksum = hashlib.sha256()
        
        for root, dirs, files in os.walk(backup_path):
            for file in files:
                file_path = os.path.join(root, file)
                with open(file_path, 'rb') as f:
                    while chunk := f.read(8192):
                        checksum.update(chunk)
        
        return checksum.hexdigest()
    
    def restore_backup(self, backup_name: str, verify: bool = True) -> Dict:
        """Restore from a backup"""
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        if not os.path.exists(backup_path):
            return {'success': False, 'error': f'Backup {backup_name} not found'}
        
        # Load manifest
        manifest_path = os.path.join(backup_path, 'manifest.json')
        if not os.path.exists(manifest_path):
            return {'success': False, 'error': 'Manifest not found'}
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        results = {
            'backup_name': backup_name,
            'timestamp': datetime.now().isoformat(),
            'databases_restored': [],
            'directories_restored': [],
            'success': True,
            'errors': []
        }
        
        # Verify checksum if requested
        if verify:
            current_checksum = self._calculate_backup_checksum(backup_path)
            if current_checksum != manifest.get('checksum'):
                return {'success': False, 'error': 'Checksum verification failed'}
        
        # Restore databases
        for db_info in manifest.get('databases', []):
            try:
                self._restore_database(db_info['backup_path'], db_info['file'])
                results['databases_restored'].append(db_info['file'])
            except Exception as e:
                results['errors'].append(f"Database restore failed for {db_info['file']}: {e}")
                results['success'] = False
        
        # Restore directories
        for dir_info in manifest.get('directories', []):
            try:
                self._restore_directory(dir_info['backup_path'], dir_info['directory'])
                results['directories_restored'].append(dir_info['directory'])
            except Exception as e:
                results['errors'].append(f"Directory restore failed for {dir_info['directory']}: {e}")
                results['success'] = False
        
        return results
    
    def _restore_database(self, backup_path: str, target_db: str):
        """Restore a database from backup"""
        # Remove existing database
        if os.path.exists(target_db):
            os.remove(target_db)
        
        # Restore from backup
        target = sqlite3.connect(target_db)
        
        with gzip.open(backup_path, 'rb') as f:
            sql_script = f.read().decode('utf-8')
            target.executescript(sql_script)
        
        target.close()
    
    def _restore_directory(self, backup_path: str, target_dir: str):
        """Restore a directory from backup"""
        import tarfile
        
        # Remove existing directory
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        
        # Extract from backup
        with tarfile.open(backup_path, "r:gz") as tar:
            tar.extractall()
    
    def list_backups(self) -> List[Dict]:
        """List all available backups"""
        backups = []
        
        if not os.path.exists(self.backup_dir):
            return backups
        
        for backup_name in os.listdir(self.backup_dir):
            backup_path = os.path.join(self.backup_dir, backup_name)
            manifest_path = os.path.join(backup_path, 'manifest.json')
            
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                    
                    backups.append({
                        'name': backup_name,
                        'timestamp': manifest.get('timestamp'),
                        'size_mb': manifest.get('total_size_mb', 0),
                        'databases': len(manifest.get('databases', [])),
                        'directories': len(manifest.get('directories', [])),
                        'checksum': manifest.get('checksum')
                    })
                except:
                    continue
        
        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return backups
    
    def cleanup_old_backups(self) -> Dict:
        """Remove backups older than retention period"""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        
        removed = []
        errors = []
        
        for backup_name in os.listdir(self.backup_dir):
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            # Get backup timestamp from directory name or manifest
            try:
                # Try to parse from directory name
                timestamp_str = backup_name.replace('backup_', '').split('_')[0:2]
                backup_date = datetime.strptime('_'.join(timestamp_str), '%Y%m%d_%H%M%S')
            except:
                # Fallback to file modification time
                backup_date = datetime.fromtimestamp(os.path.getmtime(backup_path))
            
            if backup_date < cutoff_date:
                try:
                    shutil.rmtree(backup_path)
                    removed.append(backup_name)
                except Exception as e:
                    errors.append(f"Failed to remove {backup_name}: {e}")
        
        return {
            'removed_count': len(removed),
            'removed_backups': removed,
            'errors': errors
        }
    
    def verify_backup(self, backup_name: str) -> Dict:
        """Verify a backup's integrity"""
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        if not os.path.exists(backup_path):
            return {'success': False, 'error': 'Backup not found'}
        
        manifest_path = os.path.join(backup_path, 'manifest.json')
        if not os.path.exists(manifest_path):
            return {'success': False, 'error': 'Manifest not found'}
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Verify checksum
        current_checksum = self._calculate_backup_checksum(backup_path)
        checksum_valid = current_checksum == manifest.get('checksum')
        
        # Verify all files exist
        files_exist = True
        missing_files = []
        
        for db_info in manifest.get('databases', []):
            if not os.path.exists(db_info['backup_path']):
                files_exist = False
                missing_files.append(db_info['backup_path'])
        
        for dir_info in manifest.get('directories', []):
            if not os.path.exists(dir_info['backup_path']):
                files_exist = False
                missing_files.append(dir_info['backup_path'])
        
        return {
            'success': checksum_valid and files_exist,
            'checksum_valid': checksum_valid,
            'all_files_exist': files_exist,
            'missing_files': missing_files,
            'expected_checksum': manifest.get('checksum'),
            'actual_checksum': current_checksum
        }
    
    def schedule_automatic_backup(self, interval_hours: int = 24):
        """Schedule automatic backups (for use with scheduler)"""
        # This would be integrated with the intelligent scheduler
        # For now, it's a placeholder for the scheduling logic
        pass


class CloudBackup:
    """Cloud storage integration for off-site backups"""
    
    def __init__(self, provider: str = 'local'):
        self.provider = provider
        
        if provider == 's3':
            self._init_s3()
        elif provider == 'gcs':
            self._init_gcs()
    
    def _init_s3(self):
        """Initialize AWS S3 client"""
        try:
            import boto3
            self.s3_client = boto3.client('s3')
            self.bucket = os.getenv('AWS_S3_BUCKET', 'fb-auto-poster-backups')
        except ImportError:
            print("boto3 not installed. Install with: pip install boto3")
            self.s3_client = None
    
    def _init_gcs(self):
        """Initialize Google Cloud Storage client"""
        try:
            from google.cloud import storage
            self.gcs_client = storage.Client()
            self.bucket = os.getenv('GCS_BUCKET', 'fb-auto-poster-backups')
        except ImportError:
            print("google-cloud-storage not installed. Install with: pip install google-cloud-storage")
            self.gcs_client = None
    
    def upload_backup(self, backup_path: str, backup_name: str) -> bool:
        """Upload backup to cloud storage"""
        if self.provider == 's3' and self.s3_client:
            try:
                self.s3_client.upload_file(
                    backup_path,
                    self.bucket,
                    backup_name,
                    ExtraArgs={'ServerSideEncryption': 'AES256'}
                )
                return True
            except Exception as e:
                print(f"S3 upload failed: {e}")
                return False
        
        elif self.provider == 'gcs' and self.gcs_client:
            try:
                bucket = self.gcs_client.bucket(self.bucket)
                blob = bucket.blob(backup_name)
                blob.upload_from_filename(backup_path)
                return True
            except Exception as e:
                print(f"GCS upload failed: {e}")
                return False
        
        return False
    
    def download_backup(self, backup_name: str, local_path: str) -> bool:
        """Download backup from cloud storage"""
        if self.provider == 's3' and self.s3_client:
            try:
                self.s3_client.download_file(self.bucket, backup_name, local_path)
                return True
            except Exception as e:
                print(f"S3 download failed: {e}")
                return False
        
        elif self.provider == 'gcs' and self.gcs_client:
            try:
                bucket = self.gcs_client.bucket(self.bucket)
                blob = bucket.blob(backup_name)
                blob.download_to_filename(local_path)
                return True
            except Exception as e:
                print(f"GCS download failed: {e}")
                return False
        
        return False
    
    def list_cloud_backups(self) -> List[str]:
        """List backups in cloud storage"""
        backups = []
        
        if self.provider == 's3' and self.s3_client:
            try:
                response = self.s3_client.list_objects_v2(Bucket=self.bucket)
                backups = [obj['Key'] for obj in response.get('Contents', [])]
            except Exception as e:
                print(f"S3 list failed: {e}")
        
        elif self.provider == 'gcs' and self.gcs_client:
            try:
                bucket = self.gcs_client.bucket(self.bucket)
                blobs = bucket.list_blobs()
                backups = [blob.name for blob in blobs]
            except Exception as e:
                print(f"GCS list failed: {e}")
        
        return backups
