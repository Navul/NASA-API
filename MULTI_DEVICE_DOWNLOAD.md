# Multi-Device Parallel Download Guide

## Overview
Download Himawari-8 satellite data across **3 devices simultaneously**, with each device handling a different year to speed up the process.

## ✅ What Changed
- Each year now uses a **separate progress file** to prevent conflicts:
  - `pipeline_progress_2023.json` → Device 1
  - `pipeline_progress_2024.json` → Device 2
  - `pipeline_progress_2025.json` → Device 3
- All devices can now run independently without overwriting each other's checkpoints
- Downloads will auto-resume after interruptions (like power outages)

## 🚀 How to Run on Each Device

### Device 1: Download 2023
```bash
cd "d:\Study mat\THESIS\NASA API"
python himawari_pipeline\run_pipeline.py --year 2023
```

### Device 2: Download 2024
```bash
cd "d:\Study mat\THESIS\NASA API"
python himawari_pipeline\run_pipeline.py --year 2024
```

### Device 3: Download 2025
```bash
cd "d:\Study mat\THESIS\NASA API"
python himawari_pipeline\run_pipeline.py --year 2025
```

## 📊 Monitor Progress

Check progress on each device:
```powershell
# Device 1 (2023)
$json = Get-Content "himawari_pipeline\pipeline_progress_2023.json" | ConvertFrom-Json
Write-Host "2023 Progress: $($json.processed.Count) timestamps completed"

# Device 2 (2024)
$json = Get-Content "himawari_pipeline\pipeline_progress_2024.json" | ConvertFrom-Json
Write-Host "2024 Progress: $($json.processed.Count) timestamps completed"

# Device 3 (2025)
$json = Get-Content "himawari_pipeline\pipeline_progress_2025.json" | ConvertFrom-Json
Write-Host "2025 Progress: $($json.processed.Count) timestamps completed"
```

Or check all at once:
```powershell
Get-ChildItem "himawari_pipeline\pipeline_progress_*.json" | ForEach-Object {
    $json = Get-Content $_.FullName | ConvertFrom-Json
    Write-Host "$($_.Name): $($json.processed.Count) completed"
}
```

## 🔄 Resume After Interruption

If download stops (power outage, internet issue, etc.), just **run the same command again**:
- The pipeline automatically detects completed timestamps
- Skips already downloaded data
- Continues from where it stopped

**Your current situation:**
- Last completed: `20230125_2330`
- Next to download: `20230126_0000` onwards
- Simply run: `python himawari_pipeline\run_pipeline.py --year 2023`

## 📁 File Storage

All devices save to the **same output folders** but process different time periods:
- `himawari_pipeline/images/` - Processed satellite images
- `himawari_pipeline/cache/` - Temporary download cache
- `himawari_pipeline/logs/` - Processing logs

This is safe because each device works on different timestamps (different years).

## ⚙️ Advanced Options

### Parallel Workers (within each device)
Speed up processing on powerful devices:
```bash
python himawari_pipeline\run_pipeline.py --year 2023 --workers 4
```

### Resume Control
```bash
# Force fresh start (ignores previous progress)
python himawari_pipeline\run_pipeline.py --year 2023 --no-resume

# Resume (default behavior)
python himawari_pipeline\run_pipeline.py --year 2023 --resume
```

### Dry Run (test without downloading)
```bash
python himawari_pipeline\run_pipeline.py --year 2023 --dry-run
```

## 📝 Expected Data Volume

**Per year (assuming 30-min intervals):**
- Total timestamps: ~17,520 (365 days × 48 intervals)
- Size per timestamp: ~50-100 MB
- **Total per year: ~1-2 TB**

**All 3 years combined: ~3-6 TB**

## ⚠️ Important Notes

1. **Shared Folder**: All devices must have access to the same base directory
2. **Network Share**: If using network storage, ensure stable connection
3. **Disk Space**: Each device needs sufficient local cache space
4. **Internet**: Stable connection required (downloads from AWS S3)
5. **Progress Files**: Don't manually edit `pipeline_progress_*.json` files

## 🐛 Troubleshooting

### Progress files conflict
- **Symptom**: "File already in use" errors
- **Solution**: Each device must use `--year` parameter

### Download stuck at same timestamp
- **Check**: Progress file shows repeated timestamp
- **Solution**: Delete that specific entry from progress file and retry

### Out of disk space
- **Solution**: Enable auto-cleanup in config:
  ```python
  config.storage.delete_raw_after_processing = True
  ```

## 📞 Need Help?

Check logs for each year:
```bash
himawari_pipeline/logs/pipeline_*.log
```

Last processed timestamps:
```powershell
Get-Content "himawari_pipeline\pipeline_progress_2023.json" | ConvertFrom-Json | Select-Object -ExpandProperty processed | Select-Object -Last 1
```
