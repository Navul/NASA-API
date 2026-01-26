# Himawari-8 Satellite Data Pipeline

A modular, efficient Python pipeline for downloading, preprocessing, and storing Himawari-8 geostationary satellite imagery over Bangladesh for lightning nowcasting applications.

## Features

- **Targeted Download**: Only downloads required bands (B08, B10, B13) - no RGB or full 16-band downloads
- **Spatial Cropping**: Automatically crops to Bangladesh region (20°N-27°N, 88°E-93°E)
- **Efficient Storage**: 64×64 tensors saved as compressed NPZ files
- **Temporal Alignment**: Aligns observations to fixed 30-minute intervals
- **Resumable**: Tracks progress for interrupted downloads
- **Multiple Sources**: NOAA AWS (primary) with fallback options

## Quick Start

```bash
# Test with simulated data (no network required)
python run_pipeline.py --simulated --start 2023-01-01 --end 2023-01-07

# Process real data for 2023
python run_pipeline.py --year 2023

# Process custom date range
python run_pipeline.py --start 2023-06-01 --end 2023-06-30
```

## Installation

### Requirements

```bash
pip install numpy scipy requests
```

### Optional Dependencies

```bash
# For visualization
pip install matplotlib

# For NetCDF reading (if using JAXA source)
pip install xarray netCDF4

# For Zarr storage format
pip install zarr numcodecs
```

## Pipeline Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌───────────────────┐
│   Downloader    │───>│   Preprocessor   │───>│ Temporal Aligner  │
│   (B08,B10,B13) │    │ (Crop + Regrid)  │    │ (30-min intervals)│
└─────────────────┘    └──────────────────┘    └───────────────────┘
                                                         │
                                                         v
                                               ┌───────────────────┐
                                               │  Storage Manager  │
                                               │  (NPZ tensors)    │
                                               └───────────────────┘
```

## Directory Structure

```
himawari_pipeline/
├── __init__.py           # Package initialization
├── config.py             # Configuration management
├── downloader.py         # Data acquisition
├── preprocessor.py       # Spatial processing
├── temporal_alignment.py # Temporal alignment
├── storage.py            # Storage management
├── utils.py              # Utilities and validation
├── run_pipeline.py       # Main orchestration script
└── README.md             # This file

Output Structure:
images/
├── 2023/
│   ├── 20230101_0000.npz
│   ├── 20230101_0030.npz
│   └── ...
├── 2024/
└── 2025/
stats/
├── normalization_stats.json
└── normalization_stats.npz
logs/
└── pipeline_*.log
```

## Output Data Format

Each `.npz` file contains:

```python
import numpy as np

# Load a single timestamp
with np.load('images/2023/20230101_0000.npz') as data:
    tensor = data['data']        # Shape: (3, 64, 64)
    # Channel 0: B08 (6.2 µm) - Upper-level water vapor
    # Channel 1: B10 (7.3 µm) - Mid-level water vapor
    # Channel 2: B13 (10.4 µm) - Cloud-top temperature (IR window)
    
    timestamp = str(data['timestamp'])  # ISO format
    bands = data['bands']               # ['B08', 'B10', 'B13']
    units = str(data['units'])          # 'K' (Kelvin)
```

## Band Selection Rationale

| Band | Wavelength | Purpose | Meteorological Use |
|------|------------|---------|-------------------|
| B08 | 6.2 µm | Upper-level water vapor | Jet stream, tropopause moisture |
| B10 | 7.3 µm | Mid-level water vapor | Mid-tropospheric moisture |
| B13 | 10.4 µm | IR window (clean) | Cloud-top temperature, convection detection |

These bands are optimal for lightning/convection detection:
- **B13** (cloud-top temperature): Cold tops indicate deep convection
- **B08/B10** (water vapor): Track moisture feeding storms

## Configuration

Edit `config.py` or create a custom configuration:

```python
from config import PipelineConfig, GeographicConfig

# Custom geographic region
geo = GeographicConfig(
    lat_min=20.0,
    lat_max=27.0,
    lon_min=88.0,
    lon_max=93.0,
    output_height=64,
    output_width=64
)

