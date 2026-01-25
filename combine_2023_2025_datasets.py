"""
Combine Lightning Prediction Datasets (2023-2025) for All Districts
This script combines tabular datasets from 2023 to 2025 for all districts
into a single CSV file for lightning prediction analysis.
"""

import pandas as pd
import os
from pathlib import Path

def combine_datasets():
    # Define the base directory
    base_dir = Path(r"d:\Study mat\THESIS\NASA API\lightning_prediction_dataset")
    
    # Define the districts
    districts = [
        'barisal', 'chittagong', 'dhaka', 'khulna',
        'mymensingh', 'rajshahi', 'rangpur', 'sylhet'
    ]
    
    # Define the years to combine
    years = [2023, 2024, 2025]
    
    # List to store all dataframes
    all_dataframes = []
    
    # Statistics tracking
    stats = {
        'files_loaded': 0,
        'total_rows': 0,
        'rows_per_district': {},
        'rows_per_year': {}
    }
    
    print("=" * 60)
    print("Combining Lightning Prediction Datasets (2023-2025)")
    print("=" * 60)
    print()
    
    # Iterate through each district and year
    for district in districts:
        district_rows = 0
        for year in years:
            filename = f"{district}_{year}_lightning_dataset.csv"
            filepath = base_dir / filename
            
            if filepath.exists():
                try:
                    # Read the CSV file
                    df = pd.read_csv(filepath)
                    
                    # Add Year column if not present (for filtering later)
                    if 'Year' not in df.columns:
                        df['Year'] = year
                    
                    # Add District column for clarity (capitalize first letter)
                    if 'District' not in df.columns:
                        df['District'] = district.capitalize()
                    
                    all_dataframes.append(df)
                    
                    rows = len(df)
                    stats['files_loaded'] += 1
                    stats['total_rows'] += rows
                    district_rows += rows
                    
                    # Track rows per year
                    if year not in stats['rows_per_year']:
                        stats['rows_per_year'][year] = 0
                    stats['rows_per_year'][year] += rows
                    
                    print(f"✓ Loaded: {filename} ({rows:,} rows)")
                    
                except Exception as e:
                    print(f"✗ Error loading {filename}: {e}")
            else:
                print(f"✗ File not found: {filename}")
        
        stats['rows_per_district'][district.capitalize()] = district_rows
    
    print()
    print("=" * 60)
    print("Combining all datasets...")
    print("=" * 60)
    
    if all_dataframes:
        # Combine all dataframes
        combined_df = pd.concat(all_dataframes, ignore_index=True)
        
        # Sort by DateTime, District for better organization
        if 'DateTime' in combined_df.columns:
            combined_df = combined_df.sort_values(['District', 'DateTime'])
        
        # Reset index
        combined_df = combined_df.reset_index(drop=True)
        
        # Reorder columns to put District and Year at the beginning after DateTime
        cols = combined_df.columns.tolist()
        
        # Define preferred column order
        priority_cols = ['DateTime', 'Date', 'Time', 'Year', 'District', 'Location', 'Latitude', 'Longitude']
        
        # Build new column order
        new_cols = []
        for col in priority_cols:
            if col in cols:
                new_cols.append(col)
                cols.remove(col)
        new_cols.extend(cols)  # Add remaining columns
        
        combined_df = combined_df[new_cols]
        
        # Save the combined dataset
        output_filename = "combined_2023_2025_all_districts.csv"
        output_path = base_dir / output_filename
        
        combined_df.to_csv(output_path, index=False)
        
        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"\n✓ Successfully combined {stats['files_loaded']} files")
        print(f"✓ Total rows: {stats['total_rows']:,}")
        print(f"✓ Total columns: {len(combined_df.columns)}")
        print(f"\n✓ Output saved to: {output_path}")
        
        print("\n--- Rows per District ---")
        for district, rows in sorted(stats['rows_per_district'].items()):
            print(f"  {district}: {rows:,} rows")
        
        print("\n--- Rows per Year ---")
        for year, rows in sorted(stats['rows_per_year'].items()):
            print(f"  {year}: {rows:,} rows")
        
        print("\n--- Column Names ---")
        print(", ".join(combined_df.columns.tolist()))
        
        print("\n--- Dataset Preview (first 5 rows) ---")
        print(combined_df.head().to_string())
        
        # Check for any missing values
        missing = combined_df.isnull().sum()
        missing_cols = missing[missing > 0]
        if len(missing_cols) > 0:
            print("\n--- Columns with Missing Values ---")
            for col, count in missing_cols.items():
                print(f"  {col}: {count:,} missing values")
        else:
            print("\n✓ No missing values detected in any column")
        
        return combined_df
    else:
        print("✗ No data files found to combine!")
        return None

if __name__ == "__main__":
    combined_df = combine_datasets()
