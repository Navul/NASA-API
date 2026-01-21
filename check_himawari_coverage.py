"""
Debug script to check actual Himawari data coverage for Bangladesh
"""
import os
import glob
from satpy import Scene
import numpy as np
import matplotlib.pyplot as plt

# Download first
print("Checking existing temp files...")
files = glob.glob('temp_download/*.DAT')
print(f"Found {len(files)} DAT files")

if len(files) == 0:
    print("\nRe-downloading B13 data...")
    from extract_himawari_pipeline import download_himawari_data
    from datetime import datetime
    target_time = datetime(2023, 8, 20, 6, 0)
    files = download_himawari_data(target_time, bands=['B13'])

print(f"\nLoading {len(files)} files with satpy...")
scn = Scene(filenames=files, reader='ahi_hsd')
scn.load(['B13'])

print(f"Loaded dataset: {list(scn.keys())}")
data = scn['B13']

print(f"\nFull Disk Data Info:")
print(f"Shape: {data.shape}")
print(f"Area: {data.attrs.get('area')}")

# Get the data values
vals = data.values
print(f"\nData Statistics:")
print(f"Total pixels: {vals.size:,}")
print(f"NaN count: {np.isnan(vals).sum():,} ({np.isnan(vals).sum()/vals.size*100:.1f}%)")
print(f"Valid pixels: {(~np.isnan(vals)).sum():,}")
print(f"Min (valid): {np.nanmin(vals):.2f} K")
print(f"Max (valid): {np.nanmax(vals):.2f} K")
print(f"Mean (valid): {np.nanmean(vals):.2f} K")

# Check specific regions
print("\nChecking corner samples:")
print(f"Top-left (0:5, 0:5) mean: {np.nanmean(vals[0:5, 0:5]):.2f} K")
print(f"Center mean: {np.nanmean(vals[2750:2755, 2750:2755]):.2f} K")
print(f"Bottom-right mean: {np.nanmean(vals[-5:, -5:]):.2f} K")

# Try to find Bangladesh location in the data
print("\nTrying to find Bangladesh region in full disk...")
if hasattr(data, 'attrs') and 'area' in data.attrs:
    area = data.attrs['area']
    print(f"Satellite projection: {area.crs}")
    print(f"Area extent: {area.area_extent}")
    
    # Bangladesh center: ~90.5E, 23.5N
    # Try to find this in the satellite projection
    try:
        from pyresample import geometry
        # Create a point for Bangladesh center
        bd_lon, bd_lat = 90.5, 23.5
        print(f"\nBangladesh center: {bd_lon}E, {bd_lat}N")
        
        # Get row/col for Bangladesh
        lons = np.array([[bd_lon]])
        lats = np.array([[bd_lat]])
        
        # This will help us understand if Bangladesh is in view
        print("\nNote: Himawari views from ~140.7E longitude")
        print("Bangladesh at ~90.5E is about 50° west of the satellite")
        print("This is within the ~80° field of view, but at a steep angle")
        
    except Exception as e:
        print(f"Could not compute Bangladesh location: {e}")

# Save a sample visualization
print("\nCreating visualization...")
plt.figure(figsize=(12, 10))

# Plot the full disk
plt.subplot(1, 2, 1)
plt.imshow(vals, cmap='gray', vmin=200, vmax=300)
plt.title('Full Disk B13 (IR)')
plt.colorbar(label='Brightness Temperature (K)')

# Plot histogram of valid values
plt.subplot(1, 2, 2)
valid_vals = vals[~np.isnan(vals)]
plt.hist(valid_vals.flatten(), bins=100, edgecolor='black')
plt.xlabel('Brightness Temperature (K)')
plt.ylabel('Frequency')
plt.title('Distribution of Valid Pixels')
plt.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('himawari_full_disk_check.png', dpi=150, bbox_inches='tight')
print("Saved: himawari_full_disk_check.png")

print("\nDone!")
