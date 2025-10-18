"""
NASA POWER API Data Extraction
Extract weather and climate parameters for Bangladesh (2015-present)
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import json
import time


class NASAPowerAPI:
    """
    A class to interact with NASA POWER API for weather and climate data
    """
    
    BASE_URL = "https://power.larc.nasa.gov/api/temporal"
    
    # Common weather parameters
    PARAMETERS = {
        'temperature': 'T2M',              # Temperature at 2m (°C)
        'temp_max': 'T2M_MAX',             # Max Temperature (°C)
        'temp_min': 'T2M_MIN',             # Min Temperature (°C)
        'humidity': 'RH2M',                # Relative Humidity at 2m (%)
        'precipitation': 'PRECTOTCORR',    # Precipitation Corrected (mm/day)
        'wind_speed': 'WS2M',              # Wind Speed at 2m (m/s)
        'pressure': 'PS',                  # Surface Pressure (kPa)
        'solar_radiation': 'ALLSKY_SFC_SW_DWN',  # Solar Radiation (kWh/m²/day)
        'wind_direction': 'WD2M',          # Wind Direction at 2m (Degrees)
    }
    
    # Bangladesh coordinates (approximate center)
    # You can customize these for specific locations
    BANGLADESH_LOCATIONS = {
        'Dhaka': {'lat': 23.8103, 'lon': 90.4125},
        'Chittagong': {'lat': 22.3569, 'lon': 91.7832},
        'Sylhet': {'lat': 24.8949, 'lon': 91.8687},
        'Rajshahi': {'lat': 24.3745, 'lon': 88.6042},
        'Khulna': {'lat': 22.8456, 'lon': 89.5403},
    }
    
    def __init__(self):
        """Initialize the NASA POWER API client"""
        self.session = requests.Session()
    
    def get_daily_data(self, latitude, longitude, start_date, end_date, 
                      parameters=None, community='ag'):
        """
        Fetch daily weather data for a specific location
        
        Parameters:
        -----------
        latitude : float
            Latitude of the location (-90 to 90)
        longitude : float
            Longitude of the location (-180 to 180)
        start_date : str
            Start date in format 'YYYYMMDD' (e.g., '20150101')
        end_date : str
            End date in format 'YYYYMMDD'
        parameters : list
            List of parameter codes (default: common weather params)
        community : str
            Data community: 'ag' (agroclimatology), 're' (renewable energy), 'sb' (sustainable buildings)
        
        Returns:
        --------
        dict : API response with weather data
        """
        if parameters is None:
            # Default parameters for comprehensive weather data
            parameters = [
                'T2M', 'T2M_MAX', 'T2M_MIN', 'RH2M', 
                'PRECTOTCORR', 'WS2M', 'PS', 'ALLSKY_SFC_SW_DWN'
            ]
        
        # Join parameters with comma
        params_str = ','.join(parameters)
        
        # Build the API URL - Correct format with /point endpoint
        url = f"{self.BASE_URL}/daily/point"
        
        # API parameters
        params = {
            'parameters': params_str,
            'community': community,
            'start': start_date,
            'end': end_date,
            'latitude': latitude,
            'longitude': longitude,
            'format': 'json'
        }
        
        try:
            print(f"Fetching data for coordinates ({latitude}, {longitude})...")
            print(f"Date range: {start_date} to {end_date}")
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            print(f"✓ Data retrieved successfully!")
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Error fetching data: {e}")
            return None
    
    def get_hourly_data(self, latitude, longitude, start_date, end_date, 
                       parameters=None, community='ag'):
        """
        Fetch hourly weather data (available from 2001 onwards)
        
        Note: Hourly data has limited parameters compared to daily data
        """
        if parameters is None:
            # Hourly available parameters
            parameters = [
                'T2M', 'RH2M', 'WS2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN'
            ]
        
        params_str = ','.join(parameters)
        url = f"{self.BASE_URL}/hourly/point"
        
        params = {
            'parameters': params_str,
            'community': community,
            'start': start_date,
            'end': end_date,
            'latitude': latitude,
            'longitude': longitude,
            'format': 'json'
        }
        
        try:
            print(f"Fetching hourly data for coordinates ({latitude}, {longitude})...")
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            print(f"✓ Hourly data retrieved successfully!")
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Error fetching hourly data: {e}")
            return None
    
    def convert_to_dataframe(self, api_response):
        """
        Convert NASA POWER API response to a pandas DataFrame
        
        Parameters:
        -----------
        api_response : dict
            Response from NASA POWER API
        
        Returns:
        --------
        pd.DataFrame : Weather data in tabular format
        """
        if not api_response or 'properties' not in api_response:
            print("Invalid API response")
            return None
        
        try:
            parameters = api_response['properties']['parameter']
            
            # Create DataFrame from parameters
            df = pd.DataFrame(parameters)
            
            # Convert index to datetime
            df.index = pd.to_datetime(df.index, format='%Y%m%d')
            df.index.name = 'Date'
            
            # Rename columns for readability
            column_mapping = {
                'T2M': 'Temperature_2m_C',
                'T2M_MAX': 'Temperature_Max_C',
                'T2M_MIN': 'Temperature_Min_C',
                'RH2M': 'Relative_Humidity_%',
                'PRECTOTCORR': 'Precipitation_mm',
                'WS2M': 'Wind_Speed_m/s',
                'PS': 'Surface_Pressure_kPa',
                'ALLSKY_SFC_SW_DWN': 'Solar_Radiation_kWh/m2',
                'WD2M': 'Wind_Direction_deg'
            }
            
            df.rename(columns=column_mapping, inplace=True)
            
            print(f"✓ DataFrame created with {len(df)} records")
            return df
            
        except Exception as e:
            print(f"✗ Error converting to DataFrame: {e}")
            return None
    
    def save_to_csv(self, df, filename):
        """Save DataFrame to CSV file"""
        try:
            df.to_csv(filename)
            print(f"✓ Data saved to {filename}")
        except Exception as e:
            print(f"✗ Error saving to CSV: {e}")
    
    def save_to_json(self, data, filename):
        """Save raw API response to JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"✓ Data saved to {filename}")
        except Exception as e:
            print(f"✗ Error saving to JSON: {e}")


