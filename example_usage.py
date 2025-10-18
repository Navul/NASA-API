"""
Example usage scenarios for NASA POWER API
"""

from nasa_power_api import NASAPowerAPI
from datetime import datetime, timedelta
import pandas as pd


def example_1_last_30_days():
    """
    Example 1: Get weather data for the last 30 days in Dhaka
    """
    print("\n" + "="*60)
    print("EXAMPLE 1: Recent Weather Data for Dhaka")
    print("="*60)
    
    api = NASAPowerAPI()
    
    # Use a date range with available data (NASA POWER has ~2 month delay)
    # Using data from mid-2024 to ensure availability
    end_date = datetime(2024, 8, 31)
    start_date = datetime(2024, 8, 1)
    
    # Fetch data
    data = api.get_daily_data(
        latitude=23.8103,   # Dhaka
        longitude=90.4125,
        start_date=start_date.strftime('%Y%m%d'),
        end_date=end_date.strftime('%Y%m%d')
    )
    
    if data:
        df = api.convert_to_dataframe(data)
        if df is not None:
            print("\n📊 Data Summary:")
            print(df.describe())
            
            print("\n📈 Last 5 days:")
            print(df.tail())
            
            # Save to CSV
            api.save_to_csv(df, 'dhaka_august_2024.csv')
            return df


def example_2_yearly_data():
    """
    Example 2: Get full year data for 2023
    """
    print("\n" + "="*60)
    print("EXAMPLE 2: Full Year 2023 Data for Dhaka")
    print("="*60)
    
    api = NASAPowerAPI()
    
    data = api.get_daily_data(
        latitude=23.8103,
        longitude=90.4125,
        start_date='20230101',
        end_date='20231231'
    )
    
    if data:
        df = api.convert_to_dataframe(data)
        if df is not None:
            print(f"\n✓ Retrieved {len(df)} days of data")
            
            # Calculate statistics
            print("\n📊 2023 Weather Statistics:")
            print(f"Average Temperature: {df['Temperature_2m_C'].mean():.2f}°C")
            print(f"Highest Temperature: {df['Temperature_Max_C'].max():.2f}°C")
            print(f"Lowest Temperature: {df['Temperature_Min_C'].min():.2f}°C")
            print(f"Total Precipitation: {df['Precipitation_mm'].sum():.2f} mm")
            print(f"Average Humidity: {df['Relative_Humidity_%'].mean():.2f}%")
            
            api.save_to_csv(df, 'dhaka_2023_full_year.csv')
            return df


def example_3_multiple_cities():
    """
    Example 3: Compare weather across multiple Bangladesh cities
    """
    print("\n" + "="*60)
    print("EXAMPLE 3: Multi-City Weather Comparison (January 2024)")
    print("="*60)
    
    api = NASAPowerAPI()
    
    cities = {
        'Dhaka': {'lat': 23.8103, 'lon': 90.4125},
        'Chittagong': {'lat': 22.3569, 'lon': 91.7832},
        'Sylhet': {'lat': 24.8949, 'lon': 91.8687},
    }
    
    results = {}
    
    for city, coords in cities.items():
        print(f"\n📍 Fetching data for {city}...")
        
        data = api.get_daily_data(
            latitude=coords['lat'],
            longitude=coords['lon'],
            start_date='20240101',
            end_date='20240131'
        )
        
        if data:
            df = api.convert_to_dataframe(data)
            if df is not None:
                results[city] = df
                
                # Print summary
                print(f"  Average Temperature: {df['Temperature_2m_C'].mean():.2f}°C")
                print(f"  Total Precipitation: {df['Precipitation_mm'].sum():.2f} mm")
                
                # Save individual city data
                api.save_to_csv(df, f'{city.lower()}_jan2024.csv')
        
        # Be nice to the API
        import time
        time.sleep(1)
    
    return results


def example_4_specific_parameters():
    """
    Example 4: Fetch only temperature and rainfall (lighter request)
    """
    print("\n" + "="*60)
    print("EXAMPLE 4: Temperature & Rainfall Only (2023)")
    print("="*60)
    
    api = NASAPowerAPI()
    
    # Only temperature and precipitation
    parameters = ['T2M', 'T2M_MAX', 'T2M_MIN', 'PRECTOTCORR']
    
    data = api.get_daily_data(
        latitude=23.8103,
        longitude=90.4125,
        start_date='20230101',
        end_date='20231231',
        parameters=parameters
    )
    
    if data:
        df = api.convert_to_dataframe(data)
        if df is not None:
            print("\n📊 Available columns:")
            print(df.columns.tolist())
            
            print("\n📈 Data preview:")
            print(df.head(10))
            
            api.save_to_csv(df, 'dhaka_temp_rainfall_2023.csv')
            return df


def example_5_monthly_averages():
    """
    Example 5: Calculate monthly averages for analysis
    """
    print("\n" + "="*60)
    print("EXAMPLE 5: Monthly Averages for 2023")
    print("="*60)
    
    api = NASAPowerAPI()
    
    data = api.get_daily_data(
        latitude=23.8103,
        longitude=90.4125,
        start_date='20230101',
        end_date='20231231'
    )
    
    if data:
        df = api.convert_to_dataframe(data)
        if df is not None:
            # Calculate monthly averages
            monthly = df.resample('M').agg({
                'Temperature_2m_C': 'mean',
                'Temperature_Max_C': 'max',
                'Temperature_Min_C': 'min',
                'Precipitation_mm': 'sum',
                'Relative_Humidity_%': 'mean',
                'Wind_Speed_m/s': 'mean'
            })
            
            monthly.index = monthly.index.strftime('%B %Y')
            
            print("\n📊 Monthly Statistics:")
            print(monthly)
            
            # Save monthly data
            monthly.to_csv('dhaka_monthly_2023.csv')
            return monthly


def example_6_custom_location():
    """
    Example 6: Use custom coordinates (e.g., your specific study area)
    """
    print("\n" + "="*60)
    print("EXAMPLE 6: Custom Location Weather Data")
    print("="*60)
    
    api = NASAPowerAPI()
    
    # Example: Cox's Bazar (coastal region)
    custom_lat = 21.4272
    custom_lon = 92.0058
    
    print(f"📍 Location: Cox's Bazar ({custom_lat}°N, {custom_lon}°E)")
    
    data = api.get_daily_data(
        latitude=custom_lat,
        longitude=custom_lon,
        start_date='20240101',
        end_date='20240630'
    )
    
    if data:
        df = api.convert_to_dataframe(data)
        if df is not None:
            print(f"\n✓ Retrieved {len(df)} days of data")
            print("\n📊 Summary Statistics:")
            print(df.describe())
            
            api.save_to_csv(df, 'coxs_bazar_2024_h1.csv')
            return df


def main():
    """
    Run all examples (uncomment the ones you want to try)
    """
    print("\n🌦️  NASA POWER API - Example Usage Scenarios")
    print("=" * 60)
    
    # Example 1: Last 30 days
    example_1_last_30_days()
    
    # Example 2: Full year data
    # example_2_yearly_data()
    
    # Example 3: Multiple cities
    # example_3_multiple_cities()
    
    # Example 4: Specific parameters only
    # example_4_specific_parameters()
    
    # Example 5: Monthly averages
    # example_5_monthly_averages()
    
    # Example 6: Custom location
    # example_6_custom_location()
    
    print("\n✅ Examples completed!")
    print("\nTip: Uncomment other examples in main() to try them")


if __name__ == "__main__":
    main()
