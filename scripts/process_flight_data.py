import json
import os
import shutil
import time
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

try:
    import holidays
except ImportError:
    raise ImportError("The 'holidays' package is missing. Please run 'pip install holidays' before executing.")

# ------------------------------
# Environment Setup
# ------------------------------

source_dir = './'
serpapi_csv = 'serpapi_response.csv'
feature_csv = 'feature_batch.csv'
dataset_csv = 'dataset.csv'
LCC_xlsx = 'LCC List.xlsx'

today_str = datetime.now().strftime('%Y-%m-%d')

# Archiving schema paths
processed_json_dir = './serpapi_response/Processed serpapi_response'
serpapi_archive_dir = './serpapi_response/serpapi_response_archive'
feature_archive_dir = './feature_archive'
dataset_archive_dir = './dataset_archive'

def initialise_environment():
    """Dynamically ensures all operational and archival directories exist.""" 
    directories = [
        processed_json_dir,
        serpapi_archive_dir,
        feature_archive_dir,
        dataset_archive_dir
    ]
    for directory in directories: 
        os.makedirs(directory, exist_ok=True) 

# ------------------------------
# SerpApi Batch Processing
# ------------------------------

def process_raw_json_batch():
    json_files = [
        os.path.join(source_dir, file)
        for file in os.listdir(source_dir)
        if file.endswith(".json")
    ] 

    print(f"Step 1: Processing SerpApi JSON batch")
    print(f"Found {len(json_files)} files to process.")

    if not json_files:
        print("No new raw JSON files found.")
        return []

    # Archive the old SerpApi response, if it exists
    if os.path.exists(serpapi_csv):
        archive_file_name = f"serpapi_response_{today_str}.csv"
        archive_path = os.path.join(serpapi_archive_dir, archive_file_name)
        shutil.move(serpapi_csv, archive_path)
        print(f"Successfully archived SerpApi Response file to: {archive_path}")

    all_flattened_data = []

    for file in json_files: 
        processing_successful = False
        try: 
            with open(file, "r", encoding = "utf-8") as f:
                batch_data = json.load(f)

            for route_label, data in batch_data.items():
                if not isinstance(data, dict):
                    print(f"Skipping {route_label}: Data is not a dictionary.")
                    continue
                if "search_parameters" not in data: 
                    print(f"Skipping {route_label}: Missing 'search_parameters'.")
                    continue

                search_metadata = data.get("search_metadata", {})
                search_parameters = data.get("search_parameters", {})
        
                date_str = search_metadata.get("processed_at", "")[:10]
                departure_str = search_parameters.get("outbound_date", "")
        
                date = datetime.strptime(date_str, "%Y-%m-%d")
                departure_date = datetime.strptime(departure_str, "%Y-%m-%d")

                # Time-based features
                days_to_departure = (departure_date - date).days
                day_of_week = departure_date.weekday() 
                day_name = departure_date.strftime("%A")
                is_weekend = day_of_week in [4, 5, 6]
        
                # Booking Window logic
                if days_to_departure <= 0:
                    booking_window = "0 days"
                else: 
                    lower_bound = ((days_to_departure - 1) // 14) * 14 + 1
                    upper_bound = lower_bound + 13
                    booking_window = f"{lower_bound}-{upper_bound} days"

                # Label features
                departure_airport = search_parameters.get("departure_id")
                arrival_airport = search_parameters.get("arrival_id")
                other_airport = arrival_airport if departure_airport == "SIN" else departure_airport
        
                all_itineraries = data.get("best_flights", []) + data.get("other_flights", [])
        
                for flight in all_itineraries: 
                    price = flight.get("price")
                    if not price:
                        continue
        
                    flights_segments = flight.get("flights", [])
                    first_segment = flights_segments[0] if flights_segments else {}
                    
                    airline = first_segment.get("airline", "Unknown Airline")
                    raw_flight_num = first_segment.get("flight_number", "")
                    airline_code = raw_flight_num[:2] if raw_flight_num else "NIL"

                    row_record = {
                        "date": date_str,
                        "route": f"{departure_airport}-{arrival_airport}",
                        "departure_date": departure_str,
                        "airline": airline,
                        "airline_code": airline_code,
                        "price": float(price),
                        "days_to_departure": days_to_departure,
                        "day_of_week": day_of_week,
                        "day_name": day_name,
                        "is_weekend": is_weekend,
                        "departure_airport": departure_airport,
                        "out_inbound": 1 if departure_airport == "SIN" else 2,
                        "other_airport": other_airport,
                        "data_source": "api",
                        "booking_window": booking_window
                    }
                    all_flattened_data.append(row_record)
                
                processing_successful = True

        except Exception as e:
            print(f"Error processing file {file}: {e}")

        # Archive processed raw JSON file
        if processing_successful: 
            file_name = os.path.basename(file)
            dest_path = os.path.join(processed_json_dir, file_name)
            shutil.move(file, dest_path)
            print(f"Moved processed file to archive: {dest_path}")
        else: 
            print(f"WARNING: {file} left in source directory due to processing failure.")

    if all_flattened_data:
        flat_df = pd.DataFrame(all_flattened_data)
        flat_df.to_csv(serpapi_csv, index=False)
        print(f"Serpapi cleaning complete. New batch saved as: {serpapi_csv}\n")
        return flat_df
    else:
        print("No new data parsed this execution run.\n")
        return []

# ------------------------------
# Feature Engineering
# ------------------------------

def generate_holiday_lookup_set(country_iso, years_range, buffer_days=2):
    country_hols = holidays.country_holidays(country_iso, years=years_range)
    expanded_set = set()

    for h_date in country_hols.keys():
        core_window = [h_date + timedelta(days=i) for i in range(-buffer_days, buffer_days + 1)]
        for date_item in core_window:
            expanded_set.add(date_item)
            weekday = date_item.weekday()

            # If holiday falls on Saturday, include Friday
            if weekday == 5:
                expanded_set.add(date_item - timedelta(days=1))
            # If holiday falls on Sunday, include Monday
            elif weekday == 6:
                expanded_set.add(date_item + timedelta(days=1))
            # If holiday falls on Monday, include Friday
            elif weekday == 0:
                expanded_set.add(date_item - timedelta(days=3))
    return expanded_set

def apply_feature_enrichment(df):
    print(f"Step 2: Applying Feature Engineering")
    if isinstance(df, list) or df.empty:
        print("No new batch data available to enrich.")
        return None

    # Archive the old feature batch data, if it exists
    if os.path.exists(feature_csv):
        archive_file_name = f"feature_batch_{today_str}.csv"
        archive_path = os.path.join(feature_archive_dir, archive_file_name)
        shutil.move(feature_csv, archive_path)
        print(f"Successfully archived old feature batch to: {archive_path}")

    df['departure_date'] = pd.to_datetime(df['departure_date'])
    start_year = df['departure_date'].min().year
    end_year = df['departure_date'].max().year 
    years_range = list(range(start_year, end_year + 1))

    # 1. Map Public Holidays
    airport_to_country = {'LHR': 'GB', 'NRT': 'JP', 'BKK': 'TH', 'MEL': 'AU', 'SIN': 'SG'}
    sg_bridged_set = generate_holiday_lookup_set('SG', years_range)
    df['is_holiday_sin'] = df['departure_date'].dt.date.isin(sg_bridged_set).astype(int)

    dest_maps = {code: generate_holiday_lookup_set(iso, years_range) for code, iso in airport_to_country.items() if code != 'SIN'}

    def dest_holiday(row):
        dest = row['other_airport']
        if dest not in dest_maps:
            return 0
        return 1 if row['departure_date'].date() in dest_maps[dest] else 0

    df['is_holiday_other'] = df.apply(dest_holiday, axis=1)
    print("Public holidays feature engineering completed.")

    # 2. Map (Singapore) School Holidays
    def check_school_holiday(row):
        flight_date = row['departure_date'].date()
        current_year = flight_date.year
        month = flight_date.month

        if month in [6, 12]:
            return 1

        for target_month in [6, 12]:
            day1 = datetime(current_year, target_month, 1).date()
            day1_weekday = day1.weekday() # 5 = Sat; 6 = Sun
            if day1_weekday == 5 and flight_date == (day1 - timedelta(days=1)):
                return 1
            if day1_weekday == 6 and flight_date == (day1 - timedelta(days=2)):
                return 1
        return 0

    df['is_sch_holiday'] = df.apply(check_school_holiday, axis=1)
    print("School holidays feature engineering completed.")

    # 3. Carrier Classification (LCC vs FSC)
    if os.path.exists(LCC_xlsx):
        df_lcc = pd.read_excel(LCC_xlsx)
        lcc_col_name = 'airline_code' if 'airline_code' in df_lcc.columns else df_lcc.columns[1]
        lcc_set = set(df_lcc[lcc_col_name].astype(str).str.strip().str.upper())
        df['is_lcc'] = np.where(df['airline_code'].isin(lcc_set), 1, 0)
        print(f"Carrier classification applied successfully using mapping index.")
    else:
        print(f"WARNING: '{LCC_xlsx}' not found. Defaulting 'is_lcc' flags to 0.")
        df['is_lcc'] = 0

    df.to_csv(feature_csv, index=False)
    print(f"Feature enrichment complete. Consolidated batch saved to: {feature_csv}\n")
    return df

# ------------------------------
# Integration
# ------------------------------

def integrate_and_finalize_dataset(batch_df):
    """Merges processed batch features with historical master data, enforces integrity, and runs automated QA."""
    print(f"Step 3: Master Dataset Assembly & Validation")
    if batch_df is None or batch_df.empty:
        print("Pipeline sequence halted: No updated features available for integration.")
        return

    existing_df = pd.DataFrame()
    
    # Check-archive existing production dataset asset
    if os.path.exists(dataset_csv):
        try:
            existing_df = pd.read_csv(dataset_csv)
            print(f"Loaded {len(existing_df)} existing historical records from {dataset_csv}")
            
            archive_file_name = f"dataset_{today_str}.csv"
            archive_path = os.path.join(dataset_archive_dir, archive_file_name)
            shutil.copy(dataset_csv, archive_path)
            print(f"Successfully archived master backup copy to: {archive_path}")
        except Exception as e:
            print(f"Warning: Issue reading existing {dataset_csv} ({e}). Starting fresh.")

    # Standardize types before concatenation to avoid warning boundaries
    if not existing_df.empty:
        existing_df['departure_date'] = pd.to_datetime(existing_df['departure_date'], dayfirst=True, format='mixed', errors='coerce')
        batch_df['departure_date'] = pd.to_datetime(batch_df['departure_date'], dayfirst=True, format='mixed', errors='coerce')
        combined_df = pd.concat([existing_df, batch_df], axis=0, ignore_index=True)
    else:
        combined_df = batch_df

    # Deduplication Engine
    dedup_keys = ['date', 'route', 'departure_date', 'airline', 'price']
    available_keys = [key for key in dedup_keys if key in combined_df.columns]
    
    initial_count = len(combined_df)
    combined_df = combined_df.drop_duplicates(subset=available_keys, keep='first')
    dropped_rows = initial_count - len(combined_df)
    
    if dropped_rows > 0:
        print(f"Data Integrity Enforcement: Removed {dropped_rows} redundant record variants.")

    # Save finalized output file
    combined_df.to_csv(dataset_csv, index=False)
    print(f"Production Master Database committed successfully at: {dataset_csv}\n")

    # Audit and Quality Assurance Check
    print("--- Automated Quality Assurance Log ---")
    qa_columns = [
        'route', 'is_weekend', 'departure_airport', 'out_inbound',
        'other_airport', 'data_source', 'booking_window', 'airline',
        'airline_code', 'is_lcc', 'is_holiday_sin', 'is_holiday_other', 'is_sch_holiday'
    ]
    for col in qa_columns:
        if col in combined_df.columns:
            unique_vals = list(combined_df[col].dropna().unique())
            try:
                unique_vals = sorted(unique_vals)
            except TypeError:
                pass
            print(f"  Column [ {col:18} ] -> Distinct Entries ({len(unique_vals)}): {unique_vals}")

# ------------------------------
# Main Run
# ------------------------------

def main():
    start_time = time.time()
    log_dir = "process_log"
    os.makedirs(log_dir, exist_ok=True)

    log_filename = f"process_log_{today_str}.txt"
    log_path = os.path.join(log_dir, log_filename)

    log_file = open(log_path, "a", encoding = "utf-8")
    original_stdout = sys.stdout
    sys.stdout = log_file

    try: 
        print("=" * 60)
        print(f"Execution log initialised: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        print("Starting Automated Flight Data Integration Pipeline")

        # Run the setup steps in sequential dependencies
        initialise_environment()
        raw_cleaned_batch = process_raw_json_batch()
        enriched_feature_batch = apply_feature_enrichment(raw_cleaned_batch)
        integrate_and_finalize_dataset(enriched_feature_batch)

        elapsed = round(time.time() - start_time, 2)
        print(f"Execution Finished Successfully! Master Data Ready. Total Time Elapsed: {elapsed} seconds.")

    except Exception as e:
        # Audit Trail: If code crashes, log the failure point
        print(f"Failure at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Error Diagnostic Message: {e}")
        raise e

    finally:
        sys.stdout = original_stdout
        log_file.close()

    print(f"Processing complete. Files are captured in: {log_path}")

if __name__ == "__main__":
    main()