"""
Main Orchestration Script for Himawari-8 Pipeline

This script coordinates all pipeline components to:
1. Download Himawari-8 data (B08, B10, B13 bands)
2. Preprocess: crop, regrid, quality control
3. Temporal alignment to 30-minute intervals
4. Store as efficient tensors
5. Compute and save normalization statistics

Usage:
    # Process full date range (2023-2025)
    python run_pipeline.py
    
    # Process specific year
    python run_pipeline.py --year 2023
    
    # Process date range
    python run_pipeline.py --start 2023-06-01 --end 2023-06-30
    
    # Use simulated data for testing
    python run_pipeline.py --simulated --start 2023-01-01 --end 2023-01-07
    
    # Resume interrupted processing
    python run_pipeline.py --resume

Design Philosophy:
- Modular: Each component can be run/tested independently
- Resumable: Progress tracked to handle interruptions
- Efficient: Minimal memory footprint, cleanup raw files after processing
- Observable: Detailed logging and progress reporting
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

import numpy as np

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import PipelineConfig, DEFAULT_CONFIG
from downloader import HimawariDownloader, timestamp_to_str, generate_timestamps
from preprocessor import HimawariPreprocessor
from temporal_alignment import TemporalAlignmentManager
from storage import StorageManager

# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging(config: PipelineConfig, log_level: str = 'INFO') -> logging.Logger:
    """Configure comprehensive logging."""
    logger = logging.getLogger('himawari_pipeline')
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create log directory
    log_dir = config.storage.base_dir / config.storage.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # File handler - detailed log
    fh = logging.FileHandler(
        log_dir / f'pipeline_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    # Console handler - summary
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger


# =============================================================================
# PROGRESS TRACKING
# =============================================================================

class PipelineProgress:
    """
    Track overall pipeline progress for resumability.
    
    Stores:
    - Processed timestamps
    - Processing statistics
    - Error log
    """
    
    def __init__(self, config: PipelineConfig, year_suffix: str = None):
        self.config = config
        # Use year-specific progress file if year is specified
        if year_suffix:
            self.progress_file = config.storage.base_dir / f'pipeline_progress_{year_suffix}.json'
        else:
            self.progress_file = config.storage.base_dir / 'pipeline_progress.json'
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Load existing progress or create new."""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            'processed': [],
            'failed': [],
            'statistics': {},
            'last_update': None,
            'started': datetime.now().isoformat()
        }
    
    def save(self):
        """Save progress to file."""
        self.data['last_update'] = datetime.now().isoformat()
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.progress_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def is_processed(self, timestamp_str: str) -> bool:
        """Check if timestamp has been processed."""
        return timestamp_str in self.data['processed']
    
    def mark_processed(self, timestamp_str: str):
        """Mark timestamp as successfully processed."""
        if timestamp_str not in self.data['processed']:
            self.data['processed'].append(timestamp_str)
    
    def mark_failed(self, timestamp_str: str, error: str):
        """Mark timestamp as failed."""
        self.data['failed'].append({
            'timestamp': timestamp_str,
            'error': error,
            'when': datetime.now().isoformat()
        })
    
    def get_pending(self, all_timestamps: List[str]) -> List[str]:
        """Get list of timestamps not yet processed."""
        processed_set = set(self.data['processed'])
        return [t for t in all_timestamps if t not in processed_set]
    
    def update_statistics(self, stats: Dict):
        """Update processing statistics."""
        self.data['statistics'].update(stats)
    
    def get_summary(self) -> Dict:
        """Get progress summary."""
        return {
            'processed_count': len(self.data['processed']),
            'failed_count': len(self.data['failed']),
            'started': self.data.get('started'),
            'last_update': self.data.get('last_update'),
        }


# =============================================================================
# MAIN PIPELINE CLASS
# =============================================================================

