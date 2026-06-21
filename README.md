# Taking Turbulence out of Ticket Pricing for the Singapore Traveller
An end-to-end data pipeline and machine learning implementation designed to decode dynamic fare volatility, optimise international flight purchasing windows, and deliver actionable "Buy vs. Wait" decision support for Singapore-hub air travellers.

## The Problem
Every traveller knows the frustration of seeing a ticket price jumping overnight. Currently, there is a fundamental information trap. Booking platforms only show today's price with little context on whether that price is a good deal or a temporary spike. Airlines rely on that ambiguity to trigger panic-buying. Our goal is to break that cycle, allowing travellers to make informative decisions instead of emotional ones. 

## Target Audience
1. **Flexible leisure travellers:**
Users seeking value who possess the flexibility to optimise booking dats
2. **Budget-conscious consumers:**
Individuals who require high-precision data to navigate the dynamic pricing and secure low fares.

## Project Scope
By gathering continuous market indicators and building a dedicated machine learning pipeline, this system isolates predictable timeline behaviors over a 90-day booking horizon (critical period where airlines dynamically restrict lower-tier fare classes). 

### Flight Routes
It maps out localised fare trajectories for four vital bidirectional routes originating from or returning to Singapore:
* SIN $\leftrightarrow$ Bangkok (BKK)
* SIN $\leftrightarrow$ Tokyo (NRT)
* SIN $\leftrightarrow$ London (LHR)
* SIN $\leftrightarrow$ Melbourne (MEL)

### Carrier Segmentation
The model tracks and segments data across the full fare distribution spectrum:
* Low-Cost Carriers (LCC)
* Full-Service Carriers (FSC)

## The Solution
The engine trains a robust Random Forest machine learning model on fare prices behind an interactive, user-facing Streamlit web dashboard operating across two high-value modes:
* **Predictive Mode (What will it cost?):** A point-in-time lookup allowing travelers to input a departure date and search window to evaluate if a live flight price matches the expected market baseline.
* **Prescriptive Mode (When should I buy?):** An optimization timeline sweep that programmatically checks future booking windows to recommend the absolute minimum price point on the fare curve.

### Random Forest Model Performance and Justification
Milestones achieved: 
* **Holdout Mean Average Percentage Error (MAPE):** $19.3\%$
* **Holdout Variance Explained ($R^{2}$ Score):** $85.3\%$
* **Holdout Root Mean Square Error (RMSE):** $\$294.75$

Analytical justifications: 
* MAPE: Because our mixed-route dataset combines cheap short-hauls (BKK) with expensive long-hauls (LHR), absolute dollar metrics like MAE are mathematically skewed upward by premium ticket costs. Tracking MAPE provides an honest, scale-independent validation across all distance brackets.
* RMSE: Airfares are prone to sudden, severe pricing cliffs (such as last-minute 1–14 day close-in purchase surges). Because RMSE squares the residuals before averaging them, it heavily penalises massive, catastrophic misses. Prioritising a low RMSE ensures the model actively protects travellers from budget-destroying pricing spikes.

### Feature Dictionary
To shift from raw price collection to predictive modeling, the dataset incorporates engineered categorical and temporal layers:
* **Time-Based Features (Temporal):** 
    * `booking_window`: A timeline interval capturing advance purchase curves
    * `departure_month`: Numeric representation tracking the price snapshot collection day
    * `day_of_week`: Binary flag identifying weekend price fluctuations
    * `is_weekend`: Calendar month capturing broader annual seasonality trends
* **Label Features (Categorical Segments):** 
    * `route`: One-way directional sectors setting baseline pricing coordinates
    * `is_lcc`: Categorical indicator isolating Low-Cost Carriers from Full-Service Carriers
* **Demand drivers (External Overlays):** 
    * `is_holiday_sin`: Proximity-buffered flag mapping Singapore Public Holiday demand shocks.
    * `is_holiday_other`: Proximity-buffered flag mapping destination-specific holiday waves.
    * `is_sch_holiday`: Custom flag isolating major Singapore school vacation blocks (June and December)

## The Data Lineage 
The project uses a reliable, repeatable data pipeline to scale up from manual data collection to automated, production-ready extraction.

1. **Phase 1 - Historical Baseline:** Manual extraction of flight prices from Google Flights and using WebPlotDigitizer to establish baseline price-to-departure curves
2. **Phase 2 - Automated Scaling:** Scaling up programmatically using Python requests to query SerpApi
3. **Phase 3 - Feature Enrichment:** Ingestion of external categorical layers
4. **Phase 4 - Storage and Staging:** Data cleaning scripts that fix text formats, unpack raw API data, and safely remove duplicate records while preserving real flight options.

### Repository Directory Structure
```text
├── data/
│   └── dataset - base (2026-05-26).csv      # Cleaned master staging dataset used for model training
|   └── dataset.csv                          # Main dataset
├── notebooks/
│   ├── 01. Manual_Clean_Feature_EDA.ipynb    # Manual dataset transformation
|   ├── 01b. Combine.ipynb                    # Combining manual and api dataset
|   ├── 01b. dataset.csv                      # Output from step 1b
│   ├── 02. Serpapi_Extraction_Loop.ipynb     # API extraction
|   ├── 02a. Sepapi_batch_cleaning.ipynb      # Cleaning API extracted data
|   ├── 2b. Feature_batch_cleaning.ipynb      # Adding features
|   ├── 3. Dataset_batch_cleaning.ipynb       # Adding extracted API data into main dataset
|   ├── 4. EDA on base (2026-05-26).ipynb     # Exploratory data analysis on data till 2026-05-26
|   ├── 4a. Multiple Linear Regression - Base (2026-05-26) v1.ipynb     # Base machine learning model
|   ├── 4b. Random Forest - Base (2026-05-26) v1.ipynb                  # Machine learning model
|   ├── 5. Random Forest - Forward Testing.ipynb
├── scripts/
│   ├── extract_flight_data.py      # API data extraction
│   ├── process_flight_data.py      # Data cleaning
├── slides/
│   ├── Predicting Flight Prices for the Singapore Traveller.pdf  
├── app.py                          # Streamlit web application dashboard execution script
├── requirements.txt                # Project dependencies and environment tracking
├── .gitignore                      # Enforces exclusion of local .env and raw payload dumps
└── README.md                       # Repository documentation front page
```
### Setup & Local Deployment Guide

**Environment Setup:** Clone the repository, create a clean virtual environment, and install the tracked project dependencies:
```
1. Navigate into the project folder 
cd singapore-aviation-pricing

2. Create an isolated folder named 'pricing_env'
python -m venv pricing_env

3. Activate the folder so your terminal uses it
source pricing_env/bin/activate  # On Windows terminal use: pricing_env\Scripts\activate

4. Install all required data libraries safely into this folder
pip install -r requirements.txt
```

**API Credentials Configuration:** Populate the `.env` file with your secure access token.   
``` bash
SERPAPI_KEY=your_secret_serpapi_key_here
```

**Run the Dashboard:** Launch the interactive Streamlit user application:
```  
streamlit run app.py
```