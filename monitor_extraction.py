"""
Monitor the progress of Himawari historical data extraction
"""
import json
import os
from datetime import datetime

PROGRESS_FILE = 'himawari_extraction_progress.json'
LOG_FILE = 'himawari_extraction_log.txt'

def format_seconds(seconds):
    """Convert seconds to human readable format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours}h {minutes}m {secs}s"

def check_progress():
    """Check and display extraction progress"""
    
    if not os.path.exists(PROGRESS_FILE):
        print("⚠ No progress file found. Extraction may not have started yet.")
        return
    
    with open(PROGRESS_FILE, 'r') as f:
        progress = json.load(f)
    
    total = progress.get('total_expected', 0)
    completed = progress.get('total_completed', 0)
    failed = progress.get('total_failed', 0)
    last = progress.get('last_processed', 'N/A')
    
    if total == 0:
        print("⚠ No total count found in progress file.")
        return
    
    percent = (completed / total) * 100
    remaining = total - completed
    
    print("=" * 80)
    print("HIMAWARI EXTRACTION PROGRESS")
    print("=" * 80)
    print(f"Total timestamps:     {total:,}")
    print(f"Completed:            {completed:,} ({percent:.2f}%)")
    print(f"Failed:               {failed:,}")
    print(f"Remaining:            {remaining:,}")
    print(f"Last processed:       {last}")
    print("=" * 80)
    
    # Check recent log entries
    if os.path.exists(LOG_FILE):
        print("\nRecent log entries:")
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-10:]:
                print(f"  {line.strip()}")
    
    # Estimate remaining time (assuming average 45s per item)
    if completed > 0:
        avg_time = 45  # seconds per timestamp (conservative estimate)
        est_seconds = remaining * avg_time
        est_hours = est_seconds / 3600
        print(f"\n📊 Estimated time remaining: ~{est_hours:.1f} hours ({est_hours/24:.1f} days)")
    
    # Check dataset directory
    dataset_size = 0
    file_count = 0
    if os.path.exists('dataset'):
        for root, dirs, files in os.walk('dataset'):
            for file in files:
                file_count += 1
                file_path = os.path.join(root, file)
                try:
                    dataset_size += os.path.getsize(file_path)
                except:
                    pass
    
    size_gb = dataset_size / (1024**3)
    print(f"\n💾 Dataset size: {size_gb:.2f} GB ({file_count:,} files)")
    
    if completed > 0:
        est_total_size = (total / completed) * size_gb
        print(f"   Estimated final size: ~{est_total_size:.1f} GB")

if __name__ == "__main__":
    check_progress()