class HimawariPipeline:
    """
    Main pipeline orchestrator.
    
    Coordinates downloading, preprocessing, temporal alignment, and storage.
    """
    
    def __init__(self, config: PipelineConfig = None, 
                 use_simulated: bool = False,
                 log_level: str = 'INFO',
                 year: int = None):
        """
        Initialize the pipeline.
        
        Args:
            config: Pipeline configuration
            use_simulated: Use synthetic data for testing
            log_level: Logging verbosity
            year: Specific year for multi-device parallel processing
        """
        self.config = config or DEFAULT_CONFIG
        self.use_simulated = use_simulated
        self.year = year
        
        # Ensure directories exist
        self.config.storage.ensure_directories()
        
        # Set up logging
        self.logger = setup_logging(self.config, log_level)
        self.logger.info("Initializing Himawari-8 Pipeline")
        if year:
            self.logger.info(f"Year-specific mode: {year}")
        self.logger.info(self.config.summary())
        
        # Initialize components
        self.downloader = HimawariDownloader(self.config, use_simulated=use_simulated)
        self.preprocessor = HimawariPreprocessor(self.config)
        self.temporal_manager = TemporalAlignmentManager(self.config)
        self.storage = StorageManager(self.config)
        # Use year-specific progress file for multi-device processing
        self.progress = PipelineProgress(self.config, year_suffix=str(year) if year else None)
        
        # Processing statistics
        self.stats = {
            'timestamps_attempted': 0,
            'timestamps_successful': 0,
            'timestamps_failed': 0,
            'download_errors': 0,
            'processing_errors': 0,
            'storage_errors': 0,
            'start_time': None,
            'end_time': None,
        }
    
    def process_timestamp(self, timestamp: datetime) -> bool:
        """
        Process a single timestamp through the full pipeline.
        
        Steps:
        1. Download raw data for all bands
        2. Preprocess each band
        3. Temporal alignment (if needed)
        4. Quality control
        5. Save to storage
        
        Args:
            timestamp: Target timestamp
            
        Returns:
            True if processing succeeded
        """
        timestamp_str = timestamp_to_str(timestamp)
        
        # Check if already processed
        if self.progress.is_processed(timestamp_str):
            self.logger.debug(f"Skipping {timestamp_str} (already processed)")
            return True
        
        # Check if already stored
        if self.storage.image_exists(timestamp):
            self.logger.debug(f"Skipping {timestamp_str} (already in storage)")
            self.progress.mark_processed(timestamp_str)
            return True
        
        self.stats['timestamps_attempted'] += 1
        self.logger.debug(f"Processing {timestamp_str}")
        
        try:
            # Step 1: Download
            cache_dir = self.config.storage.base_dir / self.config.storage.cache_dir
            download_result = self.downloader.download_timestamp(timestamp)
            
            if not download_result or not all(v is not None for v in download_result.values()):
                self.logger.warning(f"Download incomplete for {timestamp_str}")
                self.stats['download_errors'] += 1
                
                # For simulated data, files are already created
                # Check if files exist in cache
                all_exist = True
                for band in self.config.bands.band_order:
                    expected = cache_dir / f"{timestamp_str}_{band}.npz"
                    if not expected.exists():
                        all_exist = False
                        break
                
                if not all_exist:
                    self.progress.mark_failed(timestamp_str, "Download failed")
                    self.stats['timestamps_failed'] += 1
                    return False
            
            # Step 2: Preprocess
            processed_data = self.preprocessor.process_timestamp(cache_dir, timestamp_str)
            
            if processed_data is None:
                self.logger.warning(f"Preprocessing failed for {timestamp_str}")
                self.stats['processing_errors'] += 1
                self.progress.mark_failed(timestamp_str, "Preprocessing failed")
                self.stats['timestamps_failed'] += 1
                return False
            
            # Step 3: Save to storage
            success = self.storage.save_image(
                processed_data, 
                timestamp,
                normalized=False,
                extra_metadata={
                    'processing_time': datetime.now().isoformat(),
                    'simulated': self.use_simulated,
                }
            )
            
            if not success:
                self.logger.warning(f"Storage failed for {timestamp_str}")
                self.stats['storage_errors'] += 1
                self.progress.mark_failed(timestamp_str, "Storage failed")
                self.stats['timestamps_failed'] += 1
                return False
            
            # Step 4: Cleanup raw files (if configured)
            if self.config.storage.delete_raw_after_processing:
                self._cleanup_raw_files(cache_dir, timestamp_str)
            
            # Mark as processed
            self.progress.mark_processed(timestamp_str)
            self.stats['timestamps_successful'] += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing {timestamp_str}: {e}", exc_info=True)
            self.progress.mark_failed(timestamp_str, str(e))
            self.stats['timestamps_failed'] += 1
            return False
    
    def _cleanup_raw_files(self, cache_dir: Path, timestamp_str: str):
        """Remove raw files after successful processing."""
        for band in self.config.bands.band_order:
            for ext in ['.dat', '.npz', '.npy', '.nc']:
                raw_file = cache_dir / f"{timestamp_str}_{band}{ext}"
                if raw_file.exists():
                    try:
                        raw_file.unlink()
                    except Exception as e:
                        self.logger.warning(f"Failed to delete {raw_file}: {e}")
    
    def run(self, start_date: str = None, end_date: str = None,
            year: int = None, resume: bool = True,
            max_workers: int = 1) -> Dict:
        """
        Run the full pipeline.
        
        Args:
            start_date: Override start date (YYYY-MM-DD)
            end_date: Override end date (YYYY-MM-DD)
            year: Process only specific year
            resume: Skip already processed timestamps
            max_workers: Parallel processing workers
            
        Returns:
            Processing statistics
        """
        self.stats['start_time'] = datetime.now().isoformat()
        
        # Determine date range
        if year:
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"
        else:
            start_date = start_date or self.config.temporal.start_date
            end_date = end_date or self.config.temporal.end_date
        
        self.logger.info(f"Processing period: {start_date} to {end_date}")
        
        # Generate all target timestamps
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        
        all_timestamps = [
            t for t in generate_timestamps(self.config)
            if start_dt <= t < end_dt
        ]
        
        self.logger.info(f"Total timestamps to process: {len(all_timestamps)}")
        
        # Filter for pending (if resuming)
        if resume:
            pending_strs = self.progress.get_pending(
                [timestamp_to_str(t) for t in all_timestamps]
            )
            # Convert back to datetime
            pending_timestamps = [
                datetime.strptime(s, "%Y%m%d_%H%M") 
                for s in pending_strs
            ]
            self.logger.info(f"Pending timestamps: {len(pending_timestamps)} "
                           f"({len(all_timestamps) - len(pending_timestamps)} already done)")
        else:
            pending_timestamps = all_timestamps
        
        if not pending_timestamps:
            self.logger.info("No pending timestamps to process!")
            return self.stats
        
        # Process timestamps
        if max_workers > 1:
            self._process_parallel(pending_timestamps, max_workers)
        else:
            self._process_sequential(pending_timestamps)
        
        # Compute and save normalization statistics
        self.logger.info("Computing normalization statistics...")
        norm_stats = self.preprocessor.get_normalization_stats()
        self.storage.save_normalization_stats(norm_stats)
        self.logger.info(f"Normalization stats: {norm_stats}")
        
        # Final statistics
        self.stats['end_time'] = datetime.now().isoformat()
        self.progress.update_statistics(self.stats)
        self.progress.save()
        
        # Print summary
        self._print_summary()
        
        return self.stats
    
    def _process_sequential(self, timestamps: List[datetime]):
        """Process timestamps sequentially."""
        total = len(timestamps)
        
        for i, timestamp in enumerate(timestamps):
            self.process_timestamp(timestamp)
            
            # Progress update
            if (i + 1) % 48 == 0:  # Every day's worth
                self.logger.info(
                    f"Progress: {i + 1}/{total} "
                    f"({self.stats['timestamps_successful']} successful, "
                    f"{self.stats['timestamps_failed']} failed)"
                )
                self.progress.save()
    
    def _process_parallel(self, timestamps: List[datetime], max_workers: int):
        """Process timestamps in parallel."""
        total = len(timestamps)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.process_timestamp, t): t 
                for t in timestamps
            }
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                
                # Progress update
                if completed % 48 == 0:
                    self.logger.info(
                        f"Progress: {completed}/{total} "
                        f"({self.stats['timestamps_successful']} successful, "
                        f"{self.stats['timestamps_failed']} failed)"
                    )
                    self.progress.save()
    
    def _print_summary(self):
        """Print processing summary."""
        print("\n" + "="*60)
        print("HIMAWARI-8 PIPELINE PROCESSING COMPLETE")
        print("="*60)
        print(f"Timestamps attempted: {self.stats['timestamps_attempted']}")
        print(f"Timestamps successful: {self.stats['timestamps_successful']}")
        print(f"Timestamps failed: {self.stats['timestamps_failed']}")
        print(f"  - Download errors: {self.stats['download_errors']}")
        print(f"  - Processing errors: {self.stats['processing_errors']}")
        print(f"  - Storage errors: {self.stats['storage_errors']}")
        
        if self.stats['timestamps_attempted'] > 0:
            success_rate = (self.stats['timestamps_successful'] / 
                          self.stats['timestamps_attempted'] * 100)
            print(f"Success rate: {success_rate:.1f}%")
        
        # Storage statistics
        storage_stats = self.storage.get_statistics()
        print(f"\nStorage:")
        print(f"  Total images: {storage_stats['total_images']}")
        print(f"  Total size: {storage_stats['total_size_mb']:.1f} MB")
        
        for year, year_stats in storage_stats['by_year'].items():
            print(f"  {year}: {year_stats['count']} images, "
                  f"{year_stats['size_mb']:.1f} MB")
        
        print("="*60)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Himawari-8 Satellite Data Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process full date range (2023-2025)
  python run_pipeline.py
  
  # Process specific year
  python run_pipeline.py --year 2023
  
  # Process custom date range
  python run_pipeline.py --start 2023-06-01 --end 2023-06-30
  
  # Quick test with simulated data
  python run_pipeline.py --simulated --start 2023-01-01 --end 2023-01-02
  
  # Parallel processing
  python run_pipeline.py --workers 4 --year 2023
