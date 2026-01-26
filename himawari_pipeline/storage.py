"""
Storage Pipeline Module for Himawari-8 Dataset

This module handles efficient storage of processed satellite data:
1. Save individual timestamps as tensors
2. Store normalization statistics
3. Manage directory structure
4. Support multiple output formats (NPZ, NPY, Zarr)
5. Provide data loading utilities

Design choices:
- NPZ with compression: Best balance of size and speed for 64x64 images
- Separate normalization stats: Allows flexible normalization strategies
- Year-based directory structure: Easy to process/backup by year
- Include metadata in each file: Self-documenting data
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Iterator
import logging

import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
from config import PipelineConfig, DEFAULT_CONFIG

# =============================================================================
# LOGGING
# =============================================================================

logger = logging.getLogger('himawari_storage')


# =============================================================================
# STORAGE FORMAT HANDLERS
# =============================================================================

class StorageFormat:
    """Base class for storage format implementations."""
    
    def save(self, data: np.ndarray, path: Path, metadata: Dict = None) -> bool:
        raise NotImplementedError
    
    def load(self, path: Path) -> Tuple[np.ndarray, Dict]:
        raise NotImplementedError
    
    def get_extension(self) -> str:
        raise NotImplementedError


class NPZStorage(StorageFormat):
    """
    NumPy compressed archive storage.
    
    Advantages:
    - Good compression ratio (~50% reduction)
    - Fast I/O
    - Can store metadata alongside data
    - Native Python/NumPy (no extra dependencies)
    
    File structure:
    - 'data': Main tensor (C, H, W)
    - 'timestamp': ISO format timestamp string
    - 'bands': Band names
    - 'units': Data units
    - 'normalized': Whether data is normalized
    """
    
    def __init__(self, compressed: bool = True):
        """
        Initialize NPZ storage.
        
        Args:
            compressed: Use compression (recommended)
        """
        self.compressed = compressed
    
    def save(self, data: np.ndarray, path: Path, metadata: Dict = None) -> bool:
        """Save tensor to NPZ file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare save dict
            save_dict = {'data': data.astype(np.float32)}
            
            # Add metadata
            if metadata:
                for key, value in metadata.items():
                    if isinstance(value, (str, int, float, bool)):
                        save_dict[key] = np.array(value)
                    elif isinstance(value, (list, tuple)):
                        save_dict[key] = np.array(value)
                    elif isinstance(value, np.ndarray):
                        save_dict[key] = value
            
            # Save with or without compression
            if self.compressed:
                np.savez_compressed(path, **save_dict)
            else:
                np.savez(path, **save_dict)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save to {path}: {e}")
            return False
    
    def load(self, path: Path) -> Tuple[np.ndarray, Dict]:
        """Load tensor from NPZ file."""
        try:
            with np.load(path, allow_pickle=True) as npz:
                data = npz['data']
                
                metadata = {}
                for key in npz.files:
                    if key != 'data':
                        val = npz[key]
                        # Convert 0-d arrays back to scalars
                        if val.ndim == 0:
                            metadata[key] = val.item()
                        else:
                            metadata[key] = val
                
                return data, metadata
                
        except Exception as e:
            logger.error(f"Failed to load from {path}: {e}")
            raise


