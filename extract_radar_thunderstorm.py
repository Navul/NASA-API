"""
Radar & Thunderstorm Data Extractor - 30-Minute Intervals
Extracts precipitation radar and thunderstorm data using OpenWeatherMap API
Combined with NASA POWER weather data and Google Earth Engine satellite imagery
"""

import ee
import requests
import pandas as pd
import time
from pathlib import Path
from datetime import datetime, timedelta
import sys
import json

try:
    from nasa_power_api import NASAPowerAPI
except ImportError:
    print("❌ Error: nasa_power_api.py not found")
    sys.exit(1)


class RadarThunderstormExtractor:
    """
    Extracts multi-modal data at 30-minute intervals:
    - Weather data: NASA POWER API
    - Satellite images: Google Earth Engine (Landsat 8)
    - Radar images: OpenWeatherMap precipitation layer
    - Thunderstorm alerts: OpenWeatherMap weather alerts
    """
    
    def __init__(self, openweather_api_key):
        """Initialize the extractor"""
        
        self.openweather_key = openweather_api_key
        
        # Initialize Earth Engine
        try:
            ee.Initialize(project='bangladesh-lightning-detection')
            print("✅ Google Earth Engine initialized")
        except Exception as e:
            print(f"❌ Error initializing Earth Engine: {e}")
            sys.exit(1)
        
        # Initialize NASA POWER API
        self.nasa_api = NASAPowerAPI()
        print("✅ NASA POWER API initialized")
        print("✅ OpenWeatherMap API key configured")
        
        # Create directories
        self.base_dir = Path(__file__).parent
        self.satellite_dir = self.base_dir / 'satellite_images_multimodal'
        self.radar_dir = self.base_dir / 'radar_images_multimodal'
        self.data_dir = self.base_dir / 'weather_data_multimodal'
        
        self.satellite_dir.mkdir(exist_ok=True)
        self.radar_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        
        self.satellite_results = []
        self.radar_results = []
        self.weather_data = []
        self.thunderstorm_alerts = []
        
        # API call counters
        self.api_calls = {
            'openweather_radar': 0,
            'openweather_alerts': 0,
            'nasa_power': 0,
            'google_earth': 0
        }
    
    def get_current_weather_alerts(self, lat, lon, location_name):
        """
        Get current weather alerts including thunderstorm warnings
        Uses OpenWeatherMap One Call API
        """
        
        try:
            url = "https://api.openweathermap.org/data/3.0/onecall"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.openweather_key,
                'exclude': 'minutely,hourly,daily'  # Only get alerts
            }
            
            response = requests.get(url, params=params, timeout=30)
            self.api_calls['openweather_alerts'] += 1
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for alerts
                if 'alerts' in data and data['alerts']:
                    for alert in data['alerts']:
                        alert_info = {
                            'location': location_name,
                            'latitude': lat,
                            'longitude': lon,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'event': alert.get('event', 'Unknown'),
                            'start': datetime.fromtimestamp(alert.get('start', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                            'end': datetime.fromtimestamp(alert.get('end', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                            'sender_name': alert.get('sender_name', 'Unknown'),
                            'description': alert.get('description', 'No description'),
                            'tags': ', '.join(alert.get('tags', []))
                        }
                        self.thunderstorm_alerts.append(alert_info)
                        
                        # Check if it's thunderstorm related
                        event_lower = alert_info['event'].lower()
                        if any(keyword in event_lower for keyword in ['thunder', 'lightning', 'storm', 'severe']):
                            print(f"   ⚡ THUNDERSTORM ALERT: {alert_info['event']}")
                        else:
                            print(f"   ⚠️  Weather alert: {alert_info['event']}")
                    
                    return True
                else:
                    print(f"   ✅ No active weather alerts")
                    return False
            else:
                print(f"   ⚠️  Weather alerts API: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error getting weather alerts: {e}")
            return False
    
    def get_precipitation_radar(self, lat, lon, date, time_str, location_name):
        """
        Get precipitation radar image from OpenWeatherMap
        Uses Map Tiles API for radar overlay
        """
        
        try:
            # OpenWeatherMap tiles API
            # Zoom level 10 is good for city-level coverage
            zoom = 10
            
            # Convert lat/lon to tile coordinates
            n = 2 ** zoom
            x = int((lon + 180) / 360 * n)
            y = int((1 - (lat * 3.14159265359 / 180).tan().asinh() / 3.14159265359) / 2 * n)
            
            # Precipitation layer
            layer = 'precipitation_new'  # Current precipitation radar
            
            url = f"https://tile.openweathermap.org/map/{layer}/{zoom}/{x}/{y}.png?appid={self.openweather_key}"
            
            response = requests.get(url, timeout=30)
            self.api_calls['openweather_radar'] += 1
            
            if response.status_code == 200 and len(response.content) > 0:
                # Save radar image
                filename = f"{location_name}_{date}_{time_str.replace(':', '-')}_radar.png"
                filepath = self.radar_dir / filename
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                file_size = len(response.content) / 1024
                
                return {
                    'status': 'success',
                    'filename': filename,
                    'file_size_kb': file_size,
                    'date': date,
                    'time': time_str,
                    'location': location_name,
                    'layer': 'precipitation_radar',
                    'source': 'OpenWeatherMap'
                }
            else:
                return {
                    'status': 'error',
                    'error': f'HTTP {response.status_code}',
                    'date': date,
                    'time': time_str,
                    'location': location_name
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'date': date,
                'time': time_str,
                'location': location_name
            }
    
    def get_current_weather_data(self, lat, lon, location_name):
        """
        Get current weather data including thunderstorm indicators
        Uses OpenWeatherMap Current Weather API
        """
        
        try:
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.openweather_key,
                'units': 'metric'
            }
            
            response = requests.get(url, params=params, timeout=30)
            self.api_calls['openweather_alerts'] += 1
            
            if response.status_code == 200:
                data = response.json()
                
                weather_info = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'location': location_name,
                    'latitude': lat,
                    'longitude': lon,
                    'weather_main': data['weather'][0]['main'],
                    'weather_description': data['weather'][0]['description'],
                    'temperature': data['main']['temp'],
                    'feels_like': data['main']['feels_like'],
                    'pressure': data['main']['pressure'],
                    'humidity': data['main']['humidity'],
                    'wind_speed': data['wind']['speed'],
                    'wind_deg': data['wind'].get('deg', 0),
                    'clouds': data['clouds']['all'],
                    'visibility': data.get('visibility', 0),
                    'rain_1h': data.get('rain', {}).get('1h', 0),
                    'rain_3h': data.get('rain', {}).get('3h', 0)
                }
                
                # Check for thunderstorm
                if 'Thunderstorm' in weather_info['weather_main']:
                    print(f"   ⚡ THUNDERSTORM DETECTED: {weather_info['weather_description']}")
                    weather_info['thunderstorm_active'] = True
                else:
                    weather_info['thunderstorm_active'] = False
                
                return weather_info
            else:
                return None
                
        except Exception as e:
            print(f"   ❌ Error getting current weather: {e}")
            return None
    
    def get_hourly_weather_data(self, lat, lon, date, location_name):
        """
        Get hourly weather data from NASA POWER API for the specified date
        """
        
        try:
            date_formatted = date.replace('-', '')
            
            data = self.nasa_api.get_hourly_data(
                latitude=lat,
                longitude=lon,
                start_date=date_formatted,
                end_date=date_formatted
            )
            
            self.api_calls['nasa_power'] += 1
            
            if data and 'properties' in data and 'parameter' in data['properties']:
                params = data['properties']['parameter']
                weather_records = []
                
                for hour in range(24):
                    hour_key = f"{date_formatted}{hour:02d}"
                    
                    temp = params.get('T2M', {}).get(hour_key)
                    rh = params.get('RH2M', {}).get(hour_key)
                    ws = params.get('WS2M', {}).get(hour_key)
                    precip = params.get('PRECTOTCORR', {}).get(hour_key)
                    solar = params.get('ALLSKY_SFC_SW_DWN', {}).get(hour_key)
                    
                    if temp is not None:
                        # Create records for :00 and :30
                        for minute in [0, 30]:
                            time_str = f"{hour:02d}:{minute:02d}"
                            weather_records.append({
                                'Date': date,
                                'Time': time_str,
                                'DateTime': f"{date} {time_str}",
                                'Location': location_name,
                                'Latitude': lat,
                                'Longitude': lon,
                                'Temperature_2m_C': temp,
                                'Relative_Humidity_%': rh,
                                'Wind_Speed_2m_m/s': ws,
                                'Precipitation_mm': precip,
                                'Solar_Radiation_kWh/m2': solar,
                            })
                
                if weather_records:
                    return weather_records
                    
        except Exception as e:
            print(f"   ❌ NASA POWER API error: {e}")
            return []
    
    def get_landsat8_image(self, lat, lon, date, location_name, cloud_cover_max=70):
        """Get Landsat 8 satellite image from Google Earth Engine"""
        
        try:
            target_date = datetime.strptime(date, '%Y-%m-%d')
            start_date = (target_date - timedelta(days=8)).strftime('%Y-%m-%d')
            end_date = (target_date + timedelta(days=8)).strftime('%Y-%m-%d')
            
            point = ee.Geometry.Point([lon, lat])
            
            collection = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
                .filterBounds(point) \
                .filterDate(start_date, end_date) \
                .filter(ee.Filter.lt('CLOUD_COVER', cloud_cover_max)) \
                .sort('CLOUD_COVER')
            
            count = collection.size().getInfo()
            self.api_calls['google_earth'] += 1
            
            if count == 0:
                return {
                    'status': 'no_data',
                    'error': f'No cloud-free images found',
                    'date': date,
                    'location': location_name,
                }
            
            image = collection.first()
            image_date = ee.Date(image.get('system:time_start')).format('YYYY-MM-dd').getInfo()
            cloud_cover = image.get('CLOUD_COVER').getInfo()
            
            def apply_scale_factors(img):
                optical_bands = img.select('SR_B.').multiply(0.0000275).add(-0.2)
                return img.addBands(optical_bands, None, True)
            
            scaled_image = apply_scale_factors(image)
            rgb = scaled_image.select(['SR_B4', 'SR_B3', 'SR_B2'])
            region = point.buffer(7500).bounds()
            
            url = rgb.getThumbURL({
                'region': region.getInfo(),
                'dimensions': 512,
                'format': 'png',
                'min': 0,
                'max': 0.3
            })
            
            response = requests.get(url, timeout=60)
            
            if response.status_code == 200:
                filename = f"{location_name}_{image_date}_satellite.png"
                filepath = self.satellite_dir / filename
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                file_size = filepath.stat().st_size / 1024
                
                return {
                    'status': 'success',
                    'filename': filename,
                    'file_size_kb': file_size,
                    'date': date,
                    'actual_image_date': image_date,
                    'location': location_name,
                    'cloud_cover': cloud_cover,
                }
            else:
                return {
                    'status': 'error',
                    'error': f'HTTP {response.status_code}',
                    'date': date,
                    'location': location_name
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'date': date,
                'location': location_name
            }
    
    def extract_multimodal_data(self, locations, start_date, num_days=20, check_alerts=True):
        """
        Extract multi-modal data: Weather + Satellite + Radar + Thunderstorm alerts
        
        Args:
            locations: Dict of location names and coordinates
            start_date: Start date 'YYYY-MM-DD'
            num_days: Number of days to extract
            check_alerts: Check for active thunderstorm alerts
        """
        
        print("=" * 80)
        print("🌩️  MULTI-MODAL RADAR & THUNDERSTORM DATA EXTRACTION")
        print("=" * 80)
        print("📊 Data Sources:")
        print("   1. Weather Data: NASA POWER API (30-min intervals)")
        print("   2. Satellite Images: Google Earth Engine (Landsat 8)")
        print("   3. Radar Images: OpenWeatherMap (Precipitation)")
        print("   4. Thunderstorm Alerts: OpenWeatherMap (Real-time)")
        print("=" * 80)
        
        # Generate date range
        start = datetime.strptime(start_date, '%Y-%m-%d')
        dates = [(start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(num_days)]
        
        print(f"\n📍 Locations: {len(locations)}")
        print(f"📅 Date range: {dates[0]} to {dates[-1]} ({num_days} days)")
        print(f"⏱️  Time intervals: 48 per day (every 30 minutes)")
        print(f"📊 Expected weather records: {len(locations) * num_days * 48:,}")
        print(f"🌧️ Expected radar images: {len(locations) * num_days * 48:,}")
        print(f"🛰️  Expected satellite images: {len(locations) * num_days}")
        print(f"⚡ Thunderstorm detection: {'Enabled' if check_alerts else 'Disabled'}")
        print("=" * 80)
        print()
        
        start_time = time.time()
        
        for idx, (location_name, coords) in enumerate(locations.items(), 1):
            print(f"\n{'='*80}")
            print(f"[{idx}/{len(locations)}] 📍 {location_name} ({coords['lat']:.4f}°N, {coords['lon']:.4f}°E)")
            print(f"{'='*80}\n")
            
            # Check for active thunderstorm alerts
            if check_alerts:
                print("⚡ Checking for active thunderstorm alerts...")
                self.get_current_weather_alerts(coords['lat'], coords['lon'], location_name)
                print()
            
            for date_idx, date in enumerate(dates, 1):
                print(f"📅 Date {date_idx}/{num_days}: {date}")
                print("-" * 70)
                
                # Get satellite image (once per day)
                print("🛰️  Extracting satellite image...")
                satellite_result = self.get_landsat8_image(
                    lat=coords['lat'],
                    lon=coords['lon'],
                    date=date,
                    location_name=location_name,
                    cloud_cover_max=70
                )
                self.satellite_results.append(satellite_result)
                
                if satellite_result['status'] == 'success':
                    print(f"   ✅ Satellite: {satellite_result['actual_image_date']} ({satellite_result['cloud_cover']:.1f}% clouds)")
                else:
                    print(f"   ❌ Satellite: {satellite_result.get('error', 'Failed')}")
                
                # Get weather data for the day
                print("☁️  Extracting weather data (30-min intervals)...")
                weather_records = self.get_hourly_weather_data(
                    lat=coords['lat'],
                    lon=coords['lon'],
                    date=date,
                    location_name=location_name
                )
                
                if weather_records:
                    self.weather_data.extend(weather_records)
                    print(f"   ✅ Weather: {len(weather_records)} records")
                else:
                    print(f"   ❌ Weather: No data")
                
                # Get radar images (sample every 2 hours to save API calls)
                # This gives us 12 radar images per day instead of 48
                print("🌧️  Extracting radar images (every 2 hours)...")
                radar_count = 0
                for hour in range(0, 24, 2):  # Every 2 hours
                    time_str = f"{hour:02d}:00"
                    radar_result = self.get_precipitation_radar(
                        lat=coords['lat'],
                        lon=coords['lon'],
                        date=date,
                        time_str=time_str,
                        location_name=location_name
                    )
                    self.radar_results.append(radar_result)
                    
                    if radar_result['status'] == 'success':
                        radar_count += 1
                    
                    time.sleep(0.5)  # Small delay between API calls
                
                print(f"   ✅ Radar: {radar_count}/12 images")
                
                # Check API call limits
                total_calls = sum(self.api_calls.values())
                print(f"\n📊 API Calls: {total_calls} total")
                print(f"   - OpenWeather Radar: {self.api_calls['openweather_radar']}")
                print(f"   - OpenWeather Alerts: {self.api_calls['openweather_alerts']}")
                print(f"   - NASA POWER: {self.api_calls['nasa_power']}")
                print(f"   - Google Earth: {self.api_calls['google_earth']}")
                
                # Stop if approaching free tier limit
                if self.api_calls['openweather_radar'] + self.api_calls['openweather_alerts'] >= 950:
                    print(f"\n⚠️  Approaching OpenWeatherMap free tier limit (1,000/day)")
                    print(f"   Stopping extraction to avoid exceeding quota.")
                    self.save_results()
                    elapsed = time.time() - start_time
                    self.print_summary(elapsed)
                    return
                
                print()
                time.sleep(2)  # Delay between dates
        
        # Save all results
        self.save_results()
        
        # Print summary
        elapsed = time.time() - start_time
        self.print_summary(elapsed)
    
    def save_results(self):
        """Save all extraction results to CSV files"""
        
        print("\n💾 Saving results...")
        
        # Save satellite metadata
        if self.satellite_results:
            satellite_df = pd.DataFrame(self.satellite_results)
            satellite_file = self.data_dir / 'satellite_metadata.csv'
            satellite_df.to_csv(satellite_file, index=False)
            print(f"   ✅ Satellite metadata: {satellite_file}")
        
        # Save radar metadata
        if self.radar_results:
            radar_df = pd.DataFrame(self.radar_results)
            radar_file = self.data_dir / 'radar_metadata.csv'
            radar_df.to_csv(radar_file, index=False)
            print(f"   ✅ Radar metadata: {radar_file}")
        
        # Save weather data
        if self.weather_data:
            weather_df = pd.DataFrame(self.weather_data)
            weather_file = self.data_dir / 'weather_data_30min.csv'
            weather_df.to_csv(weather_file, index=False)
            print(f"   ✅ Weather data: {weather_file}")
        
        # Save thunderstorm alerts
        if self.thunderstorm_alerts:
            alerts_df = pd.DataFrame(self.thunderstorm_alerts)
            alerts_file = self.data_dir / 'thunderstorm_alerts.csv'
            alerts_df.to_csv(alerts_file, index=False)
            print(f"   ⚡ Thunderstorm alerts: {alerts_file}")
    
    def print_summary(self, elapsed_time):
        """Print extraction summary"""
        
        print("\n" + "=" * 80)
        print("📊 EXTRACTION SUMMARY")
        print("=" * 80)
        
        # Weather data
        if self.weather_data:
            weather_df = pd.DataFrame(self.weather_data)
            print(f"\n☁️  WEATHER DATA (30-min intervals):")
            print(f"   ✅ Total records: {len(weather_df):,}")
            print(f"   📅 Dates covered: {weather_df['Date'].nunique()}")
            print(f"   📍 Locations: {weather_df['Location'].nunique()}")
        
        # Satellite images
        if self.satellite_results:
            satellite_df = pd.DataFrame(self.satellite_results)
            successful_sat = len(satellite_df[satellite_df['status'] == 'success'])
            total_sat = len(satellite_df)
            print(f"\n🛰️  SATELLITE IMAGES:")
            print(f"   ✅ Downloaded: {successful_sat}/{total_sat} ({successful_sat/total_sat*100:.1f}%)")
            if successful_sat > 0:
                avg_cloud = satellite_df[satellite_df['status'] == 'success']['cloud_cover'].mean()
                print(f"   ☁️  Avg cloud cover: {avg_cloud:.1f}%")
        
        # Radar images
        if self.radar_results:
            radar_df = pd.DataFrame(self.radar_results)
            successful_radar = len(radar_df[radar_df['status'] == 'success'])
            total_radar = len(radar_df)
            print(f"\n🌧️  RADAR IMAGES:")
            print(f"   ✅ Downloaded: {successful_radar}/{total_radar} ({successful_radar/total_radar*100:.1f}%)")
            if successful_radar > 0:
                total_size = radar_df[radar_df['status'] == 'success']['file_size_kb'].sum()
                print(f"   📦 Total size: {total_size:.1f} KB ({total_size/1024:.1f} MB)")
        
        # Thunderstorm alerts
        if self.thunderstorm_alerts:
            print(f"\n⚡ THUNDERSTORM ALERTS:")
            print(f"   ⚠️  Total alerts detected: {len(self.thunderstorm_alerts)}")
            for alert in self.thunderstorm_alerts:
                print(f"   - {alert['event']} at {alert['location']} ({alert['start']} to {alert['end']})")
        else:
            print(f"\n⚡ THUNDERSTORM ALERTS:")
            print(f"   ✅ No active alerts during extraction period")
        
        # API usage
        total_calls = sum(self.api_calls.values())
        print(f"\n📞 API USAGE:")
        print(f"   Total calls: {total_calls}")
        print(f"   - OpenWeather Radar: {self.api_calls['openweather_radar']}")
        print(f"   - OpenWeather Alerts: {self.api_calls['openweather_alerts']}")
        print(f"   - NASA POWER: {self.api_calls['nasa_power']}")
        print(f"   - Google Earth Engine: {self.api_calls['google_earth']}")
        
        openweather_total = self.api_calls['openweather_radar'] + self.api_calls['openweather_alerts']
        remaining = 1000 - openweather_total
        print(f"   📊 OpenWeather remaining today: {remaining}/1000")
        
        print(f"\n⏱️  PERFORMANCE:")
        print(f"   Total time: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
        
        print("=" * 80)
        
        print("\n📂 OUTPUT DIRECTORIES:")
        print(f"   🛰️  {self.satellite_dir}/ - Satellite images")
        print(f"   🌧️  {self.radar_dir}/ - Radar images")
        print(f"   📊 {self.data_dir}/ - CSV data files")
        
        print("\n✅ Extraction complete!")


def main():
    """Main execution function"""
    
    print("\n" + "=" * 80)
    print("🌩️  RADAR & THUNDERSTORM DATA EXTRACTOR")
    print("   Multi-Modal Dataset for Lightning Detection Research")
    print("=" * 80)
    
    # OpenWeatherMap API key
    API_KEY = "8f170bd0e1e47d3f74c53906cbee8c65"
    
    # Configuration
    locations = {
        'Dhaka': {'lat': 23.8103, 'lon': 90.4125},
    }
    
    # Start from 2023 and extract as much as API allows
    start_date = '2023-01-01'
    num_days = 20  # Will stop early if API limit reached
    
    print(f"\n📍 Location: Dhaka, Bangladesh")
    print(f"📅 Start date: {start_date}")
    print(f"📊 Requested days: {num_days} (will stop at API limit)")
    print(f"⏱️  Intervals: Every 30 minutes (weather)")
    print(f"🌧️  Radar: Every 2 hours (to conserve API calls)")
    print(f"⚡ Thunderstorm detection: Enabled")
    print(f"\n🔑 API Key configured: {API_KEY[:8]}...{API_KEY[-4:]}")
    
    print("\n🚀 Starting extraction...")
    print("⚠️  Note: Will automatically stop at ~950 API calls to stay within free tier\n")
    
    # Create extractor and run
    extractor = RadarThunderstormExtractor(openweather_api_key=API_KEY)
    extractor.extract_multimodal_data(
        locations=locations,
        start_date=start_date,
        num_days=num_days,
        check_alerts=True
    )
    
    print("\n🎉 All done! Check the output directories.")


if __name__ == "__main__":
    main()
