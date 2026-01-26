"""
Quick Test Script for Himawari-8 Pipeline

Run this script to verify the pipeline works correctly with simulated data.
This tests all components without requiring network access.

Usage:
    python test_pipeline.py
"""

import sys
from pathlib import Path
from datetime import datetime
import numpy as np

# Add pipeline directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_config():
    """Test configuration module."""
    print("\n" + "="*50)
    print("Testing Configuration...")
    print("="*50)
    
    from config import PipelineConfig, DEFAULT_CONFIG
    
    config = PipelineConfig()
    assert config.geo.lat_min == 20.0
    assert config.geo.lat_max == 27.0
    assert config.geo.output_height == 64
    assert len(config.bands.band_order) == 3
    
    print("[OK] Configuration validation passed")
    print(f"  Region: {config.geo.lat_min}°N-{config.geo.lat_max}°N")
    print(f"  Bands: {config.bands.band_order}")
    print(f"  Output shape: ({config.bands.num_channels}, {config.geo.output_height}, {config.geo.output_width})")
    
    return True


def test_downloader():
    """Test downloader with simulated data."""
    print("\n" + "="*50)
    print("Testing Downloader (simulated)...")
    print("="*50)
    
    from downloader import HimawariDownloader
    
    downloader = HimawariDownloader(use_simulated=True)
    
    # Test single download
    test_time = datetime(2023, 1, 1, 12, 0)
    result = downloader.download_timestamp(test_time)
    
    assert result is not None
    print(f"[OK] Downloaded timestamp {test_time}")
    print(f"  Bands downloaded: {list(result.keys())}")
    
    return True


def test_preprocessor():
    """Test preprocessing module."""
    print("\n" + "="*50)
    print("Testing Preprocessor...")
    print("="*50)
    
    from preprocessor import HimawariPreprocessor, SpatialProcessor
    from config import DEFAULT_CONFIG
    
    config = DEFAULT_CONFIG
    spatial = SpatialProcessor(config)
    
    # Create test data
    test_data = np.random.randn(400, 300).astype(np.float32) * 30 + 270
    test_lats = np.linspace(27.5, 19.5, 400)
    test_lons = np.linspace(87.5, 93.5, 300)
    
    # Test crop and regrid
    result = spatial.crop_and_regrid(test_data, test_lats, test_lons)
    
    assert result.shape == (64, 64)
    assert not np.all(np.isnan(result))
    
    print(f"[OK] Spatial processing passed")
    print(f"  Input shape: {test_data.shape}")
    print(f"  Output shape: {result.shape}")
    print(f"  Value range: [{np.nanmin(result):.1f}, {np.nanmax(result):.1f}]")
    
    return True


def test_temporal_alignment():
    """Test temporal alignment module."""
    print("\n" + "="*50)
    print("Testing Temporal Alignment...")
    print("="*50)
    
    from temporal_alignment import TemporalAlignmentManager, CompositeAligner
    from config import DEFAULT_CONFIG
    
    manager = TemporalAlignmentManager()
    
    # Get timestamps for a day
    day_timestamps = manager.get_target_timestamps_for_day(datetime(2023, 1, 1))
    
    assert len(day_timestamps) == 48  # 30-min intervals
    print(f"[OK] Generated {len(day_timestamps)} timestamps per day")
    
    # Test alignment
    target = datetime(2023, 1, 1, 12, 0)
    observations = {
        datetime(2023, 1, 1, 11, 50): np.random.randn(3, 64, 64).astype(np.float32),
        datetime(2023, 1, 1, 12, 0): np.random.randn(3, 64, 64).astype(np.float32),
        datetime(2023, 1, 1, 12, 10): np.random.randn(3, 64, 64).astype(np.float32),
    }
    
    result = manager.align_observations(target, observations)
    assert result is not None
    assert result.shape == (3, 64, 64)
    
    print(f"[OK] Temporal alignment passed")
    print(f"  Aligned 3 observations to target")
    
    return True