class NPYStorage(StorageFormat):
    """
    Simple NumPy binary storage.
    
    Advantages:
    - Fastest I/O
    - Simplest format
    
    Disadvantages:
    - No compression
    - Metadata stored in separate file
    """
    
    def save(self, data: np.ndarray, path: Path, metadata: Dict = None) -> bool:
        """Save tensor to NPY file with separate metadata JSON."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save data
            np.save(path, data.astype(np.float32))
            
            # Save metadata as JSON sidecar
            if metadata:
                meta_path = path.with_suffix('.json')
                # Convert numpy types for JSON
                json_meta = {}
                for k, v in metadata.items():
                    if isinstance(v, np.ndarray):
                        json_meta[k] = v.tolist()
                    elif isinstance(v, (np.integer, np.floating)):
                        json_meta[k] = v.item()
                    else:
                        json_meta[k] = v
                
                with open(meta_path, 'w') as f:
                    json.dump(json_meta, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save to {path}: {e}")
            return False
    
    def load(self, path: Path) -> Tuple[np.ndarray, Dict]:
        """Load tensor from NPY file."""
        try:
            data = np.load(path)
            
            # Try to load metadata
            metadata = {}
            meta_path = path.with_suffix('.json')
            if meta_path.exists():
                with open(meta_path, 'r') as f:
                    metadata = json.load(f)
            
            return data, metadata
            
        except Exception as e:
            logger.error(f"Failed to load from {path}: {e}")
            raise


class ZarrStorage(StorageFormat):
    """
    Zarr array storage (optional, for large-scale deployments).
    
    Advantages:
    - Excellent for very large datasets
    - Supports chunking and parallel I/O
    - Cloud-native (works with S3, GCS)
    
    Note: Requires zarr package
    """
    
    def __init__(self, chunks: Tuple = None, compressor: str = 'blosc'):
        """
        Initialize Zarr storage.
        
        Args:
            chunks: Chunk shape for data
            compressor: Compression algorithm
        """
        self.chunks = chunks or (3, 32, 32)
        self.compressor_name = compressor
    
    def save(self, data: np.ndarray, path: Path, metadata: Dict = None) -> bool:
        """Save tensor to Zarr format."""
        try:
            import zarr
            from numcodecs import Blosc
            
            path.parent.mkdir(parents=True, exist_ok=True)
            
            compressor = Blosc(cname='zstd', clevel=3)
            
            zarr.save_array(
                str(path),
                data.astype(np.float32),
                chunks=self.chunks,
                compressor=compressor
            )
            
            # Store metadata in .zattrs
            if metadata:
                z = zarr.open(str(path), mode='a')
                z.attrs.update(metadata)
            
            return True
            
        except ImportError:
            logger.warning("Zarr not available, falling back to NPZ")
            return NPZStorage().save(data, path.with_suffix('.npz'), metadata)
        except Exception as e:
            logger.error(f"Failed to save Zarr to {path}: {e}")
            return False
    
    def load(self, path: Path) -> Tuple[np.ndarray, Dict]:
        """Load tensor from Zarr format."""
        try:
            import zarr
            
            z = zarr.open(str(path), mode='r')
            data = z[:]
            metadata = dict(z.attrs)
            
            return data, metadata
            
        except ImportError:
            logger.warning("Zarr not available")
            raise
        except Exception as e:
            logger.error(f"Failed to load Zarr from {path}: {e}")
            raise


# =============================================================================
# STORAGE MANAGER
# =============================================================================

class StorageManager:
    """
    Main storage manager for the Himawari dataset.
    
    Handles:
    - Directory structure creation
    - File naming conventions
    - Format selection
    - Statistics storage
    - Data retrieval
    """
    
    def __init__(self, config: PipelineConfig = None, 
                 output_format: str = None):
        """
        Initialize storage manager.
        
        Args:
            config: Pipeline configuration
            output_format: Override format ('npz', 'npy', 'zarr')
        """
        self.config = config or DEFAULT_CONFIG
        
        # Set up base directory
        self.base_dir = self.config.storage.base_dir
        self.images_dir = self.base_dir / self.config.storage.images_dir
        self.stats_dir = self.base_dir / self.config.storage.stats_dir
        
        # Create directories
        self._ensure_directories()
        
        # Set up storage format
        format_name = output_format or self.config.storage.output_format
        self.storage = self._get_storage_handler(format_name)
        self.format_ext = '.' + format_name
    
    def _ensure_directories(self):
        """Create all required directories."""
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.stats_dir.mkdir(parents=True, exist_ok=True)
        
        # Create year subdirectories
        for year in self.config.temporal.years:
            (self.images_dir / str(year)).mkdir(parents=True, exist_ok=True)
    
    def _get_storage_handler(self, format_name: str) -> StorageFormat:
        """Get appropriate storage handler."""
        if format_name == 'npz':
            return NPZStorage(compressed=self.config.storage.compress_npz)
        elif format_name == 'npy':
            return NPYStorage()
        elif format_name == 'zarr':
            return ZarrStorage()
        else:
            logger.warning(f"Unknown format {format_name}, using NPZ")
            return NPZStorage()
    
    def _timestamp_to_path(self, timestamp: datetime) -> Path:
        """
        Convert timestamp to output file path.
        
        Format: images/YYYY/YYYYMMDD_HHMM.npz
        """
        year = timestamp.year
        filename = timestamp.strftime("%Y%m%d_%H%M") + self.format_ext
        return self.images_dir / str(year) / filename
    
    def _path_to_timestamp(self, path: Path) -> datetime:
        """Extract timestamp from file path."""
        stem = path.stem  # e.g., "20230101_0000"
        return datetime.strptime(stem, "%Y%m%d_%H%M")
    
    def save_image(self, data: np.ndarray, timestamp: datetime,
                   normalized: bool = False, 
                   extra_metadata: Dict = None) -> bool:
        """
        Save a single processed image.
        
        Args:
            data: Tensor with shape (C=3, H=64, W=64)
            timestamp: Observation timestamp
            normalized: Whether data has been normalized
            extra_metadata: Additional metadata to store
            
        Returns:
            True if saved successfully
        """
        # Validate shape
        expected_shape = (
            self.config.bands.num_channels,
            self.config.geo.output_height,
            self.config.geo.output_width
        )
        
        if data.shape != expected_shape:
            logger.warning(f"Unexpected shape {data.shape}, expected {expected_shape}")
        
        # Prepare metadata
        metadata = {
            'timestamp': timestamp.isoformat(),
            'bands': self.config.bands.band_order,
            'units': 'K' if not normalized else 'normalized',
            'normalized': normalized,
            'lat_min': self.config.geo.lat_min,
            'lat_max': self.config.geo.lat_max,
            'lon_min': self.config.geo.lon_min,
            'lon_max': self.config.geo.lon_max,
        }
        
        if extra_metadata:
            metadata.update(extra_metadata)
        
        # Get output path
        path = self._timestamp_to_path(timestamp)
        
        # Save
        return self.storage.save(data, path, metadata)
    
    def load_image(self, timestamp: datetime) -> Tuple[np.ndarray, Dict]:
        """
        Load a single image by timestamp.
        
        Args:
            timestamp: Observation timestamp
            
        Returns:
            Tuple of (data array, metadata dict)
        """
        path = self._timestamp_to_path(timestamp)
        
        if not path.exists():
            raise FileNotFoundError(f"No image for {timestamp}")
        
        return self.storage.load(path)
    
    def load_image_by_path(self, path: Path) -> Tuple[np.ndarray, Dict]:
        """Load image from specific path."""
        return self.storage.load(path)
    
    def image_exists(self, timestamp: datetime) -> bool:
        """Check if image exists for timestamp."""
        return self._timestamp_to_path(timestamp).exists()
    
    def list_images(self, year: int = None) -> List[Path]:
        """
        List all saved image files.
        
        Args:
            year: Filter by year (optional)
            
        Returns:
            List of image file paths
        """
        if year:
            search_dir = self.images_dir / str(year)
        else:
            search_dir = self.images_dir
        
        pattern = f"*{self.format_ext}"
        return sorted(search_dir.rglob(pattern))
    
    def iter_images(self, year: int = None, 
                    batch_size: int = 1) -> Iterator[Tuple[List[datetime], np.ndarray]]:
        """
        Iterate over images in batches.
        
        Args:
            year: Filter by year
            batch_size: Number of images per batch
            
        Yields:
            Tuple of (timestamps, stacked data array)
        """
        paths = self.list_images(year)
        
        for i in range(0, len(paths), batch_size):
            batch_paths = paths[i:i + batch_size]
            
            timestamps = []
            data_list = []
            
            for path in batch_paths:
                try:
                    data, meta = self.load_image_by_path(path)
                    timestamps.append(self._path_to_timestamp(path))
                    data_list.append(data)
                except Exception as e:
                    logger.warning(f"Failed to load {path}: {e}")
            
            if data_list:
                yield timestamps, np.stack(data_list, axis=0)
    
    def save_normalization_stats(self, stats: Dict[str, Dict[str, float]]):
        """
        Save normalization statistics.
        
        Args:
            stats: Dict mapping band name to {mean, std}
        """
        stats_path = self.stats_dir / 'normalization_stats.json'
        
        with open(stats_path, 'w') as f:
            json.dump(stats, f, indent=2)
        
        logger.info(f"Saved normalization stats to {stats_path}")
        
        # Also save as numpy for easy loading
        np_stats_path = self.stats_dir / 'normalization_stats.npz'
        
        means = np.array([stats[b]['mean'] for b in self.config.bands.band_order])
        stds = np.array([stats[b]['std'] for b in self.config.bands.band_order])
        
        np.savez(np_stats_path, 
                 means=means, 
                 stds=stds,
                 bands=self.config.bands.band_order)
    
    def load_normalization_stats(self) -> Dict[str, Dict[str, float]]:
        """Load normalization statistics."""
        # Try JSON first
        json_path = self.stats_dir / 'normalization_stats.json'
        if json_path.exists():
            with open(json_path, 'r') as f:
                return json.load(f)
        
        # Fall back to NPZ
        npz_path = self.stats_dir / 'normalization_stats.npz'
        if npz_path.exists():
            with np.load(npz_path, allow_pickle=True) as data:
                means = data['means']
                stds = data['stds']
                bands = data['bands']
                
                return {
                    str(b): {'mean': float(m), 'std': float(s)}
                    for b, m, s in zip(bands, means, stds)
                }
        
        raise FileNotFoundError("No normalization stats found")
    
    def get_statistics(self) -> Dict:
        """Get dataset statistics."""
        stats = {
            'total_images': 0,
            'by_year': {},
            'total_size_mb': 0,
        }
        
        for year in self.config.temporal.years:
            year_images = self.list_images(year)
            year_size = sum(p.stat().st_size for p in year_images)
            
            stats['by_year'][year] = {
                'count': len(year_images),
                'size_mb': year_size / 1024 / 1024
            }
            
            stats['total_images'] += len(year_images)
            stats['total_size_mb'] += year_size / 1024 / 1024
        
        return stats


# =============================================================================
# DATA LOADER UTILITIES
# =============================================================================

class HimawariDataLoader:
    """
    Convenience class for loading Himawari data in various formats.
    
    Useful for:
    - Model training data loading
    - Visualization
    - Analysis
    """
    
    def __init__(self, storage_manager: StorageManager):
        """Initialize with storage manager."""
        self.storage = storage_manager
    
    def load_date_range(self, start: datetime, end: datetime,
                        normalize: bool = True) -> Tuple[np.ndarray, List[datetime]]:
        """
        Load all images in a date range.
        
        Args:
            start: Start datetime
            end: End datetime
            normalize: Apply normalization
            
        Returns:
            Tuple of (data array [N, C, H, W], timestamps)
        """
        all_paths = self.storage.list_images()
        
        selected_paths = []
        for path in all_paths:
            ts = self.storage._path_to_timestamp(path)
            if start <= ts <= end:
                selected_paths.append(path)
        
        data_list = []
        timestamps = []
        
        for path in sorted(selected_paths):
            try:
                data, _ = self.storage.load_image_by_path(path)
                data_list.append(data)
                timestamps.append(self.storage._path_to_timestamp(path))
            except Exception as e:
                logger.warning(f"Failed to load {path}: {e}")
        
        if not data_list:
            return np.array([]), []
        
        data = np.stack(data_list, axis=0)
        
        if normalize:
            try:
                stats = self.storage.load_normalization_stats()
                bands = self.storage.config.bands.band_order
                
                for i, band in enumerate(bands):
                    mean = stats[band]['mean']
                    std = stats[band]['std']
                    if std > 0:
                        data[:, i, :, :] = (data[:, i, :, :] - mean) / std
            except FileNotFoundError:
                logger.warning("No normalization stats available")
        
        return data, timestamps
    
    def load_random_samples(self, n_samples: int, 
                            seed: int = None) -> Tuple[np.ndarray, List[datetime]]:
        """
        Load random samples from the dataset.
        
        Useful for quick visualization or debugging.
        """
        if seed is not None:
            np.random.seed(seed)
        
        all_paths = self.storage.list_images()
        
        if len(all_paths) < n_samples:
            selected_paths = all_paths
        else:
            indices = np.random.choice(len(all_paths), n_samples, replace=False)
            selected_paths = [all_paths[i] for i in indices]
        
        data_list = []
        timestamps = []
        
        for path in selected_paths:
            try:
                data, _ = self.storage.load_image_by_path(path)
                data_list.append(data)
                timestamps.append(self.storage._path_to_timestamp(path))
            except Exception as e:
                logger.warning(f"Failed to load {path}: {e}")
        
        if not data_list:
            return np.array([]), []
        
        return np.stack(data_list, axis=0), timestamps


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Test storage functionality."""
    config = DEFAULT_CONFIG
    storage = StorageManager(config)
    
    print("Storage Manager Test")
    print(f"Base directory: {storage.base_dir}")
    print(f"Images directory: {storage.images_dir}")
    print(f"Format: {storage.format_ext}")
    
    # Test save/load
    test_data = np.random.randn(3, 64, 64).astype(np.float32)
    test_time = datetime(2023, 1, 1, 12, 0)
    
    print("\nTesting save/load...")
    success = storage.save_image(test_data, test_time, normalized=False)
    print(f"Save successful: {success}")
    
    if success:
        loaded_data, loaded_meta = storage.load_image(test_time)
        print(f"Loaded shape: {loaded_data.shape}")
        print(f"Loaded metadata: {loaded_meta}")
        print(f"Data match: {np.allclose(test_data, loaded_data)}")
    
    # Test statistics
    print("\nDataset statistics:")
    stats = storage.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

