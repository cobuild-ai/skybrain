import os
import glob
import gzip
import shutil
import hashlib
from datetime import datetime
from typing import Optional

def calculate_sha256(filepath: str) -> str:
    """Calculate SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def calculate_gzip_content_sha256(gz_filepath: str) -> str:
    """Calculate SHA-256 hash of decompressed content inside a .gz file."""
    sha256 = hashlib.sha256()
    with gzip.open(gz_filepath, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def backup_file(filepath: str, backup_root: str = ".skyjournal/backups") -> Optional[str]:
    """
    Compress and securely backup a markdown file to backup_root using gzip.
    Skips backup if the content has not changed compared to the latest backup.
    Returns the path to the backup file (or existing latest backup).
    """
    if not os.path.exists(filepath):
        return None

    os.makedirs(backup_root, exist_ok=True)
    filename = os.path.basename(filepath)
    current_hash = calculate_sha256(filepath)

    # Check latest existing backup for this file
    existing_backups = sorted(glob.glob(os.path.join(backup_root, f"*_{filename}.gz")))
    if existing_backups:
        latest_backup = existing_backups[-1]
        try:
            latest_backup_hash = calculate_gzip_content_sha256(latest_backup)
            if current_hash == latest_backup_hash:
                # Content has not changed, skip creating redundant backup
                return latest_backup
        except Exception:
            pass

    # Create new timestamped backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{timestamp}_{filename}.gz"
    backup_path = os.path.join(backup_root, backup_filename)

    with open(filepath, "rb") as f_in:
        with gzip.open(backup_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    return backup_path

def restore_backup(backup_path: str, target_filepath: str) -> bool:
    """Restore a .gz backup file to target_filepath."""
    if not os.path.exists(backup_path):
        return False

    os.makedirs(os.path.dirname(os.path.abspath(target_filepath)), exist_ok=True)
    with gzip.open(backup_path, "rb") as f_in:
        with open(target_filepath, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    return True
