"""
View and analyze the extracted NASA POWER weather data
"""
import pandas as pd
import os

def view_csv_data(filename='dhaka_august_2024.csv'):
    """View the contents of the weather data CSV"""
    
    if not os.path.exists(filename):
        print(f"❌ File '{filename}' not found!")
        print("\nAvailable CSV files:")
        csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
        if csv_files:
            for f in csv_files:
                print(f"  - {f}")
        else:
            print("  No CSV files found. Run example_usage.py first!")
        return
    
    # Read the CSV
    df = pd.read_csv(filename, index_col='Date', parse_dates=True)
    
    print("=" * 70)
    print(f"📊 WEATHER DATA: {filename}")
    print("=" * 70)
    
    print(f"\n📅 Date Range: {df.index.min()} to {df.index.max()}")
    print(f"📈 Total Days: {len(df)}")
    
    print("\n" + "=" * 70)
    print("🌡️  TEMPERATURE STATISTICS")
    print("=" * 70)
    print(f"  Average Temperature:  {df['Temperature_2m_C'].mean():.2f}°C")
    print(f"  Highest Temperature:  {df['Temperature_Max_C'].max():.2f}°C on {df['Temperature_Max_C'].idxmax().date()}")
    print(f"  Lowest Temperature:   {df['Temperature_Min_C'].min():.2f}°C on {df['Temperature_Min_C'].idxmin().date()}")
    
    print("\n" + "=" * 70)
    print("💧 HUMIDITY & PRECIPITATION")
    print("=" * 70)
    print(f"  Average Humidity:     {df['Relative_Humidity_%'].mean():.1f}%")
    print(f"  Total Precipitation:  {df['Precipitation_mm'].sum():.2f} mm")
    print(f"  Rainy Days (>1mm):    {(df['Precipitation_mm'] > 1).sum()} days")
    print(f"  Heaviest Rainfall:    {df['Precipitation_mm'].max():.2f} mm on {df['Precipitation_mm'].idxmax().date()}")
    
    print("\n" + "=" * 70)
    print("💨 WIND & PRESSURE")
    print("=" * 70)
    print(f"  Average Wind Speed:   {df['Wind_Speed_m/s'].mean():.2f} m/s")
    print(f"  Maximum Wind Speed:   {df['Wind_Speed_m/s'].max():.2f} m/s")
    print(f"  Average Pressure:     {df['Surface_Pressure_kPa'].mean():.2f} kPa")
    
    print("\n" + "=" * 70)
    print("☀️  SOLAR RADIATION")
    print("=" * 70)
    print(f"  Average Solar Rad.:   {df['Solar_Radiation_kWh/m2'].mean():.2f} kWh/m²/day")
    print(f"  Total Solar Energy:   {df['Solar_Radiation_kWh/m2'].sum():.2f} kWh/m²")
    
    print("\n" + "=" * 70)
    print("📋 SAMPLE DATA (First 10 days)")
    print("=" * 70)
    
    # Display sample with formatted columns
    display_df = df.head(10).copy()
    display_df.index = display_df.index.date  # Show only date, not time
    
    print(display_df.to_string())
    
    print("\n" + "=" * 70)
    print(f"✅ Full data is saved in: {filename}")
    print("=" * 70)


def compare_csv_files():
    """Compare multiple CSV files if available"""
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
    
    if len(csv_files) < 2:
        print("Need at least 2 CSV files to compare")
        return
    
    print("=" * 70)
    print("📊 COMPARING MULTIPLE LOCATIONS/PERIODS")
    print("=" * 70)
    
    for filename in csv_files[:5]:  # Compare up to 5 files
        df = pd.read_csv(filename, index_col='Date', parse_dates=True)
        print(f"\n📁 {filename}")
        print(f"  Period: {df.index.min().date()} to {df.index.max().date()}")
        print(f"  Avg Temp: {df['Temperature_2m_C'].mean():.2f}°C")
        print(f"  Total Rain: {df['Precipitation_mm'].sum():.2f} mm")
        print(f"  Avg Humidity: {df['Relative_Humidity_%'].mean():.1f}%")


if __name__ == "__main__":
    # View the most recent data file
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
    
    if csv_files:
        print("\n🌦️  NASA POWER Weather Data Viewer\n")
        
        # Show first CSV file
        view_csv_data(csv_files[0])
        
        # If multiple files exist, show comparison
        if len(csv_files) > 1:
            print("\n\n")
            compare_csv_files()
    else:
        print("❌ No CSV files found!")
        print("Run 'python example_usage.py' first to download data.")