config = PipelineConfig(geo=geo)
```

## Processing Options

### Temporal Aggregation

```python
# In config.py - ProcessingConfig
aggregation_method: str = 'min'  # Options: 'min', 'max', 'mean', 'nearest'
```

- **min**: Captures coldest cloud tops (best for convection)
- **mean**: Smooth average (general purpose)
- **nearest**: Single closest observation (fastest)

### Storage Format

```python
# In config.py - StorageConfig
output_format: str = 'npz'  # Options: 'npz', 'npy', 'zarr'
```

- **npz**: Recommended (compressed, with metadata)
- **npy**: Fastest I/O (no compression)
- **zarr**: Best for cloud storage / very large datasets

## Data Sources

### Primary: NOAA AWS S3 (Open Access)

```
https://noaa-himawari8.s3.amazonaws.com/AHI-L1b-FLDK/
```

- No authentication required
- Fast downloads from US-East region
- Data available from 2015-present

### Secondary: JAXA P-Tree (Registration Required)

```
ftp://ftp.ptree.jaxa.jp/pub/himawari/L1/FLDK/
```

- Official JAXA archive
- Complete historical data
- Requires free registration

## Usage Examples

### Basic Pipeline Run

```python
from himawari_pipeline import HimawariPipeline

# Initialize pipeline
pipeline = HimawariPipeline()

# Run for specific year
stats = pipeline.run(year=2023)
print(f"Processed: {stats['timestamps_successful']} timestamps")
```

### Loading Data for Training

```python
from himawari_pipeline import StorageManager, HimawariDataLoader
from datetime import datetime

# Initialize storage
storage = StorageManager()

# Load data loader
loader = HimawariDataLoader(storage)

# Load date range (normalized)
data, timestamps = loader.load_date_range(
    start=datetime(2023, 6, 1),
    end=datetime(2023, 6, 30),
    normalize=True
)

print(f"Loaded {len(timestamps)} images, shape: {data.shape}")
# Output: Loaded 1440 images, shape: (1440, 3, 64, 64)
```

### Creating Visualizations

```python
from himawari_pipeline.utils import create_quicklook, create_composite_image

# Load a sample
data, meta = storage.load_image(datetime(2023, 6, 15, 12, 0))

# Quick-look of B13 (cloud-top temperature)
create_quicklook(data, band_idx=2, output_path='quicklook.png', 
                 title='Cloud-Top Temperature')

# False-color composite
rgb = create_composite_image(data, method='ir_composite')
```

## Normalization

Normalization statistics are computed during processing and saved:

```python
# Load normalization stats
stats = storage.load_normalization_stats()
print(stats)
# {'B08': {'mean': 252.3, 'std': 18.5},
#  'B10': {'mean': 261.7, 'std': 16.2},
#  'B13': {'mean': 275.4, 'std': 22.8}}

# Apply normalization manually
normalized = (data - stats['B13']['mean']) / stats['B13']['std']
```

## Performance Estimates

| Metric | Value |
|--------|-------|
| Image size | ~50 KB (compressed NPZ) |
| Images per day | 48 |
| Daily storage | ~2.4 MB |
| Yearly storage | ~850 MB |
| 3-year total | ~2.5 GB |
| Processing time | ~1-2 min/day (with downloads) |

## Troubleshooting

### Download Failures

```python
# Check download statistics
downloader = HimawariDownloader()
print(downloader.get_statistics())

# Resume failed downloads
pipeline.run(resume=True)
```

### Missing Data

```python
# Check for gaps
from temporal_alignment import TemporalAlignmentManager

manager = TemporalAlignmentManager()
gaps = manager.get_gap_timestamps(aligned_timestamps)
print(f"Missing: {len(gaps)} timestamps")
```

### Validation

```python
from utils import validate_dataset, generate_quality_report

# Run validation
report = validate_dataset(storage, sample_size=100)
print(f"Valid rate: {report['valid_rate']:.1f}%")

# Full quality report
full_report = generate_quality_report(storage)
print(full_report)
```

## API Reference

### HimawariPipeline

```python
class HimawariPipeline:
    def __init__(config=None, use_simulated=False, log_level='INFO')
    def run(start_date=None, end_date=None, year=None, resume=True, max_workers=1) -> Dict
    def process_timestamp(timestamp: datetime) -> bool
```

### StorageManager

```python
class StorageManager:
    def save_image(data, timestamp, normalized=False, extra_metadata=None) -> bool
    def load_image(timestamp) -> Tuple[np.ndarray, Dict]
    def list_images(year=None) -> List[Path]
    def iter_images(year=None, batch_size=1) -> Iterator
```

### HimawariPreprocessor

```python
class HimawariPreprocessor:
    def process_file(filepath, band) -> Optional[np.ndarray]
    def process_timestamp(cache_dir, timestamp_str) -> Optional[np.ndarray]
    def get_normalization_stats() -> Dict
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Citation

If you use this pipeline in your research, please cite:

```bibtex
@software{himawari_pipeline,
  title={Himawari-8 Satellite Data Pipeline for Bangladesh},
  author={Your Name},
  year={2024},
  url={https://github.com/your-repo/himawari-pipeline}
}
```

## Acknowledgments

- JAXA and JMA for Himawari-8 data
- NOAA for AWS open data hosting
- Bangladesh Meteorological Department
