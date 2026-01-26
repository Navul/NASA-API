"""
Utility Functions for Himawari-8 Pipeline

This module provides utility functions for:
- Data validation
- Visualization
- Dataset inspection
- Quality reports
- Coordinate transformations
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import PipelineConfig, DEFAULT_CONFIG

logger = logging.getLogger('himawari_utils')


# =============================================================================
# DATA VALIDATION
# =============================================================================

def validate_tensor(data: np.ndarray, config: PipelineConfig = None) -> Dict:
    """
    Validate a tensor against expected specifications.
    
    Args:
        data: Tensor to validate
        config: Pipeline configuration
        
    Returns:
        Dict with validation results
    """
    config = config or DEFAULT_CONFIG
    
    results = {
        'valid': True,
        'issues': [],
        'warnings': []
    }
    
    # Check shape
    expected_shape = (
        config.bands.num_channels,
        config.geo.output_height,
        config.geo.output_width
    )
    
    if data.shape != expected_shape:
        results['valid'] = False
        results['issues'].append(
            f"Shape mismatch: {data.shape} (expected {expected_shape})"
        )
    
    # Check dtype
    if data.dtype not in [np.float32, np.float64]:
        results['warnings'].append(
            f"Unexpected dtype: {data.dtype} (expected float32)"
        )
    
    # Check for NaN
    nan_fraction = np.sum(np.isnan(data)) / data.size
    if nan_fraction > 0.5:
        results['valid'] = False
        results['issues'].append(f"Too many NaN values: {nan_fraction*100:.1f}%")
    elif nan_fraction > 0.1:
        results['warnings'].append(f"High NaN fraction: {nan_fraction*100:.1f}%")
    
    # Check value range per channel
    for i, band in enumerate(config.bands.band_order):
        channel_data = data[i]
        valid_data = channel_data[~np.isnan(channel_data)]
        
        if len(valid_data) > 0:
            min_val, max_val = valid_data.min(), valid_data.max()
            expected_range = config.bands.value_ranges.get(band, (180, 330))
            
            if min_val < expected_range[0] - 20 or max_val > expected_range[1] + 20:
                results['warnings'].append(
                    f"Channel {band}: values [{min_val:.1f}, {max_val:.1f}] "
                    f"outside expected range {expected_range}"
                )
    
    # Check for constant values (stuck pixels)
    std = np.nanstd(data)
    if std < 0.1:
        results['warnings'].append(f"Very low variance: {std:.4f}")
    
    return results


def validate_dataset(storage_manager, sample_size: int = 100) -> Dict:
    """
    Validate a sample of the dataset.
    
    Args:
        storage_manager: StorageManager instance
        sample_size: Number of samples to check
        
    Returns:
        Overall validation report
    """
    config = storage_manager.config
    all_images = storage_manager.list_images()
    
    if len(all_images) > sample_size:
        indices = np.random.choice(len(all_images), sample_size, replace=False)
        sample_paths = [all_images[i] for i in indices]
    else:
        sample_paths = all_images
    
    report = {
        'total_checked': 0,
        'valid_count': 0,
        'issues': [],
        'warnings': [],
    }
    
    for path in sample_paths:
        try:
            data, meta = storage_manager.load_image_by_path(path)
            result = validate_tensor(data, config)
            
            report['total_checked'] += 1
            
            if result['valid']:
                report['valid_count'] += 1
            else:
                for issue in result['issues']:
                    report['issues'].append(f"{path.name}: {issue}")
            
            for warning in result['warnings']:
                report['warnings'].append(f"{path.name}: {warning}")
                
        except Exception as e:
            report['issues'].append(f"{path.name}: Failed to load - {e}")
    
    report['valid_rate'] = (report['valid_count'] / report['total_checked'] * 100 
                           if report['total_checked'] > 0 else 0)
    
    return report


# =============================================================================
# VISUALIZATION
# =============================================================================

def create_quicklook(data: np.ndarray, band_idx: int = 2,
                     output_path: Path = None,
                     title: str = None,
                     colormap: str = 'gray_r') -> Optional[np.ndarray]:
    """
    Create a quick-look visualization of satellite data.
    
    Args:
        data: Tensor (C, H, W) or (H, W)
        band_idx: Band index to visualize (if 3D)
        output_path: Save path (optional)
        title: Plot title
        colormap: Matplotlib colormap
        
    Returns:
        RGB image array if matplotlib is not available
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
        
        # Extract band
        if data.ndim == 3:
            img = data[band_idx]
        else:
            img = data
        
        # Create figure
        fig, ax = plt.subplots(figsize=(8, 8))
        
        # Plot with appropriate colormap for IR
        # Reverse colormap so cold (high clouds) = white
        im = ax.imshow(img, cmap=colormap, origin='upper')
        
        plt.colorbar(im, ax=ax, label='Brightness Temperature (K)')
        
        if title:
            ax.set_title(title)
        
        ax.set_xlabel('Longitude (pixels)')
        ax.set_ylabel('Latitude (pixels)')
        
        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
        else:
            plt.show()
        
        return None
        
    except ImportError:
        logger.warning("matplotlib not available, creating raw RGB")
        
        # Simple normalization for display
        if data.ndim == 3:
            img = data[band_idx]
        else:
            img = data
        
        # Normalize to 0-255
        img_norm = (img - np.nanmin(img)) / (np.nanmax(img) - np.nanmin(img) + 1e-8)
        img_uint8 = (255 - img_norm * 255).astype(np.uint8)  # Invert for IR
        
        return img_uint8


