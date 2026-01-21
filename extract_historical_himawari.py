"""
Extract historical Himawari satellite data for Bangladesh
Time range: 2021-01-01 to 2026-01-19
Interval: 30 minutes
"""
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
import time

# Import the processing function from the working pipeline
from extract_himawari_pipeline import process_and_save

# Configuration
START_DATE = datetime(2021, 1, 1, 0, 0)
END_DATE = datetime(2026, 1, 19, 23, 30)
INTERVAL_MINUTES = 30

# Progress tracking
PROGRESS_FILE = 'himawari_extraction_progress.json'
LOG_FILE = 'himawari_extraction_log.txt'

def load_progress():
    """Load extraction progress from file"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {
        'completed': [],
        'failed': [],
        'last_processed': None,
        'total_expected': 0,
        'total_completed': 0,
        'total_failed': 0
    }

def save_progress(progress):
    """Save extraction progress to file"""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

def log_message(message, also_print=True):
    """Log message to file and optionally print"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {message}\n"
    
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_line)
    
    if also_print:
        print(message)

def generate_timestamps():
    """Generate all timestamps to process"""
    timestamps = []
    current = START_DATE
    
    while current <= END_DATE:
        timestamps.append(current)
        current += timedelta(minutes=INTERVAL_MINUTES)
    
    return timestamps

def estimate_time_remaining(completed, total, avg_time_per_item):
    """Estimate remaining time"""
    remaining = total - completed
    seconds = remaining * avg_time_per_item
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    
    return f"{hours}h {minutes}m"

def main():
    print("=" * 80)
    print("HIMAWARI HISTORICAL DATA EXTRACTION")
    print("=" * 80)
    print(f"Time range: {START_DATE} to {END_DATE}")
    print(f"Interval: {INTERVAL_MINUTES} minutes")
    print(f"Region: Bangladesh (88-93°E, 20-27°N)")
    print("=" * 80)
    
    # Generate all timestamps
    all_timestamps = generate_timestamps()
    total_count = len(all_timestamps)
    
    print(f"\nTotal timestamps to process: {total_count:,}")
    
    # Load progress
    progress = load_progress()
    completed_set = set(progress['completed'])
    failed_set = set(progress['failed'])
    
    if completed_set:
        print(f"Resuming from previous run:")
        print(f"  Already completed: {len(completed_set):,}")
        print(f"  Previously failed: {len(failed_set):,}")
        print(f"  Remaining: {total_count - len(completed_set):,}")
    
    progress['total_expected'] = total_count
    
    # Filter out already completed
    pending_timestamps = [ts for ts in all_timestamps 
                         if ts.strftime('%Y-%m-%d %H:%M') not in completed_set]
    
    print(f"\nStarting extraction of {len(pending_timestamps):,} timestamps...")
    print(f"Press Ctrl+C to pause and save progress\n")
    
    log_message(f"Starting extraction: {len(pending_timestamps)} pending timestamps")
    
    start_time = time.time()
    process_times = []
    
    try:
        for idx, timestamp in enumerate(pending_timestamps, 1):
            ts_str = timestamp.strftime('%Y-%m-%d %H:%M')
            
            # Check if already processed
            if ts_str in completed_set:
                continue
            
            item_start = time.time()
            
            print(f"\n[{idx}/{len(pending_timestamps)}] Processing {ts_str}...")
            
            try:
                # Process this timestamp
                process_and_save(timestamp)
                
                # Mark as completed
                completed_set.add(ts_str)
                progress['completed'].append(ts_str)
                progress['total_completed'] = len(completed_set)
                progress['last_processed'] = ts_str
                
                item_time = time.time() - item_start
                process_times.append(item_time)
                
                # Keep only last 100 times for average
                if len(process_times) > 100:
                    process_times.pop(0)
                
                avg_time = sum(process_times) / len(process_times)
                
                # Show progress
                total_completed = len(completed_set)
                percent = (total_completed / total_count) * 100
                eta = estimate_time_remaining(total_completed, total_count, avg_time)
                
                print(f"✓ Success ({item_time:.1f}s) | Progress: {total_completed:,}/{total_count:,} ({percent:.1f}%) | ETA: {eta}")
                log_message(f"SUCCESS: {ts_str} ({item_time:.1f}s)", also_print=False)
                
                # Save progress every 10 items
                if idx % 10 == 0:
                    save_progress(progress)
                    print(f"  → Progress saved")
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                # Log failure
                error_msg = str(e)
                print(f"✗ FAILED: {error_msg}")
                log_message(f"FAILED: {ts_str} - {error_msg}")
                
                failed_set.add(ts_str)
                if ts_str not in progress['failed']:
                    progress['failed'].append(ts_str)
                progress['total_failed'] = len(failed_set)
                
                # Continue to next timestamp
                continue
    
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        log_message("Extraction interrupted by user")
    
    finally:
        # Save final progress
        save_progress(progress)
        
        # Final summary
        elapsed = time.time() - start_time
        elapsed_hours = elapsed / 3600
        
        print("\n" + "=" * 80)
        print("EXTRACTION SUMMARY")
        print("=" * 80)
        print(f"Total expected: {total_count:,}")
        print(f"Completed: {len(completed_set):,} ({len(completed_set)/total_count*100:.1f}%)")
        print(f"Failed: {len(failed_set):,}")
        print(f"Remaining: {total_count - len(completed_set):,}")
        print(f"Time elapsed: {elapsed_hours:.2f} hours")
        if process_times:
            print(f"Average time per item: {sum(process_times)/len(process_times):.1f}s")
        print(f"\nProgress saved to: {PROGRESS_FILE}")
        print(f"Log saved to: {LOG_FILE}")
        
        if len(failed_set) > 0:
            print(f"\n⚠ {len(failed_set)} timestamps failed. Check log for details.")
        
        log_message(f"Extraction session ended. Completed: {len(completed_set)}, Failed: {len(failed_set)}")

if __name__ == "__main__":
    main()