"""
    )
    
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--year', type=int, choices=[2023, 2024, 2025],
                       help='Process specific year')
    parser.add_argument('--workers', type=int, default=1,
                       help='Number of parallel workers (default: 1)')
    parser.add_argument('--resume', action='store_true', default=True,
                       help='Resume from previous progress (default: True)')
    parser.add_argument('--no-resume', dest='resume', action='store_false',
                       help='Start fresh, ignoring previous progress')
    parser.add_argument('--simulated', action='store_true',
                       help='Use simulated data for testing')
    parser.add_argument('--log-level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging verbosity')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be processed without doing it')
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Create pipeline
    pipeline = HimawariPipeline(
        use_simulated=args.simulated,
        log_level=args.log_level,
        year=args.year
    )
    
    if args.dry_run:
        # Just show what would be done
        print("DRY RUN - would process:")
        print(f"  Date range: {args.start or 'config'} to {args.end or 'config'}")
        print(f"  Year filter: {args.year or 'None'}")
        print(f"  Workers: {args.workers}")
        print(f"  Resume: {args.resume}")
        print(f"  Simulated: {args.simulated}")
        return
    
    # Run pipeline
    stats = pipeline.run(
        start_date=args.start,
        end_date=args.end,
        year=args.year,
        resume=args.resume,
        max_workers=args.workers
    )
    
    # Return exit code based on success
    if stats['timestamps_failed'] == 0:
        sys.exit(0)
    elif stats['timestamps_successful'] > 0:
        sys.exit(0)  # Partial success
    else:
        sys.exit(1)  # Complete failure


if __name__ == "__main__":
    main()

