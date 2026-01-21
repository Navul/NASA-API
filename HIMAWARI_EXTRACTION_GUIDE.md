# Himawari Historical Data Extraction

## Overview
Extracting Himawari-8/9 satellite data for Bangladesh from 2021-01-01 to 2026-01-19 at 30-minute intervals.

## Quick Reference

### Start Extraction
```bash
python extract_historical_himawari.py
```

### Monitor Progress
```bash
python monitor_extraction.py
```

### Pause Extraction
Press `Ctrl+C` in the terminal running the extraction. Progress is automatically saved.

### Resume Extraction
Simply run the extraction script again:
```bash
python extract_historical_himawari.py
```
It will automatically resume from where it left off.

## Extraction Details

- **Total Timestamps**: 88,560
- **Time Range**: 2021-01-01 00:00 to 2026-01-19 23:30 UTC
- **Interval**: 30 minutes
- **Region**: Bangladesh (88-93°E, 20-27°N)
- **Resolution**: ~2km (0.02°)
- **Grid Size**: 350×250 pixels
- **Bands**: 4 channels (B13, B08, B10, B14)

## Output Structure

```
dataset/
├── 2021/
│   ├── 01/
│   │   ├── 01/
│   │   │   ├── 20210101_0000.npy  # 4-channel tensor (350×250×4)
│   │   │   ├── 20210101_0000.png  # Visualization (IR B13)
│   │   │   ├── 20210101_0030.npy
│   │   │   ├── 20210101_0030.png
│   │   │   └── ...
│   │   ├── 02/
│   │   └── ...
│   ├── 02/
│   └── ...
├── 2022/
└── ...
```

## Files

- `extract_historical_himawari.py` - Main extraction script
- `extract_himawari_pipeline.py` - Core processing pipeline
- `monitor_extraction.py` - Progress monitoring tool
- `himawari_extraction_progress.json` - Progress tracking (auto-generated)
- `himawari_extraction_log.txt` - Detailed log (auto-generated)

## Data Format

### NPY Files
- Shape: `(350, 250, 4)`
- Dtype: `float64`
- Range: `[0.0, 1.0]` (normalized)
- Channel order: `[B13, B08, B10, B14]`
  - B13: 10.4μm IR (Infrared)
  - B08: 6.2μm WV (Water Vapor)
  - B10: 7.3μm WV (Water Vapor)
  - B14: 11.2μm IR (Infrared)

### PNG Files
- Grayscale visualization of B13 (IR) channel
- Inverted for cloud visualization (white = cold/clouds)

## Estimated Metrics

- **Processing Time**: ~45 seconds per timestamp
- **Total Time**: ~1,100 hours (~46 days) at full speed
- **Final Dataset Size**: ~15-20 GB
- **Success Rate**: ~95% (some timestamps may be unavailable)

## Error Handling

- Failed timestamps are logged and skipped
- Progress is saved every 10 successful extractions
- Press Ctrl+C to safely pause and save progress
- Check `himawari_extraction_log.txt` for error details

## Troubleshooting

### If extraction seems stuck:
```bash
python monitor_extraction.py
```

### If too many failures:
Check the log file for patterns:
```bash
tail -n 50 himawari_extraction_log.txt
```

### To restart from a specific date:
Edit `START_DATE` in `extract_historical_himawari.py`

### Clean restart (⚠ will lose progress):
```bash
del himawari_extraction_progress.json
del himawari_extraction_log.txt
```

## Tips for Large-Scale Extraction

1. **Run in background**: Use screen/tmux or nohup
2. **Monitor regularly**: Check progress every few hours
3. **Disk space**: Ensure ~25 GB free space
4. **Network**: Stable internet connection required
5. **Resume capability**: Safe to pause and resume anytime

## Next Steps

After extraction completes:
1. Verify data quality with sample visualizations
2. Check for missing timestamps in the log
3. Retry failed timestamps if needed
4. Combine with lightning/weather data for multimodal dataset
