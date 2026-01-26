"""
Temporal Alignment Module for Himawari-8 Pipeline

This module handles temporal alignment of satellite observations to
fixed 30-minute intervals.

Problem:
- Himawari-8 captures images every 10 minutes
- We want consistent 30-minute intervals for the dataset
- Not all observations may be available (clouds, maintenance, etc.)

Solution approaches:
1. Nearest: Select closest observation to target time
2. Composite: Combine multiple observations within window (mean, min, max)

For lightning nowcasting, we use MIN compositing for IR bands because:
- Cold pixels indicate high cloud tops (deep convection)
- Minimum brightness temperature captures most developed convection
- Reduces temporal aliasing

Design choices:
- Configurable aggregation methods
- Handle missing observations gracefully
- Maintain accurate timestamps for each output
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Generator
import logging

import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
from config import PipelineConfig, DEFAULT_CONFIG

# =============================================================================
# LOGGING
# =============================================================================

logger = logging.getLogger('himawari_temporal')


# =============================================================================
# TIME UTILITIES
# =============================================================================

def round_to_interval(dt: datetime, interval_minutes: int) -> datetime:
    """
    Round datetime to nearest interval boundary.
    
    Example:
        round_to_interval(datetime(2023,1,1,12,23), 30)
        -> datetime(2023,1,1,12,30)
    """
    minutes = dt.hour * 60 + dt.minute
    rounded_minutes = round(minutes / interval_minutes) * interval_minutes
    
    new_hour = rounded_minutes // 60
    new_minute = rounded_minutes % 60
    
    return dt.replace(hour=new_hour, minute=new_minute, second=0, microsecond=0)


def floor_to_interval(dt: datetime, interval_minutes: int) -> datetime:
    """
    Floor datetime to interval boundary.
    
    Example:
        floor_to_interval(datetime(2023,1,1,12,23), 30)
        -> datetime(2023,1,1,12,0)
    """
    minutes = dt.hour * 60 + dt.minute
    floored_minutes = (minutes // interval_minutes) * interval_minutes
    
    new_hour = floored_minutes // 60
    new_minute = floored_minutes % 60
    
    return dt.replace(hour=new_hour, minute=new_minute, second=0, microsecond=0)


def generate_target_timestamps(start_date: str, end_date: str, 
                                interval_minutes: int = 30) -> List[datetime]:
    """
    Generate all target timestamps for the date range.
    
    Args:
        start_date: Start date string 'YYYY-MM-DD'
        end_date: End date string 'YYYY-MM-DD'
        interval_minutes: Interval between timestamps
        
    Returns:
        List of datetime objects
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    
    timestamps = []
    current = start
    
    while current < end:
        timestamps.append(current)
        current += timedelta(minutes=interval_minutes)
    
    return timestamps


def generate_himawari_timestamps(target: datetime, 
                                  window_minutes: int = 30) -> List[datetime]:
    """
    Generate all possible Himawari timestamps within a window.
    
    Himawari captures every 10 minutes, so for a 30-minute window
    there are 3 possible observations (at 00, 10, 20 minutes).
    
    Args:
        target: Target timestamp (interval boundary)
        window_minutes: Window size in minutes
        
    Returns:
        List of possible observation timestamps
    """
    himawari_interval = 10  # minutes
    half_window = window_minutes // 2
    
    start = target - timedelta(minutes=half_window)
    end = target + timedelta(minutes=half_window)
    
    # Align to Himawari 10-minute boundaries
    start_aligned = floor_to_interval(start, himawari_interval)
    
    timestamps = []
    current = start_aligned
    
    while current <= end:
        timestamps.append(current)
        current += timedelta(minutes=himawari_interval)
    
    return timestamps


# =============================================================================
# TEMPORAL ALIGNMENT STRATEGIES
# =============================================================================

class TemporalAligner:
    """
    Base class for temporal alignment strategies.
    
    Subclasses implement different methods of selecting/combining
    observations for each target timestamp.
    """
    
    def __init__(self, config: PipelineConfig):
        """Initialize with pipeline configuration."""
        self.config = config
    
    def align(self, target: datetime, 
              available_data: Dict[datetime, np.ndarray]) -> Optional[np.ndarray]:
        """
        Align data to target timestamp.
        
        Args:
            target: Target timestamp
            available_data: Dict mapping observation times to data arrays
            
        Returns:
            Aligned data array or None if no valid data
        """
        raise NotImplementedError


