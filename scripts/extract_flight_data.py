import serpapi
import pandas as pd
import json
import time
import os
import sys
from datetime import datetime 
from serpapi import GoogleSearch
from dotenv import load_dotenv

# ------------------------------
# Environment Setup
# ------------------------------

# Load API from .env
load_dotenv()
api = os.environ.get("SERPAPI_KEY")

# ------------------------------
# Search Parameters
# ------------------------------

# Target routes
destinations = ["BKK", "NRT", "LHR", "MEL"]

# Outbound travel dates
outbound_dates = ["2026-06-30", "2026-08-03"]

# Search date / extracted date
extracted_date_str = datetime.now().strftime("%Y-%m-%d")

# ===============================

def extract_flight_data():
    if not api: 
        print("Critical error: API key is not found in environment variables. Check your .env file.")
        return
        
    # Loop through travel dates independently 
    for outbound_date in outbound_dates:
        date_batch_responses = {}
        filename = f"serpapi_response_{outbound_date}_search{extracted_date_str}.json"
    
        # Loop through destinations 
        for dest in destinations:
    
            #Building vice-versa bidirectional segments
            sectors = [
                {"from": "SIN", "to": dest, "direction": "outbound"},
                {"from": dest, "to": "SIN", "direction": "inbound"}
            ]
    
            # Execute outbound followed by return leg
            for sector in sectors:
                dep = sector["from"]
                arr = sector["to"]
                direction_flag = sector["direction"]
                route_label = f"{dep}-{arr}_{outbound_date}"
    
                # Building the parameters
                params = {
                    "engine": "google_flights",
                    "departure_id": dep,
                    "arrival_id": arr,
                    "currency": "SGD",
                    "type": "2",
                    "outbound_date": outbound_date,
                    "gl":"sg",
                    "hl":"en",
                    "sort_by":"2",
                    "stops":"1",
                    "api_key":api
                }
    
                try:
                    search = GoogleSearch(params)
                    results = search.get_dict()
    
                    if "error" in results: 
                        date_batch_responses[route_label] = {"status": "error", "message": results["error"]}
                    else: 
                        best_count = len(results.get("best_flights", []))
                        other_count = len(results.get("other_flights", []))
    
                        # Store results under its route market index key
                        date_batch_responses[route_label] = results
    
                except Exception as e: 
                    print(f"Connection breakdown for {route_label}: {e}")
                    date_batch_responses[route_label] = {"status": "failed", "message": str(e)}
    
                # 2-second delay barrier to regulate request volume saefty
                time.sleep(2)

        # Exporting files to JSON
        try:
            with open(filename, "w", encoding="utf-8") as json_file:
                json.dump(date_batch_responses, json_file, indent=4, ensure_ascii=False)
    
        except Exception as file_err:
            print(f"Critical file saving failure on: {file_err}")

def main():
    start_time = time.time()
    log_dir = "flight_log"
    os.makedirs(log_dir, exist_ok=True)

    log_filename = f"flight_log_{extracted_date_str}.txt"
    log_path = os.path.join(log_dir, log_filename)

    log_file = open(log_path, "a", encoding = "utf-8")
    original_stdout = sys.stdout
    sys.stdout = log_file 

    # Logging content
    print(f"Extraction Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    extract_flight_data()

    elapsed = round(time.time() - start_time,2)
    print(f"Extraction sequence complete. Job closed in {elapsed} seconds.")
    
    sys.stdout = original_stdout
    log_file.close()

    print(f"API sweep complete. Files are captured in: {log_path}")

if __name__ == "__main__":
    main()