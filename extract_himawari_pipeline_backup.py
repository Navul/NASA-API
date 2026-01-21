import os
import sys
import glob
import shutil
import bz2
import numpy as np
import boto3
import satpy
from satpy import Scene
from pyresample import create_area_def
from botocore import UNSIGNED
from botocore.config import Config
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# --- Configuration ---
# Bangladesh Bounding Box (LightingNet uses 88E-93E, 20N-27N)
area_id = 'bangladesh'
description = 'Bangladesh Region for LightningNet'
# Use lat/lon projection instead of equidistant cylindrical
projection = {'proj': 'longlat', 'datum': 'WGS84'}
# lon_min, lat_min, lon_max, lat_max
area_extent = (88.0, 20.0, 93.0, 27.0)
# Grid shape calculation: (93-88)/0.02 = 250, (27-20)/0.02 = 350
width = int((area_extent[2] - area_extent[0]) / 0.02)
height = int((area_extent[3] - area_extent[1]) / 0.02)

area_def = create_area_def(area_id, projection, width=width, height=height,
                           area_extent=area_extent, description=description)

# Bands used in LightningNet: B13(IR), B08(WV), B10(WV), B14(IR)
# Satpy band names for AHI might differ slightly (e.g., 'B13').
# 10.4um -> B13
# 6.2um -> B08
# 7.3um -> B10
# 11.2um -> B14
TARGET_BANDS = ['B08', 'B10', 'B13', 'B14']

OUTPUT_DIR = 'dataset'
TEMP_DIR = 'temp_download'

def get_satellite_bucket(dt):
    """
    Determine if Himawari-8 or Himawari-9 should be used based on date.
    Himawari-9 replaced Himawari-8 operational services on Dec 13, 2022.
    """
    switch_date = datetime(2022, 12, 13, 0, 0)
    if dt < switch_date:
        return 'noaa-himawari8', 'H08'
    else:
        return 'noaa-himawari9', 'H09'

def download_himawari_data(dt, bands=TARGET_BANDS, temp_dir=TEMP_DIR, verbose=False):
    """
    Download Himawari L1b data for specific bands from AWS S3.
    """
    bucket_name, sat_id = get_satellite_bucket(dt)
    s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
    
    # Prefix structure: AHI-L1b-FLDK/YYYY/mm/dd/HHmm/
    prefix = f"AHI-L1b-FLDK/{dt.year}/{dt.month:02d}/{dt.day:02d}/{dt.hour:02d}{dt.minute:02d}/"
    
    if verbose:
        print(f"Checking bucket: s3://{bucket_name}/{prefix}")
    
    Path(temp_dir).mkdir(parents=True, exist_ok=True)
    downloaded_files = []
    
    # List objects to find files for our bands
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    except Exception as e:
        raise Exception(f"Error listing S3 objects: {e}")

    if 'Contents' not in response:
        raise Exception(f"No data found for {dt}")

    for obj in response['Contents']:
        key = obj['Key']
        filename = key.split('/')[-1]
        
        # Filter for desired bands (file names contain _B08_, _B10_, etc.)
        # Filename format: HS_H08_YYYYmmdd_HHmm_B13_FLDK_R20_S01.DAT.bz2
        
        is_target = False
        for b in bands:
            if f"_{b}_" in filename:
                is_target = True
                break
        
        if is_target:
            local_path = os.path.join(temp_dir, filename)
            if not os.path.exists(local_path):
                s3.download_file(bucket_name, key, local_path)
            
            downloaded_files.append(local_path)
            
            # Decompress
            if filename.endswith('.bz2'):
                dat_path = local_path.replace('.bz2', '')
                if not os.path.exists(dat_path):
                    with bz2.BZ2File(local_path, 'rb') as source, open(dat_path, 'wb') as dest:
                        shutil.copyfileobj(source, dest)
                downloaded_files.append(dat_path)

    # Filter out the .bz2 files from the list we pass to satpy, keep only .DAT
    final_files = [f for f in downloaded_files if f.endswith('.DAT')]
    
    if len(final_files) == 0:
        raise Exception("No DAT files found after download")
    
    return final_files

def normalize_channel(data, band_name, verbose=False):
    """
    Normalize channel data using Min-Max scaling to [0, 1]
    """
    valid_data = data.values
    
    if verbose:
        print(f"  {band_name}: min={np.nanmin(valid_data):.1f}K max={np.nanmax(valid_data):.1f}K")
    
    # Handle NaNs - replace with 0
    valid_data = np.nan_to_num(valid_data, nan=0.0)
    
    # Get min/max from non-zero values
    non_zero = valid_data[valid_data != 0]
    if len(non_zero) == 0:
        return np.zeros_like(valid_data)
    
    min_val = np.min(non_zero)
    max_val = np.max(non_zero)
    
    if max_val - min_val == 0:
        return np.zeros_like(valid_data)
    
    # Normalize: (x - min) / (max - min), keep zeros as zeros
    norm_data = np.where(valid_data == 0, 0, (valid_data - min_val) / (max_val - min_val))
    
    return norm_data