class NearestAligner(TemporalAligner):
    """
    Select observation nearest to target timestamp.
    
    Pros:
    - Preserves original observation values exactly
    - Simple and fast
    
    Cons:
    - May miss convection if nearest observation is before/after peak
    - Temporal jitter in effective observation time
    """
    
    def align(self, target: datetime,
              available_data: Dict[datetime, np.ndarray]) -> Optional[np.ndarray]:
        """Select data from observation nearest to target."""
        if not available_data:
            return None
        
        tolerance = timedelta(minutes=self.config.temporal.time_tolerance_minutes)
        
        # Find nearest observation
        best_time = None
        best_diff = timedelta.max
        
        for obs_time in available_data.keys():
            diff = abs(obs_time - target)
            
            if diff < best_diff and diff <= tolerance:
                best_diff = diff
                best_time = obs_time
        
        if best_time is None:
            logger.debug(f"No observation within tolerance for {target}")
            return None
        
        return available_data[best_time]


class CompositeAligner(TemporalAligner):
    """
    Composite multiple observations within window.
    
    Aggregation methods:
    - 'mean': Average of observations (smooths variability)
    - 'min': Minimum value (captures coldest clouds - best for convection)
    - 'max': Maximum value (captures warmest surfaces)
    
    For IR brightness temperature and lightning prediction:
    - MIN is preferred because cold pixels = high clouds = deep convection
    """
    
    def __init__(self, config: PipelineConfig, method: str = None):
        """
        Initialize composite aligner.
        
        Args:
            config: Pipeline configuration
            method: Aggregation method ('mean', 'min', 'max')
        """
        super().__init__(config)
        self.method = method or config.processing.aggregation_method
    
    def align(self, target: datetime,
              available_data: Dict[datetime, np.ndarray]) -> Optional[np.ndarray]:
        """Composite observations within window."""
        if not available_data:
            return None
        
        tolerance = timedelta(minutes=self.config.temporal.time_tolerance_minutes)
        
        # Collect observations within window
        valid_data = []
        
        for obs_time, data in available_data.items():
            diff = abs(obs_time - target)
            
            if diff <= tolerance and data is not None:
                valid_data.append(data)
        
        if not valid_data:
            logger.debug(f"No valid observations for {target}")
            return None
        
        # Stack observations
        stacked = np.stack(valid_data, axis=0)  # (N, C, H, W)
        
        # Apply aggregation
        if self.method == 'min':
            # Use nanmin to handle NaN properly
            result = np.nanmin(stacked, axis=0)
        elif self.method == 'max':
            result = np.nanmax(stacked, axis=0)
        elif self.method == 'mean':
            result = np.nanmean(stacked, axis=0)
        else:
            raise ValueError(f"Unknown aggregation method: {self.method}")
        
        return result


class AdaptiveAligner(TemporalAligner):
    """
    Adaptive alignment that chooses method based on data availability.
    
    - If only one observation available: use it directly
    - If multiple observations: compute composite
    - If no observations: return None (gap)
    
    This maximizes data retention while providing composites when possible.
    """
    
    def __init__(self, config: PipelineConfig, method: str = None):
        """Initialize adaptive aligner."""
        super().__init__(config)
        self.composite_method = method or config.processing.aggregation_method
        self.nearest = NearestAligner(config)
        self.composite = CompositeAligner(config, self.composite_method)
    
    def align(self, target: datetime,
              available_data: Dict[datetime, np.ndarray]) -> Optional[np.ndarray]:
        """Adaptively align based on data availability."""
        if not available_data:
            return None
        
        tolerance = timedelta(minutes=self.config.temporal.time_tolerance_minutes)
        
        # Count valid observations
        valid_count = sum(
            1 for obs_time, data in available_data.items()
            if abs(obs_time - target) <= tolerance and data is not None
        )
        
        if valid_count == 0:
            return None
        elif valid_count == 1:
            return self.nearest.align(target, available_data)
        else:
            return self.composite.align(target, available_data)


# =============================================================================
# TEMPORAL ALIGNMENT MANAGER
# =============================================================================

