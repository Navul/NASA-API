"""
Configuration module for Himawari-8 satellite data pipeline.

This module centralizes all configuration parameters for:
- Geographic boundaries (Bangladesh region)
- Temporal settings (2023-2025, 30-min intervals)
- Band specifications (B08, B10, B13)
- Processing parameters (resolution, normalization)
- Storage settings

Design choice: Centralized config allows easy modification and consistency
across all pipeline components.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np

# =============================================================================
# GEOGRAPHIC CONFIGURATION
# =============================================================================

@dataclass
class GeographicConfig:
    """
    Bangladesh region with small buffer for edge effects.
    
    The region covers Bangladesh's full extent:
    - Latitude: 20°N to 27°N (7° span)
    - Longitude: 88°E to 93°E (5° span)
    """
    lat_min: float = 20.0  # Southern boundary
    lat_max: float = 27.0  # Northern boundary
    lon_min: float = 88.0  # Western boundary
    lon_max: float = 93.0  # Eastern boundary
    
    # Target resolution after downsampling
    # ~0.05° gives roughly 5.5 km at equator (matches operational needs)
    target_resolution: float = 0.05
    
    # Output grid dimensions
    # Height: (27-20) / 0.05 = 140, but we use 64 for efficiency
    # Width: (93-88) / 0.05 = 100, but we use 64 for efficiency
    output_height: int = 64
    output_width: int = 64
    
    def get_extent(self) -> Tuple[float, float, float, float]:
        """Return (lon_min, lon_max, lat_min, lat_max) for cropping."""
        return (self.lon_min, self.lon_max, self.lat_min, self.lat_max)
    
    def get_output_lats(self) -> np.ndarray:
        """Generate output latitude coordinates (N to S for satellite convention)."""
        return np.linspace(self.lat_max, self.lat_min, self.output_height)
    
    def get_output_lons(self) -> np.ndarray:
        """Generate output longitude coordinates (W to E)."""
        return np.linspace(self.lon_min, self.lon_max, self.output_width)


# =============================================================================
# TEMPORAL CONFIGURATION
# =============================================================================

@dataclass
class TemporalConfig:
    """
    Time range and resolution settings.
    
    Himawari-8 provides images every 10 minutes for full disk.
    We aggregate to 30-minute intervals to:
    1. Reduce data volume by 3x
    2. Match typical lightning nowcasting temporal resolution
    3. Smooth out minor atmospheric fluctuations
    """
    start_date: str = "2023-01-01"
    end_date: str = "2025-12-31"
    
    # 30-minute intervals (in minutes)
    interval_minutes: int = 30
    
    # Himawari native resolution (minutes)
    himawari_native_interval: int = 10
    
    # Tolerance for finding nearest observation (minutes)
    time_tolerance_minutes: int = 15
    
    # Years to process
    years: List[int] = field(default_factory=lambda: [2023, 2024, 2025])


# =============================================================================
# BAND CONFIGURATION
# =============================================================================

@dataclass
class BandConfig:
    """
    Himawari-8 AHI band specifications.
    
    Selected bands for lightning/convection detection:
    - B08 (6.2 µm): Upper-level water vapor - detects moisture at ~350 hPa
    - B10 (7.3 µm): Mid-level water vapor - detects moisture at ~500 hPa  
    - B13 (10.4 µm): Clean IR window - cloud-top temperature (most critical)
    
    These bands are optimal for:
    - Identifying deep convection (cold cloud tops in B13)
    - Tracking moisture transport (B08, B10)
    - Detecting overshooting tops (temperature anomalies)
    
    Note: Band numbers follow AHI convention (1-16)
    """
    # Band definitions: {band_name: (wavelength_um, description)}
    bands: Dict[str, Tuple[float, str]] = field(default_factory=lambda: {
        'B08': (6.2, 'upper_level_water_vapor'),
        'B10': (7.3, 'mid_level_water_vapor'),
        'B13': (10.4, 'cloud_top_temperature'),
    })
    
    # Order of bands in output tensor (C dimension)
    band_order: List[str] = field(default_factory=lambda: ['B08', 'B10', 'B13'])
    
    # Physical value ranges for each band (in Kelvin for IR bands)
    # Used for sanity checking and normalization
    value_ranges: Dict[str, Tuple[float, float]] = field(default_factory=lambda: {
        'B08': (180.0, 320.0),  # Brightness temperature range
        'B10': (180.0, 320.0),
        'B13': (180.0, 330.0),  # Slightly wider for hot surfaces
    })
    
    @property
    def num_channels(self) -> int:
        return len(self.band_order)


# =============================================================================
# PROCESSING CONFIGURATION
# =============================================================================

@dataclass
class ProcessingConfig:
    """
    Data processing parameters.
    
    Design choices:
    - Use 'min' aggregation for IR bands: captures coldest (highest) cloud tops
    - Normalize per-band to preserve physical relationships
    - Store normalization stats for inverse transform during inference
    """
    # Temporal aggregation method for 30-min composites
    # Options: 'nearest', 'mean', 'min', 'max'
    # 'min' is best for IR (coldest = highest clouds = most convective)
    aggregation_method: str = 'min'
    
    # Spatial interpolation method
    # Options: 'nearest', 'bilinear', 'cubic'
    interpolation_method: str = 'bilinear'
    
    # Whether to compute running normalization statistics
    compute_normalization: bool = True
    
    # Chunk size for processing (number of timestamps per batch)
    batch_size: int = 48  # One day of 30-min intervals
    
    # Number of parallel download workers
    num_workers: int = 4
    
    # Maximum retries for failed downloads
    max_retries: int = 3
    
    # Timeout for HTTP requests (seconds)
    request_timeout: int = 60


# =============================================================================
# STORAGE CONFIGURATION
# =============================================================================

@dataclass
class StorageConfig:
    """
    Output storage settings.
    
    Design choice: .npz format because:
    - Compressed (smaller than raw .npy)
    - Faster I/O than HDF5 for small arrays
    - Native NumPy support (no extra dependencies)
    - Can store metadata alongside data
    
    Alternative considered: Zarr
    - Better for very large datasets with chunking
    - Overkill for 64x64 images
    """
    # Base output directory
    base_dir: Path = field(default_factory=lambda: Path("d:/Study mat/THESIS/NASA API/himawari_pipeline"))
    
    # Subdirectories
    images_dir: str = "images"
    cache_dir: str = "cache"
    stats_dir: str = "stats"
    logs_dir: str = "logs"
    
    # Output format: 'npy', 'npz', or 'zarr'
    output_format: str = 'npz'
    
    # Whether to compress npz files
    compress_npz: bool = True
    
    # Whether to delete raw files after processing
    delete_raw_after_processing: bool = True
    
    # Progress tracking file
    progress_file: str = "progress.json"
    
    def get_image_path(self, timestamp_str: str, year: int) -> Path:
        """
        Get output path for a processed image.
        
        Args:
            timestamp_str: Format 'YYYYMMDD_HHMM'
            year: Year for directory structure
            
        Returns:
            Full path like: base_dir/images/2023/20230101_0000.npz
        """
        ext = '.npz' if self.output_format == 'npz' else '.npy'
        return self.base_dir / self.images_dir / str(year) / f"{timestamp_str}{ext}"
    
    def ensure_directories(self):
        """Create all required directories."""
        for subdir in [self.images_dir, self.cache_dir, self.stats_dir, self.logs_dir]:
            (self.base_dir / subdir).mkdir(parents=True, exist_ok=True)
        for year in [2023, 2024, 2025]:
            (self.base_dir / self.images_dir / str(year)).mkdir(parents=True, exist_ok=True)


# =============================================================================
# DATA SOURCE CONFIGURATION
# =============================================================================

@dataclass
class DataSourceConfig:
    """
    Himawari-8 data source settings.
    
    Primary sources (in order of preference):
    1. NOAA AWS S3 bucket - fastest, open access
    2. JAXA P-Tree - official archive, requires registration
    3. University of Tokyo mirror - backup option
    
    Note: NOAA AWS has data from 2015-present in near real-time
    but historical archive may have gaps.
    """
    # Primary: NOAA AWS Open Data
    noaa_aws_bucket: str = "noaa-himawari8"
    noaa_aws_region: str = "us-east-1"
    
    # Data product type
    # 'AHI-L1b-FLDK' = Full Disk Level 1b (radiance)
    # 'AHI-L2-FLDK-Clouds' = Cloud products
    product_type: str = "AHI-L1b-FLDK"
    
    # File naming pattern
    # Example: HS_H08_20230101_0000_B13_FLDK_R20_S0101.DAT
    file_pattern: str = "HS_H08_{date}_{time}_B{band:02d}_FLDK_R20_S{segment:04d}.DAT"
    
    # Alternative: Japan Meteorological Agency via HTTP
    jma_base_url: str = "https://www.data.jma.go.jp/mscweb/data/himawari/"
    
    # JAXA P-Tree (requires authentication)
    jaxa_base_url: str = "ftp://ftp.ptree.jaxa.jp/pub/himawari/L1/FLDK/"


# =============================================================================
# MASTER CONFIGURATION CLASS
# =============================================================================

@dataclass
class PipelineConfig:
    """
    Master configuration combining all settings.
    
    Usage:
        config = PipelineConfig()
        config.storage.ensure_directories()
    """
    geo: GeographicConfig = field(default_factory=GeographicConfig)
    temporal: TemporalConfig = field(default_factory=TemporalConfig)
    bands: BandConfig = field(default_factory=BandConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    data_source: DataSourceConfig = field(default_factory=DataSourceConfig)
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate()
    
    def _validate(self):
        """Perform sanity checks on configuration."""
        # Check geographic bounds
        assert self.geo.lat_min < self.geo.lat_max, "Invalid latitude range"
        assert self.geo.lon_min < self.geo.lon_max, "Invalid longitude range"
        
        # Check temporal settings
        assert self.temporal.interval_minutes >= self.temporal.himawari_native_interval
        
        # Check band configuration
        assert len(self.bands.band_order) > 0, "No bands specified"
        
        print("[OK] Configuration validated successfully")
    
    def summary(self) -> str:
        """Return a human-readable summary of the configuration."""
        return f"""
