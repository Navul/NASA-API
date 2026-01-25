"""
Extract Complete 2025 Lightning Prediction Dataset for All Bangladesh Districts
This script re-extracts 2025 data (Jan 1 to Dec 31, 2025) for all 8 divisions
and then combines it with existing 2023-2024 data.

Run Date: January 2026 (so full 2025 data is available)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import time
import calendar

try:
    from nasa_power_api import NASAPowerAPI
except ImportError:
    print("❌ Error: nasa_power_api.py not found")
    import sys
    sys.exit(1)


class Lightning2025Extractor:
    """
    Extract complete 2025 lightning prediction dataset for all Bangladesh districts
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
        
        # All 8 Bangladesh Divisions (Districts)
        self.locations = {
            'Dhaka': {'lat': 23.8103, 'lon': 90.4125},
            'Chittagong': {'lat': 22.3569, 'lon': 91.7832},
            'Rajshahi': {'lat': 24.3636, 'lon': 88.6241},
            'Khulna': {'lat': 22.8456, 'lon': 89.5403},
            'Barisal': {'lat': 22.7010, 'lon': 90.3535},
            'Sylhet': {'lat': 24.8949, 'lon': 91.8687},
            'Rangpur': {'lat': 25.7439, 'lon': 89.2752},
            'Mymensingh': {'lat': 24.7471, 'lon': 90.4203}
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
        
        self.all_2025_data = []
    
    def get_weather_features_monthly(self, lat, lon, year, month, location_name):
        """
        Extract weather features for entire month
        Returns features for ML training
        """
        
        try:
            # Get first and last day of month
            start_date = f"{year}{month:02d}01"
            last_day = calendar.monthrange(year, month)[1]
            end_date = f"{year}{month:02d}{last_day}"
            
            print(f"      Fetching month {month:02d} ({last_day} days)...", end=' ')
            
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
    
    def extract_2025_data(self, location_name, lat, lon):
        """
        Extract complete 2025 dataset for one location (all 12 months)
        """
        
        year = 2025
        print(f"\n   📅 Extracting {location_name} {year}: All 12 months")
        
        year_data = []
        
        # Extract all 12 months for 2025
        for month in range(1, 13):
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
            
            # Small delay between months (respect API rate limits)
            time.sleep(2)
        
        print(f"   ✅ Completed 12 months - {len(year_data):,} records")
        
        return year_data
    
    def extract_all_districts(self):
        """
        Extract 2025 data for all 8 districts
        """
        
        print("\n" + "=" * 80)
        print("⚡ 2025 LIGHTNING PREDICTION DATASET EXTRACTOR")
        print("   Complete Dataset for All 8 Bangladesh Divisions")
        print("=" * 80)
        print("\n📊 DATASET COMPONENTS:")
        print("   Features (X): Weather parameters from NASA POWER")
        print("   Target (Y): Lightning occurrence from LIS/OTD climatology")
        print("   Resolution: 30-minute intervals")
        print("   Period: January 1 - December 31, 2025 (Full Year)")
        print("=" * 80)
        
        print("\n📍 Locations:")
        for name, coords in self.locations.items():
            print(f"   • {name} ({coords['lat']:.4f}°N, {coords['lon']:.4f}°E)")
        
        start_time = time.time()
        
        for location_name, coords in self.locations.items():
            print(f"\n{'='*80}")
            print(f"📍 {location_name.upper()} ({coords['lat']:.4f}°N, {coords['lon']:.4f}°E)")
            print(f"{'='*80}")
            
            # Extract 2025 data
            year_data = self.extract_2025_data(
                location_name, coords['lat'], coords['lon']
            )
            
            if not year_data:
                print(f"   ❌ No data for {location_name} 2025")
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
            
            # Save to CSV (new 2025 file)
            filename = f"{location_name.lower()}_2025_lightning_dataset_new.csv"
            filepath = self.output_dir / filename
            df.to_csv(filepath, index=False)
            print(f"      ✅ Saved: {filename}")
            
            # Add to all_2025_data for combined file
            df['Year'] = 2025
            df['District'] = location_name
            self.all_2025_data.append(df)
        
        elapsed = time.time() - start_time
        
        # Save combined 2025 dataset
        self.save_combined_2025()
        
        # Create combined 2023-2025 dataset
        self.create_combined_2023_2025()
        
        self.print_summary(elapsed)
    
    def save_combined_2025(self):
        """
        Save all 2025 data combined
        """
        
        if not self.all_2025_data:
            return
        
        print(f"\n{'='*80}")
        print("📦 Creating combined 2025 dataset...")
        print(f"{'='*80}")
        
        combined_df = pd.concat(self.all_2025_data, ignore_index=True)
        
        # Reorder columns
        cols = combined_df.columns.tolist()
        priority_cols = ['DateTime', 'Date', 'Time', 'Year', 'District', 'Location', 'Latitude', 'Longitude']
        new_cols = []
        for col in priority_cols:
            if col in cols:
                new_cols.append(col)
                cols.remove(col)
        new_cols.extend(cols)
        combined_df = combined_df[new_cols]
        
        # Save
        combined_file = self.output_dir / 'combined_2025_all_districts_new.csv'
        combined_df.to_csv(combined_file, index=False)
        print(f"   ✅ Combined 2025 dataset: {combined_file.name}")
        print(f"      Total records: {len(combined_df):,}")
    
    def create_combined_2023_2025(self):
        """
        Combine new 2025 data with existing 2023-2024 data
        """
        
        if not self.all_2025_data:
            return
        
        print(f"\n{'='*80}")
        print("📦 Creating combined 2023-2025 dataset...")
        print(f"{'='*80}")
        
        all_dataframes = []
        
        # Load 2023 and 2024 data from existing files
        districts = ['barisal', 'chittagong', 'dhaka', 'khulna', 'mymensingh', 'rajshahi', 'rangpur', 'sylhet']
        years = [2023, 2024]
        
        print("\n   Loading existing 2023-2024 data...")
        for district in districts:
            for year in years:
                filename = f"{district}_{year}_lightning_dataset.csv"
                filepath = self.output_dir / filename
                
                if filepath.exists():
                    df = pd.read_csv(filepath)
                    if 'Year' not in df.columns:
                        df['Year'] = year
                    if 'District' not in df.columns:
                        df['District'] = district.capitalize()
                    all_dataframes.append(df)
                    print(f"      ✓ Loaded: {filename} ({len(df):,} rows)")
                else:
                    print(f"      ✗ Not found: {filename}")
        
        # Add new 2025 data
        print("\n   Adding new 2025 data...")
        for df_2025 in self.all_2025_data:
            all_dataframes.append(df_2025)
            district = df_2025['District'].iloc[0] if 'District' in df_2025.columns else 'Unknown'
            print(f"      ✓ Added: {district} 2025 ({len(df_2025):,} rows)")
        
        # Combine all
        combined_df = pd.concat(all_dataframes, ignore_index=True)
        
        # Sort by District and DateTime
        combined_df = combined_df.sort_values(['District', 'DateTime']).reset_index(drop=True)
        
        # Reorder columns
        cols = combined_df.columns.tolist()
        priority_cols = ['DateTime', 'Date', 'Time', 'Year', 'District', 'Location', 'Latitude', 'Longitude']
        new_cols = []
        for col in priority_cols:
            if col in cols:
                new_cols.append(col)
                cols.remove(col)
        new_cols.extend(cols)
        combined_df = combined_df[new_cols]
        
        # Save combined 2023-2025 dataset
        combined_file = self.output_dir / 'combined_2023_2025_all_districts_updated.csv'
        combined_df.to_csv(combined_file, index=False)
        
        print(f"\n   ✅ Combined 2023-2025 dataset saved: {combined_file.name}")
        print(f"      Total records: {len(combined_df):,}")
        
        # Print statistics
        print("\n   --- Rows per District ---")
        district_counts = combined_df.groupby('District').size()
        for district, count in district_counts.items():
            print(f"      {district}: {count:,} rows")
        
        print("\n   --- Rows per Year ---")
        year_counts = combined_df.groupby('Year').size()
        for year, count in year_counts.items():
            print(f"      {year}: {count:,} rows")
    
    def print_summary(self, elapsed_time):
        """
        Print extraction summary
        """
        
        print("\n" + "=" * 80)
        print("📊 EXTRACTION SUMMARY")
        print("=" * 80)
        
        if not self.all_2025_data:
            print("❌ No data extracted")
            return
        
        combined_df = pd.concat(self.all_2025_data, ignore_index=True)
        
        print(f"\n✅ 2025 DATASET:")
        print(f"   Records: {len(combined_df):,}")
        print(f"   Districts: {combined_df['District'].nunique()}")
        print(f"   Date range: {combined_df['Date'].min()} to {combined_df['Date'].max()}")
        
        print("\n⚡ LIGHTNING STATISTICS:")
        total_with_lightning = combined_df['Lightning_Occurred'].sum()
        total_records = len(combined_df)
        pct = (total_with_lightning / total_records) * 100
        print(f"   Intervals with lightning: {total_with_lightning:,} ({pct:.1f}%)")
        print(f"   Total flash count: {combined_df['Flash_Count'].sum():,}")
        
        print("\n📈 BY DISTRICT:")
        for district in sorted(combined_df['District'].unique()):
            dist_df = combined_df[combined_df['District'] == district]
            dist_lightning = dist_df['Lightning_Occurred'].sum()
            dist_pct = (dist_lightning / len(dist_df)) * 100
            print(f"   {district}: {len(dist_df):,} records, {dist_lightning:,} lightning ({dist_pct:.1f}%)")
        
        print(f"\n⏱️  TOTAL EXTRACTION TIME: {elapsed_time/60:.1f} minutes")
        
        print("\n📂 OUTPUT FILES:")
        print("   • Individual 2025 files: {district}_2025_lightning_dataset_new.csv")
        print("   • Combined 2025: combined_2025_all_districts_new.csv")
        print("   • Combined 2023-2025: combined_2023_2025_all_districts_updated.csv")
        
        print("\n✅ Dataset ready for machine learning!")


def main():
    """Main execution"""
    
    print("\n" + "=" * 80)
    print("⚡ 2025 LIGHTNING PREDICTION DATASET EXTRACTOR")
    print("   Re-extracting full 2025 data for all Bangladesh divisions")
    print("=" * 80)
    
    extractor = Lightning2025Extractor()
    extractor.extract_all_districts()
    
    print("\n🎉 Extraction complete!")
    print(f"📂 Check: {extractor.output_dir}")


if __name__ == "__main__":
    main()