class TemporalAlignmentManager:
    """
    Manager class for temporal alignment across the full dataset.
    
    Handles:
    - Generating target timestamps
    - Matching observations to targets
    - Tracking alignment statistics
    - Managing gaps and missing data
    """
    
    def __init__(self, config: PipelineConfig = None):
        """Initialize alignment manager."""
        self.config = config or DEFAULT_CONFIG
        
        # Choose alignment strategy
        method = self.config.processing.aggregation_method
        if method == 'nearest':
            self.aligner = NearestAligner(self.config)
        else:
            self.aligner = AdaptiveAligner(self.config, method)
        
        # Statistics
        self.stats = {
            'total_targets': 0,
            'aligned': 0,
            'gaps': 0,
            'observations_used': 0
        }
    
    def get_target_timestamps(self) -> List[datetime]:
        """Get all target timestamps from config."""
        return generate_target_timestamps(
            self.config.temporal.start_date,
            self.config.temporal.end_date,
            self.config.temporal.interval_minutes
        )
    
    def get_target_timestamps_for_day(self, date: datetime) -> List[datetime]:
        """Get all target timestamps for a specific day."""
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        timestamps = []
        current = day_start
        interval = timedelta(minutes=self.config.temporal.interval_minutes)
        
        while current < day_end:
            timestamps.append(current)
            current += interval
        
        return timestamps
    
    def find_observations_for_target(self, target: datetime,
                                      available_times: List[datetime]) -> List[datetime]:
        """
        Find observations that could contribute to a target timestamp.
        
        Args:
            target: Target timestamp
            available_times: List of available observation times
            
        Returns:
            List of observation times within the window
        """
        tolerance = timedelta(minutes=self.config.temporal.time_tolerance_minutes)
        
        return [t for t in available_times if abs(t - target) <= tolerance]
    
    def align_observations(self, target: datetime,
                           observations: Dict[datetime, np.ndarray]) -> Optional[np.ndarray]:
        """
        Align observations to target timestamp.
        
        Args:
            target: Target timestamp
            observations: Dict of available observations
            
        Returns:
            Aligned data array or None
        """
        self.stats['total_targets'] += 1
        
        result = self.aligner.align(target, observations)
        
        if result is not None:
            self.stats['aligned'] += 1
            self.stats['observations_used'] += len([
                t for t in observations.keys()
                if abs(t - target) <= timedelta(
                    minutes=self.config.temporal.time_tolerance_minutes
                )
            ])
        else:
            self.stats['gaps'] += 1
        
        return result
    
    def get_gap_timestamps(self, aligned_timestamps: List[datetime]) -> List[datetime]:
        """
        Identify target timestamps that have no aligned data.
        
        Useful for:
        - Identifying data gaps in the dataset
        - Planning gap-filling strategies
        - Quality reporting
        """
        all_targets = set(self.get_target_timestamps())
        aligned_set = set(aligned_timestamps)
        
        return sorted(all_targets - aligned_set)
    
    def get_statistics(self) -> Dict:
        """Get alignment statistics."""
        stats = dict(self.stats)
        
        if stats['total_targets'] > 0:
            stats['alignment_rate'] = stats['aligned'] / stats['total_targets'] * 100
            stats['gap_rate'] = stats['gaps'] / stats['total_targets'] * 100
        else:
            stats['alignment_rate'] = 0
            stats['gap_rate'] = 0
        
        if stats['aligned'] > 0:
            stats['avg_observations_per_target'] = stats['observations_used'] / stats['aligned']
        else:
            stats['avg_observations_per_target'] = 0
        
        return stats
    
    def reset_statistics(self):
        """Reset statistics counters."""
        self.stats = {
            'total_targets': 0,
            'aligned': 0,
            'gaps': 0,
            'observations_used': 0
        }


# =============================================================================
# GAP FILLING STRATEGIES
# =============================================================================

