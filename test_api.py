"""
Test NASA POWER API to verify correct endpoint format
"""
import requests

# Test different API formats
print("Testing NASA POWER API formats...\n")

# Format 1: Old style
url1 = "https://power.larc.nasa.gov/api/temporal/daily/ag/T2M/json"
params1 = {
    'start': '20230101',
    'end': '20230105',
    'latitude': 23.8103,
    'longitude': 90.4125
}

print("Testing Format 1 (old style):")
print(f"URL: {url1}")
try:
    response = requests.get(url1, params=params1, timeout=10)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("✓ SUCCESS!")
        data = response.json()
        print(f"Keys: {list(data.keys())}")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "="*60 + "\n")

# Format 2: New query parameter style
url2 = "https://power.larc.nasa.gov/api/temporal/daily"
params2 = {
    'parameters': 'T2M',
    'community': 'ag',
    'start': '20230101',
    'end': '20230105',
    'latitude': 23.8103,
    'longitude': 90.4125,
    'format': 'json'
}

print("Testing Format 2 (new query style):")
print(f"URL: {url2}")
try:
    response = requests.get(url2, params=params2, timeout=10)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("✓ SUCCESS!")
        data = response.json()
        print(f"Keys: {list(data.keys())}")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "="*60 + "\n")

# Format 3: Simplified with direct parameters
url3 = "https://power.larc.nasa.gov/api/temporal/daily/point"
params3 = {
    'parameters': 'T2M,RH2M,PRECTOTCORR',
    'community': 'ag',
    'start': '20230101',
    'end': '20230105',
    'latitude': 23.8103,
    'longitude': 90.4125,
    'format': 'json'
}

print("Testing Format 3 (point endpoint):")
print(f"URL: {url3}")
try:
    response = requests.get(url3, params=params3, timeout=10)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("✓ SUCCESS!")
        data = response.json()
        print(f"Keys: {list(data.keys())}")
        if 'properties' in data:
            print(f"Parameters available: {list(data['properties']['parameter'].keys())}")
except Exception as e:
    print(f"✗ Error: {e}")