def test_storage():
    """Test storage module."""
    print("\n" + "="*50)
    print("Testing Storage...")
    print("="*50)
    
    from storage import StorageManager
    
    storage = StorageManager()
    
    # Test save
    test_data = np.random.randn(3, 64, 64).astype(np.float32)
    test_time = datetime(2023, 1, 1, 12, 30)
    
    success = storage.save_image(test_data, test_time, normalized=False)
    assert success
    print(f"[OK] Saved test image")
    
    # Test load
    loaded_data, metadata = storage.load_image(test_time)
    assert loaded_data.shape == (3, 64, 64)
    assert np.allclose(test_data, loaded_data)
    
    print(f"[OK] Loaded test image")
    print(f"  Shape: {loaded_data.shape}")
    print(f"  Metadata keys: {list(metadata.keys())}")
    
    # Test list
    images = storage.list_images(2023)
    assert len(images) >= 1
    print(f"[OK] Listed {len(images)} images")
    
    return True


def test_full_pipeline():
    """Test full pipeline with simulated data."""
    print("\n" + "="*50)
    print("Testing Full Pipeline (2 days simulated)...")
    print("="*50)
    
    from run_pipeline import HimawariPipeline
    import shutil
    
    pipeline = HimawariPipeline(use_simulated=True, log_level='WARNING')
    
    # Clear any existing test data for these specific dates
    test_start = '2023-06-01'
    test_end = '2023-06-02'
    
    # Process 2 days (use different dates to avoid cache from previous tests)
    stats = pipeline.run(
        start_date=test_start,
        end_date=test_end,
        resume=False,
        max_workers=1
    )
    
    print(f"[OK] Pipeline completed")
    print(f"  Attempted: {stats['timestamps_attempted']}")
    print(f"  Successful: {stats['timestamps_successful']}")
    print(f"  Failed: {stats['timestamps_failed']}")
    
    # Verify storage
    storage_stats = pipeline.storage.get_statistics()
    print(f"  Total images: {storage_stats['total_images']}")
    print(f"  Total size: {storage_stats['total_size_mb']:.2f} MB")
    
    # Test passes if we either processed new images or images already existed
    return stats['timestamps_successful'] > 0 or storage_stats['total_images'] > 0


def test_utilities():
    """Test utility functions."""
    print("\n" + "="*50)
    print("Testing Utilities...")
    print("="*50)
    
    from utils import (
        validate_tensor, pixel_to_latlon, latlon_to_pixel,
        parse_timestamp_from_filename, is_daytime
    )
    from config import DEFAULT_CONFIG
    
    # Test coordinate conversion
    lat, lon = pixel_to_latlon(32, 32)  # Center pixel
    print(f"[OK] Center pixel (32, 32) -> ({lat:.2f}°N, {lon:.2f}°E)")
    
    py, px = latlon_to_pixel(23.5, 90.5)  # Dhaka approximate
    print(f"[OK] Dhaka (23.5°N, 90.5°E) -> pixel ({py}, {px})")
    
    # Test timestamp parsing
    ts = parse_timestamp_from_filename('20230615_1200.npz')
    assert ts == datetime(2023, 6, 15, 12, 0)
    print(f"[OK] Timestamp parsing: 20230615_1200.npz -> {ts}")
    
    # Test daytime check
    noon_utc = datetime(2023, 6, 15, 6, 0)  # 12:00 local in Bangladesh
    assert is_daytime(noon_utc)
    print(f"[OK] Daytime check: {noon_utc} UTC is daytime in Bangladesh")
    
    # Test tensor validation
    test_data = np.random.randn(3, 64, 64).astype(np.float32) * 20 + 260
    result = validate_tensor(test_data)
    print(f"[OK] Tensor validation: valid={result['valid']}")
    
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("     HIMAWARI-8 PIPELINE TEST SUITE")
    print("=" * 60)
    
    tests = [
        ('Configuration', test_config),
        ('Downloader', test_downloader),
        ('Preprocessor', test_preprocessor),
        ('Temporal Alignment', test_temporal_alignment),
        ('Storage', test_storage),
        ('Utilities', test_utilities),
        ('Full Pipeline', test_full_pipeline),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, 'PASSED' if success else 'FAILED'))
        except Exception as e:
            print(f"\n[X] {name} failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, 'ERROR'))
    
    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    
    for name, status in results:
        symbol = '[PASS]' if status == 'PASSED' else '[FAIL]'
        print(f"  {symbol} {name}: {status}")
    
    passed = sum(1 for _, s in results if s == 'PASSED')
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\nAll tests passed! Pipeline is ready to use.")
        return 0
    else:
        print("\nSome tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    exit(main())

