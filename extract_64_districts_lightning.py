"""
Extract weather data for all 64 districts of Bangladesh
Focused on lightning detection parameters
~1000 samples: 64 districts × 16 days = 1024 samples
"""

from nasa_power_api import NASAPowerAPI
import pandas as pd
from datetime import datetime, timedelta
import time
import os

# All 64 districts of Bangladesh with coordinates
BANGLADESH_DISTRICTS = {
    # Dhaka Division
    'Dhaka': {'lat': 23.8103, 'lon': 90.4125, 'division': 'Dhaka'},
    'Faridpur': {'lat': 23.6070, 'lon': 89.8429, 'division': 'Dhaka'},
    'Gazipur': {'lat': 24.0022, 'lon': 90.4264, 'division': 'Dhaka'},
    'Gopalganj': {'lat': 23.0050, 'lon': 89.8266, 'division': 'Dhaka'},
    'Jamalpur': {'lat': 24.9375, 'lon': 89.9372, 'division': 'Dhaka'},
    'Kishoreganj': {'lat': 24.4260, 'lon': 90.7760, 'division': 'Dhaka'},
    'Madaripur': {'lat': 23.1641, 'lon': 90.1897, 'division': 'Dhaka'},
    'Manikganj': {'lat': 23.8617, 'lon': 90.0003, 'division': 'Dhaka'},
    'Munshiganj': {'lat': 23.5422, 'lon': 90.5305, 'division': 'Dhaka'},
    'Mymensingh': {'lat': 24.7471, 'lon': 90.4203, 'division': 'Mymensingh'},
    'Narayanganj': {'lat': 23.6238, 'lon': 90.5000, 'division': 'Dhaka'},
    'Narsingdi': {'lat': 23.9322, 'lon': 90.7151, 'division': 'Dhaka'},
    'Netrokona': {'lat': 24.8103, 'lon': 90.7270, 'division': 'Mymensingh'},
    'Rajbari': {'lat': 23.7574, 'lon': 89.6444, 'division': 'Dhaka'},
    'Shariatpur': {'lat': 23.2423, 'lon': 90.4348, 'division': 'Dhaka'},
    'Sherpur': {'lat': 25.0204, 'lon': 90.0152, 'division': 'Mymensingh'},
    'Tangail': {'lat': 24.2513, 'lon': 89.9167, 'division': 'Dhaka'},
    
    # Chittagong Division
    'Bandarban': {'lat': 22.1953, 'lon': 92.2183, 'division': 'Chittagong'},
    'Brahmanbaria': {'lat': 23.9570, 'lon': 91.1119, 'division': 'Chittagong'},
    'Chandpur': {'lat': 23.2332, 'lon': 90.6712, 'division': 'Chittagong'},
    'Chittagong': {'lat': 22.3569, 'lon': 91.7832, 'division': 'Chittagong'},
    'Comilla': {'lat': 23.4607, 'lon': 91.1809, 'division': 'Chittagong'},
    'Cox\'s Bazar': {'lat': 21.4272, 'lon': 92.0058, 'division': 'Chittagong'},
    'Feni': {'lat': 23.0159, 'lon': 91.3976, 'division': 'Chittagong'},
    'Khagrachari': {'lat': 23.1193, 'lon': 91.9847, 'division': 'Chittagong'},
    'Lakshmipur': {'lat': 22.9447, 'lon': 90.8298, 'division': 'Chittagong'},
    'Noakhali': {'lat': 22.8696, 'lon': 91.0995, 'division': 'Chittagong'},
    'Rangamati': {'lat': 22.7324, 'lon': 92.2985, 'division': 'Chittagong'},
    
    # Rajshahi Division
    'Bogra': {'lat': 24.8465, 'lon': 89.3770, 'division': 'Rajshahi'},
    'Joypurhat': {'lat': 25.0968, 'lon': 89.0227, 'division': 'Rajshahi'},
    'Naogaon': {'lat': 24.7936, 'lon': 88.9318, 'division': 'Rajshahi'},
    'Natore': {'lat': 24.4206, 'lon': 89.0042, 'division': 'Rajshahi'},
    'Nawabganj': {'lat': 24.5965, 'lon': 88.2775, 'division': 'Rajshahi'},
    'Pabna': {'lat': 24.0064, 'lon': 89.2372, 'division': 'Rajshahi'},
    'Rajshahi': {'lat': 24.3745, 'lon': 88.6042, 'division': 'Rajshahi'},
    'Sirajganj': {'lat': 24.4533, 'lon': 89.7006, 'division': 'Rajshahi'},
    
    # Khulna Division
    'Bagerhat': {'lat': 22.6602, 'lon': 89.7895, 'division': 'Khulna'},
    'Chuadanga': {'lat': 23.6401, 'lon': 88.8410, 'division': 'Khulna'},
    'Jessore': {'lat': 23.1634, 'lon': 89.2182, 'division': 'Khulna'},
    'Jhenaidah': {'lat': 23.5448, 'lon': 89.1539, 'division': 'Khulna'},
    'Khulna': {'lat': 22.8456, 'lon': 89.5403, 'division': 'Khulna'},
    'Kushtia': {'lat': 23.9011, 'lon': 89.1099, 'division': 'Khulna'},
    'Magura': {'lat': 23.4855, 'lon': 89.4198, 'division': 'Khulna'},
    'Meherpur': {'lat': 23.7622, 'lon': 88.6318, 'division': 'Khulna'},
    'Narail': {'lat': 23.1163, 'lon': 89.5840, 'division': 'Khulna'},
    'Satkhira': {'lat': 22.7185, 'lon': 89.0705, 'division': 'Khulna'},
    
    # Barisal Division
    'Barguna': {'lat': 22.1590, 'lon': 90.1119, 'division': 'Barisal'},
    'Barisal': {'lat': 22.7010, 'lon': 90.3535, 'division': 'Barisal'},
    'Bhola': {'lat': 22.6859, 'lon': 90.6482, 'division': 'Barisal'},
    'Jhalokati': {'lat': 22.6406, 'lon': 90.1987, 'division': 'Barisal'},
    'Patuakhali': {'lat': 22.3596, 'lon': 90.3298, 'division': 'Barisal'},
    'Pirojpur': {'lat': 22.5841, 'lon': 89.9720, 'division': 'Barisal'},
    
    # Sylhet Division
    'Habiganj': {'lat': 24.3745, 'lon': 91.4156, 'division': 'Sylhet'},
    'Moulvibazar': {'lat': 24.4820, 'lon': 91.7313, 'division': 'Sylhet'},
    'Sunamganj': {'lat': 25.0657, 'lon': 91.3950, 'division': 'Sylhet'},
    'Sylhet': {'lat': 24.8949, 'lon': 91.8687, 'division': 'Sylhet'},
    
    # Rangpur Division
    'Dinajpur': {'lat': 25.6217, 'lon': 88.6354, 'division': 'Rangpur'},
    'Gaibandha': {'lat': 25.3297, 'lon': 89.5430, 'division': 'Rangpur'},
    'Kurigram': {'lat': 25.8074, 'lon': 89.6361, 'division': 'Rangpur'},
    'Lalmonirhat': {'lat': 25.9923, 'lon': 89.2847, 'division': 'Rangpur'},
    'Nilphamari': {'lat': 25.9317, 'lon': 88.8560, 'division': 'Rangpur'},
    'Panchagarh': {'lat': 26.3411, 'lon': 88.5541, 'division': 'Rangpur'},
    'Rangpur': {'lat': 25.7439, 'lon': 89.2752, 'division': 'Rangpur'},
    'Thakurgaon': {'lat': 26.0336, 'lon': 88.4616, 'division': 'Rangpur'},
}


