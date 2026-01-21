import os
import sys
import glob
import shutil
import bz2
import numpy as np
import boto3
from botocore import UNSIGNED
from botocore.config import Config
from datetime import datetime
from pathlib import Path

# Test download without processing
def test_download(dt):
    """Test if download works and check file contents"""
    bucket_name = 'noaa-himawari8'
    sat_id = 'H08'
    
    switch_date = datetime(2022, 12, 13, 0, 0)
    if dt >= switch_date:
        bucket_name = 'noaa-himawari9'
        sat_id = 'H09'
    
    s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
    
    prefix = f"AHI-L1b-FLDK/{dt.year}/{dt.month:02d}/{dt.day:02d}/{dt.hour:02d}{dt.minute:02d}/"
    
    print(f"\n=== DIAGNOSTIC INFO ===")
    print(f"Bucket: {bucket_name}")
    print(f"Satellite: {sat_id}")
    print(f"Prefix: {prefix}")
    print(f"Target time: {dt}")
    
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    except Exception as e:
        print(f"❌ Error listing S3 objects: {e}")
        return False
    
    if 'Contents' not in response:
        print(f"❌ No data found for this timestamp")
        print("Trying to find nearby available times...")
        
        # Check what's available for this day
        day_prefix = f"AHI-L1b-FLDK/{dt.year}/{dt.month:02d}/{dt.day:02d}/"
        try:
            day_response = s3.list_objects_v2(Bucket=bucket_name, Prefix=day_prefix, MaxKeys=100)
            if 'Contents' in day_response:
                available_times = set()
                for obj in day_response['Contents']:
                    parts = obj['Key'].split('/')
                    if len(parts) >= 5:
                        available_times.add(parts[4])  # HHmm folder
                
                print(f"Available times for {dt.date()}: {sorted(available_times)[:10]}")
        except Exception as e:
            print(f"Error checking day: {e}")
        
        return False
    
    print(f"✅ Found {len(response['Contents'])} files")
    
    # Check for our target bands
    TARGET_BANDS = ['B08', 'B10', 'B13', 'B14']
    band_files = {b: [] for b in TARGET_BANDS}
    
    for obj in response['Contents']:
        key = obj['Key']
        filename = key.split('/')[-1]
        size = obj['Size']
        
        for band in TARGET_BANDS:
            if f"_{band}_" in filename:
                band_files[band].append((filename, size))
                print(f"  {band}: {filename} ({size:,} bytes)")
    
    # Check if we have all bands
    missing_bands = [b for b in TARGET_BANDS if not band_files[b]]
    if missing_bands:
        print(f"❌ Missing bands: {missing_bands}")
        return False
    
    print(f"✅ All required bands found!")
    
    # Try downloading one small file to test
    test_band = 'B13'
    test_file = band_files[test_band][0]
    test_key = f"{prefix}{test_file[0]}"
    
    temp_dir = 'temp_diagnostic'
    Path(temp_dir).mkdir(exist_ok=True)
    local_path = os.path.join(temp_dir, test_file[0])
    
    print(f"\nDownloading test file: {test_file[0]}")
    try:
        s3.download_file(bucket_name, test_key, local_path)
        actual_size = os.path.getsize(local_path)
        print(f"✅ Downloaded successfully: {actual_size:,} bytes")
        
        # Try decompressing
        if local_path.endswith('.bz2'):
            dat_path = local_path.replace('.bz2', '')
            with bz2.BZ2File(local_path, 'rb') as source, open(dat_path, 'wb') as dest:
                shutil.copyfileobj(source, dest)
            decompressed_size = os.path.getsize(dat_path)
            print(f"✅ Decompressed: {decompressed_size:,} bytes")
        
        return True
        
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False

if __name__ == "__main__":
    # Test with the same timestamp from your script
    target_time = datetime(2023, 8, 20, 6, 0)
    
    print("=" * 60)
    print("HIMAWARI DOWNLOAD DIAGNOSTIC")
    print("=" * 60)
    
    success = test_download(target_time)
    
    if success:
        print("\n✅ Download system is working!")
        print("The issue is likely in the satpy processing/resampling step.")
    else:
        print("\n❌ Download system has issues.")
        print("Try a different timestamp or check AWS availability.")
