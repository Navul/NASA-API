# 🚀 QUICK START GUIDE - NASA POWER API

## ✅ Setup Complete!

Your NASA POWER API environment is ready to use. Here's everything you need to know:

---

## 📁 Files Created

1. **`nasa_power_api.py`** - Main API client (import this in your code)
2. **`example_usage.py`** - 6 example scenarios
3. **`view_data.py`** - View and analyze downloaded data
4. **`requirements.txt`** - Python dependencies
5. **`README.md`** - Full documentation

---

## 🎯 How to Use (3 Simple Steps)

### Step 1: Run an Example
```cmd
python example_usage.py
```
This downloads weather data for Dhaka (August 2024) and saves it as CSV.

### Step 2: View the Data
```cmd
python view_data.py
```
This shows you statistics and analysis of the downloaded data.

### Step 3: Customize for Your Needs
Edit `example_usage.py` or create your own script!

---

## 💡 Common Use Cases

### Get Weather Data for Any Location in Bangladesh

```python
from nasa_power_api import NASAPowerAPI

api = NASAPowerAPI()

# Your specific location (replace with your coordinates)
data = api.get_daily_data(
    latitude=23.8103,    # Replace with your latitude
    longitude=90.4125,   # Replace with your longitude
    start_date='20230101',  # Format: YYYYMMDD
    end_date='20231231'
)

# Convert to DataFrame
df = api.convert_to_dataframe(data)

# Save to CSV
api.save_to_csv(df, 'my_location_data.csv')
```

### Get Specific Parameters Only

```python
# Only temperature and rainfall
data = api.get_daily_data(
    latitude=23.8103,
    longitude=90.4125,
    start_date='20230101',
    end_date='20231231',
    parameters=['T2M', 'PRECTOTCORR']  # Temperature and precipitation only
)
```

### Get Data for Multiple Years

```python
# 2015-2024 (10 years)
data = api.get_daily_data(
    latitude=23.8103,
    longitude=90.4125,
    start_date='20150101',
    end_date='20241231'
)
```

---

## 🗺️ Bangladesh City Coordinates

Use these coordinates for major cities:

| City | Latitude | Longitude |
|------|----------|-----------|
| **Dhaka** | 23.8103 | 90.4125 |
| **Chittagong** | 22.3569 | 91.7832 |
| **Sylhet** | 24.8949 | 91.8687 |
| **Rajshahi** | 24.3745 | 88.6042 |
| **Khulna** | 22.8456 | 89.5403 |
| **Cox's Bazar** | 21.4272 | 92.0058 |

Or find coordinates for any location: https://www.latlong.net/

---

## 📊 Available Weather Parameters

### Temperature
- `T2M` - Temperature at 2m (°C)
- `T2M_MAX` - Maximum Temperature
- `T2M_MIN` - Minimum Temperature

### Moisture
- `RH2M` - Relative Humidity (%)
- `PRECTOTCORR` - Precipitation (mm/day)

### Wind
- `WS2M` - Wind Speed (m/s)
- `WD2M` - Wind Direction (degrees)

### Other
- `PS` - Surface Pressure (kPa)
- `ALLSKY_SFC_SW_DWN` - Solar Radiation (kWh/m²/day)

**Full list:** https://power.larc.nasa.gov/docs/services/api/temporal/daily/

---

## ⚠️ Important Notes

### Date Format
Always use `YYYYMMDD` format:
- ✅ Correct: `'20230101'`
- ❌ Wrong: `'2023-01-01'`, `'01/01/2023'`

### Data Availability
- **Daily Data:** 1981 - ~2 months ago
- **Hourly Data:** 2001 - ~2 months ago
- Recent data has a delay (typically 1-2 months)

### No API Key Required
The NASA POWER API is completely free and requires no registration!

### Rate Limiting
- Be respectful to the API
- Add delays between requests (`time.sleep(1)`)
- Don't make thousands of requests rapidly

---

## 🔍 Troubleshooting

### Error: "ModuleNotFoundError"
**Solution:** Install packages
```cmd
pip install requests pandas python-dotenv
```

### Error: "404 Not Found"
**Solution:** Check your date range - use dates before ~2 months ago

### Error: Invalid coordinates
**Solution:** 
- Latitude must be between -90 and 90
- Longitude must be between -180 and 180
- Use decimal format (e.g., 23.8103, not 23°48'37")

---

## 📚 For Your Thesis

### Climate Trend Analysis
```python
# Get 10 years of data
data = api.get_daily_data(
    latitude=23.8103,
    longitude=90.4125,
    start_date='20150101',
    end_date='20241231'
)
df = api.convert_to_dataframe(data)

# Analyze yearly trends
df['Year'] = df.index.year
yearly_avg = df.groupby('Year')['Temperature_2m_C'].mean()
print(yearly_avg)
```

### Seasonal Analysis
```python
# Get full year
df = api.convert_to_dataframe(data)
df['Month'] = df.index.month

# Monthly averages
monthly_stats = df.groupby('Month').agg({
    'Temperature_2m_C': 'mean',
    'Precipitation_mm': 'sum',
    'Relative_Humidity_%': 'mean'
})
```

### Export for Analysis
```python
# Save as CSV for Excel/SPSS
api.save_to_csv(df, 'thesis_data.csv')

# Save as JSON for programming
api.save_to_json(data, 'thesis_data.json')
```

---

## 🎓 Next Steps

1. **Test with your coordinates:** Replace Dhaka coordinates with your study area
2. **Adjust date range:** Use the time period relevant to your thesis
3. **Select parameters:** Choose only the weather variables you need
4. **Analyze data:** Use pandas, Excel, or statistical software
5. **Visualize:** Create charts with matplotlib, seaborn, or Excel

---

## 📞 Resources

- **API Documentation:** https://power.larc.nasa.gov/docs/
- **Data Access Viewer:** https://power.larc.nasa.gov/data-access-viewer/
- **Parameter Definitions:** https://power.larc.nasa.gov/docs/methodology/

---

## ✨ Example Commands

```cmd
# Run examples
python example_usage.py

# View downloaded data
python view_data.py

# Create your own script
python my_thesis_analysis.py
```

---

**🎉 You're all set! Start extracting weather data for your thesis!**

For questions about the API itself, visit: https://power.larc.nasa.gov/docs/support/
