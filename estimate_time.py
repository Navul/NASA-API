"""
Estimate time to extract 10,000 data samples from NASA POWER API
"""
import time
from datetime import datetime, timedelta

def estimate_extraction_time():
    """
    Calculate estimated time for different scenarios
    """
    
    print("=" * 70)
    print("⏱️  NASA POWER API - Time Estimation for 10,000 Data Samples")
    print("=" * 70)
    
    # API response time (based on testing)
    avg_api_response_time = 2.0  # seconds per request (conservative estimate)
    
    print("\n📊 SCENARIO 1: Single Location, 10,000 Days (~27 years)")
    print("-" * 70)
    days_needed = 10000
    years = days_needed / 365.25
    
    # Single API call can fetch multiple years at once
    requests_needed = 1  # NASA POWER can fetch all data in one request
    total_time_1 = requests_needed * avg_api_response_time
    
    print(f"  Data Points: {days_needed:,} days ({years:.1f} years)")
    print(f"  API Requests: {requests_needed}")
    print(f"  Estimated Time: {total_time_1:.1f} seconds (~{total_time_1/60:.1f} minutes)")
    print(f"  ✅ Very Fast! (Single API call)")
    
    print("\n" + "=" * 70)
    print("📊 SCENARIO 2: Multiple Locations, Daily Data")
    print("-" * 70)
    
    # If you need 10,000 samples across multiple locations
    locations = [1, 5, 10, 20, 50, 100]
    
    for num_locations in locations:
        samples_per_location = 10000 // num_locations
        days_per_location = samples_per_location
        
        # Add 1 second delay between requests (being respectful to API)
        delay_between_requests = 1.0
        total_time = (num_locations * avg_api_response_time) + ((num_locations - 1) * delay_between_requests)
        
        print(f"\n  {num_locations} locations × {samples_per_location} days each:")
        print(f"    API Requests: {num_locations}")
        print(f"    Estimated Time: {total_time:.1f}s (~{total_time/60:.1f} min)")
    
    print("\n" + "=" * 70)
    print("📊 SCENARIO 3: Grid of Coordinates (Spatial Coverage)")
    print("-" * 70)
    
    # Grid covering Bangladesh
    grid_sizes = [
        (5, 5, "5×5 grid (25 points)"),
        (10, 10, "10×10 grid (100 points)"),
        (20, 20, "20×20 grid (400 points)"),
    ]
    
    for rows, cols, description in grid_sizes:
        total_points = rows * cols
        days_per_point = 10000 // total_points if total_points > 0 else 0
        
        if days_per_point > 0:
            delay_between_requests = 1.0
            total_time = (total_points * avg_api_response_time) + ((total_points - 1) * delay_between_requests)
            
            print(f"\n  {description}:")
            print(f"    Total Points: {total_points}")
            print(f"    Days per Point: {days_per_point}")
            print(f"    Total Samples: {total_points * days_per_point:,}")
            print(f"    Estimated Time: {total_time:.1f}s (~{total_time/60:.1f} min or ~{total_time/3600:.2f} hours)")
    
    print("\n" + "=" * 70)
    print("📊 SCENARIO 4: Hourly Data (More Granular)")
    print("-" * 70)
    
    # Hourly data gives 24 samples per day
    hourly_samples = 10000
    days_needed_hourly = hourly_samples / 24
    
    # Hourly data might need to be split into smaller chunks
    # NASA POWER limits hourly requests to shorter periods
    max_days_per_request = 365  # Typical limit for hourly data
    requests_needed_hourly = int(days_needed_hourly / max_days_per_request) + 1
    
    delay_between_requests = 1.0
    total_time_hourly = (requests_needed_hourly * avg_api_response_time) + ((requests_needed_hourly - 1) * delay_between_requests)
    
    print(f"  Hourly Samples: {hourly_samples:,}")
    print(f"  Days Needed: {days_needed_hourly:.1f}")
    print(f"  API Requests: {requests_needed_hourly}")
    print(f"  Estimated Time: {total_time_hourly:.1f}s (~{total_time_hourly/60:.1f} min)")
    
    print("\n" + "=" * 70)
    print("⚡ REALISTIC ESTIMATES")
    print("=" * 70)
    
    scenarios = [
        {
            'name': 'Best Case (1 location, daily)',
            'requests': 1,
            'time_seconds': 2
        },
        {
            'name': 'Common Case (10 locations)',
            'requests': 10,
            'time_seconds': 29
        },
        {
            'name': 'Large Dataset (100 locations)',
            'requests': 100,
            'time_seconds': 299
        },
        {
            'name': 'Very Large (500 locations)',
            'requests': 500,
            'time_seconds': 1499
        }
    ]
    
    for scenario in scenarios:
        time_sec = scenario['time_seconds']
        time_min = time_sec / 60
        time_hour = time_sec / 3600
        
        print(f"\n  🔹 {scenario['name']}:")
        print(f"      Requests: {scenario['requests']}")
        
        if time_sec < 60:
            print(f"      Time: {time_sec} seconds")
        elif time_min < 60:
            print(f"      Time: {time_min:.1f} minutes")
        else:
            print(f"      Time: {time_hour:.2f} hours ({time_min:.0f} minutes)")
    
    print("\n" + "=" * 70)
    print("💡 KEY FACTORS AFFECTING TIME")
    print("=" * 70)
    print("""
  1. ✅ API Response Time: ~1-3 seconds per request
  2. ✅ Respectful Delays: 1 second between requests (recommended)
  3. ✅ Network Speed: Your internet connection
  4. ✅ Data Processing: Converting to DataFrame (~instant)
  5. ✅ File Writing: Saving to CSV (~instant for <1M rows)
  
  Most bottleneck = Number of API requests needed
  
  """)
    
    print("=" * 70)
    print("🎯 RECOMMENDATIONS")
    print("=" * 70)
    print("""
  For 10,000 samples:
  
  ➡️  Single Location: 2-5 seconds total
      (One API call for 27 years of daily data)
  
  ➡️  10 Locations: ~30 seconds
      (1,000 days each)
  
  ➡️  100 Locations: ~5 minutes
      (100 days each)
  
  ➡️  Spatial Grid (25 points): ~1-2 minutes
      (400 days per point)
  
  The NASA POWER API is VERY EFFICIENT because:
  - ✅ One request can fetch years of data
  - ✅ No pagination needed
  - ✅ Fast response times
  - ✅ No rate limits (just be respectful)
  """)
    
    print("=" * 70)


if __name__ == "__main__":
    estimate_extraction_time()