def create_composite_image(data: np.ndarray,
                           output_path: Path = None,
                           method: str = 'ir_composite') -> Optional[np.ndarray]:
    """
    Create a false-color composite from multiple bands.
    
    Args:
        data: Tensor (C=3, H, W) with bands B08, B10, B13
        output_path: Save path (optional)
        method: Composite method ('ir_composite', 'difference')
        
    Returns:
        RGB array
    """
    # Channels: 0=B08 (6.2µm), 1=B10 (7.3µm), 2=B13 (10.4µm)
    
    if method == 'ir_composite':
        # Simple IR composite
        # R = B13 (window channel - clouds and surface)
        # G = B10 (mid-level WV)
        # B = B08 (upper-level WV)
        
        def normalize_channel(ch):
            ch_min, ch_max = np.nanpercentile(ch, [2, 98])
            return np.clip((ch - ch_min) / (ch_max - ch_min + 1e-8), 0, 1)
        
        r = normalize_channel(data[2])  # B13
        g = normalize_channel(data[1])  # B10
        b = normalize_channel(data[0])  # B08
        
        # Invert so cold = bright
        rgb = np.stack([1-r, 1-g, 1-b], axis=-1)
        
    elif method == 'difference':
        # Difference product for convection detection
        # B13 - B08 highlights cold cloud tops with moisture
        
        diff = data[2] - data[0]  # B13 - B08
        diff_norm = (diff - np.nanmin(diff)) / (np.nanmax(diff) - np.nanmin(diff) + 1e-8)
        
        # Apply a colormap manually
        rgb = np.stack([diff_norm, 1-diff_norm, 0.5*np.ones_like(diff_norm)], axis=-1)
        
    else:
        # Grayscale from B13
        b13_norm = (data[2] - np.nanmin(data[2])) / (np.nanmax(data[2]) - np.nanmin(data[2]) + 1e-8)
        rgb = np.stack([1-b13_norm, 1-b13_norm, 1-b13_norm], axis=-1)
    
    # Handle NaN
    nan_mask = np.isnan(rgb).any(axis=-1)
    rgb[nan_mask] = [0.5, 0.5, 0.5]  # Gray for missing
    
    # Save or return
    if output_path:
        try:
            import matplotlib.pyplot as plt
            plt.imsave(str(output_path), rgb)
        except ImportError:
            # Save as raw
            rgb_uint8 = (rgb * 255).astype(np.uint8)
            # Would need PIL/cv2 to save, so just return
            return rgb_uint8
    
    return (rgb * 255).astype(np.uint8)


# =============================================================================
# COORDINATE UTILITIES
# =============================================================================

def pixel_to_latlon(pixel_y: int, pixel_x: int, 
                    config: PipelineConfig = None) -> Tuple[float, float]:
    """
    Convert pixel coordinates to latitude/longitude.
    
    Args:
        pixel_y: Row index (0 = north)
        pixel_x: Column index (0 = west)
        config: Pipeline configuration
        
    Returns:
        Tuple of (latitude, longitude)
    """
    config = config or DEFAULT_CONFIG
    
    lat = config.geo.lat_max - (pixel_y / (config.geo.output_height - 1)) * (
        config.geo.lat_max - config.geo.lat_min
    )
    
    lon = config.geo.lon_min + (pixel_x / (config.geo.output_width - 1)) * (
        config.geo.lon_max - config.geo.lon_min
    )
    
    return lat, lon


