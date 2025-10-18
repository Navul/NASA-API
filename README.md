# NASA POWER API - Weather & Climate Data Extraction

Extract weather and climate parameters for Bangladesh (2015-present) using NASA's POWER API.

## 🌟 Features

- **Free & No API Key Required**: NASA POWER API is completely free
- **Historical Data**: Access data from 1981 onwards (hourly from 2001)
- **Multiple Parameters**: Temperature, humidity, precipitation, wind, solar radiation, etc.
- **Daily & Hourly Data**: Choose your temporal resolution
- **Easy to Use**: Simple Python interface

## 📋 Available Parameters

### Temperature
- `T2M` - Temperature at 2 Meters (°C)
- `T2M_MAX` - Maximum Temperature (°C)
- `T2M_MIN` - Minimum Temperature (°C)

### Humidity & Precipitation
- `RH2M` - Relative Humidity at 2 Meters (%)
- `PRECTOTCORR` - Precipitation Corrected (mm/day)

### Wind
- `WS2M` - Wind Speed at 2 Meters (m/s)
- `WD2M` - Wind Direction at 2 Meters (Degrees)

### Pressure & Solar
- `PS` - Surface Pressure (kPa)
- `ALLSKY_SFC_SW_DWN` - All Sky Surface Shortwave Downward Irradiance (kWh/m²/day)

[Full parameter list](https://power.larc.nasa.gov/docs/services/api/temporal/daily/)

## 🚀 Setup

### 1. Install Python (if not already installed)
Download Python 3.8+ from [python.org](https://www.python.org/downloads/)

### 2. Install Required Packages

```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install requests pandas python-dotenv
```

## 💻 Usage

### Basic Example - Fetch Daily Data

```python
from nasa_power_api import NASAPowerAPI

# Initialize API client
api = NASAPowerAPI()

# Fetch data for Dhaka
data = api.get_daily_data(
    latitude=23.8103,
    longitude=90.4125,
    start_date='20240101',
    end_date='20241231'
)

# Convert to DataFrame
df = api.convert_to_dataframe(data)

# Save to CSV
api.save_to_csv(df, 'dhaka_weather.csv')
```

### Run the Example Script

```bash
python nasa_power_api.py
```

### Customize Parameters

```python
# Fetch only temperature and rainfall
parameters = ['T2M', 'PRECTOTCORR']

data = api.get_daily_data(
    latitude=23.8103,
    longitude=90.4125,
    start_date='20200101',
    end_date='20201231',
    parameters=parameters
)
```

### Fetch Hourly Data

```python
data = api.get_hourly_data(
    latitude=23.8103,
    longitude=90.4125,
    start_date='20240101',
    end_date='20240131'
)
```

### Multiple Locations

```python
locations = {
    'Dhaka': {'lat': 23.8103, 'lon': 90.4125},
    'Chittagong': {'lat': 22.3569, 'lon': 91.7832},
}

for city, coords in locations.items():
    data = api.get_daily_data(
        latitude=coords['lat'],
        longitude=coords['lon'],
        start_date='20240101',
        end_date='20241231'
    )
    df = api.convert_to_dataframe(data)
    api.save_to_csv(df, f'{city}_weather.csv')
```

## 📊 Output Format

### CSV Output
The data will be saved as a CSV file with columns:
- Date
- Temperature_2m_C
- Temperature_Max_C
- Temperature_Min_C
- Relative_Humidity_%
- Precipitation_mm
- Wind_Speed_m/s
- Surface_Pressure_kPa
- Solar_Radiation_kWh/m2

### JSON Output
Raw API response in JSON format for advanced use cases.

## 🗺️ Bangladesh Locations (Pre-configured)

- **Dhaka**: 23.8103°N, 90.4125°E
- **Chittagong**: 22.3569°N, 91.7832°E
- **Sylhet**: 24.8949°N, 91.8687°E
- **Rajshahi**: 24.3745°N, 88.6042°E
- **Khulna**: 22.8456°N, 89.5403°E

## 🔗 API Endpoint Structure

```
https://power.larc.nasa.gov/api/temporal/{temporal}/point
```

Example:
```
https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M,PRECTOTCORR&community=ag&start=20200101&end=20201231&latitude=23.8103&longitude=90.4125&format=json
```

## ⚠️ Important Notes

1. **No API Key Required**: The NASA POWER API is completely free and doesn't require registration
2. **Rate Limiting**: Be respectful - add delays between multiple requests
3. **Data Availability**: 
   - Daily data: 1981 onwards
   - Hourly data: 2001 onwards
4. **Coordinates**: Use decimal degrees (e.g., 23.8103, not 23°48'37")
5. **Date Format**: Use YYYYMMDD format (e.g., 20240101)

## 📚 Additional Resources

- [NASA POWER API Documentation](https://power.larc.nasa.gov/docs/services/api/)
- [Parameter Definitions](https://power.larc.nasa.gov/docs/methodology/)
- [Data Access Viewer](https://power.larc.nasa.gov/data-access-viewer/)

## 🎯 Use Cases for Thesis

- Climate trend analysis
- Agricultural planning
- Solar energy potential assessment
- Weather pattern studies
- Climate change impact analysis
- Extreme weather event detection

## 📝 Example Applications

1. **Temperature Trend Analysis**: Analyze temperature changes over years
2. **Rainfall Patterns**: Study monsoon patterns and precipitation trends
3. **Solar Potential**: Assess solar energy potential for different regions
4. **Agricultural Planning**: Use temperature and rainfall data for crop planning
5. **Climate Comparison**: Compare weather patterns across different cities

## 🆘 Troubleshooting

**Issue**: Request timeout
- **Solution**: Reduce date range or try again later

**Issue**: No data returned
- **Solution**: Check coordinates and date format

**Issue**: Missing parameters
- **Solution**: Check [parameter availability](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) for your temporal resolution

## 📧 Support

For API issues, visit: https://power.larc.nasa.gov/docs/support/

---

**Data Source**: NASA Langley Research Center (LaRC) Prediction of Worldwide Energy Resources (POWER) Project
