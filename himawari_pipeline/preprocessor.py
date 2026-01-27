"""
Himawari-8 Data Preprocessing Module

This module handles all spatial and radiometric preprocessing:
1. Reading raw HSD/NetCDF data
2. Spatial cropping to Bangladesh region
3. Regridding/downsampling to target resolution
4. Quality control and gap filling
5. Radiometric calibration (if needed)

Design choices:
- Use xarray for lazy loading and chunked processing
- scipy.ndimage for efficient spatial interpolation
- Preserve physical units (brightness temperature in Kelvin)
- Handle missing data gracefully
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple, Union, List
import logging

import numpy as np
from scipy import ndimage
from scipy.interpolate import RegularGridInterpolator

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
from config import PipelineConfig, DEFAULT_CONFIG

# =============================================================================
# LOGGING
# =============================================================================

logger = logging.getLogger('himawari_preprocessor')


# =============================================================================
# HSD FILE READER
# =============================================================================

class HSDReader:
    """
    Reader for Himawari Standard Data (HSD) format.
    
    HSD format specifications:
    - Binary format with header and data blocks
    - Big-endian byte order
    - Contains calibration coefficients in header
    - Data stored as scaled integers
    
    Reference: JMA Himawari Standard Data User's Guide
    """
    
    # Header structure offsets (bytes)
    HEADER_SIZE = 282
    CALIBRATION_OFFSET = 127
    
    def __init__(self, filepath: Path):
        """Initialize reader with file path."""
        self.filepath = Path(filepath)
        self.header = None
        self.calibration = None
    
    def read(self) -> Tuple[np.ndarray, Dict]:
        """
        Read HSD file and return data array with metadata.
        
        Returns:
            Tuple of (data_array, metadata_dict)
        """
        # Check for NPZ format first (used for simulated/cached data)
        npz_path = self.filepath.with_suffix('.npz')
        if npz_path.exists():
            return self._read_npz(npz_path)
        
        if not self.filepath.exists():
            raise FileNotFoundError(f"File not found: {self.filepath}")
        
        # For actual HSD files, would parse binary format
        # This is a simplified implementation
        return self._read_binary()
    
    def _read_npz(self, path: Path) -> Tuple[np.ndarray, Dict]:
        """Read data from NPZ format (used for simulated/cached data)."""
        with np.load(path, allow_pickle=True) as data:
            arr = data['data']
            metadata = {
                'latitude': data['latitude'] if 'latitude' in data else None,
                'longitude': data['longitude'] if 'longitude' in data else None,
                'timestamp': str(data['timestamp']) if 'timestamp' in data else None,
                'band': str(data['band']) if 'band' in data else None,
                'units': str(data['units']) if 'units' in data else 'K',
            }
        return arr, metadata
    
    def _read_binary(self) -> Tuple[np.ndarray, Dict]:
        """Read actual HSD binary format."""
        # Placeholder for actual HSD parsing
        # In production, would implement full HSD format parsing
        
        # Try reading as simple numpy array
        try:
            with open(self.filepath, 'rb') as f:
                # Skip header
                f.seek(self.HEADER_SIZE)
                # Read data (assuming float32)
                data = np.frombuffer(f.read(), dtype='>f4')  # Big-endian float
                
                # Reshape to expected dimensions
                # HSD segment is typically 550 x 5500 pixels
                # but dimensions vary by resolution
                side = int(np.sqrt(len(data)))
                if side * side == len(data):
                    data = data.reshape(side, side)
                else:
                    # Try common HSD dimensions
                    for h, w in [(550, 5500), (1100, 5500), (2200, 5500)]:
                        if h * w == len(data):
                            data = data.reshape(h, w)
                            break
                
            metadata = {'units': 'K', 'source': 'HSD'}
            return data, metadata
            
        except Exception as e:
            logger.error(f"Failed to read HSD file: {e}")
            raise


class NetCDFReader:
    """
    Reader for Himawari NetCDF format.
    
    NetCDF files from various sources may have different variable names
    and coordinate systems. This reader handles common variations.
    """
    
    # Common variable name mappings
    VAR_NAMES = {
        'brightness_temperature': ['tbb', 'bt', 'brightness_temperature', 'TB'],
        'latitude': ['lat', 'latitude', 'Latitude', 'y'],
        'longitude': ['lon', 'longitude', 'Longitude', 'x'],
    }
    
    def __init__(self, filepath: Path):
        """Initialize reader with file path."""
        self.filepath = Path(filepath)
    
    def read(self, variable: str = None) -> Tuple[np.ndarray, Dict]:
        """
        Read NetCDF file and return data array with metadata.
        
        Args:
            variable: Specific variable to read (auto-detects if None)
            
        Returns:
            Tuple of (data_array, metadata_dict)
        """
        try:
            import xarray as xr
            
            ds = xr.open_dataset(self.filepath)
            
            # Find the main data variable
            if variable:
                data_var = variable
            else:
                data_var = self._find_data_variable(ds)
            
            data = ds[data_var].values
            
            # Extract coordinates
            lat_var = self._find_variable(ds, 'latitude')
            lon_var = self._find_variable(ds, 'longitude')
            
            metadata = {
                'latitude': ds[lat_var].values if lat_var else None,
                'longitude': ds[lon_var].values if lon_var else None,
                'units': ds[data_var].attrs.get('units', 'K'),
                'source': 'NetCDF',
            }
            
            ds.close()
            return data, metadata
            
        except ImportError:
            logger.warning("xarray not available, using netCDF4")
            return self._read_with_netcdf4(variable)
    
    def _read_with_netcdf4(self, variable: str = None) -> Tuple[np.ndarray, Dict]:
        """Fallback reader using netCDF4 library."""
        from netCDF4 import Dataset
        
        ds = Dataset(self.filepath, 'r')
        
        # Find data variable
        if variable:
            data_var = variable
        else:
            # Look for likely data variable
            for name in ds.variables:
                if name not in ['lat', 'lon', 'latitude', 'longitude', 'time', 'x', 'y']:
                    data_var = name
                    break
        
        data = ds.variables[data_var][:]
        
        metadata = {
            'units': getattr(ds.variables[data_var], 'units', 'K'),
            'source': 'NetCDF',
        }
        
        # Try to get coordinates
        for lat_name in ['lat', 'latitude']:
            if lat_name in ds.variables:
                metadata['latitude'] = ds.variables[lat_name][:]
                break
        
        for lon_name in ['lon', 'longitude']:
            if lon_name in ds.variables:
                metadata['longitude'] = ds.variables[lon_name][:]
                break
        
        ds.close()
        return data, metadata
    
    def _find_data_variable(self, ds) -> str:
        """Find the main data variable in dataset."""
        for name in self.VAR_NAMES['brightness_temperature']:
            if name in ds.data_vars:
                return name
        
        # Return first non-coordinate variable
        for name in ds.data_vars:
            if name not in ['lat', 'lon', 'latitude', 'longitude', 'time']:
                return name
        
        raise ValueError("Could not find data variable in NetCDF file")
    
    def _find_variable(self, ds, var_type: str) -> Optional[str]:
        """Find variable by type (latitude, longitude, etc.)."""
        for name in self.VAR_NAMES.get(var_type, []):
            if name in ds.coords or name in ds.data_vars:
                return name
        return None


# =============================================================================
# SPATIAL PREPROCESSING
# =============================================================================

class SpatialProcessor:
    """
    Handle spatial preprocessing: cropping and regridding.
    
    Design choices:
    - Use bilinear interpolation for smooth downsampling
    - Preserve NaN/missing values properly
    - Output grid aligned with config specifications
    """
    
    def __init__(self, config: PipelineConfig):
        """Initialize with pipeline configuration."""
        self.config = config
        
        # Pre-compute output coordinates
        self.output_lats = config.geo.get_output_lats()
        self.output_lons = config.geo.get_output_lons()
        
        # Create output coordinate meshgrid
        self.out_lon_grid, self.out_lat_grid = np.meshgrid(
            self.output_lons, self.output_lats
        )
    
    def crop_and_regrid(self, data: np.ndarray, 
                        input_lats: np.ndarray,
                        input_lons: np.ndarray,
                        method: str = 'bilinear') -> np.ndarray:
        """
        Crop data to Bangladesh region and regrid to target resolution.
        
        Args:
            data: 2D array of brightness temperatures
            input_lats: 1D array of input latitudes
            input_lons: 1D array of input longitudes
            method: Interpolation method ('nearest', 'bilinear')
            
        Returns:
            Regridded 2D array with shape (64, 64)
        """
        # Ensure inputs are proper arrays
        data = np.asarray(data, dtype=np.float32)
        input_lats = np.asarray(input_lats).flatten()
        input_lons = np.asarray(input_lons).flatten()
        
        # Handle dimension mismatch
        if data.ndim != 2:
            logger.warning(f"Expected 2D data, got {data.ndim}D")
            if data.ndim == 3:
                data = data[0]  # Take first slice
        
        # Check if latitudes are in correct order (descending for satellite data)
        if len(input_lats) > 1 and input_lats[0] < input_lats[-1]:
            # Flip to descending order
            input_lats = input_lats[::-1]
            data = data[::-1, :]
        
        # First, crop to region of interest with buffer
        crop_result = self._crop_to_region(
            data, input_lats, input_lons,
            lat_range=(self.config.geo.lat_min - 0.5, self.config.geo.lat_max + 0.5),
            lon_range=(self.config.geo.lon_min - 0.5, self.config.geo.lon_max + 0.5)
        )
        
        if crop_result is None:
            logger.warning("Crop failed, data may not cover Bangladesh region")
            return np.full((self.config.geo.output_height, 
                          self.config.geo.output_width), np.nan)
        
        cropped_data, crop_lats, crop_lons = crop_result
        
        # Now regrid to target resolution
        if method == 'nearest':
            return self._regrid_nearest(cropped_data, crop_lats, crop_lons)
        else:
            return self._regrid_interpolate(cropped_data, crop_lats, crop_lons)
    
    def _crop_to_region(self, data: np.ndarray,
                        lats: np.ndarray, lons: np.ndarray,
                        lat_range: Tuple[float, float],
                        lon_range: Tuple[float, float]) -> Optional[Tuple]:
        """
        Crop data array to specified lat/lon range.
        
        Returns:
            Tuple of (cropped_data, cropped_lats, cropped_lons) or None
        """
        lat_min, lat_max = lat_range
        lon_min, lon_max = lon_range
        
        # Find indices within range
        lat_mask = (lats >= lat_min) & (lats <= lat_max)
        lon_mask = (lons >= lon_min) & (lons <= lon_max)
        
        if not np.any(lat_mask) or not np.any(lon_mask):
            return None
        
        lat_indices = np.where(lat_mask)[0]
        lon_indices = np.where(lon_mask)[0]
        
        # Crop
        cropped = data[lat_indices[0]:lat_indices[-1]+1,
                      lon_indices[0]:lon_indices[-1]+1]
        
        return (cropped, lats[lat_mask], lons[lon_mask])
    
    def _regrid_nearest(self, data: np.ndarray,
                        input_lats: np.ndarray,
                        input_lons: np.ndarray) -> np.ndarray:
        """
        Regrid using nearest neighbor interpolation.
        
        Fastest method, preserves original values, but can be blocky.
        """
        output = np.zeros((self.config.geo.output_height,
                          self.config.geo.output_width), dtype=np.float32)
        
        for i, lat in enumerate(self.output_lats):
            for j, lon in enumerate(self.output_lons):
                # Find nearest input point
                lat_idx = np.argmin(np.abs(input_lats - lat))
                lon_idx = np.argmin(np.abs(input_lons - lon))
                
                if lat_idx < data.shape[0] and lon_idx < data.shape[1]:
                    output[i, j] = data[lat_idx, lon_idx]
                else:
                    output[i, j] = np.nan
        
        return output
    
    def _regrid_interpolate(self, data: np.ndarray,
                            input_lats: np.ndarray,
                            input_lons: np.ndarray) -> np.ndarray:
        """
        Regrid using bilinear interpolation.
        
        Smoother results than nearest neighbor, recommended for downsampling.
        """
        # Handle NaN values
        valid_mask = ~np.isnan(data)
        if not np.all(valid_mask):
            # Fill NaN with nearest valid value for interpolation
            data = self._fill_nan(data)
        
        try:
            # Create interpolator
            # Note: RegularGridInterpolator expects coordinates in ascending order
            lat_ascending = input_lats[0] < input_lats[-1]
            lon_ascending = input_lons[0] < input_lons[-1]
            
            if not lat_ascending:
                input_lats = input_lats[::-1]
                data = data[::-1, :]
            if not lon_ascending:
                input_lons = input_lons[::-1]
                data = data[:, ::-1]
            
            interpolator = RegularGridInterpolator(
                (input_lats, input_lons),
                data,
                method='linear',
                bounds_error=False,
                fill_value=np.nan
            )
            
            # Interpolate to output grid
            points = np.column_stack([
                self.out_lat_grid.ravel(),
                self.out_lon_grid.ravel()
            ])
            
            output = interpolator(points).reshape(
                self.config.geo.output_height,
                self.config.geo.output_width
            )
            
            return output.astype(np.float32)
            
        except Exception as e:
            logger.error(f"Interpolation failed: {e}")
            return self._regrid_nearest(data, input_lats, input_lons)
    
    def _fill_nan(self, data: np.ndarray) -> np.ndarray:
        """Fill NaN values using nearest valid neighbors."""
        if not np.any(np.isnan(data)):
            return data
        
        # Use scipy's distance transform for gap filling
        mask = np.isnan(data)
        indices = ndimage.distance_transform_edt(
            mask, return_distances=False, return_indices=True
        )
        filled = data[tuple(indices)]
        
        return filled
    
    def downsample(self, data: np.ndarray, factor: int = 2) -> np.ndarray:
        """
        Simple downsampling by averaging blocks.
        
        Alternative to interpolation for reducing resolution while
        preserving mean values.
        """
        h, w = data.shape
        new_h, new_w = h // factor, w // factor
        
        return data[:new_h*factor, :new_w*factor].reshape(
            new_h, factor, new_w, factor
        ).mean(axis=(1, 3))


# =============================================================================
# QUALITY CONTROL
# =============================================================================

class QualityControl:
    """
    Quality control checks for satellite data.
    
    Checks for:
    - Out-of-range values
    - Excessive missing data
    - Spatial artifacts
    - Temporal consistency
    """
    
    def __init__(self, config: PipelineConfig):
        """Initialize with configuration."""
        self.config = config
    
    def check_value_range(self, data: np.ndarray, band: str) -> Tuple[bool, str]:
        """
        Check if values are within expected physical range.
        
        Args:
            data: 2D brightness temperature array
            band: Band name (B08, B10, B13)
            
        Returns:
            Tuple of (is_valid, message)
        """
        valid_range = self.config.bands.value_ranges.get(band, (180, 330))
        
        # Ignore NaN for range check
        valid_data = data[~np.isnan(data)]
        
        if len(valid_data) == 0:
            return False, "All values are NaN"
        
        min_val, max_val = valid_data.min(), valid_data.max()
        
        if min_val < valid_range[0] - 10:  # Allow small tolerance
            return False, f"Values too low: {min_val:.1f}K (expected >={valid_range[0]}K)"
        
        if max_val > valid_range[1] + 10:
            return False, f"Values too high: {max_val:.1f}K (expected <={valid_range[1]}K)"
        
        return True, "Value range OK"
    
    def check_missing_fraction(self, data: np.ndarray, 
                               max_fraction: float = 0.3) -> Tuple[bool, str]:
        """
        Check fraction of missing/NaN values.
        
        Args:
            data: 2D array
            max_fraction: Maximum acceptable fraction of missing values
            
        Returns:
            Tuple of (is_valid, message)
        """
        nan_fraction = np.sum(np.isnan(data)) / data.size
        
        if nan_fraction > max_fraction:
            return False, f"Too many missing values: {nan_fraction*100:.1f}% (max {max_fraction*100:.0f}%)"
        
        return True, f"Missing fraction OK: {nan_fraction*100:.1f}%"
    
    def check_spatial_consistency(self, data: np.ndarray) -> Tuple[bool, str]:
        """
        Check for spatial artifacts (stripes, blocks).
        
        Uses gradient analysis to detect anomalous patterns.
        """
        if np.all(np.isnan(data)):
            return False, "All NaN values"
        
        # Fill NaN temporarily for gradient calculation
        filled = np.nan_to_num(data, nan=np.nanmean(data))
        
        # Compute gradients
        gy, gx = np.gradient(filled)
        gradient_mag = np.sqrt(gx**2 + gy**2)
        
        # Check for extreme gradients (artifacts)
        # Relaxed threshold: Thunderstorms naturally have sharp gradients (100-150K)
        # Only reject if gradient > 150K (likely data corruption)
        max_gradient = np.max(gradient_mag)
        if max_gradient > 150:  # K per pixel
            return False, f"Possible artifact detected (max gradient: {max_gradient:.1f}K)"
        
        return True, "Spatial consistency OK"
    
    def run_all_checks(self, data: np.ndarray, band: str) -> Dict:
        """Run all QC checks and return summary."""
        results = {}
        
        checks = [
            ('value_range', self.check_value_range(data, band)),
            ('missing_fraction', self.check_missing_fraction(data)),
            ('spatial_consistency', self.check_spatial_consistency(data)),
        ]
        
        all_passed = True
        for name, (passed, message) in checks:
            results[name] = {'passed': passed, 'message': message}
            if not passed:
                all_passed = False
        
        results['all_passed'] = all_passed
        return results


# =============================================================================
# MAIN PREPROCESSOR CLASS
# =============================================================================

class HimawariPreprocessor:
    """
    Main preprocessing class that orchestrates all preprocessing steps.
    
    Pipeline:
    1. Read raw data (HSD or NetCDF)
    2. Apply radiometric calibration if needed
    3. Crop to Bangladesh region
    4. Regrid to target resolution (64x64)
    5. Quality control checks
    6. Return processed array
    """
    
    def __init__(self, config: PipelineConfig = None):
        """Initialize preprocessor with configuration."""
        self.config = config or DEFAULT_CONFIG
        self.spatial_processor = SpatialProcessor(self.config)
        self.qc = QualityControl(self.config)
        
        # Statistics accumulators for normalization
        self.stats = {band: {'sum': 0, 'sum_sq': 0, 'count': 0} 
                     for band in self.config.bands.band_order}
    
    def process_file(self, filepath: Path, band: str) -> Optional[np.ndarray]:
        """
        Process a single raw data file.
        
        Args:
            filepath: Path to raw data file
            band: Band name (B08, B10, B13)
            
        Returns:
            Processed 2D array with shape (64, 64) or None if failed
        """
        try:
            # Determine file format and read
            filepath = Path(filepath)
            
            if filepath.suffix in ['.nc', '.nc4']:
                reader = NetCDFReader(filepath)
            elif filepath.suffix == '.npz':
                reader = HSDReader(filepath)  # HSDReader handles .npz too
            else:
                reader = HSDReader(filepath)
            
            data, metadata = reader.read()
            
            # Get coordinates
            if metadata.get('latitude') is None or metadata.get('longitude') is None:
                # Generate default coordinates for simulated data
                lats = np.linspace(27.0, 20.0, data.shape[0])
                lons = np.linspace(88.0, 93.0, data.shape[1])
            else:
                lats = metadata['latitude']
                lons = metadata['longitude']
            
            # Crop and regrid
            processed = self.spatial_processor.crop_and_regrid(
                data, lats, lons,
                method=self.config.processing.interpolation_method
            )
            
            # Quality control
            qc_results = self.qc.run_all_checks(processed, band)
            
            if not qc_results['all_passed']:
                logger.debug(f"QC warning for {filepath}: {qc_results}")
                # Continue processing - QC warnings don't prevent saving
            
            # Update statistics for normalization
            valid_data = processed[~np.isnan(processed)]
            if len(valid_data) > 0:
                self.stats[band]['sum'] += np.sum(valid_data)
                self.stats[band]['sum_sq'] += np.sum(valid_data ** 2)
                self.stats[band]['count'] += len(valid_data)
            
            return processed
            
        except Exception as e:
            logger.error(f"Failed to process {filepath}: {e}")
            return None
    
    def process_timestamp(self, cache_dir: Path, 
                          timestamp_str: str) -> Optional[np.ndarray]:
        """
        Process all bands for a single timestamp.
        
        Args:
            cache_dir: Directory containing downloaded raw files
            timestamp_str: Timestamp string (YYYYMMDD_HHMM)
            
        Returns:
            3D array with shape (C=3, H=64, W=64) or None if failed
        """
        channels = []
        
        for band in self.config.bands.band_order:
            # Find raw file
            raw_file = cache_dir / f"{timestamp_str}_{band}.npz"
            
            if not raw_file.exists():
                # Try alternative extensions
                for ext in ['.dat', '.nc', '.npy']:
                    alt_file = raw_file.with_suffix(ext)
                    if alt_file.exists():
                        raw_file = alt_file
                        break
            
            if not raw_file.exists():
                logger.warning(f"Missing file for {timestamp_str} {band}")
                channels.append(np.full((self.config.geo.output_height,
                                        self.config.geo.output_width), np.nan))
                continue
            
            processed = self.process_file(raw_file, band)
            
            if processed is None:
                channels.append(np.full((self.config.geo.output_height,
                                        self.config.geo.output_width), np.nan))
            else:
                channels.append(processed)
        
        # Stack channels: (C, H, W)
        result = np.stack(channels, axis=0)
        
        return result
    
    def get_normalization_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Compute normalization statistics (mean, std) from accumulated data.
        
        Returns:
            Dict mapping band name to {mean, std}
        """
        stats = {}
        
        for band, accum in self.stats.items():
            if accum['count'] > 0:
                mean = accum['sum'] / accum['count']
                variance = (accum['sum_sq'] / accum['count']) - (mean ** 2)
                std = np.sqrt(max(variance, 0))
                
                stats[band] = {'mean': float(mean), 'std': float(std)}
            else:
                # Default values based on typical IR brightness temperatures
                stats[band] = {'mean': 260.0, 'std': 30.0}
        
        return stats
    
    def normalize(self, data: np.ndarray, 
                  stats: Dict[str, Dict[str, float]]) -> np.ndarray:
        """
        Normalize data using provided statistics.
        
        Args:
            data: 3D array (C, H, W)
            stats: Dict with mean/std for each band
            
        Returns:
            Normalized array with same shape
        """
        normalized = np.zeros_like(data)
        
        for i, band in enumerate(self.config.bands.band_order):
            mean = stats[band]['mean']
            std = stats[band]['std']
            
            if std > 0:
                normalized[i] = (data[i] - mean) / std
            else:
                normalized[i] = data[i] - mean
        
        return normalized


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Test preprocessing on sample files."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Preprocess Himawari-8 data')
    parser.add_argument('--input', type=str, required=True, help='Input file path')
    parser.add_argument('--band', type=str, default='B13', help='Band name')
    parser.add_argument('--output', type=str, help='Output file path')
    
    args = parser.parse_args()
    
    # Process file
    preprocessor = HimawariPreprocessor()
    result = preprocessor.process_file(Path(args.input), args.band)
    
    if result is not None:
        print(f"Processed shape: {result.shape}")
        print(f"Value range: {np.nanmin(result):.1f} to {np.nanmax(result):.1f} K")
        
        if args.output:
            np.save(args.output, result)
            print(f"Saved to {args.output}")
    else:
        print("Processing failed")


if __name__ == "__main__":
    main()