def latlon_to_pixel(lat: float, lon: float,
                    config: PipelineConfig = None) -> Tuple[int, int]:
    """
    Convert latitude/longitude to pixel coordinates.
    
    Args:
        lat: Latitude (degrees)
        lon: Longitude (degrees)
        config: Pipeline configuration
        
    Returns:
        Tuple of (pixel_y, pixel_x)
    """
    config = config or DEFAULT_CONFIG
    
    pixel_y = int((config.geo.lat_max - lat) / (
        config.geo.lat_max - config.geo.lat_min
    ) * (config.geo.output_height - 1))
    
    pixel_x = int((lon - config.geo.lon_min) / (
        config.geo.lon_max - config.geo.lon_min
    ) * (config.geo.output_width - 1))
    
    # Clamp to valid range
    pixel_y = max(0, min(pixel_y, config.geo.output_height - 1))
    pixel_x = max(0, min(pixel_x, config.geo.output_width - 1))
    
    return pixel_y, pixel_x


def get_coordinate_grids(config: PipelineConfig = None) -> Tuple[np.ndarray, np.ndarray]:
    """
    Get 2D arrays of latitude and longitude coordinates.
    
    Returns:
        Tuple of (lat_grid, lon_grid) with shape (H, W)
    """
    config = config or DEFAULT_CONFIG
    
    lats = config.geo.get_output_lats()
    lons = config.geo.get_output_lons()
    
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    return lat_grid, lon_grid


# =============================================================================
# TIME UTILITIES
# =============================================================================

def parse_timestamp_from_filename(filename: str) -> datetime:
    """
    Extract timestamp from standard filename format.
    
    Args:
        filename: Filename like '20230101_0030.npz'
        
    Returns:
        datetime object
    """
    stem = Path(filename).stem
    return datetime.strptime(stem, "%Y%m%d_%H%M")


def format_timestamp(dt: datetime) -> str:
    """Format datetime for filename."""
    return dt.strftime("%Y%m%d_%H%M")


def get_local_time(utc_time: datetime, lon: float) -> datetime:
    """
    Convert UTC to approximate local solar time.
    
    Args:
        utc_time: UTC datetime
        lon: Longitude in degrees
        
    Returns:
        Approximate local solar time
    """
    offset_hours = lon / 15.0  # 15 degrees per hour
    return utc_time + timedelta(hours=offset_hours)


def is_daytime(utc_time: datetime, lat: float = 23.5, lon: float = 90.5) -> bool:
    """
    Check if it's daytime at given location (approximate).
    
    Uses simple approximation for Bangladesh region.
    
    Args:
        utc_time: UTC datetime
        lat: Latitude (default: Bangladesh center)
        lon: Longitude (default: Bangladesh center)
        
    Returns:
        True if daytime (6 AM - 6 PM local)
    """
    local_time = get_local_time(utc_time, lon)
    hour = local_time.hour
    return 6 <= hour <= 18


# =============================================================================
# STATISTICS
# =============================================================================

def compute_dataset_statistics(storage_manager, 
                               sample_fraction: float = 0.1) -> Dict:
    """
    Compute comprehensive statistics over the dataset.
    
    Args:
        storage_manager: StorageManager instance
        sample_fraction: Fraction of images to sample
        
    Returns:
        Dict with statistics per band
    """
    config = storage_manager.config
    all_images = storage_manager.list_images()
    
    n_samples = max(10, int(len(all_images) * sample_fraction))
    if n_samples >= len(all_images):
        sample_paths = all_images
    else:
        indices = np.random.choice(len(all_images), n_samples, replace=False)
        sample_paths = [all_images[i] for i in indices]
    
    # Accumulators per band
    stats = {band: {
        'values': [],
        'min': float('inf'),
        'max': float('-inf'),
    } for band in config.bands.band_order}
    
    for path in sample_paths:
        try:
            data, _ = storage_manager.load_image_by_path(path)
            
            for i, band in enumerate(config.bands.band_order):
                valid = data[i][~np.isnan(data[i])]
                if len(valid) > 0:
                    # Random subsample to avoid memory issues
                    if len(valid) > 1000:
                        valid = np.random.choice(valid, 1000, replace=False)
                    stats[band]['values'].extend(valid.tolist())
                    stats[band]['min'] = min(stats[band]['min'], valid.min())
                    stats[band]['max'] = max(stats[band]['max'], valid.max())
                    
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
    
    # Compute final statistics
    result = {}
    for band in config.bands.band_order:
        values = np.array(stats[band]['values'])
        
        result[band] = {
            'mean': float(np.mean(values)) if len(values) > 0 else None,
            'std': float(np.std(values)) if len(values) > 0 else None,
            'min': float(stats[band]['min']) if stats[band]['min'] != float('inf') else None,
            'max': float(stats[band]['max']) if stats[band]['max'] != float('-inf') else None,
            'percentile_5': float(np.percentile(values, 5)) if len(values) > 0 else None,
            'percentile_95': float(np.percentile(values, 95)) if len(values) > 0 else None,
            'n_samples': len(values),
        }
    
    return result


