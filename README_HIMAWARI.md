# Himawari-8/9 Satellite Data Pipeline for Lightning Prediction

This project implements a data pipeline to download, process, and prepare Himawari-8 and Himawari-9 AHI satellite data for lightning prediction models (specifically following the LightningNet methodology).

## 🚀 Features

- **Automated Download**: Fetches data from NOAA's public AWS S3 buckets (`noaa-himawari8`, `noaa-himawari9`).
- **No Credentials Needed**: Uses anonymous S3 access.
- **Smart Switching**: Automatically handles the transition from Himawari-8 to Himawari-9 (Dec 2022).
- **Bangladesh Focused**: Crops data specifically to the Bangladesh region (88E-93E, 20N-27N).
- **ML-Ready**: Outputs processed `.npy` tensors (Height x Width x 4 Channels).
- **Visualization**: Generates `.png` previews of the infrared channel.

## 🛠️ Setup

### Prerequisites

You need Python 3.8+ and the following libraries:

```bash
pip install satpy[all] pyresample boto3 s3fs xarray dask netCDF4 h5netcdf pillow matplotlib
```

*Note: `satpy[all]` installs valid readers including `ahi_hsd` which is required for Himawari .DAT files.*

## 📋 Usage

run the script directly:

```bash
python extract_himawari_pipeline.py
```

### Customizing the Date

Modify the `__main__` section in `extract_himawari_pipeline.py` to change the target date and time:

```python
# Example: August 20, 2023 at 06:00 UTC
target_time = datetime(2023, 8, 20, 6, 0)
```

## 📂 Output Structure

The data is saved in a hierarchical directory structure:

```
dataset/
├── 2023/
│   └── 08/
│       └── 20/
│           ├── 20230820_0600.npy  # 4-channel normalized tensor
│           └── 20230820_0600.png  # Infrared visualization
```

### Channel Order (Tensor)

The `.npy` file contains a 3D array of shape `(Height, Width, 4)`. The channels are ordered as follows:

1. **Index 0**: Band 13 (10.4 µm) - Infrared
2. **Index 1**: Band 08 (6.2 µm) - Upper-level Water Vapor
3. **Index 2**: Band 10 (7.3 µm) - Mid-level Water Vapor
4. **Index 3**: Band 14 (11.2 µm) - Infrared

*Note: All channels are normalized to [0, 1] range.*

## 🗺️ Geographic Details

- **Region**: Bangladesh
- **Bounding Box**: 88°E - 93°E, 20°N - 27°N
- **Resolution**: ~2km (0.02° grid)
- **Projection**: Equidistant Cylindrical (EQC)

## ⚠️ Notes

- **Data Size**: Himawari Full Disk files are large (hundreds of MBs). The script downloads segments to a `temp_download/` folder and deletes them after processing. Ensure you have ~2GB of free space for temporary files per timestamp.
- **Processing Time**: Each timestamp takes roughly 1-2 minutes depending on internet speed and CPU.