def extract_lightning_data():
    """
    Extract weather data for all 64 districts with parameters important for lightning detection
    """
    
    print("=" * 80)
    print("⚡ LIGHTNING DETECTION DATA EXTRACTION")
    print("📍 All 64 Districts of Bangladesh")
    print("=" * 80)
    
    api = NASAPowerAPI()
    
    # Lightning-relevant parameters
    # More parameters than default to detect atmospheric instability
    lightning_parameters = [
        'T2M',              # Temperature at 2m (°C) - Thermal instability
        'T2M_MAX',          # Maximum Temperature (°C)
        'T2M_MIN',          # Minimum Temperature (°C)
        'T2MDEW',           # Dew Point Temperature (°C) - Moisture content
        'RH2M',             # Relative Humidity (%) - Moisture
        'PRECTOTCORR',      # Precipitation (mm/day) - Storm activity
        'WS2M',             # Wind Speed at 2m (m/s) - Convection
        'WS10M',            # Wind Speed at 10m (m/s) - Upper wind
        'WD2M',             # Wind Direction (degrees)
        'PS',               # Surface Pressure (kPa) - Pressure systems
        'ALLSKY_SFC_SW_DWN', # Solar Radiation (kWh/m²/day) - Heating
        'ALLSKY_SFC_LW_DWN', # Longwave Radiation - Atmospheric heat
        'T2M_RANGE',        # Temperature Range - Instability indicator
        'QV2M',             # Specific Humidity (g/kg) - Moisture content
    ]
    
    # Date range: 16 days (recent period)
    # 64 districts × 16 days = 1024 samples
    end_date = datetime(2024, 8, 31)  # Using August 2024 (monsoon season - high lightning)
    start_date = datetime(2024, 8, 16)
    
    start_str = start_date.strftime('%Y%m%d')
    end_str = end_date.strftime('%Y%m%d')
    
    print(f"\n📅 Date Range: {start_date.date()} to {end_date.date()}")
    print(f"📊 Days per District: {(end_date - start_date).days + 1}")
    print(f"🎯 Total Expected Samples: {len(BANGLADESH_DISTRICTS) * ((end_date - start_date).days + 1)}")
    print(f"\n⚡ Lightning Detection Parameters ({len(lightning_parameters)}):")
    for i, param in enumerate(lightning_parameters, 1):
        print(f"  {i}. {param}")
    
    print(f"\n🚀 Starting extraction...")
    print("=" * 80)
    
    all_data = []
    success_count = 0
    failed_districts = []
    
    start_time = time.time()
    
    for idx, (district, coords) in enumerate(BANGLADESH_DISTRICTS.items(), 1):
        print(f"\n[{idx}/{len(BANGLADESH_DISTRICTS)}] 📍 {district} ({coords['division']} Division)")
        print(f"    Coordinates: {coords['lat']:.4f}°N, {coords['lon']:.4f}°E")
        
        try:
            # Fetch data
            data = api.get_daily_data(
                latitude=coords['lat'],
                longitude=coords['lon'],
                start_date=start_str,
                end_date=end_str,
                parameters=lightning_parameters
            )
            
            if data:
                # Convert to DataFrame
                df = api.convert_to_dataframe(data)
                
                if df is not None:
                    # Add district information
                    df['District'] = district
                    df['Division'] = coords['division']
                    df['Latitude'] = coords['lat']
                    df['Longitude'] = coords['lon']
                    
                    all_data.append(df)
                    success_count += 1
                    print(f"    ✓ Success! {len(df)} records retrieved")
                else:
                    failed_districts.append(district)
                    print(f"    ✗ Failed to convert data")
            else:
                failed_districts.append(district)
                print(f"    ✗ No data received")
                
        except Exception as e:
            failed_districts.append(district)
            print(f"    ✗ Error: {e}")
        
        # Be respectful to API - add delay
        if idx < len(BANGLADESH_DISTRICTS):
            time.sleep(1)  # 1 second delay between requests
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    print("\n" + "=" * 80)
    print("📊 EXTRACTION SUMMARY")
    print("=" * 80)
    print(f"✓ Successful: {success_count}/{len(BANGLADESH_DISTRICTS)} districts")
    print(f"✗ Failed: {len(failed_districts)} districts")
    if failed_districts:
        print(f"   Failed: {', '.join(failed_districts)}")
    print(f"⏱️  Total Time: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
    print(f"⚡ Average: {elapsed_time/len(BANGLADESH_DISTRICTS):.2f} seconds per district")
    
    if all_data:
        # Combine all data
        print("\n🔄 Combining data from all districts...")
        combined_df = pd.concat(all_data, ignore_index=False)
        combined_df.reset_index(inplace=True)
        combined_df.rename(columns={'index': 'Date'}, inplace=True)
        
        # Reorder columns
        cols = ['Date', 'District', 'Division', 'Latitude', 'Longitude'] + \
               [col for col in combined_df.columns if col not in 
                ['Date', 'District', 'Division', 'Latitude', 'Longitude']]
        combined_df = combined_df[cols]
        
        print(f"\n✅ Combined Dataset Shape: {combined_df.shape}")
        print(f"   Rows: {combined_df.shape[0]:,}")
        print(f"   Columns: {combined_df.shape[1]}")
        
        # Save to CSV
        filename = f'bangladesh_64_districts_lightning_data.csv'
        combined_df.to_csv(filename, index=False)
        print(f"\n💾 Data saved to: {filename}")
        
        # Display statistics
        print("\n" + "=" * 80)
        print("📈 DATASET STATISTICS")
        print("=" * 80)
        
        print("\n🌡️  Temperature Statistics:")
        print(f"   Average: {combined_df['Temperature_2m_C'].mean():.2f}°C")
        print(f"   Range: {combined_df['Temperature_Min_C'].min():.2f}°C to {combined_df['Temperature_Max_C'].max():.2f}°C")
        
        print("\n💧 Humidity & Precipitation:")
        print(f"   Average Humidity: {combined_df['Relative_Humidity_%'].mean():.1f}%")
        print(f"   Total Precipitation: {combined_df['Precipitation_mm'].sum():.2f} mm")
        print(f"   Days with Rain (>1mm): {(combined_df['Precipitation_mm'] > 1).sum()}")
        
        print("\n💨 Wind Statistics:")
        print(f"   Average Wind Speed (2m): {combined_df['Wind_Speed_m/s'].mean():.2f} m/s")
        print(f"   Max Wind Speed: {combined_df['Wind_Speed_m/s'].max():.2f} m/s")
        
        print("\n📊 Data by Division:")
        division_counts = combined_df.groupby('Division').size()
        for division, count in division_counts.items():
            print(f"   {division}: {count} records")
        
        # Sample preview
        print("\n" + "=" * 80)
        print("👁️  DATA PREVIEW (First 10 rows)")
        print("=" * 80)
        print(combined_df.head(10).to_string(max_colwidth=15))
        
        print("\n" + "=" * 80)
        print("✅ EXTRACTION COMPLETE!")
        print("=" * 80)
        print(f"\n📁 Output file: {filename}")
        print(f"📊 Total records: {len(combined_df):,}")
        print(f"⚡ Features: {combined_df.shape[1]} (optimized for lightning detection)")
        print("\n🎯 This dataset is ready for lightning prediction analysis!")
        
        return combined_df
    else:
        print("\n❌ No data was successfully extracted!")
        return None


if __name__ == "__main__":
    df = extract_lightning_data()
