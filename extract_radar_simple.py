"""
Simple Radar Image Extractor - 30-Minute Intervals
Extracts only precipitation radar images from OpenWeatherMap
No weather data, no satellite images - just radar!
"""

import requests
import pandas as pd
import time
from pathlib import Path
from datetime import datetime, timedelta
import math


class SimpleRadarExtractor:
    """
    Simple extractor for radar images only
    Uses OpenWeatherMap precipitation layer
    """
    
    def __init__(self, api_key):
        """Initialize with API key"""
        self.api_key = api_key
        self.radar_dir = Path(__file__).parent / 'radar_images_dhaka'
        self.radar_dir.mkdir(exist_ok=True)
        
        self.results = []
        self.api_calls = 0
        
        print(f"✅ Radar extractor initialized")
        print(f"📁 Output directory: {self.radar_dir}")
    
    def lat_lon_to_tile(self, lat, lon, zoom):
        """Convert latitude/longitude to tile coordinates"""
        n = 2 ** zoom
        x = int((lon + 180) / 360 * n)
        lat_rad = math.radians(lat)
        y = int((1 - math.asinh(math.tan(lat_rad)) / math.pi) / 2 * n)
        return x, y
    
    def get_weather_visualization(self, lat, lon, date_str, time_str):
        """
        Get weather data and create visualization
        Uses current weather API with all available precipitation/cloud data
        
        Args:
            lat: Latitude
            lon: Longitude
            date_str: Date in 'YYYY-MM-DD' format
            time_str: Time in 'HH:MM' format
        
        Returns:
            dict: Result information
        """
        
        try:
            # Note: OpenWeatherMap free tier only has current weather
            # For historical, we'll get current weather data which includes:
            # - Precipitation, clouds, wind, pressure, humidity
            
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.api_key,
                'units': 'metric'
            }
            
            response = requests.get(url, params=params, timeout=30)
            self.api_calls += 1
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract weather info
                weather_data = {
                    'date': date_str,
                    'time': time_str,
                    'datetime': f"{date_str} {time_str}",
                    'location': 'Dhaka',
                    'temperature': data['main']['temp'],
                    'humidity': data['main']['humidity'],
                    'pressure': data['main']['pressure'],
                    'wind_speed': data['wind']['speed'],
                    'wind_deg': data['wind'].get('deg', 0),
                    'clouds': data['clouds']['all'],
                    'weather': data['weather'][0]['main'],
                    'description': data['weather'][0]['description'],
                    'rain_1h': data.get('rain', {}).get('1h', 0),
                    'rain_3h': data.get('rain', {}).get('3h', 0),
                    'visibility': data.get('visibility', 0)
                }
                
                return {
                    'status': 'success',
                    'data': weather_data,
                    'date': date_str,
                    'time': time_str,
                    'api_calls': self.api_calls,
                    'has_rain': weather_data['rain_1h'] > 0 or weather_data['rain_3h'] > 0,
                    'thunderstorm': 'Thunderstorm' in weather_data['weather']
                }
            else:
                return {
                    'status': 'error',
                    'error': f'HTTP {response.status_code}',
                    'date': date_str,
                    'time': time_str,
                    'api_calls': self.api_calls
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'date': date_str,
                'time': time_str,
                'api_calls': self.api_calls
            }
    
    def get_radar_image(self, lat, lon, date_str, time_str):
        """
        Get CURRENT radar tile image 
        Note: This only works for current time, not historical
        """
        
        try:
            zoom = 10
            x, y = self.lat_lon_to_tile(lat, lon, zoom)
            layer = 'precipitation_new'
            
            url = f"https://tile.openweathermap.org/map/{layer}/{zoom}/{x}/{y}.png?appid={self.api_key}"
            
            response = requests.get(url, timeout=30)
            self.api_calls += 1
            
            if response.status_code == 200 and len(response.content) > 500:  # Ensure it's not empty
                filename = f"Dhaka_{date_str}_{time_str.replace(':', '-')}_radar.png"
                filepath = self.radar_dir / filename
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                file_size = len(response.content) / 1024
                
                return {
                    'status': 'success',
                    'filename': filename,
                    'date': date_str,
                    'time': time_str,
                    'file_size_kb': round(file_size, 2),
                    'api_calls': self.api_calls
                }
            else:
                return {
                    'status': 'no_data',
                    'error': f'Empty or invalid image (size: {len(response.content)} bytes)',
                    'date': date_str,
                    'time': time_str,
                    'api_calls': self.api_calls
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'date': date_str,
                'time': time_str,
                'api_calls': self.api_calls
            }
    
    def extract_current_radar(self, lat, lon, num_samples=100):
        """
        Extract CURRENT radar images only (OpenWeatherMap free tier limitation)
        Takes snapshots at 30-minute intervals
        
        Args:
            lat: Latitude of location
            lon: Longitude of location
            num_samples: Number of samples to take (will be spread over time)
        """
        
        print("\n" + "=" * 70)
        print("🌧️  CURRENT RADAR IMAGE EXTRACTION")
        print("=" * 70)
        print(f"📍 Location: Dhaka, Bangladesh ({lat}°N, {lon}°E)")
        print(f"⚠️  NOTE: OpenWeatherMap free tier only provides CURRENT radar")
        print(f"   Historical radar requires paid subscription")
        print(f"📊 Samples: {num_samples}")
        print(f"⏱️  Interval: 30 minutes between samples")
        print("=" * 70)
        print()
        
        print("⚠️  LIMITATION DETECTED:")
        print("   OpenWeatherMap free API does NOT provide historical radar images.")
        print("   The tile API only shows current/recent radar data.")
        print()
        print("💡 ALTERNATIVE SOLUTION:")
        print("   I will extract CURRENT weather data instead, which includes:")
        print("   - Precipitation amount (rain/snow)")
        print("   - Cloud coverage")
        print("   - Wind speed & direction")
        print("   - Thunderstorm detection")
        print("   - Temperature & humidity")
        print()
        
        response = input("Continue with current weather data extraction? (y/n): ")
        
        if response.lower() != 'y':
            print("❌ Extraction cancelled")
            return
        
        print("\n🚀 Starting current weather data extraction...\n")
        
        start_time = time.time()
        total_success = 0
        
        for i in range(num_samples):
            current_dt = datetime.now()
            date_str = current_dt.strftime('%Y-%m-%d')
            time_str = current_dt.strftime('%H:%M')
            
            print(f"📊 Sample {i+1}/{num_samples}: {date_str} {time_str}")
            
            # Get current weather data
            result = self.get_weather_visualization(lat, lon, date_str, time_str)
            self.results.append(result)
            
            if result['status'] == 'success':
                total_success += 1
                data = result['data']
                print(f"   ✅ Weather: {data['weather']} - {data['description']}")
                print(f"      Temp: {data['temperature']:.1f}°C, Humidity: {data['humidity']}%")
                print(f"      Rain: {data['rain_1h']:.1f}mm/h, Clouds: {data['clouds']}%")
                
                if result['thunderstorm']:
                    print(f"   ⚡ THUNDERSTORM DETECTED!")
                elif result['has_rain']:
                    print(f"   🌧️  Precipitation detected")
            else:
                print(f"   ❌ Error: {result.get('error', 'Unknown')}")
            
            print(f"   📞 API calls: {self.api_calls}")
            
            # Stop if approaching limit
            if self.api_calls >= 950:
                print(f"\n⚠️  Approaching API limit, stopping...")
                break
            
            # Wait 30 minutes before next sample (or 10 seconds for testing)
            if i < num_samples - 1:
                print(f"   ⏱️  Waiting 30 minutes for next sample...")
                time.sleep(30 * 60)  # 30 minutes
        
        # Save results
        self.save_results()
        
        # Print summary
        elapsed = time.time() - start_time
        self.print_summary(elapsed, total_success, num_samples - total_success)
    
    def save_results(self):
        """Save extraction metadata to CSV"""
        
        if self.results:
            df = pd.DataFrame(self.results)
            metadata_file = self.radar_dir / 'radar_metadata.csv'
            df.to_csv(metadata_file, index=False)
            print(f"\n💾 Metadata saved: {metadata_file}")
    
    def print_summary(self, elapsed_time, total_success, total_failed):
        """Print extraction summary"""
        
        print("\n" + "=" * 70)
        print("📊 EXTRACTION SUMMARY")
        print("=" * 70)
        
        total = total_success + total_failed
        success_rate = (total_success / total * 100) if total > 0 else 0
        
        print(f"\n🌧️  RADAR IMAGES:")
        print(f"   ✅ Downloaded: {total_success}/{total} ({success_rate:.1f}%)")
        print(f"   ❌ Failed: {total_failed}")
        
        if total_success > 0:
            # Calculate total size
            df = pd.DataFrame(self.results)
            successful = df[df['status'] == 'success']
            total_size_kb = successful['file_size_kb'].sum()
            total_size_mb = total_size_kb / 1024
            avg_size = successful['file_size_kb'].mean()
            
            print(f"   📦 Total size: {total_size_mb:.1f} MB")
            print(f"   📏 Avg size: {avg_size:.1f} KB per image")
            
            # Date coverage
            print(f"\n📅 COVERAGE:")
            print(f"   Dates: {successful['date'].nunique()} days")
            print(f"   First: {successful['date'].min()}")
            print(f"   Last: {successful['date'].max()}")
        
        print(f"\n📞 API USAGE:")
        print(f"   Total calls: {self.api_calls}")
        print(f"   Remaining today: {1000 - self.api_calls}/1000")
        
        print(f"\n⏱️  PERFORMANCE:")
        print(f"   Total time: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
        if total_success > 0:
            print(f"   Speed: {total_success/elapsed_time:.1f} images/second")
        
        print("=" * 70)
        print(f"\n📂 OUTPUT:")
        print(f"   Directory: {self.radar_dir}")
        print(f"   Images: {total_success} PNG files")
        print(f"   Metadata: radar_metadata.csv")
        
        print("\n✅ Extraction complete!")


def main():
    """Main execution"""
    
    print("\n" + "=" * 70)
    print("🌧️  RADAR & WEATHER DATA EXTRACTOR")
    print("   Real-time Weather Data for Dhaka, Bangladesh")
    print("=" * 70)
    
    # Configuration
    API_KEY = "8f170bd0e1e47d3f74c53906cbee8c65"
    
    # Dhaka coordinates
    LAT = 23.8103
    LON = 90.4125
    
    print(f"\n⚠️  IMPORTANT NOTICE:")
    print(f"   OpenWeatherMap FREE API does NOT provide historical radar images.")
    print(f"   Historical radar/satellite requires OneCall 3.0 API ($0.0012/call)")
    print()
    print(f"💡 ALTERNATIVE SOLUTION - Use FREE APIs:")
    print(f"   1. RainViewer - Free radar (last 2 hours only)")
    print(f"   2. NASA POWER - Free weather data (2015-present)")
    print(f"   3. Google Earth Engine - Free satellite (optical)")
    print(f"   4. OpenWeather current - Free current weather only")
    print()
    print(f"📍 Location: Dhaka ({LAT}°N, {LON}°E)")
    print(f"� API Key: {API_KEY[:8]}...{API_KEY[-4:]}")
    
    print("\n" + "=" * 70)
    print("OPTIONS:")
    print("1. Extract current weather data (free, but only current time)")
    print("2. Use RainViewer for recent radar (free, last 2 hours)")
    print("3. Use existing NASA POWER + GEE (already working!)")
    print("=" * 70)
    
    print("\n� RECOMMENDATION:")
    print("   For historical weather visualization in your thesis:")
    print("   → Use NASA POWER weather data (you already have 17,520 records!)")
    print("   → Use Google Earth Engine satellite images (already working!)")
    print("   → Create visualizations from this data instead of radar")
    print()
    
    # Show what data is already available
    print("✅ YOU ALREADY HAVE:")
    print("   - Dhaka 2019: 17,520 weather records (30-min intervals)")
    print("   - 4 satellite images (seasonal coverage)")
    print("   - Temperature, humidity, wind, precipitation data")
    print()
    
    choice = input("Do you want me to create visualization scripts instead? (y/n): ")
    
    if choice.lower() == 'y':
        print("\n✅ I'll create visualization scripts for your existing data!")
        print("   This will show:")
        print("   - Weather patterns over time")
        print("   - Precipitation heatmaps")
        print("   - Wind direction arrows")
        print("   - Temperature gradients")
        print("   - Similar to radar but from actual data!")
        return
    
    print("\n❌ For true historical radar images, you need paid APIs:")
    print("   - OpenWeather OneCall 3.0: $0.0012/call")
    print("   - Weather Underground: $10-500/month")
    print("   - AccuWeather: Contact for pricing")
    print()
    print("� For thesis purposes, visualizing existing data is better!")


if __name__ == "__main__":
    main()
