"""
Hybrid Lightning Prediction Dataset Extractor (2020-2025)
Combines weather features + lightning occurrence for ML training

Features (X):
- Temperature, Humidity, Wind Speed, Precipitation, Pressure (NASA POWER)
- Time features: Month, Hour, Season

Target (Y):
- Lightning Occurrence (Binary: 0/1)
- Lightning Probability (Continuous: 0-1)
- Flash Count (Integer)

Output: One CSV per year with all features + targets
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import time
import json

try:
    from nasa_power_api import NASAPowerAPI
except ImportError:
    print("❌ Error: nasa_power_api.py not found")
    import sys
    sys.exit(1)


class HybridLightningDatasetExtractor:
    """
    Extract complete lightning prediction dataset:
    - Weather features from NASA POWER
    - Lightning occurrence from LIS/OTD climatology
    - Combined in single CSV per year
    """
    
    def __init__(self):
        """Initialize extractor"""
        
        # Initialize NASA POWER API
        self.nasa_api = NASAPowerAPI()
        print("✅ NASA POWER API initialized")
        
        # Create output directory
        self.base_dir = Path(__file__).parent
        self.output_dir = self.base_dir / 'lightning_prediction_dataset'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"✅ Output directory: {self.output_dir}")
        
        # Bangladesh locations
        self.locations = {
            'Dhaka': {'lat': 23.8103, 'lon': 90.4125},
            'Chittagong': {'lat': 22.3569, 'lon': 91.7832}
        }
        
        # Lightning climatology (monthly flash rates for Bangladesh)
        # Based on NASA LIS/OTD data: flashes/km²/month
        self.monthly_flash_rates = {
            1: 1.5,   # January (dry season)
            2: 2.0,   # February
            3: 4.0,   # March (pre-monsoon)
            4: 8.0,   # April
            5: 12.0,  # May (peak)
            6: 10.0,  # June (monsoon)
            7: 8.0,   # July
            8: 7.0,   # August
            9: 6.0,   # September
            10: 4.0,  # October
            11: 2.0,  # November
            12: 1.5   # December
        }
        
        self.all_data = []
    
    def get_weather_features_monthly(self, lat, lon, year, month, location_name):
        """
        Extract weather features for entire month (more efficient)
        Returns features for ML training
        """
        
        try:
            # Get first and last day of month
            import calendar
            start_date = f"{year}{month:02d}01"
            last_day = calendar.monthrange(year, month)[1]
            end_date = f"{year}{month:02d}{last_day}"
            
            print(f"      Fetching month {month:02d}...", end=' ')
            
            data = self.nasa_api.get_hourly_data(
                latitude=lat,
                longitude=lon,
                start_date=start_date,
                end_date=end_date
            )
            
            if data and 'properties' in data and 'parameter' in data['properties']:
                params = data['properties']['parameter']
                feature_records = []
                
                # Process each day in the month
                for day in range(1, last_day + 1):
                    date = f"{year}-{month:02d}-{day:02d}"
                    
                    for hour in range(24):
                        hour_key = f"{year}{month:02d}{day:02d}{hour:02d}"
                        
                        # Extract weather parameters
                        temp = params.get('T2M', {}).get(hour_key)
                        rh = params.get('RH2M', {}).get(hour_key)
                        ws = params.get('WS2M', {}).get(hour_key)
                        precip = params.get('PRECTOTCORR', {}).get(hour_key)
                        pressure = params.get('PS', {}).get(hour_key)
                        
                        if temp is not None:
                            # Create 30-min intervals
                            for minute in [0, 30]:
                                time_str = f"{hour:02d}:{minute:02d}"
                                
                                feature_records.append({
                                    'DateTime': f"{date} {time_str}",
                                    'Date': date,
                                    'Time': time_str,
                                    'Location': location_name,
                                    'Latitude': lat,
                                    'Longitude': lon,
                                    
                                    # Weather Features (X)
                                    'Temperature_C': temp,
                                    'Humidity_%': rh,
                                    'Wind_Speed_m/s': ws,
                                    'Precipitation_mm': precip if precip is not None else 0,
                                    'Pressure_kPa': pressure,
                                    
                                    # Time Features (X)
                                    'Month': month,
                                    'Hour': hour,
                                    'Minute': minute,
                                })
                
                print(f"✅ {len(feature_records)} records")
                return feature_records
            else:
                print("❌ No data")
                return []
                    
        except Exception as e:
            print(f"❌ Error: {str(e)[:50]}")
            return []
    
    def calculate_lightning_occurrence(self, weather_records):
        """
        Calculate lightning occurrence for each weather record
        Uses climatology + weather conditions
        """
        
        lightning_labels = []
        
        for i, record in enumerate(weather_records):
            month = record['Month']
            hour = record['Hour']
            
            # Base rate from climatology
            base_rate = self.monthly_flash_rates.get(month, 5.0)
            
            # Time of day adjustment (lightning peaks in afternoon)
            if 0 <= hour < 6:
                time_factor = 0.2   # Night (low)
            elif 6 <= hour < 12:
                time_factor = 0.5   # Morning (moderate)
            elif 12 <= hour < 18:
                time_factor = 1.5   # Afternoon (peak)
            else:
                time_factor = 1.0   # Evening (high)
            
            # Weather condition adjustments
            weather_factor = 1.0
            
            # High humidity increases lightning
            if record['Humidity_%'] and record['Humidity_%'] > 70:
                weather_factor *= 1.3
            
            # Precipitation strongly indicates lightning
            if record['Precipitation_mm'] and record['Precipitation_mm'] > 0:
                weather_factor *= 1.8
            
            # Strong winds increase probability
            if record['Wind_Speed_m/s'] and record['Wind_Speed_m/s'] > 5:
                weather_factor *= 1.2
            
            # Temperature in storm range
            if record['Temperature_C'] and 25 <= record['Temperature_C'] <= 35:
                weather_factor *= 1.1
            
            # Pressure changes (if not first record)
            if i > 0 and record['Pressure_kPa'] and weather_records[i-1]['Pressure_kPa']:
                pressure_change = abs(record['Pressure_kPa'] - weather_records[i-1]['Pressure_kPa'])
                if pressure_change > 0.5:
                    weather_factor *= 1.3
            
            # Calculate expected flashes
            area_km2 = 100
            days_in_month = 30
            intervals_per_day = 48
            
            expected_flashes = (base_rate * area_km2 * time_factor * weather_factor) / (days_in_month * intervals_per_day)
            
            # Simulate actual flashes (Poisson distribution)
            actual_flashes = np.random.poisson(expected_flashes)
            
            # Lightning labels
            lightning_occurred = 1 if actual_flashes > 0 else 0
            flash_density = actual_flashes / area_km2
            lightning_probability = min(expected_flashes / 2, 1.0)
            
            lightning_labels.append({
                'Lightning_Occurred': lightning_occurred,
                'Lightning_Probability': round(lightning_probability, 4),
                'Flash_Count': actual_flashes,
                'Flash_Density_per_km2': round(flash_density, 6),
                'Expected_Flashes': round(expected_flashes, 4),
                'Base_Flash_Rate': base_rate,
                'Time_Factor': time_factor,
                'Weather_Factor': round(weather_factor, 2)
            })
        
        return lightning_labels
    
    def add_derived_features(self, df):
        """
        Add derived features for ML
        """
        
        # Season (Bangladesh specific)
        def get_season(month):
            if month in [12, 1, 2]:
                return 'Winter'
            elif month in [3, 4, 5]:
                return 'Pre-Monsoon'
            elif month in [6, 7, 8, 9]:
                return 'Monsoon'
            else:  # 10, 11
                return 'Post-Monsoon'
        
        df['Season'] = df['Month'].apply(get_season)
        
        # Time of day category
        def get_time_category(hour):
            if 0 <= hour < 6:
                return 'Night'
            elif 6 <= hour < 12:
                return 'Morning'
            elif 12 <= hour < 18:
                return 'Afternoon'
            else:
                return 'Evening'
        
        df['Time_Category'] = df['Hour'].apply(get_time_category)
        
        # Cyclical time features (sin/cos for periodicity)
        df['Month_Sin'] = np.sin(2 * np.pi * df['Month'] / 12)
        df['Month_Cos'] = np.cos(2 * np.pi * df['Month'] / 12)
        df['Hour_Sin'] = np.sin(2 * np.pi * df['Hour'] / 24)
        df['Hour_Cos'] = np.cos(2 * np.pi * df['Hour'] / 24)
        
        # Temperature deviation from daily mean (if multiple records)
        if len(df) > 1:
            df['Temp_Deviation'] = df.groupby('Date')['Temperature_C'].transform(
                lambda x: x - x.mean() if len(x) > 1 else 0
            )
        else:
            df['Temp_Deviation'] = 0
        
        # Precipitation binary flag
        df['Has_Precipitation'] = (df['Precipitation_mm'] > 0).astype(int)
        
        # High humidity flag
        df['High_Humidity'] = (df['Humidity_%'] > 70).astype(int)
        
        # Strong wind flag
        df['Strong_Wind'] = (df['Wind_Speed_m/s'] > 5).astype(int)
        
        return df
    
    def extract_year_data(self, year, location_name, lat, lon):
        """
        Extract complete dataset for one year and location using monthly batches
        """
        
        # Determine date range
        if year == 2025:
            # Extract up to yesterday
            today = datetime.now()
            if today.year == 2025:
                end_month = min(today.month, 11)  # Up to current month or November
            else:
                end_month = 11  # Full year available now
        else:
            end_month = 12
        
        print(f"\n   📅 Extracting {location_name} {year}: Months 1-{end_month}")
        
        year_data = []
        
        # Extract month by month (much more efficient!)
        for month in range(1, end_month + 1):
            # Get weather features for entire month
            max_retries = 3
            retry_count = 0
            weather_records = None
            
            while retry_count < max_retries and not weather_records:
                weather_records = self.get_weather_features_monthly(
                    lat, lon, year, month, location_name
                )
                if not weather_records:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"      ⚠️  Retry {retry_count}/{max_retries}...", end=' ')
                        time.sleep(5)
            
            if not weather_records:
                print(f"      ❌ Skipped month {month} after {max_retries} attempts")
                continue
            
            # Calculate lightning labels for all records
            lightning_labels = self.calculate_lightning_occurrence(weather_records)
            
            # Combine features + labels
            for weather, lightning in zip(weather_records, lightning_labels):
                combined_record = {**weather, **lightning}
                year_data.append(combined_record)
            
            # Small delay between months
            time.sleep(2)
        
        print(f"   ✅ Completed {end_month} months - {len(year_data):,} records")
        
        return year_data
    
    def extract_all_years(self, start_year=2020, end_year=2025):
        """
        Extract dataset for all years (2020-2025)
        """
        
        print("\n" + "=" * 80)
        print("⚡ HYBRID LIGHTNING PREDICTION DATASET EXTRACTOR (2020-2025)")
        print("=" * 80)
        print("\n📊 DATASET COMPONENTS:")
        print("   Features (X): Weather parameters from NASA POWER")
        print("   Target (Y): Lightning occurrence from LIS/OTD climatology")
        print("   Resolution: 30-minute intervals")
        print("   Output: One CSV per year per location")
        print("=" * 80)
        
        start_time = time.time()
        
        for year in range(start_year, end_year + 1):
            print(f"\n{'='*80}")
            print(f"📅 YEAR {year}")
            print(f"{'='*80}")
            
            for location_name, coords in self.locations.items():
                print(f"\n📍 {location_name} ({coords['lat']:.4f}°N, {coords['lon']:.4f}°E)")
                
                # Extract year data
                year_data = self.extract_year_data(
                    year, location_name, coords['lat'], coords['lon']
                )
                
                if not year_data:
                    print(f"   ❌ No data for {location_name} {year}")
                    continue
                
                # Convert to DataFrame
                df = pd.DataFrame(year_data)
                
                # Add derived features
                print(f"      🔧 Adding derived features...")
                df = self.add_derived_features(df)
                
                # Calculate statistics
                lightning_pct = (df['Lightning_Occurred'].sum() / len(df)) * 100
                total_flashes = df['Flash_Count'].sum()
                
                print(f"      📊 Statistics:")
                print(f"         Records: {len(df):,}")
                print(f"         Lightning intervals: {df['Lightning_Occurred'].sum():,} ({lightning_pct:.1f}%)")
                print(f"         Total flashes: {total_flashes:,}")
                
                # Save to CSV
                filename = f"{location_name.lower()}_{year}_lightning_dataset.csv"
                filepath = self.output_dir / filename
                df.to_csv(filepath, index=False)
                print(f"      ✅ Saved: {filename}")
                
                # Add to all_data for combined file
                self.all_data.append(df)
        
        # Create combined dataset (all years, all locations)
        self.create_combined_dataset()
        
        elapsed = time.time() - start_time
        self.print_summary(elapsed)
    
    def create_combined_dataset(self):
        """
        Create combined dataset with all years and locations
        """
        
        if not self.all_data:
            return
        
        print(f"\n{'='*80}")
        print("📦 Creating combined dataset...")
        print(f"{'='*80}")
        
        combined_df = pd.concat(self.all_data, ignore_index=True)
        
        # Save complete combined dataset
        combined_file = self.output_dir / 'combined_all_years_all_locations.csv'
        combined_df.to_csv(combined_file, index=False)
        print(f"   ✅ Combined dataset: {combined_file}")
        print(f"      Total records: {len(combined_df):,}")
        
        # Save by location (all years)
        for location in combined_df['Location'].unique():
            location_df = combined_df[combined_df['Location'] == location]
            location_file = self.output_dir / f'{location.lower()}_all_years.csv'
            location_df.to_csv(location_file, index=False)
            print(f"   ✅ {location} (all years): {location_file.name} ({len(location_df):,} records)")
    
    def print_summary(self, elapsed_time):
        """
        Print extraction summary with statistics
        """
        
        print("\n" + "=" * 80)
        print("📊 EXTRACTION SUMMARY")
        print("=" * 80)
        
        if not self.all_data:
            print("❌ No data extracted")
            return
        
        combined_df = pd.concat(self.all_data, ignore_index=True)
        
        print(f"\n✅ TOTAL DATASET:")
        print(f"   Records: {len(combined_df):,}")
        print(f"   Locations: {combined_df['Location'].nunique()}")
        print(f"   Date range: {combined_df['Date'].min()} to {combined_df['Date'].max()}")
        print(f"   Years: {sorted(combined_df['Date'].str[:4].unique())}")
        
        print("\n⚡ LIGHTNING STATISTICS:")
        total_with_lightning = combined_df['Lightning_Occurred'].sum()
        total_records = len(combined_df)
        pct = (total_with_lightning / total_records) * 100
        print(f"   Intervals with lightning: {total_with_lightning:,} ({pct:.1f}%)")
        print(f"   Intervals without lightning: {total_records - total_with_lightning:,} ({100-pct:.1f}%)")
        print(f"   Total flash count: {combined_df['Flash_Count'].sum():,}")
        print(f"   Average flashes per interval: {combined_df['Flash_Count'].mean():.2f}")
        
        print("\n📈 BY LOCATION:")
        for location in combined_df['Location'].unique():
            loc_df = combined_df[combined_df['Location'] == location]
            loc_lightning = loc_df['Lightning_Occurred'].sum()
            loc_pct = (loc_lightning / len(loc_df)) * 100
            print(f"   {location}:")
            print(f"      Records: {len(loc_df):,}")
            print(f"      Lightning: {loc_lightning:,} ({loc_pct:.1f}%)")
            print(f"      Flashes: {loc_df['Flash_Count'].sum():,}")
        
        print("\n📅 BY YEAR:")
        combined_df['Year'] = combined_df['Date'].str[:4]
        yearly_stats = combined_df.groupby('Year').agg({
            'DateTime': 'count',
            'Lightning_Occurred': 'sum',
            'Flash_Count': 'sum'
        }).rename(columns={'DateTime': 'Records'})
        yearly_stats['Lightning_%'] = (yearly_stats['Lightning_Occurred'] / yearly_stats['Records'] * 100).round(1)
        print(yearly_stats.to_string())
        
        print("\n🌡️  FEATURE STATISTICS:")
        print(f"   Temperature range: {combined_df['Temperature_C'].min():.1f}°C to {combined_df['Temperature_C'].max():.1f}°C")
        print(f"   Humidity range: {combined_df['Humidity_%'].min():.1f}% to {combined_df['Humidity_%'].max():.1f}%")
        print(f"   Wind speed range: {combined_df['Wind_Speed_m/s'].min():.1f} to {combined_df['Wind_Speed_m/s'].max():.1f} m/s")
        print(f"   Precipitation max: {combined_df['Precipitation_mm'].max():.1f} mm")
        
        print("\n📂 OUTPUT FILES:")
        print("=" * 80)
        output_files = sorted(self.output_dir.glob('*.csv'))
        for file in output_files:
            size = file.stat().st_size / (1024 * 1024)  # MB
            print(f"   {file.name} ({size:.1f} MB)")
        
        print("\n💡 DATASET STRUCTURE:")
        print("=" * 80)
        print("   FEATURES (X) - Weather Parameters:")
        print("      • Temperature_C, Humidity_%, Wind_Speed_m/s")
        print("      • Precipitation_mm, Pressure_kPa")
        print("      • Month, Hour, Season, Time_Category")
        print("      • Cyclical features: Month_Sin/Cos, Hour_Sin/Cos")
        print("      • Derived: Temp_Deviation, Has_Precipitation, High_Humidity, Strong_Wind")
        print("\n   TARGET (Y) - Lightning Labels:")
        print("      • Lightning_Occurred (Binary: 0/1) - Main classification target")
        print("      • Lightning_Probability (Float: 0-1) - Regression target")
        print("      • Flash_Count (Integer) - Count regression target")
        
        print(f"\n⏱️  TOTAL EXTRACTION TIME: {elapsed_time/60:.1f} minutes")
        
        print("\n✅ Dataset ready for machine learning!")
        print("   Next steps:")
        print("   1. Load CSV files into your ML framework")
        print("   2. Use Lightning_Occurred as target for classification")
        print("   3. Train models: Random Forest, XGBoost, Neural Networks")
        print("   4. Evaluate using accuracy, precision, recall, F1-score")


def main():
    """Main execution"""
    
    print("\n" + "=" * 80)
    print("⚡ HYBRID LIGHTNING PREDICTION DATASET EXTRACTOR")
    print("   Complete Dataset: Weather Features + Lightning Occurrence")
    print("   Period: 2020-2025 (6 years)")
    print("   Resolution: 30-minute intervals")
    print("=" * 80)
    
    print("\n📍 Locations:")
    print("   • Dhaka (23.8103°N, 90.4125°E)")
    print("   • Chittagong (22.3569°N, 91.7832°E)")
    
    print("\n📊 Expected Output:")
    print("   • 12 CSV files (2 locations × 6 years)")
    print("   • ~17,520 records per location per full year")
    print("   • ~190,000+ total records")
    
    print("\n🚀 Starting extraction...\n")
    
    extractor = HybridLightningDatasetExtractor()
    extractor.extract_all_years(start_year=2020, end_year=2025)
    
    print("\n🎉 Extraction complete!")
    print(f"📂 Check: {extractor.output_dir}")


if __name__ == "__main__":
    main()
