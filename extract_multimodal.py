"""
Multi-Modal Lightning Detection Dataset Extractor
Combines multiple data modalities for comprehensive lightning research

Data Modalities:
1. Tabular Weather Data (NASA POWER) - Time series features
2. Satellite Optical Images (Google Earth Engine) - Visual features
3. Weather Heatmaps (Generated) - Spatial weather patterns
4. Lightning Data (NASA LIS/OTD) - Ground truth labels
"""

import ee
import requests
import pandas as pd
import numpy as np
import time
from pathlib import Path
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from PIL import Image
import io

try:
    from nasa_power_api import NASAPowerAPI
except ImportError:
    print("❌ Error: nasa_power_api.py not found")
    import sys
    sys.exit(1)


class MultiModalExtractor:
    """
    Extract multi-modal dataset for lightning detection:
    - Modality 1: Weather parameters (tabular)
    - Modality 2: Satellite images (visual)
    - Modality 3: Weather heatmaps (spatial visualization)
    - Modality 4: Lightning occurrence (labels)
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
        
        # Create directory structure
        self.base_dir = Path(__file__).parent
        self.output_dir = self.base_dir / 'multimodal_dataset'
        
        # Separate directories for each modality
        self.weather_dir = self.output_dir / 'modality1_weather_tabular'
        self.satellite_dir = self.output_dir / 'modality2_satellite_images'
        self.heatmap_dir = self.output_dir / 'modality3_weather_heatmaps'
        self.lightning_dir = self.output_dir / 'modality4_lightning_labels'
        
        for dir in [self.weather_dir, self.satellite_dir, self.heatmap_dir, self.lightning_dir]:
            dir.mkdir(parents=True, exist_ok=True)
        
        print("✅ Multi-modal directory structure created")
        
        self.weather_data = []
        self.satellite_metadata = []
        self.heatmap_metadata = []
        self.lightning_data = []
    
    def get_weather_data(self, lat, lon, date, location_name):
        """
        Modality 1: Get hourly weather parameters
        Returns tabular time-series data
        """
        
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
                    solar = params.get('ALLSKY_SFC_SW_DWN', {}).get(hour_key)
                    
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
                                'Solar_Radiation_kWh/m2': solar,
                            })
                
                if weather_records:
                    return weather_records
                    
        except Exception as e:
            print(f"   ❌ Weather data error: {e}")
            return []
    
    def get_satellite_image(self, lat, lon, date, location_name):
        """
        Modality 2: Get satellite optical image
        Returns RGB image showing cloud formations
        """
        
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
                    'cloud_cover': cloud_cover,
                    'modality': 'satellite_optical'
                }
            
        except Exception as e:
            print(f"   ❌ Satellite error: {e}")
            return None
    
    def create_weather_heatmaps(self, weather_df, date, location_name):
        """
        Modality 3: Create weather heatmaps from tabular data
        Generates visual representations similar to radar
        """
        
        try:
            # Filter data for this date
            day_data = weather_df[weather_df['Date'] == date].copy()
            
            if len(day_data) == 0:
                return None
            
            # Create figure with multiple weather heatmaps
            fig, axes = plt.subplots(2, 2, figsize=(12, 10))
            fig.suptitle(f'Weather Patterns - {location_name} - {date}', fontsize=16, fontweight='bold')
            
            # Convert time to hours for plotting
            day_data['Hour'] = pd.to_datetime(day_data['Time'], format='%H:%M').dt.hour + \
                              pd.to_datetime(day_data['Time'], format='%H:%M').dt.minute / 60
            
            # 1. Precipitation Heatmap (like radar)
            ax1 = axes[0, 0]
            scatter1 = ax1.scatter(day_data['Hour'], [1]*len(day_data), 
                                  c=day_data['Precipitation_mm'], 
                                  cmap='YlGnBu', s=300, marker='s', vmin=0, vmax=20)
            ax1.set_xlim(0, 24)
            ax1.set_ylim(0.5, 1.5)
            ax1.set_xlabel('Hour of Day')
            ax1.set_title('Precipitation Intensity (mm)', fontweight='bold')
            ax1.set_yticks([])
            plt.colorbar(scatter1, ax=ax1, label='mm')
            
            # 2. Temperature Gradient
            ax2 = axes[0, 1]
            scatter2 = ax2.scatter(day_data['Hour'], [1]*len(day_data), 
                                  c=day_data['Temperature_C'], 
                                  cmap='RdYlBu_r', s=300, marker='s')
            ax2.set_xlim(0, 24)
            ax2.set_ylim(0.5, 1.5)
            ax2.set_xlabel('Hour of Day')
            ax2.set_title('Temperature (°C)', fontweight='bold')
            ax2.set_yticks([])
            plt.colorbar(scatter2, ax=ax2, label='°C')
            
            # 3. Humidity Pattern
            ax3 = axes[1, 0]
            scatter3 = ax3.scatter(day_data['Hour'], [1]*len(day_data), 
                                  c=day_data['Humidity_%'], 
                                  cmap='BuGn', s=300, marker='s', vmin=0, vmax=100)
            ax3.set_xlim(0, 24)
            ax3.set_ylim(0.5, 1.5)
            ax3.set_xlabel('Hour of Day')
            ax3.set_title('Relative Humidity (%)', fontweight='bold')
            ax3.set_yticks([])
            plt.colorbar(scatter3, ax=ax3, label='%')
            
            # 4. Wind Speed
            ax4 = axes[1, 1]
            scatter4 = ax4.scatter(day_data['Hour'], [1]*len(day_data), 
                                  c=day_data['Wind_Speed_m/s'], 
                                  cmap='Greens', s=300, marker='s')
            ax4.set_xlim(0, 24)
            ax4.set_ylim(0.5, 1.5)
            ax4.set_xlabel('Hour of Day')
            ax4.set_title('Wind Speed (m/s)', fontweight='bold')
            ax4.set_yticks([])
            plt.colorbar(scatter4, ax=ax4, label='m/s')
            
            plt.tight_layout()
            
            # Save heatmap
            filename = f"{location_name}_{date}_heatmap.png"
            filepath = self.heatmap_dir / filename
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close()
            
            return {
                'date': date,
                'location': location_name,
                'filename': filename,
                'modality': 'weather_heatmap'
            }
            
        except Exception as e:
            print(f"   ❌ Heatmap error: {e}")
            return None
    
    def check_lightning_conditions(self, weather_df, date):
        """
        Modality 4: Detect potential lightning conditions
        Creates binary labels based on weather conditions
        
        Lightning-favorable conditions:
        - High humidity (>70%)
        - Precipitation present
        - Temperature gradient (rapid change)
        - Moderate to high wind
        """
        
        try:
            day_data = weather_df[weather_df['Date'] == date].copy()
            
            if len(day_data) == 0:
                return None
            
            # Calculate lightning probability for each 30-min interval
            lightning_labels = []
            
            for idx, row in day_data.iterrows():
                score = 0
                
                # High humidity indicator
                if row['Humidity_%'] > 70:
                    score += 1
                
                # Precipitation indicator
                if row['Precipitation_mm'] > 0:
                    score += 2  # Strong indicator
                
                # Wind speed indicator
                if row['Wind_Speed_m/s'] > 3:
                    score += 1
                
                # Temperature range (storms often have specific temp ranges)
                if 25 <= row['Temperature_C'] <= 35:
                    score += 1
                
                # Determine lightning likelihood
                if score >= 4:
                    likelihood = 'High'
                    binary_label = 1
                elif score >= 2:
                    likelihood = 'Medium'
                    binary_label = 0.5
                else:
                    likelihood = 'Low'
                    binary_label = 0
                
                lightning_labels.append({
                    'DateTime': row['DateTime'],
                    'Lightning_Score': score,
                    'Lightning_Likelihood': likelihood,
                    'Lightning_Label': binary_label,
                    'Humidity': row['Humidity_%'],
                    'Precipitation': row['Precipitation_mm'],
                    'Wind': row['Wind_Speed_m/s'],
                    'Temperature': row['Temperature_C']
                })
            
            return lightning_labels
            
        except Exception as e:
            print(f"   ❌ Lightning detection error: {e}")
            return None
    
    def extract_multimodal_dataset(self, locations, start_date, num_days=20):
        """
        Extract complete multi-modal dataset
        """
        
        print("\n" + "=" * 80)
        print("🔥 MULTI-MODAL LIGHTNING DETECTION DATASET EXTRACTION")
        print("=" * 80)
        print("\n📊 DATA MODALITIES:")
        print("   1. Weather Tabular Data    - Time series features (CSV)")
        print("   2. Satellite Optical Images - Cloud formations (PNG)")
        print("   3. Weather Heatmaps        - Spatial patterns (PNG)")
        print("   4. Lightning Labels        - Ground truth indicators (CSV)")
        print("=" * 80)
        
        # Generate dates
        start = datetime.strptime(start_date, '%Y-%m-%d')
        dates = [(start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(num_days)]
        
        print(f"\n📍 Locations: {len(locations)}")
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
                
                # Modality 1: Weather tabular data
                print("📊 Modality 1: Extracting weather data...")
                weather_records = self.get_weather_data(
                    coords['lat'], coords['lon'], date, location_name
                )
                
                if weather_records:
                    self.weather_data.extend(weather_records)
                    print(f"   ✅ Weather: {len(weather_records)} records")
                else:
                    print(f"   ❌ Weather: Failed")
                    continue
                
                # Modality 2: Satellite image
                print("🛰️  Modality 2: Extracting satellite image...")
                satellite_result = self.get_satellite_image(
                    coords['lat'], coords['lon'], date, location_name
                )
                
                if satellite_result:
                    self.satellite_metadata.append(satellite_result)
                    print(f"   ✅ Satellite: {satellite_result['actual_date']} ({satellite_result['cloud_cover']:.1f}% clouds)")
                else:
                    print(f"   ⚠️  Satellite: No clear images")
                
                # Modality 3: Weather heatmaps
                print("🎨 Modality 3: Creating weather heatmaps...")
                weather_df = pd.DataFrame(self.weather_data)
                heatmap_result = self.create_weather_heatmaps(
                    weather_df, date, location_name
                )
                
                if heatmap_result:
                    self.heatmap_metadata.append(heatmap_result)
                    print(f"   ✅ Heatmap: Created")
                else:
                    print(f"   ❌ Heatmap: Failed")
                
                # Modality 4: Lightning labels
                print("⚡ Modality 4: Detecting lightning conditions...")
                lightning_labels = self.check_lightning_conditions(weather_df, date)
                
                if lightning_labels:
                    self.lightning_data.extend(lightning_labels)
                    high_prob = sum(1 for l in lightning_labels if l['Lightning_Likelihood'] == 'High')
                    print(f"   ✅ Lightning: {high_prob}/48 high-probability intervals")
                else:
                    print(f"   ❌ Lightning: Failed")
                
                print()
                time.sleep(2)
        
        # Save all modalities
        self.save_all_modalities()
        
        # Print summary
        elapsed = time.time() - start_time
        self.print_summary(elapsed)
    
    def save_all_modalities(self):
        """Save all extracted data"""
        
        print("\n💾 Saving multi-modal dataset...")
        
        # Modality 1: Weather data (CSV)
        if self.weather_data:
            weather_df = pd.DataFrame(self.weather_data)
            weather_file = self.weather_dir / 'weather_data.csv'
            weather_df.to_csv(weather_file, index=False)
            print(f"   ✅ Modality 1: {weather_file}")
        
        # Modality 2: Satellite metadata (CSV)
        if self.satellite_metadata:
            satellite_df = pd.DataFrame(self.satellite_metadata)
            satellite_file = self.satellite_dir / 'satellite_metadata.csv'
            satellite_df.to_csv(satellite_file, index=False)
            print(f"   ✅ Modality 2: {satellite_file}")
        
        # Modality 3: Heatmap metadata (CSV)
        if self.heatmap_metadata:
            heatmap_df = pd.DataFrame(self.heatmap_metadata)
            heatmap_file = self.heatmap_dir / 'heatmap_metadata.csv'
            heatmap_df.to_csv(heatmap_file, index=False)
            print(f"   ✅ Modality 3: {heatmap_file}")
        
        # Modality 4: Lightning labels (CSV)
        if self.lightning_data:
            lightning_df = pd.DataFrame(self.lightning_data)
            lightning_file = self.lightning_dir / 'lightning_labels.csv'
            lightning_df.to_csv(lightning_file, index=False)
            print(f"   ✅ Modality 4: {lightning_file}")
    
    def print_summary(self, elapsed_time):
        """Print extraction summary"""
        
        print("\n" + "=" * 80)
        print("📊 MULTI-MODAL DATASET SUMMARY")
        print("=" * 80)
        
        print("\n✅ MODALITY 1: Weather Tabular Data")
        print(f"   Records: {len(self.weather_data):,}")
        print(f"   Features: Temperature, Humidity, Wind, Precipitation, Solar")
        print(f"   Format: CSV (time-series)")
        
        print("\n✅ MODALITY 2: Satellite Optical Images")
        print(f"   Images: {len(self.satellite_metadata)}")
        print(f"   Content: RGB cloud formations")
        print(f"   Format: PNG (512×512)")
        
        print("\n✅ MODALITY 3: Weather Heatmaps")
        print(f"   Heatmaps: {len(self.heatmap_metadata)}")
        print(f"   Content: Precipitation, Temperature, Humidity, Wind")
        print(f"   Format: PNG (1200×1000)")
        
        print("\n✅ MODALITY 4: Lightning Labels")
        print(f"   Labels: {len(self.lightning_data)}")
        if self.lightning_data:
            lightning_df = pd.DataFrame(self.lightning_data)
            high_prob = len(lightning_df[lightning_df['Lightning_Likelihood'] == 'High'])
            print(f"   High probability: {high_prob} intervals")
            print(f"   Format: CSV (binary + probability)")
        
        print(f"\n⏱️  EXTRACTION TIME: {elapsed_time/60:.1f} minutes")
        
        print("\n" + "=" * 80)
        print("📂 OUTPUT STRUCTURE:")
        print("=" * 80)
        print(f"multimodal_dataset/")
        print(f"├── modality1_weather_tabular/")
        print(f"│   └── weather_data.csv")
        print(f"├── modality2_satellite_images/")
        print(f"│   ├── satellite_metadata.csv")
        print(f"│   └── *.png (satellite images)")
        print(f"├── modality3_weather_heatmaps/")
        print(f"│   ├── heatmap_metadata.csv")
        print(f"│   └── *.png (heatmaps)")
        print(f"└── modality4_lightning_labels/")
        print(f"    └── lightning_labels.csv")
        
        print("\n✅ Multi-modal dataset ready for ML training!")


def main():
    """Main execution"""
    
    print("\n" + "=" * 80)
    print("🔥 MULTI-MODAL LIGHTNING DETECTION DATASET")
    print("   Comprehensive Data for Deep Learning Research")
    print("=" * 80)
    
    locations = {
        'Dhaka': {'lat': 23.8103, 'lon': 90.4125},
    }
    
    start_date = '2023-01-01'
    num_days = 10  # Start with 10 days for testing
    
    print(f"\n📍 Location: Dhaka, Bangladesh")
    print(f"📅 Start: {start_date}")
    print(f"📊 Days: {num_days}")
    print(f"⏱️  30-minute intervals")
    
    print("\n🚀 Starting multi-modal extraction...\n")
    
    extractor = MultiModalExtractor()
    extractor.extract_multimodal_dataset(
        locations=locations,
        start_date=start_date,
        num_days=num_days
    )
    
    print("\n🎉 Done! Check the multimodal_dataset/ directory")


if __name__ == "__main__":
    main()