# =============================================================================
# REPORTING
# =============================================================================

def generate_quality_report(storage_manager) -> str:
    """
    Generate a comprehensive quality report for the dataset.
    
    Returns:
        Formatted report string
    """
    config = storage_manager.config
    
    report = []
    report.append("=" * 60)
    report.append("HIMAWARI-8 DATASET QUALITY REPORT")
    report.append("=" * 60)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Storage statistics
    storage_stats = storage_manager.get_statistics()
    report.append("STORAGE OVERVIEW:")
    report.append(f"  Total images: {storage_stats['total_images']}")
    report.append(f"  Total size: {storage_stats['total_size_mb']:.2f} MB")
    report.append("")
    
    report.append("  By Year:")
    for year, year_stats in storage_stats['by_year'].items():
        expected = 365 * 48 if int(year) != 2024 else 366 * 48  # 48 intervals/day
        coverage = year_stats['count'] / expected * 100
        report.append(f"    {year}: {year_stats['count']} images "
                     f"({coverage:.1f}% coverage), {year_stats['size_mb']:.1f} MB")
    report.append("")
    
    # Validation
    report.append("DATA VALIDATION (sample check):")
    validation = validate_dataset(storage_manager, sample_size=50)
    report.append(f"  Checked: {validation['total_checked']} images")
    report.append(f"  Valid: {validation['valid_count']} ({validation['valid_rate']:.1f}%)")
    
    if validation['issues']:
        report.append(f"  Issues ({len(validation['issues'])}):")
        for issue in validation['issues'][:5]:
            report.append(f"    - {issue}")
        if len(validation['issues']) > 5:
            report.append(f"    ... and {len(validation['issues']) - 5} more")
    report.append("")
    
    # Statistics
    report.append("DATA STATISTICS:")
    try:
        norm_stats = storage_manager.load_normalization_stats()
        for band, stats in norm_stats.items():
            report.append(f"  {band}:")
            report.append(f"    Mean: {stats['mean']:.2f} K")
            report.append(f"    Std:  {stats['std']:.2f} K")
    except FileNotFoundError:
        report.append("  Normalization statistics not yet computed")
    report.append("")
    
    # Configuration summary
    report.append("CONFIGURATION:")
    report.append(f"  Region: {config.geo.lat_min}°N-{config.geo.lat_max}°N, "
                 f"{config.geo.lon_min}°E-{config.geo.lon_max}°E")
    report.append(f"  Resolution: {config.geo.output_height}x{config.geo.output_width}")
    report.append(f"  Bands: {', '.join(config.bands.band_order)}")
    report.append(f"  Interval: {config.temporal.interval_minutes} minutes")
    
    report.append("")
    report.append("=" * 60)
    
    return "\n".join(report)


# =============================================================================
# CLI
# =============================================================================

def main():
    """Command-line interface for utilities."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Himawari Pipeline Utilities')
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Validate command
    val_parser = subparsers.add_parser('validate', help='Validate dataset')
    val_parser.add_argument('--samples', type=int, default=100,
                           help='Number of samples to check')
    
    # Report command
    rep_parser = subparsers.add_parser('report', help='Generate quality report')
    rep_parser.add_argument('--output', type=str, help='Output file path')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Compute statistics')
    stats_parser.add_argument('--fraction', type=float, default=0.1,
                             help='Fraction of data to sample')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize storage
    from storage import StorageManager
    storage = StorageManager()
    
    if args.command == 'validate':
        result = validate_dataset(storage, args.samples)
        print(f"Validation Results:")
        print(f"  Checked: {result['total_checked']}")
        print(f"  Valid: {result['valid_count']} ({result['valid_rate']:.1f}%)")
        print(f"  Issues: {len(result['issues'])}")
        for issue in result['issues'][:10]:
            print(f"    - {issue}")
            
    elif args.command == 'report':
        report = generate_quality_report(storage)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"Report saved to {args.output}")
        else:
            print(report)
            
    elif args.command == 'stats':
        stats = compute_dataset_statistics(storage, args.fraction)
        for band, band_stats in stats.items():
            print(f"{band}:")
            for key, value in band_stats.items():
                if value is not None:
                    print(f"  {key}: {value:.2f}" if isinstance(value, float) 
                          else f"  {key}: {value}")


if __name__ == "__main__":
    main()