def process_and_save(datetime_target, verbose=False):
    # Check if already exists
    save_dir = Path(OUTPUT_DIR) / f"{datetime_target.year}" / f"{datetime_target.month:02d}" / f"{datetime_target.day:02d}"
    file_prefix = f"{datetime_target.strftime('%Y%m%d_%H%M')}"
    npy_path = save_dir / f"{file_prefix}.npy"
    
    if npy_path.exists():
        if verbose:
            print(f"  Already exists: {npy_path}")
        return
    
    # 1. Download
    files = download_himawari_data(datetime_target, verbose=verbose)

    try:
        # 2. Load Scene
        print("\nLoading Scene with satpy...")
        print(f"Files to load: {len(files)}")
        for f in files:
            print(f"  - {os.path.basename(f)} ({os.path.getsize(f):,} bytes)")
        
        scn = Scene(filenames=files, reader='ahi_hsd')
        
        available = scn.available_dataset_names()
        print(f"\nAvailable datasets: {available}")
        
        # Load required bands
        print(f"\nLoading bands: {TARGET_BANDS}")
        scn.load(TARGET_BANDS)
        
        # Check what was actually loaded
        print(f"Loaded datasets: {list(scn.keys())}")
        
        # Check data before resampling
        for band in TARGET_BANDS:
            if band in scn:
                print(f"\nBand {band} before resampling:")
                print(f"  Shape: {scn[band].shape}")
                print(f"  Min/Max: {scn[band].values.min():.2f} / {scn[band].values.max():.2f}")
                print(f"  Attrs: {scn[band].attrs.get('units', 'unknown')}")
        
        # 3. Resample
        print("\nResampling to Bangladesh grid...")
        print(f"Target area: {area_def}")
        print(f"Target shape: {height}x{width}")
        
        # For geostationary to geographic projection, use bilinear or nearest
        # The default 'nearest' resampler might not work well - use bilinear or ewa
        local_scene = scn.resample(area_def, resampler='bilinear', radius_of_influence=20000)
        
        # Check data after resampling
        print("\nAfter resampling:")
        for band in TARGET_BANDS:
            if band in local_scene:
                print(f"  {band}: {local_scene[band].shape}")
        
        # 4. Prepare Tensor
        print("\n" + "="*60)
        print("PREPARING TENSOR")
        print("="*60)
        
        ordered_bands = ['B13', 'B08', 'B10', 'B14']
        stacked_data = []
        
        for band in ordered_bands:
            if band not in local_scene:
                print(f"ERROR: Band {band} not in resampled scene!")
                continue
                
            data_arr = local_scene[band]
            
            # Check units
            print(f"\nProcessing {band}:")
            if 'units' in data_arr.attrs:
                print(f"  Units: {data_arr.attrs['units']}")
            print(f"  Shape: {data_arr.shape}")
            
            # Normalize
            norm = normalize_channel(data_arr, band)
            stacked_data.append(norm)
        
        if len(stacked_data) != 4:
            print(f"\nERROR: Expected 4 bands, got {len(stacked_data)}")
            return
            
        # Stack: (Channels, H, W) -> Transpose to (H, W, Channels)
        tensor = np.stack(stacked_data, axis=-1) 
        print(f"\nFinal Tensor Shape: {tensor.shape}") # Should be (H, W, 4)
        print(f"Final Tensor Stats:")
        print(f"  Min: {np.min(tensor):.4f}")
        print(f"  Max: {np.max(tensor):.4f}")
        print(f"  Mean: {np.mean(tensor):.4f}")
        print(f"  Non-zero: {np.count_nonzero(tensor):,} / {tensor.size:,}")
        
        # 5. Save
        # Directory structure: dataset/year/month/day/
        save_dir = Path(OUTPUT_DIR) / f"{datetime_target.year}" / f"{datetime_target.month:02d}" / f"{datetime_target.day:02d}"
        save_dir.mkdir(parents=True, exist_ok=True)
        
        file_prefix = f"{datetime_target.strftime('%Y%m%d_%H%M')}"
        
        # Save .npy
        npy_path = save_dir / f"{file_prefix}.npy"
        np.save(npy_path, tensor)
        print(f"Saved NPY: {npy_path}")
        
        # Save .png (visualization of Channel 0 - B13 IR)
        # Invert IR for visualization (clouds white, warm ground dark) so 1-val or just save as is if normalized 0-1 (0=cold/cloud top, 1=warm).
        # Typically IR images show cold clouds as white (low temp) and warm ground as dark (high temp).
        # Our norm: min (cold) -> 0, max (warm) -> 1.
        # So low temp is 0 (black), high temp is 1 (white).
        # To make clouds white and ground dark, we should invert: 1 - data
        
        viz_data = 1.0 - tensor[:, :, 0] # B13 inverted
        
        png_path = save_dir / f"{file_prefix}.png"
        plt.imsave(png_path, viz_data, cmap='gray')
        print(f"Saved PNG: {png_path}")
        
    except Exception as e:
        print(f"Error processing data: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup temp files
        print("Cleaning up temp files...")
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

if __name__ == "__main__":
    # Example Usage:
    # Process one timestamp
    # Note: Himawari time is UTC. 
    # Example: 2023-08-20 06:00 UTC (12:00 PM Bangladesh Standard Time) - Daytime/Afternoon storm likely
    
    target_time = datetime(2023, 8, 20, 6, 0)
    
    print("Starting Himawari Extraction Pipeline...")
    print(f"Target Area: {area_id} {area_extent}")
    process_and_save(target_time)
    print("Done.")