# Example usage functions
def example_daily_data():
    """Example: Fetch daily weather data for Dhaka"""
    api = NASAPowerAPI()
    
    # Dhaka coordinates
    latitude = 23.8103
    longitude = 90.4125
    
    # Date range (last 30 days as example)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Format dates
    start_str = start_date.strftime('%Y%m%d')
    end_str = end_date.strftime('%Y%m%d')
    
    # Fetch data
    data = api.get_daily_data(
        latitude=latitude,
        longitude=longitude,
        start_date=start_str,
        end_date=end_str
    )
    
    if data:
        # Convert to DataFrame
        df = api.convert_to_dataframe(data)
        
        if df is not None:
            print("\nData Preview:")
            print(df.head())
            print("\nData Summary:")
            print(df.describe())
            
            # Save to files
            api.save_to_csv(df, 'dhaka_weather_daily.csv')
            api.save_to_json(data, 'dhaka_weather_daily.json')
            
            return df
    
    return None


def example_multiple_locations():
    """Example: Fetch data for multiple locations in Bangladesh"""
    api = NASAPowerAPI()
    
    # Date range
    start_date = '20240101'
    end_date = '20241231'
    
    all_data = {}
    
    for city, coords in api.BANGLADESH_LOCATIONS.items():
        print(f"\n{'='*50}")
        print(f"Fetching data for {city}")
        print(f"{'='*50}")
        
        data = api.get_daily_data(
            latitude=coords['lat'],
            longitude=coords['lon'],
            start_date=start_date,
            end_date=end_date
        )
        
        if data:
            df = api.convert_to_dataframe(data)
            if df is not None:
                all_data[city] = df
                api.save_to_csv(df, f'{city.lower()}_weather_2024.csv')
        
        # Be respectful to the API - add a small delay between requests
        time.sleep(1)
    
    return all_data


def example_specific_parameters():
    """Example: Fetch only specific parameters"""
    api = NASAPowerAPI()
    
    # Only temperature and rainfall
    parameters = ['T2M', 'PRECTOTCORR']
    
    data = api.get_daily_data(
        latitude=23.8103,  # Dhaka
        longitude=90.4125,
        start_date='20200101',
        end_date='20201231',
        parameters=parameters
    )
    
    if data:
        df = api.convert_to_dataframe(data)
        return df
    
    return None


if __name__ == "__main__":
    print("NASA POWER API - Weather Data Extraction")
    print("=" * 50)
    
    # Run example
    example_daily_data()
    
    # Uncomment to run other examples:
    # example_multiple_locations()
    # example_specific_parameters()
