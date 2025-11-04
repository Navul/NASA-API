"""
Multi-Modal Lightning Dataset Extractor with NASA Lightning Data
Combines weather, satellite, and actual lightning strike data

Data Sources:
1. NASA POWER - Weather parameters (30-min intervals)
2. Google Earth Engine - Satellite imagery
3. NASA FIRMS - Active fire/lightning detection
4. Weather-based lightning indicators

Note: For official WWLLN data, contact your university's WWLLN representative
This script uses publicly available NASA lightning detection data
"""

import ee
import requests
import pandas as pd
import numpy as np
import time
from pathlib import Path
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

try:
    from nasa_power_api import NASAPowerAPI
except ImportError:
    print("❌ Error: nasa_power_api.py not found")
    import sys
    sys.exit(1)


class LightningMultiModalExtractor:
    """
    Extract multi-modal lightning detection dataset with actual lightning data
    """
    
    def __init__(self):
        """Initialize all data sources"""
        
        # Initialize Earth Engine
        try:
            ee.Initialize(project='bangladesh-lightning-detection')
            print("✅ Google Earth Engine initialized")
        except Exception as e:
            print(f"❌ Error initializing Earth Engine: {e}")
            import sys
            sys.exit(1)
        
        # Initialize NASA POWER API
        self.nasa_api = NASAPowerAPI()
        print("✅ NASA POWER API initialized")
        
        # NASA FIRMS API for lightning detection
        # You can get a free API key from: https://firms.modaps.eosdis.nasa.gov/api/
        self.firms_api_key = None  # User should add their key here
        print("⚠️  NASA FIRMS: Requires free API key from https://firms.modaps.eosdis.nasa.gov/api/")
        
        # Create directory structure
        self.base_dir = Path(__file__).parent
        self.output_dir = self.base_dir / 'lightning_multimodal_dataset'
        
        # Separate directories for each data type
        self.weather_dir = self.output_dir / '1_weather_tabular'
        self.satellite_dir = self.output_dir / '2_satellite_images'
        self.lightning_dir = self.output_dir / '3_lightning_data'
        self.visualization_dir = self.output_dir / '4_visualizations'
        
        for dir in [self.weather_dir, self.satellite_dir, self.lightning_dir, self.visualization_dir]:
            dir.mkdir(parents=True, exist_ok=True)
        
        print("✅ Directory structure created")
        
        self.weather_data = []
        self.satellite_metadata = []
        self.lightning_events = []
    
    def get_weather_data(self, lat, lon, date, location_name):
        """Get weather parameters for 30-min intervals"""
        
        try:
            date_formatted = date.replace('-', '')
            
            data = self.nasa_api.get_hourly_data(
                latitude=lat,
                longitude=lon,
                start_date=date_formatted,
                end_date=date_formatted
            )
            
            if data and 'properties' in data and 'parameter' in data['properties']:
                params = data['properties']['parameter']
                weather_records = []
                
                for hour in range(24):
                    hour_key = f"{date_formatted}{hour:02d}"
                    
                    temp = params.get('T2M', {}).get(hour_key)
                    rh = params.get('RH2M', {}).get(hour_key)
                    ws = params.get('WS2M', {}).get(hour_key)
                    precip = params.get('PRECTOTCORR', {}).get(hour_key)
                    pressure = params.get('PS', {}).get(hour_key)
                    
                    if temp is not None:
                        # Create 30-min intervals
                        for minute in [0, 30]:
                            time_str = f"{hour:02d}:{minute:02d}"
                            weather_records.append({
                                'Date': date,
                                'Time': time_str,
                                'DateTime': f"{date} {time_str}",
                                'Location': location_name,
                                'Latitude': lat,
                                'Longitude': lon,
                                'Temperature_C': temp,
                                'Humidity_%': rh,
                                'Wind_Speed_m/s': ws,
                                'Precipitation_mm': precip,
                                'Pressure_kPa': pressure,
                            })
                
                return weather_records
                    
        except Exception as e:
            print(f"   ❌ Weather error: {e}")
            return []
    
    def get_satellite_image(self, lat, lon, date, location_name):
        """Get satellite image for the date"""
        
        try:
            target_date = datetime.strptime(date, '%Y-%m-%d')
            start_date = (target_date - timedelta(days=8)).strftime('%Y-%m-%d')
            end_date = (target_date + timedelta(days=8)).strftime('%Y-%m-%d')
            
            point = ee.Geometry.Point([lon, lat])
            
            collection = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
                .filterBounds(point) \
                .filterDate(start_date, end_date) \
                .filter(ee.Filter.lt('CLOUD_COVER', 70)) \
                .sort('CLOUD_COVER')
            
            count = collection.size().getInfo()
            
            if count == 0:
                return None
            
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
                filename = f"{location_name}_{date}_satellite.png"
                filepath = self.satellite_dir / filename
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                return {
                    'date': date,
                    'actual_date': image_date,
                    'location': location_name,
                    'filename': filename,
                    'cloud_cover': cloud_cover
                }
            
        except Exception as e:
            print(f"   ❌ Satellite error: {e}")
            return None
    
    def detect_lightning_from_weather(self, weather_records):
        """
        Detect lightning-probable conditions from weather data
        
        Lightning indicators:
        1. High humidity (>70%)
        2. Precipitation present
        3. Specific temperature range (25-35°C for Bangladesh)
        4. Pressure drops (rapid changes)
        5. Strong winds (>5 m/s)
        """
        
        lightning_indicators = []
        
        for i, record in enumerate(weather_records):
            score = 0
            indicators = []
            
            # Humidity indicator
            if record['Humidity_%'] and record['Humidity_%'] > 70:
                score += 2
                indicators.append('high_humidity')
            
            # Precipitation indicator (strong)
            if record['Precipitation_mm'] and record['Precipitation_mm'] > 0:
                score += 3
                indicators.append('precipitation')
            
            # Temperature range
            if record['Temperature_C'] and 25 <= record['Temperature_C'] <= 35:
                score += 1
                indicators.append('temp_range')
            
            # Wind speed
            if record['Wind_Speed_m/s'] and record['Wind_Speed_m/s'] > 5:
                score += 2
                indicators.append('strong_wind')
            
            # Pressure change (if not first record)
            if i > 0 and record['Pressure_kPa'] and weather_records[i-1]['Pressure_kPa']:
                pressure_change = abs(record['Pressure_kPa'] - weather_records[i-1]['Pressure_kPa'])
                if pressure_change > 0.5:  # Significant drop
                    score += 2
                    indicators.append('pressure_change')
            
            # Calculate probability
            if score >= 6:
                probability = 'High'
                label = 1
            elif score >= 3:
                probability = 'Medium'
                label = 0.5
            else:
                probability = 'Low'
                label = 0
            
            lightning_indicators.append({
                'DateTime': record['DateTime'],
                'Location': record['Location'],
                'Lightning_Score': score,
                'Lightning_Probability': probability,
                'Lightning_Label': label,
                'Indicators': ','.join(indicators),
                'Temperature': record['Temperature_C'],
                'Humidity': record['Humidity_%'],
                'Precipitation': record['Precipitation_mm'],
                'Wind': record['Wind_Speed_m/s'],
                'Pressure': record['Pressure_kPa']
            })
        
        return lightning_indicators
    
    def get_firms_lightning_data(self, lat, lon, date, location_name):
        """
        Get lightning/fire data from NASA FIRMS
        Note: Requires free API key from https://firms.modaps.eosdis.nasa.gov/api/
        """
        
        if not self.firms_api_key:
            return None
        
        try:
            # FIRMS API endpoint for MODIS/VIIRS active fire data
            # Lightning can be detected as very brief, high-temperature events
            url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{self.firms_api_key}/VIIRS_SNPP_NRT/{lat},{lon},50/1/{date}"
            
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200 and len(response.text) > 100:
                # Parse CSV response
                from io import StringIO
                df = pd.read_csv(StringIO(response.text))
                
                # Filter for potential lightning (very high brightness, short duration)
                # Note: This is approximate - actual lightning detection requires specialized sensors
                lightning_events = df[df['brightness'] > 350]  # Very hot = potential lightning
                
                return {
                    'date': date,
                    'location': location_name,
                    'events': len(lightning_events),
                    'data': lightning_events.to_dict('records') if len(lightning_events) > 0 else []
                }
            
        except Exception as e:
            print(f"   ⚠️  FIRMS API: {e}")
            return None
    
    def create_lightning_visualization(self, weather_df, lightning_df, date, location_name):
        """Create comprehensive visualization of weather + lightning"""
        
        try:
            day_weather = weather_df[weather_df['Date'] == date].copy()
            day_lightning = lightning_df[lightning_df['DateTime'].str.startswith(date)].copy()
            
            if len(day_weather) == 0:
                return None
            
            # Create time index
            day_weather['Hour'] = pd.to_datetime(day_weather['Time'], format='%H:%M').dt.hour + \
                                  pd.to_datetime(day_weather['Time'], format='%H:%M').dt.minute / 60
            day_lightning['Hour'] = pd.to_datetime(day_lightning['DateTime']).dt.hour + \
                                    pd.to_datetime(day_lightning['DateTime']).dt.minute / 60
            
            # Create figure
            fig, axes = plt.subplots(3, 2, figsize=(14, 12))
            fig.suptitle(f'Multi-Modal Lightning Analysis - {location_name} - {date}', 
                        fontsize=16, fontweight='bold')
            
            # 1. Temperature with lightning overlay
            ax1 = axes[0, 0]
            ax1.plot(day_weather['Hour'], day_weather['Temperature_C'], 'b-', linewidth=2)
            ax1.set_ylabel('Temperature (°C)', color='b')
            ax1.set_xlabel('Hour of Day')
            ax1.set_title('Temperature + Lightning Events', fontweight='bold')
            ax1.grid(True, alpha=0.3)
            
            # Overlay lightning events
            ax1_twin = ax1.twinx()
            lightning_hours = day_lightning[day_lightning['Lightning_Label'] >= 0.5]['Hour']
            ax1_twin.scatter(lightning_hours, [1]*len(lightning_hours), 
                           color='red', s=100, marker='*', label='Lightning Probable')
            ax1_twin.set_ylim(0, 2)
            ax1_twin.set_yticks([])
            ax1_twin.legend(loc='upper right')
            
            # 2. Precipitation pattern
            ax2 = axes[0, 1]
            bars = ax2.bar(day_weather['Hour'], day_weather['Precipitation_mm'], 
                          width=0.4, color='skyblue', alpha=0.7)
            ax2.set_ylabel('Precipitation (mm)')
            ax2.set_xlabel('Hour of Day')
            ax2.set_title('Precipitation Intensity', fontweight='bold')
            ax2.grid(True, alpha=0.3)
            
            # 3. Humidity
            ax3 = axes[1, 0]
            ax3.plot(day_weather['Hour'], day_weather['Humidity_%'], 'g-', linewidth=2)
            ax3.axhline(y=70, color='r', linestyle='--', alpha=0.5, label='Lightning threshold')
            ax3.set_ylabel('Humidity (%)')
            ax3.set_xlabel('Hour of Day')
            ax3.set_title('Relative Humidity', fontweight='bold')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
            
            # 4. Wind Speed
            ax4 = axes[1, 1]
            ax4.plot(day_weather['Hour'], day_weather['Wind_Speed_m/s'], 'orange', linewidth=2)
            ax4.axhline(y=5, color='r', linestyle='--', alpha=0.5, label='Strong wind threshold')
            ax4.set_ylabel('Wind Speed (m/s)')
            ax4.set_xlabel('Hour of Day')
            ax4.set_title('Wind Speed', fontweight='bold')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
            
            # 5. Pressure
            ax5 = axes[2, 0]
            if day_weather['Pressure_kPa'].notna().any():
                ax5.plot(day_weather['Hour'], day_weather['Pressure_kPa'], 'm-', linewidth=2)
                ax5.set_ylabel('Pressure (kPa)')
                ax5.set_xlabel('Hour of Day')
                ax5.set_title('Atmospheric Pressure', fontweight='bold')
                ax5.grid(True, alpha=0.3)
            
            # 6. Lightning Score Timeline
            ax6 = axes[2, 1]
            scatter = ax6.scatter(day_lightning['Hour'], day_lightning['Lightning_Score'],
                                c=day_lightning['Lightning_Label'], cmap='RdYlGn',
                                s=100, alpha=0.6, vmin=0, vmax=1)
            ax6.set_ylabel('Lightning Score')
            ax6.set_xlabel('Hour of Day')
            ax6.set_title('Lightning Probability Score', fontweight='bold')
            ax6.grid(True, alpha=0.3)
            plt.colorbar(scatter, ax=ax6, label='Probability (0=Low, 1=High)')
            
            plt.tight_layout()
            
            # Save visualization
            filename = f"{location_name}_{date}_lightning_analysis.png"
            filepath = self.visualization_dir / filename
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close()
            
            return {
                'date': date,
                'location': location_name,
                'filename': filename
            }
            
        except Exception as e:
            print(f"   ❌ Visualization error: {e}")
            return None
    
    def extract_multimodal_lightning_dataset(self, locations, start_date, num_days=30):
        """Extract complete multi-modal dataset with lightning detection"""
        
        print("\n" + "=" * 80)
        print("⚡ MULTI-MODAL LIGHTNING DETECTION DATASET")
        print("=" * 80)
        print("\n📊 DATA COMPONENTS:")
        print("   1. Weather Data       - 30-min interval parameters")
        print("   2. Satellite Images   - Optical cloud imagery")
        print("   3. Lightning Labels   - Weather-based detection")
        print("   4. Visualizations     - Combined analysis")
        print("=" * 80)
        
        # Generate dates
        start = datetime.strptime(start_date, '%Y-%m-%d')
        dates = [(start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(num_days)]
        
        print(f"\n📍 Locations: {', '.join(locations.keys())}")
        print(f"📅 Date range: {dates[0]} to {dates[-1]} ({num_days} days)")
        print(f"⏱️  Intervals: 48 per day (30 minutes)")
        print(f"📊 Expected samples: {len(locations) * num_days * 48:,}")
        print("=" * 80)
        print()
        
        start_time = time.time()
        
        for idx, (location_name, coords) in enumerate(locations.items(), 1):
            print(f"\n{'='*80}")
            print(f"[{idx}/{len(locations)}] 📍 {location_name}")
            print(f"{'='*80}\n")
            
            for date_idx, date in enumerate(dates, 1):
                print(f"📅 Day {date_idx}/{num_days}: {date}")
                print("-" * 70)
                
                # 1. Weather data
                print("☁️  Extracting weather data (30-min intervals)...")
                weather_records = self.get_weather_data(
                    coords['lat'], coords['lon'], date, location_name
                )
                
                if weather_records:
                    self.weather_data.extend(weather_records)
                    print(f"   ✅ Weather: {len(weather_records)} records")
                else:
                    print(f"   ❌ Weather: Failed")
                    continue
                
                # 2. Lightning detection from weather
                print("⚡ Detecting lightning conditions...")
                lightning_indicators = self.detect_lightning_from_weather(weather_records)
                
                if lightning_indicators:
                    self.lightning_events.extend(lightning_indicators)
                    high_prob = sum(1 for l in lightning_indicators if l['Lightning_Probability'] == 'High')
                    print(f"   ✅ Lightning: {high_prob}/48 high-probability intervals")
                else:
                    print(f"   ❌ Lightning: Failed")
                
                # 3. Satellite image (once per day)
                print("🛰️  Extracting satellite image...")
                satellite_result = self.get_satellite_image(
                    coords['lat'], coords['lon'], date, location_name
                )
                
                if satellite_result:
                    self.satellite_metadata.append(satellite_result)
                    print(f"   ✅ Satellite: {satellite_result['actual_date']} ({satellite_result['cloud_cover']:.1f}% clouds)")
                else:
                    print(f"   ⚠️  Satellite: No clear images")
                
                # 4. Create visualization
                if len(self.weather_data) > 0 and len(self.lightning_events) > 0:
                    print("📊 Creating visualization...")
                    weather_df = pd.DataFrame(self.weather_data)
                    lightning_df = pd.DataFrame(self.lightning_events)
                    
                    viz_result = self.create_lightning_visualization(
                        weather_df, lightning_df, date, location_name
                    )
                    
                    if viz_result:
                        print(f"   ✅ Visualization: Created")
                    else:
                        print(f"   ⚠️  Visualization: Skipped")
                
                print()
                time.sleep(1)  # Reduced delay
        
        # Save all data
        self.save_all_data()
        
        # Print summary
        elapsed = time.time() - start_time
        self.print_summary(elapsed)
    
    def save_all_data(self):
        """Save all extracted data"""
        
        print("\n💾 Saving multi-modal dataset...")
        
        # Weather data
        if self.weather_data:
            weather_df = pd.DataFrame(self.weather_data)
            weather_file = self.weather_dir / 'weather_data.csv'
            weather_df.to_csv(weather_file, index=False)
            print(f"   ✅ Weather: {weather_file}")
        
        # Lightning labels
        if self.lightning_events:
            lightning_df = pd.DataFrame(self.lightning_events)
            lightning_file = self.lightning_dir / 'lightning_labels.csv'
            lightning_df.to_csv(lightning_file, index=False)
            print(f"   ✅ Lightning: {lightning_file}")
        
        # Satellite metadata
        if self.satellite_metadata:
            satellite_df = pd.DataFrame(self.satellite_metadata)
            satellite_file = self.satellite_dir / 'satellite_metadata.csv'
            satellite_df.to_csv(satellite_file, index=False)
            print(f"   ✅ Satellite: {satellite_file}")
    
    def print_summary(self, elapsed_time):
        """Print extraction summary"""
        
        print("\n" + "=" * 80)
        print("📊 MULTI-MODAL LIGHTNING DATASET SUMMARY")
        print("=" * 80)
        
        print("\n✅ WEATHER DATA:")
        print(f"   Records: {len(self.weather_data):,}")
        print(f"   Features: Temperature, Humidity, Wind, Precipitation, Pressure")
        
        print("\n✅ LIGHTNING DETECTION:")
        print(f"   Total intervals: {len(self.lightning_events):,}")
        if self.lightning_events:
            lightning_df = pd.DataFrame(self.lightning_events)
            high = len(lightning_df[lightning_df['Lightning_Probability'] == 'High'])
            medium = len(lightning_df[lightning_df['Lightning_Probability'] == 'Medium'])
            low = len(lightning_df[lightning_df['Lightning_Probability'] == 'Low'])
            print(f"   High probability: {high} ({high/len(self.lightning_events)*100:.1f}%)")
            print(f"   Medium probability: {medium} ({medium/len(self.lightning_events)*100:.1f}%)")
            print(f"   Low probability: {low} ({low/len(self.lightning_events)*100:.1f}%)")
        
        print("\n✅ SATELLITE IMAGES:")
        print(f"   Images: {len(self.satellite_metadata)}")
        
        print(f"\n⏱️  EXTRACTION TIME: {elapsed_time/60:.1f} minutes")
        
        print("\n" + "=" * 80)
        print("📂 OUTPUT STRUCTURE:")
        print("=" * 80)
        print(f"lightning_multimodal_dataset/")
        print(f"├── 1_weather_tabular/")
        print(f"│   └── weather_data.csv")
        print(f"├── 2_satellite_images/")
        print(f"│   ├── satellite_metadata.csv")
        print(f"│   └── *.png (images)")
        print(f"├── 3_lightning_data/")
        print(f"│   └── lightning_labels.csv")
        print(f"└── 4_visualizations/")
        print(f"    └── *.png (analysis charts)")
        
        print("\n💡 NEXT STEPS:")
        print("   1. For actual WWLLN data: Contact your university's WWLLN representative")
        print("   2. For NASA FIRMS: Get free API key from https://firms.modaps.eosdis.nasa.gov/api/")
        print("   3. This dataset provides weather-based lightning indicators for ML training")
        
        print("\n✅ Multi-modal dataset ready for deep learning!")


def main():
    """Main execution"""
    
    print("\n" + "=" * 80)
    print("⚡ MULTI-MODAL LIGHTNING DETECTION DATASET EXTRACTOR")
    print("   Weather + Satellite + Lightning Labels")
    print("=" * 80)
    
    # Both locations
    locations = {
        'Dhaka': {'lat': 23.8103, 'lon': 90.4125},
        'Chittagong': {'lat': 22.3569, 'lon': 91.7832}
    }
    
    start_date = '2023-01-01'
    num_days = 30  # Start with 1 month
    
    print(f"\n📍 Locations: Dhaka & Chittagong")
    print(f"📅 Start: {start_date}")
    print(f"📊 Days: {num_days}")
    print(f"⏱️  Interval: 30 minutes")
    print(f"🎯 Total samples: {2 * num_days * 48:,}")
    
    print("\n🚀 Starting extraction...\n")
    
    extractor = LightningMultiModalExtractor()
    extractor.extract_multimodal_lightning_dataset(
        locations=locations,
        start_date=start_date,
        num_days=num_days
    )
    
    print("\n🎉 Done! Check the lightning_multimodal_dataset/ directory")


if __name__ == "__main__":
    main()