class GapFiller:
    """
    Handle missing data (gaps) in the temporal sequence.
    
    Strategies:
    - Interpolation: Linear interpolation between neighbors
    - Persistence: Use previous valid observation
    - Climatology: Use historical average for that time
    - NaN: Leave as missing (default, safest for science)
    """
    
    def __init__(self, config: PipelineConfig, method: str = 'nan'):
        """
        Initialize gap filler.
        
        Args:
            config: Pipeline configuration
            method: Gap filling method ('nan', 'interpolate', 'persistence')
        """
        self.config = config
        self.method = method
    
    def fill_gaps(self, data_sequence: Dict[datetime, np.ndarray],
                  target_times: List[datetime]) -> Dict[datetime, np.ndarray]:
        """
        Fill gaps in data sequence.
        
        Args:
            data_sequence: Existing data (timestamp -> array)
            target_times: All target timestamps
            
        Returns:
            Complete sequence with gaps filled
        """
        if self.method == 'nan':
            return self._fill_with_nan(data_sequence, target_times)
        elif self.method == 'interpolate':
            return self._fill_with_interpolation(data_sequence, target_times)
        elif self.method == 'persistence':
            return self._fill_with_persistence(data_sequence, target_times)
        else:
            return data_sequence
    
    def _fill_with_nan(self, data_sequence: Dict, 
                       target_times: List[datetime]) -> Dict:
        """Fill gaps with NaN arrays."""
        result = dict(data_sequence)
        
        # Get shape from existing data
        sample = next(iter(data_sequence.values()))
        shape = sample.shape
        
        for t in target_times:
            if t not in result:
                result[t] = np.full(shape, np.nan, dtype=np.float32)
        
        return result
    
    def _fill_with_persistence(self, data_sequence: Dict,
                                target_times: List[datetime]) -> Dict:
        """Fill gaps using previous valid observation."""
        result = dict(data_sequence)
        
        sorted_times = sorted(target_times)
        last_valid = None
        
        for t in sorted_times:
            if t in result:
                last_valid = result[t]
            elif last_valid is not None:
                result[t] = last_valid.copy()
            else:
                # No previous valid data, use NaN
                sample = next(iter(data_sequence.values()))
                result[t] = np.full(sample.shape, np.nan, dtype=np.float32)
        
        return result
    
    def _fill_with_interpolation(self, data_sequence: Dict,
                                  target_times: List[datetime]) -> Dict:
        """Fill gaps using linear interpolation."""
        result = dict(data_sequence)
        
        sorted_times = sorted(target_times)
        existing_times = sorted(data_sequence.keys())
        
        for t in sorted_times:
            if t in result:
                continue
            
            # Find neighbors
            prev_time = None
            next_time = None
            
            for et in existing_times:
                if et < t:
                    prev_time = et
                elif et > t and next_time is None:
                    next_time = et
                    break
            
            if prev_time is not None and next_time is not None:
                # Linear interpolation
                prev_data = data_sequence[prev_time]
                next_data = data_sequence[next_time]
                
                total_diff = (next_time - prev_time).total_seconds()
                prev_weight = (next_time - t).total_seconds() / total_diff
                next_weight = (t - prev_time).total_seconds() / total_diff
                
                result[t] = prev_data * prev_weight + next_data * next_weight
                
            elif prev_time is not None:
                result[t] = data_sequence[prev_time].copy()
            elif next_time is not None:
                result[t] = data_sequence[next_time].copy()
            else:
                sample = next(iter(data_sequence.values()))
                result[t] = np.full(sample.shape, np.nan, dtype=np.float32)
        
        return result


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Test temporal alignment functionality."""
    config = DEFAULT_CONFIG
    manager = TemporalAlignmentManager(config)
    
    # Print target timestamps for first day
    day_targets = manager.get_target_timestamps_for_day(
        datetime(2023, 1, 1)
    )
    
    print(f"Target timestamps for 2023-01-01:")
    for t in day_targets[:10]:
        print(f"  {t.strftime('%Y-%m-%d %H:%M')}")
    print(f"  ... ({len(day_targets)} total)")
    
    # Test alignment with synthetic data
    print("\nTesting alignment:")
    target = datetime(2023, 1, 1, 12, 0)
    
    # Simulate available observations
    observations = {
        datetime(2023, 1, 1, 11, 50): np.random.randn(3, 64, 64).astype(np.float32),
        datetime(2023, 1, 1, 12, 0): np.random.randn(3, 64, 64).astype(np.float32),
        datetime(2023, 1, 1, 12, 10): np.random.randn(3, 64, 64).astype(np.float32),
    }
    
    result = manager.align_observations(target, observations)
    print(f"  Target: {target}")
    print(f"  Available observations: {len(observations)}")
    print(f"  Result shape: {result.shape if result is not None else None}")
    print(f"  Statistics: {manager.get_statistics()}")


if __name__ == "__main__":
    main()