================================================================
         Himawari-8 Pipeline Configuration Summary
================================================================
Geographic Region:
  Latitude:  {self.geo.lat_min}°N to {self.geo.lat_max}°N
  Longitude: {self.geo.lon_min}°E to {self.geo.lon_max}°E
  Output:    {self.geo.output_height}x{self.geo.output_width} grid (~0.05° resolution)
----------------------------------------------------------------
Temporal Settings:
  Period:    {self.temporal.start_date} to {self.temporal.end_date}
  Interval:  {self.temporal.interval_minutes} minutes
----------------------------------------------------------------
Bands:
  B08 (6.2 um)  - Upper-level water vapor
  B10 (7.3 um)  - Mid-level water vapor
  B13 (10.4 um) - Cloud-top temperature
----------------------------------------------------------------
Processing:
  Aggregation: {self.processing.aggregation_method}
  Interpolation: {self.processing.interpolation_method}
----------------------------------------------------------------
Storage:
  Format:    {self.storage.output_format}
  Directory: {self.storage.base_dir}
================================================================
"""


# =============================================================================
# DEFAULT CONFIGURATION INSTANCE
# =============================================================================

# Create default configuration for import
DEFAULT_CONFIG = PipelineConfig()


if __name__ == "__main__":
    # Print configuration summary when run directly
    config = PipelineConfig()
    print(config.summary())

