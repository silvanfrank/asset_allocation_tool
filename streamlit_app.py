# streamlit_app.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io  # For exporting plot as image
import itertools  # For generating regime combinations
import requests # Added for API calls
import json     # Added for API calls
import base64   # Added for API calls

# Set page configuration
st.set_page_config(
    page_title="Macroeconomic Regimes and Asset Performance",
    layout="wide",
    page_icon="📈"
)

# Title and Description
st.title("Macroeconomic Regimes and Asset Performance Analysis")
st.write("""
This app visualizes macroeconomic regimes based on S&P 500 and Inflation Rate data, and analyzes asset performance across different regimes.
Select the moving average type and period for both S&P 500 and Inflation Rate independently, define custom thresholds for both derivatives,
and explore how regimes affect asset performance over time.
""")

# --- Helper Functions for API Data Fetching ---

def decode_base64_data(encoded_data):
    """Decodes a list of [base64_date, base64_value] pairs."""
    decoded_list = []
    for date_b64, value_b64 in encoded_data:
        try:
            date_str = base64.b64decode(date_b64).decode('utf-8')
            value_str = base64.b64decode(value_b64).decode('utf-8')
            # Convert value to float, handle potential errors (e.g., non-numeric values)
            value_float = float(value_str)
            decoded_list.append([date_str, value_float])
        except (base64.binascii.Error, UnicodeDecodeError, ValueError) as e:
            # Use print for terminal output instead of st.warning
            print(f"WARNING: Skipping record due to decoding/conversion error: {e} - Date: {date_b64}, Value: {value_b64}")
            # Optionally append with None or np.nan if you want to keep the row
            # date_str = base64.b64decode(date_b64).decode('utf-8', errors='ignore')
            # decoded_list.append([date_str, None])
    return decoded_list

def fetch_and_decode(url, column_name):
    """Fetches data from a URL, decodes it, and returns a Pandas DataFrame."""
    # Use print for terminal output instead of st.info
    print(f"INFO: Fetching data from {url}...")
    try:
        response = requests.get(url, timeout=30) # Added timeout
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        encoded_data = response.json()
        decoded_data = decode_base64_data(encoded_data)

        if not decoded_data: # Handle case where decoding resulted in an empty list
             # Use print for terminal output instead of st.warning
             print(f"WARNING: No valid data decoded from {url}")
             return None

        df = pd.DataFrame(decoded_data, columns=['Date', column_name])
        df['Date'] = pd.to_datetime(df['Date']) # Convert Date column to datetime objects
        df = df.set_index('Date') # Set Date as index for easy merging
        # Use print for terminal output instead of st.success
        print(f"SUCCESS: Successfully fetched and processed data for {column_name}.")
        return df
    except requests.exceptions.Timeout:
        # Use print for terminal output instead of st.error
        print(f"ERROR: Request timed out while fetching data from {url}")
        return None
    except requests.exceptions.RequestException as e:
        # Use print for terminal output instead of st.error
        print(f"ERROR: Error fetching data from {url}: {e}")
        return None
    except json.JSONDecodeError as e:
        # Use print for terminal output instead of st.error
        print(f"ERROR: Error decoding JSON from {url}. Response text: {response.text[:500]}... Error: {e}") # Log part of the response
        return None
    except Exception as e:
        # Use print for terminal output instead of st.error
        print(f"ERROR: An unexpected error occurred while processing {url}: {e}")
        return None

# --- End Helper Functions ---

# Load Data Function
@st.cache_data
def load_data():
    # --- Fetch S&P 500, Inflation, CPI from API ---
    sp500_url = "https://www.longtermtrends.net/data-sp500-since-1871/"
    inflation_url = "https://www.longtermtrends.net/data-inflation/"
    cpi_url = "https://www.longtermtrends.net/data-cpi/"

    # Fetch each dataset (returns df with 'Date' as index or None)
    df_sp500 = fetch_and_decode(sp500_url, 'S&P 500')
    df_inflation = fetch_and_decode(inflation_url, 'Inflation Rate')
    df_cpi = fetch_and_decode(cpi_url, 'CPI')

    # --- Apply preprocessing steps from preprocessing3.ipynb ---
    print("DEBUG: Applying resampling and merging logic (like preprocessing3.ipynb)...")

    # 1. Resample to Business Month End ('BME')
    if df_sp500 is not None:
        print(f"DEBUG: Resampling S&P 500 (initial shape: {df_sp500.shape})")
        df_sp500 = df_sp500.resample('BME').last()
        print(f"DEBUG: Resampled S&P 500 shape: {df_sp500.shape}")
    if df_inflation is not None:
        print(f"DEBUG: Resampling Inflation Rate (initial shape: {df_inflation.shape})")
        df_inflation = df_inflation.resample('BME').last()
        print(f"DEBUG: Resampled Inflation Rate shape: {df_inflation.shape}")
    if df_cpi is not None:
        print(f"DEBUG: Resampling CPI (initial shape: {df_cpi.shape})")
        df_cpi = df_cpi.resample('BME').last()
        print(f"DEBUG: Resampled CPI shape: {df_cpi.shape}")

    # 2. Inner Merge S&P 500 and Inflation Rate
    sp_inflation_df = pd.DataFrame() # Initialize empty df
    if df_sp500 is not None and df_inflation is not None:
        print("DEBUG: Performing INNER merge on resampled S&P 500 and Inflation Rate...")
        sp_inflation_df = pd.merge(df_sp500, df_inflation, left_index=True, right_index=True, how='inner')
        print(f"DEBUG: Inner merge result shape: {sp_inflation_df.shape}")
    elif df_sp500 is not None:
        print("WARN: Inflation data missing, using only S&P 500 data.")
        sp_inflation_df = df_sp500.copy()
        sp_inflation_df['Inflation Rate'] = np.nan # Add missing column
    elif df_inflation is not None:
        print("WARN: S&P 500 data missing, using only Inflation data.")
        sp_inflation_df = df_inflation.copy()
        sp_inflation_df['S&P 500'] = np.nan # Add missing column
    else:
        print("ERROR: Both S&P 500 and Inflation data failed to load or resample.")
        # sp_inflation_df remains empty

    # 3. Left Merge CPI
    if not sp_inflation_df.empty and df_cpi is not None:
        print("DEBUG: Performing LEFT merge with resampled CPI...")
        sp_inflation_df = pd.merge(sp_inflation_df, df_cpi, left_index=True, right_index=True, how='left')
        print(f"DEBUG: Left merge CPI result shape: {sp_inflation_df.shape}")
    elif 'CPI' not in sp_inflation_df.columns:
         print("DEBUG: Adding empty CPI column as CPI data was missing.")
         sp_inflation_df['CPI'] = np.nan

    # 4. Drop rows with NaN in core columns (S&P 500, Inflation Rate) after merge
    if not sp_inflation_df.empty:
        initial_rows = len(sp_inflation_df)
        sp_inflation_df.dropna(subset=['S&P 500', 'Inflation Rate'], inplace=True)
        dropped_rows = initial_rows - len(sp_inflation_df)
        if dropped_rows > 0:
            print(f"DEBUG: Dropped {dropped_rows} rows with NaN in S&P 500 or Inflation Rate after merge.")
        print(f"DEBUG: Shape after NaN drop: {sp_inflation_df.shape}")

    # 5. Reset index to make 'Date' (or 'DateTime') a column
    if not sp_inflation_df.empty:
        sp_inflation_df = sp_inflation_df.reset_index()
        # Ensure the date column is named 'DateTime' as expected downstream
        if 'Date' in sp_inflation_df.columns and 'DateTime' not in sp_inflation_df.columns:
            sp_inflation_df = sp_inflation_df.rename(columns={'Date': 'DateTime'})
        elif 'index' in sp_inflation_df.columns and 'DateTime' not in sp_inflation_df.columns:
             sp_inflation_df = sp_inflation_df.rename(columns={'index': 'DateTime'})
        print("DEBUG: Reset index, 'DateTime' column created.")


    # --- Load Asset time series data from CSV ---
    path = './processed_data/'
    asset_ts_df = pd.DataFrame(columns=['DateTime']) # Default empty
    try:
        asset_ts_df_raw = pd.read_csv(path + 'asset_classes_preprocessed.csv', parse_dates=['DateTime'])
        # Ensure DateTime is parsed correctly
        asset_ts_df_raw['DateTime'] = pd.to_datetime(asset_ts_df_raw['DateTime'], errors='coerce')
        asset_ts_df = asset_ts_df_raw.dropna(subset=['DateTime']).copy()
        print(f"SUCCESS: Asset class data loaded successfully from CSV. Shape: {asset_ts_df.shape}")
    except FileNotFoundError:
        print(f"ERROR: Asset data file not found at {path + 'asset_classes_preprocessed.csv'}")
    except Exception as e:
         print(f"ERROR: Failed to load or parse asset data CSV: {e}")


    # --- Apply >= 1990 Filter AFTER resampling/merging ---
    filter_date = pd.Timestamp('1990-01-01')
    print(f"DEBUG: Applying final filter for dates >= {filter_date}...")

    if not sp_inflation_df.empty:
        if 'DateTime' in sp_inflation_df.columns:
            sp_inflation_df['DateTime'] = pd.to_datetime(sp_inflation_df['DateTime']) # Ensure datetime type
            original_rows_before_1990_filter = len(sp_inflation_df)
            sp_inflation_df = sp_inflation_df[sp_inflation_df['DateTime'] >= filter_date].copy()
            print(f"DEBUG: Filtered resampled/merged S&P/Inflation data >= {filter_date}. Shape: {sp_inflation_df.shape}. (Was {original_rows_before_1990_filter} rows before)")
        else:
             print("ERROR: 'DateTime' column missing before final 1990 filter for S&P/Inflation data.")
             sp_inflation_df = pd.DataFrame() # Make empty if date column is lost

    if not asset_ts_df.empty:
        if 'DateTime' in asset_ts_df.columns:
            asset_ts_df['DateTime'] = pd.to_datetime(asset_ts_df['DateTime']) # Ensure datetime type
            asset_ts_df = asset_ts_df[asset_ts_df['DateTime'] >= filter_date].copy()
            print(f"DEBUG: Filtered Asset data >= {filter_date}. Shape: {asset_ts_df.shape}")
        else:
            print("ERROR: 'DateTime' column missing before final 1990 filter for Asset data.")
            asset_ts_df = pd.DataFrame() # Make empty

    print("DEBUG: load_data function finished.")
    # Return the processed S&P/Inflation/CPI df and the filtered asset df
    return sp_inflation_df.copy(), asset_ts_df.copy()

with st.spinner('Loading data...'):
    sp_inflation_data, asset_ts_data = load_data()
    print("DEBUG: Data loading complete.") # Added debug print

# Check if dataframes are empty after loading attempt
if sp_inflation_data.empty or asset_ts_data.empty:
    # Keep st.error here for frontend visibility of critical failure
    st.error("Failed to load necessary data. Please check the data sources and try again.")
    print("ERROR: Halting execution due to empty dataframes after load.") # Add terminal log
    st.stop() # Stop execution if data loading failed

# Ensure 'DateTime' is datetime type
sp_inflation_data['DateTime'] = pd.to_datetime(sp_inflation_data['DateTime'])
asset_ts_data['DateTime'] = pd.to_datetime(asset_ts_data['DateTime'])

# Sidebar User Inputs
st.sidebar.header("User Input Parameters")

# Tabs for S&P 500 and Inflation Rate Parameters
param_tabs = st.sidebar.tabs(["S&P 500 Parameters", "Inflation Rate Parameters"])

# Initialize threshold lists
sp500_thresholds = []
inflation_thresholds = []

# S&P 500 Parameters
with param_tabs[0]:
    st.subheader("S&P 500 Parameters")
    # Moving Average Type Selection
    sp500_ma_type = st.selectbox(
        "Select Moving Average Type for S&P 500:",
        options=["SMA", "EMA", "WMA"],
        index=0,
        help="""
        **Simple Moving Average (SMA):** Calculates the average of the last 'n' data points.
        
        **Exponential Moving Average (EMA):** Gives more weight to recent data points.
        
        **Weighted Moving Average (WMA):** Assigns linearly increasing weights over the moving window, giving more importance to recent data.
        """
    )

    # Rolling Window Size Input
    sp500_n = st.number_input(
        "Select n (months) for S&P 500 Moving Average:",
        min_value=1,
        max_value=120,
        value=12,
        step=1,
        help="Enter the number of months for the moving average window for S&P 500."
    )

    # Threshold Inputs for S&P 500 MA Derivative
    st.markdown("### Thresholds for S&P 500 MA Derivative")
    num_sp500_thresholds = st.number_input(
        "Number of Thresholds for S&P 500 MA Derivative:",
        min_value=0,
        max_value=5,
        value=1,
        step=1,
        key='num_sp500_thresholds',
        help="Specify the number of thresholds for the S&P 500 MA Derivative."
    )

    sp500_min_placeholder = st.empty()
    sp500_max_placeholder = st.empty()

    # Placeholder for thresholds
    sp500_thresholds_inputs = []
    for i in range(int(num_sp500_thresholds)):
        threshold = st.number_input(
            f"S&P 500 MA Derivative Threshold {i+1}:",
            key=f"sp500_threshold_{i}",
            help="Set a threshold value for the S&P 500 MA Derivative."
        )
        sp500_thresholds.append(threshold)

# Inflation Rate Parameters
with param_tabs[1]:
    st.subheader("Inflation Rate Parameters")
    # Moving Average Type Selection
    inflation_ma_type = st.selectbox(
        "Select Moving Average Type for Inflation Rate:",
        options=["SMA", "EMA", "WMA"],
        index=0,
        help="""
        **Simple Moving Average (SMA):** Calculates the average of the last 'n' data points.
        
        **Exponential Moving Average (EMA):** Gives more weight to recent data points.
        
        **Weighted Moving Average (WMA):** Assigns linearly increasing weights over the moving window, giving more importance to recent data.
        """
    )

    # Rolling Window Size Input
    inflation_n = st.number_input(
        "Select n (months) for Inflation Rate Moving Average:",
        min_value=1,
        max_value=120,
        value=12,
        step=1,
        help="Enter the number of months for the moving average window for Inflation Rate."
    )

    # Threshold Inputs for Inflation Rate MA Derivative
    st.markdown("### Thresholds for Inflation Rate MA Derivative")
    num_inflation_thresholds = st.number_input(
        "Number of Thresholds for Inflation Rate MA Derivative:",
        min_value=0,
        max_value=5,
        value=1,
        step=1,
        key='num_inflation_thresholds',
        help="Specify the number of thresholds for the Inflation Rate MA Derivative."
    )

    inflation_min_placeholder = st.empty()
    inflation_max_placeholder = st.empty()

    # Placeholder for thresholds
    for i in range(int(num_inflation_thresholds)):
        threshold = st.number_input(
            f"Inflation Rate MA Derivative Threshold {i+1}:",
            key=f"inflation_threshold_{i}",
            help="Set a threshold value for the Inflation Rate MA Derivative."
        )
        inflation_thresholds.append(threshold)

# Data range selection
min_date = max(sp_inflation_data['DateTime'].min(), asset_ts_data['DateTime'].min())
max_date = min(sp_inflation_data['DateTime'].max(), asset_ts_data['DateTime'].max())

start_date = st.sidebar.date_input('Start date', min_date, min_value=min_date, max_value=max_date)
end_date = st.sidebar.date_input('End date', max_date, min_value=min_date, max_value=max_date)

# Convert start_date and end_date to pd.Timestamp
start_date = pd.to_datetime(start_date)
end_date = pd.to_datetime(end_date)

if start_date > end_date:
    st.sidebar.error('Error: End date must fall after start date.')
    st.stop()

# Define a color palette for regimes
color_palette = [
    'green', 'yellow', 'orange', 'red', 'purple', 'cyan', 'magenta', 'brown', 'pink', 'olive',
    'blue', 'gray', 'black', 'teal', 'navy', 'maroon'
]

# Caching dynamic computations
@st.cache_data
def compute_moving_average(data, window_size, ma_type='SMA'):
    if ma_type == 'SMA':
        return data.rolling(window=window_size).mean()
    elif ma_type == 'EMA':
        return data.ewm(span=window_size, adjust=False).mean()
    elif ma_type == 'WMA':
        # Compute WMA
        weights = np.arange(1, window_size + 1)
        def wma(x):
            return np.dot(x, weights) / weights.sum()
        return data.rolling(window=window_size).apply(wma, raw=True)
    else:
        raise ValueError("Unsupported moving average type.")

@st.cache_data
def compute_derivative(ma_data, method='difference'):
    if method == 'difference':
        return ma_data.diff()
    elif method == 'percentage':
        return ma_data.pct_change()
    else:
        raise ValueError("Unsupported derivative calculation method.")

@st.cache_data
def get_filtered_data(sp_inflation_df, asset_ts_df, start_date, end_date):
    # Filter data by date range
    sp_inflation_filtered = sp_inflation_df[
        (sp_inflation_df['DateTime'] >= start_date) & (sp_inflation_df['DateTime'] <= end_date)
    ].copy()
    
    asset_ts_filtered = asset_ts_df[
        (asset_ts_df['DateTime'] >= start_date) & (asset_ts_df['DateTime'] <= end_date)
    ].copy()
    
    return sp_inflation_filtered, asset_ts_filtered

# Filter data based on date range
with st.spinner('Filtering data...'):
    sp_inflation_filtered, asset_ts_filtered = get_filtered_data(
        sp_inflation_data,
        asset_ts_data,
        start_date,
        end_date
    )
    print(f"DEBUG: Data filtered. sp_inflation_filtered shape: {sp_inflation_filtered.shape}, asset_ts_filtered shape: {asset_ts_filtered.shape}") # Added debug print

# Compute Moving Averages
with st.spinner('Computing Moving Averages...'):
    sp_inflation_filtered['S&P 500 MA'] = compute_moving_average(
        sp_inflation_filtered['S&P 500'], window_size=sp500_n, ma_type=sp500_ma_type
    )
    sp_inflation_filtered['Inflation Rate MA'] = compute_moving_average(
        sp_inflation_filtered['Inflation Rate'], window_size=inflation_n, ma_type=inflation_ma_type
    )
    print("DEBUG: Moving averages computed.") # Added debug print

# Compute Derivatives
with st.spinner('Computing Derivatives...'):
    sp_inflation_filtered['S&P 500 MA Derivative'] = compute_derivative(
        sp_inflation_filtered['S&P 500 MA'], method='difference'
    )
    sp_inflation_filtered['Inflation Rate MA Derivative'] = compute_derivative(
        sp_inflation_filtered['Inflation Rate MA'], method='difference'
    )
    print("DEBUG: Derivatives computed.") # Added debug print

# Now that we have the derivatives, we can get min and max values
sp500_deriv = sp_inflation_filtered['S&P 500 MA Derivative'].dropna()
inflation_deriv = sp_inflation_filtered['Inflation Rate MA Derivative'].dropna()

sp500_min = float(sp500_deriv.min())
sp500_max = float(sp500_deriv.max())
inflation_min = float(inflation_deriv.min())
inflation_max = float(inflation_deriv.max())

# Update placeholders with min and max values
with param_tabs[0]:
    sp500_min_placeholder.markdown(f"Minimum S&P 500 MA Derivative: **{sp500_min:.4f}**")
    sp500_max_placeholder.markdown(f"Maximum S&P 500 MA Derivative: **{sp500_max:.4f}**")
with param_tabs[1]:
    inflation_min_placeholder.markdown(f"Minimum Inflation Rate MA Derivative: **{inflation_min:.4f}**")
    inflation_max_placeholder.markdown(f"Maximum Inflation Rate MA Derivative: **{inflation_max:.4f}**")

# Validate thresholds and sort them
sp500_thresholds = sorted([t for t in sp500_thresholds if sp500_min <= t <= sp500_max])
inflation_thresholds = sorted([t for t in inflation_thresholds if inflation_min <= t <= inflation_max])

# Add min and max to thresholds
sp500_intervals = [sp500_min] + sp500_thresholds + [sp500_max]
inflation_intervals = [inflation_min] + inflation_thresholds + [inflation_max]

# Generate regime combinations
regime_combinations = list(itertools.product(
    zip(sp500_intervals[:-1], sp500_intervals[1:]),
    zip(inflation_intervals[:-1], inflation_intervals[1:])
))

# Create regime definitions
regime_definitions = []
for idx, ((sp500_lower, sp500_upper), (inflation_lower, inflation_upper)) in enumerate(regime_combinations):
    regime_definitions.append({
        'Regime': idx + 1,
        'S&P 500 Lower': sp500_lower,
        'S&P 500 Upper': sp500_upper,
        'Inflation Lower': inflation_lower,
        'Inflation Upper': inflation_upper,
        'Label': f"Regime {idx + 1}"
    })

# Assign colors and labels to regimes
regime_colors = {}
regime_labels_dict = {}
for i, regime in enumerate(regime_definitions):
    regime_num = regime['Regime']
    color = color_palette[i % len(color_palette)]
    regime_colors[regime_num] = color
    regime_labels_dict[regime_num] = regime['Label']

# Function to assign regimes based on thresholds
@st.cache_data
def assign_regimes(sp_inflation_df, regime_definitions):
    # Initialize Regime column
    sp_inflation_df['Regime'] = np.nan

    # Iterate over regimes and assign regime numbers
    for regime in regime_definitions:
        mask = (
            (sp_inflation_df['S&P 500 MA Derivative'] >= regime['S&P 500 Lower']) &
            (sp_inflation_df['S&P 500 MA Derivative'] < regime['S&P 500 Upper']) &
            (sp_inflation_df['Inflation Rate MA Derivative'] >= regime['Inflation Lower']) &
            (sp_inflation_df['Inflation Rate MA Derivative'] < regime['Inflation Upper'])
        )
        sp_inflation_df.loc[mask, 'Regime'] = regime['Regime']
    return sp_inflation_df

# Assign Regimes
with st.spinner('Assigning Regimes...'):
    sp_inflation_filtered = assign_regimes(sp_inflation_filtered, regime_definitions)
    print("DEBUG: Regimes assigned.") # Added debug print

# Handle any NaN regimes (should not happen)
sp_inflation_filtered['Regime'] = sp_inflation_filtered['Regime'].fillna('Unknown')
if 'Unknown' in sp_inflation_filtered['Regime'].unique():
    regime_colors['Unknown'] = 'lightgrey'
    regime_labels_dict['Unknown'] = 'Unknown'

# Tabs for different analyses
tabs = st.tabs(["Regime Visualization", "Asset Performance Over Time", "Performance Metrics per Regime"])
print("DEBUG: Starting Tab rendering.") # Added debug print

# Tab 1: Regime Visualization
with tabs[0]:
    st.subheader("Regime Visualization")
    print("DEBUG: Rendering Tab 1: Regime Visualization.") # Added debug print
    
    # Checkboxes to show/hide curves
    show_sp500_ma = st.checkbox(f"Show S&P 500 {sp500_ma_type} ({sp500_n}m)", value=True, key='regime_sp500_ma')
    show_inflation_ma = st.checkbox(f"Show Inflation Rate {inflation_ma_type} ({inflation_n}m)", value=True, key='regime_inflation_ma')
    show_sp500 = st.checkbox("Show S&P 500", value=False, key='regime_sp500')
    show_inflation = st.checkbox("Show Inflation Rate", value=False, key='regime_inflation')
    
    # Checkboxes to toggle log scales
    log_scale_sp500 = st.checkbox("Log Scale for S&P 500 Axis", value=False, key='regime_log_sp500')
    log_scale_inflation_rate = st.checkbox("Log Scale for Inflation Rate Axis", value=False, key='regime_log_inflation')
    
    # Initialize the plot
    fig = go.Figure()
    print("DEBUG: Tab 1 - Initialized go.Figure.") # Added debug print

    # Add shaded regions for regimes (updated to handle continuous periods)
    # Identify where the regime changes
    sp_inflation_filtered['Regime_Change'] = (sp_inflation_filtered['Regime'] != sp_inflation_filtered['Regime'].shift()).cumsum()
    print("DEBUG: Tab 1 - Calculated Regime_Change.") # Added debug print

    # Group by 'Regime' and 'Regime_Change' to get continuous periods
    grouped = sp_inflation_filtered.groupby(['Regime', 'Regime_Change'])
    print(f"DEBUG: Tab 1 - Grouped regimes. Number of groups: {len(grouped)}") # Added debug print

    # Collect regime periods
    regime_periods = []
    print("DEBUG: Tab 1 - Starting regime period collection loop.") # Added debug print
    loop_count = 0
    for (regime, _), group in grouped:
        color = regime_colors.get(regime, 'grey')
        start_date_regime = group['DateTime'].iloc[0]
        end_date_regime = group['DateTime'].iloc[-1]
        regime_periods.append({
            'Regime': regime,
            'Start Date': start_date_regime,
            'End Date': end_date_regime
        })
        loop_count += 1
        if loop_count % 50 == 0: # Print progress every 50 groups
             print(f"DEBUG: Tab 1 - Processed {loop_count} regime groups.")
    print(f"DEBUG: Tab 1 - Finished regime period collection loop. Total periods collected: {len(regime_periods)}") # Added debug print

    # Sort regime periods by start date
    regime_periods_df = pd.DataFrame(regime_periods)
    regime_periods_df = regime_periods_df.sort_values('Start Date').reset_index(drop=True)
    print("DEBUG: Tab 1 - Sorted regime periods DataFrame.") # Added debug print

    # Adjust end dates and add vrects
    print("DEBUG: Tab 1 - Starting add_vrect loop.") # Added debug print
    vrect_count = 0
    for i in range(len(regime_periods_df)):
        start_date_regime = regime_periods_df.loc[i, 'Start Date']
        regime = regime_periods_df.loc[i, 'Regime']
        color = regime_colors.get(regime, 'grey')
        if i < len(regime_periods_df) - 1:
            # Set end date to one day before the next regime's start date
            end_date_regime = regime_periods_df.loc[i+1, 'Start Date'] - pd.Timedelta(days=1)
        else:
            # For the last regime, set end date to the maximum date
            end_date_regime = sp_inflation_filtered['DateTime'].max()
        # Ensure end_date_regime is not before start_date_regime
        if end_date_regime < start_date_regime:
            end_date_regime = start_date_regime
        # Add vrect for this regime
        fig.add_vrect(
            x0=start_date_regime,
            x1=end_date_regime,
            fillcolor=color,
            opacity=0.3,
            layer="below",
            line_width=0
        )
        vrect_count += 1
        if vrect_count % 50 == 0: # Print progress every 50 vrects
            print(f"DEBUG: Tab 1 - Added {vrect_count} vrects.")
    print(f"DEBUG: Tab 1 - Finished add_vrect loop. Total vrects added: {vrect_count}") # Added debug print

    # --- Optimization: Create customdata ONCE ---
    print("DEBUG: Tab 1 - Preparing customdata array...") # Added debug print
    try:
        # Ensure required columns exist and handle potential NaNs before stacking
        required_cols = ['Regime', 'S&P 500', 'S&P 500 MA', 'Inflation Rate', 'Inflation Rate MA']
        # Check if all required columns are present
        if not all(col in sp_inflation_filtered.columns for col in required_cols):
             raise ValueError(f"Missing one or more required columns for customdata: {required_cols}")

        # Map regimes (handle potential missing keys in dict gracefully)
        regime_labels = sp_inflation_filtered['Regime'].map(lambda x: regime_labels_dict.get(x, 'Unknown'))

        # Select data, fill NaNs that might interfere with stacking (e.g., with 0 or a placeholder)
        # Choose a fill value appropriate for your data, or handle NaNs differently if needed
        sp500_data = sp_inflation_filtered['S&P 500'].fillna(0)
        sp500_ma_data = sp_inflation_filtered['S&P 500 MA'].fillna(0)
        inflation_data = sp_inflation_filtered['Inflation Rate'].fillna(0)
        inflation_ma_data = sp_inflation_filtered['Inflation Rate MA'].fillna(0)

        customdata = np.stack((
            regime_labels,
            sp500_data,
            sp500_ma_data,
            inflation_data,
            inflation_ma_data
        ), axis=-1)
        print(f"DEBUG: Tab 1 - Customdata array created successfully. Shape: {customdata.shape}") # Added debug print
    except Exception as e:
        print(f"ERROR: Tab 1 - Failed to create customdata array: {e}")
        st.error(f"Failed to prepare data for plotting: {e}")
        # Assign a dummy array or stop execution if customdata is critical
        customdata = np.empty((len(sp_inflation_filtered), 5)) # Example dummy
        # Or potentially st.stop() here if the plot can't proceed

    # Add traces based on user selection, reusing the customdata array
    print("DEBUG: Tab 1 - Starting add_trace section.") # Added debug print
    if show_sp500_ma:
        print("DEBUG: Tab 1 - Preparing S&P 500 MA trace...") # Added debug print
        # REUSE customdata
        fig.add_trace(go.Scatter(
            x=sp_inflation_filtered['DateTime'],
            y=sp_inflation_filtered['S&P 500 MA'], # Use original MA data for plotting Y
            mode='lines',
            name=f'S&P 500 {sp500_ma_type} ({sp500_n}m)',
            line=dict(color='blue'),
            yaxis='y1',
            customdata=customdata, # Use the pre-calculated customdata
            hovertemplate=(
                'Date: %{x|%Y-%m-%d}<br>' +
                'Regime: %{customdata[0]}<br>' +
                'S&P 500: %{customdata[1]:.2f}<br>' +
                f'S&P 500 {sp500_ma_type}: ' + '%{customdata[2]:.2f}<br>' +
                'Inflation Rate: %{customdata[3]:.2f}<br>' +
                f'Inflation Rate {inflation_ma_type}: ' + '%{customdata[4]:.2f}<extra></extra>'
            )
        ))
        print("DEBUG: Tab 1 - Added S&P 500 MA trace.") # Added debug print

    if show_inflation_ma:
        print("DEBUG: Tab 1 - Preparing Inflation Rate MA trace...") # Added debug print
        # REUSE customdata
        fig.add_trace(go.Scatter(
            x=sp_inflation_filtered['DateTime'],
            y=sp_inflation_filtered['Inflation Rate MA'], # Use original MA data for plotting Y
            mode='lines',
            name=f'Inflation Rate {inflation_ma_type} ({inflation_n}m)',
            line=dict(color='red'),
            yaxis='y2',
            customdata=customdata, # Use the pre-calculated customdata
            hovertemplate=(
                'Date: %{x|%Y-%m-%d}<br>' +
                'Regime: %{customdata[0]}<br>' +
                'S&P 500: %{customdata[1]:.2f}<br>' +
                f'S&P 500 {sp500_ma_type}: ' + '%{customdata[2]:.2f}<br>' +
                'Inflation Rate: %{customdata[3]:.2f}<br>' +
                f'Inflation Rate {inflation_ma_type}: ' + '%{customdata[4]:.2f}<extra></extra>'
            )
        ))
        print("DEBUG: Tab 1 - Added Inflation Rate MA trace.") # Added debug print

    if show_sp500:
        print("DEBUG: Tab 1 - Preparing S&P 500 trace...") # Added debug print
        # REUSE customdata
        fig.add_trace(go.Scatter(
            x=sp_inflation_filtered['DateTime'],
            y=sp_inflation_filtered['S&P 500'], # Use original S&P data for plotting Y
            mode='lines',
            name='S&P 500',
            line=dict(color='blue', dash='dot'),
            yaxis='y1',
            customdata=customdata, # Use the pre-calculated customdata
            hovertemplate=(
                'Date: %{x|%Y-%m-%d}<br>' +
                'Regime: %{customdata[0]}<br>' +
                'S&P 500: %{customdata[1]:.2f}<br>' +
                f'S&P 500 {sp500_ma_type}: ' + '%{customdata[2]:.2f}<br>' +
                'Inflation Rate: %{customdata[3]:.2f}<br>' +
                f'Inflation Rate {inflation_ma_type}: ' + '%{customdata[4]:.2f}<extra></extra>'
            )
        ))
        print("DEBUG: Tab 1 - Added S&P 500 trace.") # Added debug print

    if show_inflation:
        print("DEBUG: Tab 1 - Preparing Inflation Rate trace...") # Added debug print
        # REUSE customdata
        fig.add_trace(go.Scatter(
            x=sp_inflation_filtered['DateTime'],
            y=sp_inflation_filtered['Inflation Rate'], # Use original Inflation data for plotting Y
            mode='lines',
            name='Inflation Rate',
            line=dict(color='red', dash='dot'),
            yaxis='y2',
            customdata=customdata, # Use the pre-calculated customdata
            hovertemplate=(
                'Date: %{x|%Y-%m-%d}<br>' +
                'Regime: %{customdata[0]}<br>' +
                'S&P 500: %{customdata[1]:.2f}<br>' +
                f'S&P 500 {sp500_ma_type}: ' + '%{customdata[2]:.2f}<br>' +
                'Inflation Rate: %{customdata[3]:.2f}<br>' +
                f'Inflation Rate {inflation_ma_type}: ' + '%{customdata[4]:.2f}<extra></extra>'
            )
        ))
        print("DEBUG: Tab 1 - Added Inflation Rate trace.") # Added debug print

    print("DEBUG: Tab 1 - Finished add_trace section.") # Added debug print

    # Update layout with optional log scales
    print("DEBUG: Tab 1 - Updating layout...") # Added debug print
    fig.update_layout(
        title=f'Moving Averages of S&P 500 and Inflation Rate with Defined Regimes',
        xaxis=dict(title='Date'),
        yaxis=dict(
            title=dict(
                text='S&P 500',
                font=dict(
                    family='Arial',
                    size=14,
                    color='black'
                )
            ),
            tickfont=dict(
                family='Arial',
                size=12,
                color='black'
            ),
            side='left',
            type='log' if log_scale_sp500 else 'linear'
        ),
        yaxis2=dict(
            title=dict(
                text='Inflation Rate',
                font=dict(
                    family='Arial',
                    size=14,
                    color='black'
                )
            ),
            tickfont=dict(
                family='Arial',
                size=12,
                color='black'
            ),
            overlaying='y',
            side='right',
            type='log' if log_scale_inflation_rate else 'linear'
        ),
        hovermode='x unified',
        width=1200,
        height=700,
        margin=dict(l=50, r=50, t=100, b=100),
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial",
            font_color="black"
        )
    )
    print("DEBUG: Tab 1 - Layout updated.") # Added debug print

    # Display the plot
    print("DEBUG: Tab 1 - Calling st.plotly_chart(fig)...") # Added debug print
    st.plotly_chart(fig, use_container_width=False)
    print("DEBUG: Tab 1 Plotting complete.") # Added debug print
    
    # Create Curve Legend under the graph
    st.markdown("### Curve Legend")
    curve_legend_html = "<ul style='list-style-type:none;'>"
    
    if show_sp500_ma:
        curve_legend_html += f"<li><span style='color:blue;'>■</span> S&P 500 {sp500_ma_type} ({sp500_n}m)</li>"
    if show_inflation_ma:
        curve_legend_html += f"<li><span style='color:red;'>■</span> Inflation Rate {inflation_ma_type} ({inflation_n}m)</li>"
    if show_sp500:
        curve_legend_html += f"<li><span style='border-bottom: 2px dashed blue; display:inline-block; width:15px; margin-right:5px;'></span> S&P 500</li>"
    if show_inflation:
        curve_legend_html += f"<li><span style='border-bottom: 2px dashed red; display:inline-block; width:15px; margin-right:5px;'></span> Inflation Rate</li>"
    
    curve_legend_html += "</ul>"
    st.markdown(curve_legend_html, unsafe_allow_html=True)
    
    # Create Regime Legend under the graph with regime definitions
    st.markdown("### Regime Legend with Definitions")
    regime_legend_html = "<ul style='list-style-type:none;'>"
    
    # Add numeric regimes
    for regime_num in sorted(regime_labels_dict.keys(), key=lambda x: int(x) if x != 'Unknown' else float('inf')):
        color = regime_colors.get(regime_num, 'grey')
        label = regime_labels_dict.get(regime_num, 'Unknown')
        if regime_num != 'Unknown':
            # Get the regime definition
            regime_def = next((regime for regime in regime_definitions if regime['Regime'] == regime_num), None)
            if regime_def:
                sp500_lower = regime_def['S&P 500 Lower']
                sp500_upper = regime_def['S&P 500 Upper']
                inflation_lower = regime_def['Inflation Lower']
                inflation_upper = regime_def['Inflation Upper']
                definition = f"S&P 500 MA Derivative: [{sp500_lower:.4f}, {sp500_upper:.4f}), Inflation Rate MA Derivative: [{inflation_lower:.4f}, {inflation_upper:.4f})"
            else:
                definition = "Definition not found"
        else:
            definition = "Unknown"
        
        regime_legend_html += f"<li><span style='background-color:{color}; width:15px; height:15px; display:inline-block; margin-right:5px;'></span> {label} - {definition}</li>"
    
    regime_legend_html += "</ul>"
    st.markdown(regime_legend_html, unsafe_allow_html=True)
    
    # Export plot as image
    buffer = io.BytesIO()
    fig.write_image(buffer, format='png')
    st.download_button(
        label="Download Plot as PNG",
        data=buffer,
        file_name='regime_plot.png',
        mime='image/png'
    )
    
    # Provide a download button for the regime data
    regime_download_df = sp_inflation_filtered[['DateTime', 'Regime']].copy()
    regime_download_df['Regime Label'] = regime_download_df['Regime'].map(regime_labels_dict)
    csv = regime_download_df.to_csv(index=False)
    st.download_button(
        label="Download Regime Data as CSV",
        data=csv,
        file_name='regime_data.csv',
        mime='text/csv',
    )
    
    # Add Regime Diagrams under the legends
    st.markdown("## Regime Diagrams")
    
    ### Diagram 1: 2D Scatter Plot of Derivative Values with Regime Boundaries
    st.markdown("### 1. 2D Scatter Plot of Derivative Values with Regime Boundaries")
    print("DEBUG: Tab 1 - Preparing Scatter Plot...") # Added debug print
    # Prepare data for plotting
    derivative_df = sp_inflation_filtered[['DateTime', 'S&P 500 MA Derivative', 'Inflation Rate MA Derivative', 'Regime']].dropna()
    derivative_df['Regime Label'] = derivative_df['Regime'].map(regime_labels_dict)
    
    # Create the scatter plot
    scatter_fig = go.Figure()
    
    for regime in derivative_df['Regime'].unique():
        regime_data = derivative_df[derivative_df['Regime'] == regime]
        regime_label = regime_labels_dict.get(regime, 'Unknown')
        color = regime_colors.get(regime, 'grey')
    
        scatter_fig.add_trace(go.Scatter(
            x=regime_data['S&P 500 MA Derivative'],
            y=regime_data['Inflation Rate MA Derivative'],
            mode='markers',
            name=regime_label,
            marker=dict(color=color),
            customdata=np.stack((regime_data['DateTime'],), axis=-1),
            hovertemplate=(
                'Date: %{customdata[0]|%Y-%m-%d}<br>' +
                'S&P 500 MA Derivative: %{x:.4f}<br>' +
                'Inflation Rate MA Derivative: %{y:.4f}<br>' +
                'Regime: ' + str(regime_label) + '<extra></extra>'
            )
        ))
    
    # Add regime boundaries
    # Add vertical lines for S&P 500 thresholds
    for threshold in sp500_thresholds:
        scatter_fig.add_shape(
            type="line",
            x0=threshold,
            y0=inflation_min,
            x1=threshold,
            y1=inflation_max,
            line=dict(color="black", dash="dash")
        )
    # Add horizontal lines for Inflation Rate thresholds
    for threshold in inflation_thresholds:
        scatter_fig.add_shape(
            type="line",
            x0=sp500_min,
            y0=threshold,
            x1=sp500_max,
            y1=threshold,
            line=dict(color="black", dash="dash")
        )
    
    # Update layout
    scatter_fig.update_layout(
        xaxis_title='S&P 500 MA Derivative',
        yaxis_title='Inflation Rate MA Derivative',
        title='Scatter Plot of Derivatives with Regime Boundaries',
        legend_title='Regime',
        width=800,
        height=600,
    )
    
    st.plotly_chart(scatter_fig)
    print("DEBUG: Tab 1 Scatter Plot complete.") # Added debug print
    
    ### Diagram 2: Interactive Heatmap of Derivative Density with Regime Boundaries
    st.markdown("### 2. Interactive Heatmap of Derivative Density with Regime Boundaries")
    print("DEBUG: Tab 1 - Preparing Heatmap...") # Added debug print
    # Create 2D histogram
    heatmap_fig = go.Figure()
    
    heatmap_fig.add_trace(go.Histogram2d(
        x=derivative_df['S&P 500 MA Derivative'],
        y=derivative_df['Inflation Rate MA Derivative'],
        colorscale='Viridis',
        reversescale=True,
        xbins=dict(
            start=sp500_min,
            end=sp500_max,
            size=(sp500_max - sp500_min)/50  # Adjust bin size as needed
        ),
        ybins=dict(
            start=inflation_min,
            end=inflation_max,
            size=(inflation_max - inflation_min)/50
        ),
        colorbar=dict(title='Density')
    ))
    
    # Add regime boundaries
    for threshold in sp500_thresholds:
        heatmap_fig.add_shape(
            type="line",
            x0=threshold,
            y0=inflation_min,
            x1=threshold,
            y1=inflation_max,
            line=dict(color="white", dash="dash")
        )
    for threshold in inflation_thresholds:
        heatmap_fig.add_shape(
            type="line",
            x0=sp500_min,
            y0=threshold,
            x1=sp500_max,
            y1=threshold,
            line=dict(color="white", dash="dash")
        )
    
    heatmap_fig.update_layout(
        xaxis_title='S&P 500 MA Derivative',
        yaxis_title='Inflation Rate MA Derivative',
        title='Heatmap of Derivative Density with Regime Boundaries',
        width=800,
        height=600,
    )
    
    st.plotly_chart(heatmap_fig)
    print("DEBUG: Tab 1 Heatmap complete.") # Added debug print
    
    ### Diagram 3: Threshold Distribution Histograms
    st.markdown("### 3. Threshold Distribution Histograms")
    
    # Histogram for S&P 500 MA Derivative
    st.markdown("#### S&P 500 MA Derivative Distribution")
    print("DEBUG: Tab 1 - Preparing SP500 Hist...") # Added debug print
    sp500_hist_fig = go.Figure()
    
    sp500_hist_fig.add_trace(go.Histogram(
        x=derivative_df['S&P 500 MA Derivative'],
        nbinsx=50,
        marker_color='blue',
        opacity=0.7,
        name='S&P 500 MA Derivative'
    ))
    
    # Add vertical lines for thresholds
    for threshold in sp500_thresholds:
        sp500_hist_fig.add_vline(
            x=threshold,
            line=dict(color='red', dash='dash'),
            annotation_text=f"{threshold:.4f}",
            annotation_position="top left"
        )
    
    sp500_hist_fig.update_layout(
        xaxis_title='S&P 500 MA Derivative',
        yaxis_title='Count',
        width=800,
        height=400,
        showlegend=False
    )
    
    st.plotly_chart(sp500_hist_fig)
    print("DEBUG: Tab 1 SP500 Hist complete.") # Added debug print
    
    # Histogram for Inflation Rate MA Derivative
    st.markdown("#### Inflation Rate MA Derivative Distribution")
    print("DEBUG: Tab 1 - Preparing Inflation Hist...") # Added debug print
    inflation_hist_fig = go.Figure()
    
    inflation_hist_fig.add_trace(go.Histogram(
        x=derivative_df['Inflation Rate MA Derivative'],
        nbinsx=50,
        marker_color='green',
        opacity=0.7,
        name='Inflation Rate MA Derivative'
    ))
    
    # Add vertical lines for thresholds
    for threshold in inflation_thresholds:
        inflation_hist_fig.add_vline(
            x=threshold,
            line=dict(color='red', dash='dash'),
            annotation_text=f"{threshold:.4f}",
            annotation_position="top left"
        )
    
    inflation_hist_fig.update_layout(
        xaxis_title='Inflation Rate MA Derivative',
        yaxis_title='Count',
        width=800,
        height=400,
        showlegend=False
    )
    
    st.plotly_chart(inflation_hist_fig)
    print("DEBUG: Tab 1 Inflation Hist complete.") # Added debug print

# Function to adjust prices for inflation (ensure this is defined before Tabs 2 and 3)
def adjust_prices_for_inflation(df, price_columns, cpi_column='CPI'):
    base_cpi = df[cpi_column].iloc[0]
    for col in price_columns:
        df[f'{col}_Adjusted'] = df[col] * (base_cpi / df[cpi_column])
    return df

# Sidebar for Asset Settings (ensure this is before Tabs 2 and 3 so that 'selected_assets' and 'adjust_for_inflation' are accessible)
st.sidebar.header("Asset Settings")
# Sidebar Asset Selection
asset_options = list(asset_ts_data.columns)
asset_options.remove('DateTime')
selected_assets = st.sidebar.multiselect("Select Assets to Display:", asset_options, default=['Gold', 'Bonds'])
# Checkbox for inflation adjustment
adjust_for_inflation = st.sidebar.checkbox("Adjust Prices for Inflation (CPI)", value=False)

# Tab 2: Asset Performance Over Time
with tabs[1]:
    st.subheader("Asset Performance Over Time")
    print("DEBUG: Rendering Tab 2: Asset Performance.") # Added debug print
    
    # Add checkbox for log scale within the tab (this is fine)
    log_scale_normalized = st.checkbox(
        "Log Scale for Normalized Prices", value=False, key='log_scale_normalized'
    )
    
    # Check if assets are selected
    if not selected_assets:
        st.warning("Please select at least one asset to display.")
    else:
        # Merge asset data with regimes
        @st.cache_data
        def merge_asset_with_regimes(asset_ts_df, sp_inflation_df):
            merged = pd.merge(
                asset_ts_df,
                sp_inflation_df[['DateTime', 'Regime', 'CPI']],
                on='DateTime',
                how='left'
            )
            return merged
        
        with st.spinner('Merging asset data with regimes...'):
            merged_asset_data = merge_asset_with_regimes(asset_ts_filtered, sp_inflation_filtered)
            print(f"DEBUG: Tab 2 - Asset data merged. Shape: {merged_asset_data.shape}") # Added debug print
        
        # Adjust asset prices for inflation if checkbox is checked
        if adjust_for_inflation:
            # Adjust prices
            price_columns = selected_assets  # List of asset columns to adjust
            merged_asset_data = adjust_prices_for_inflation(merged_asset_data, price_columns, cpi_column='CPI')
        
        # Add 'Regime' to asset data and fill NaN values
        merged_asset_data['Regime'] = merged_asset_data['Regime'].fillna('Unknown')
        
        # Initialize the plot
        fig2 = go.Figure()
        
        # Add shaded regions for regimes (updated to handle continuous periods)
        # Identify where the regime changes
        merged_asset_data['Regime_Change'] = (merged_asset_data['Regime'] != merged_asset_data['Regime'].shift()).cumsum()
    
        # Group by 'Regime' and 'Regime_Change' to get continuous periods
        grouped = merged_asset_data.groupby(['Regime', 'Regime_Change'])
    
        # Collect regime periods
        regime_periods = []
        for (regime, _), group in grouped:
            if regime == 'Unknown':
                continue
            color = regime_colors.get(regime, 'grey')
            start_date_regime = group['DateTime'].iloc[0]
            end_date_regime = group['DateTime'].iloc[-1]
            regime_periods.append({
                'Regime': regime,
                'Start Date': start_date_regime,
                'End Date': end_date_regime
            })
    
        # Sort regime periods by start date
        regime_periods_df = pd.DataFrame(regime_periods)
        regime_periods_df = regime_periods_df.sort_values('Start Date').reset_index(drop=True)
    
        # Adjust end dates to be one day before the next regime's start date
        for i in range(len(regime_periods_df)):
            start_date_regime = regime_periods_df.loc[i, 'Start Date']
            regime = regime_periods_df.loc[i, 'Regime']
            color = regime_colors.get(regime, 'grey')
            if i < len(regime_periods_df) - 1:
                # Set end date to one day before the next regime's start date
                end_date_regime = regime_periods_df.loc[i+1, 'Start Date'] - pd.Timedelta(days=1)
            else:
                # For the last regime, set end date to the maximum date
                end_date_regime = merged_asset_data['DateTime'].max()
            # Ensure end_date_regime is not before start_date_regime
            if end_date_regime < start_date_regime:
                end_date_regime = start_date_regime
            # Add vrect for this regime
            fig2.add_vrect(
                x0=start_date_regime,
                x1=end_date_regime,
                fillcolor=color,
                opacity=0.3,
                layer="below",
                line_width=0
            )
        
        # Add asset traces
        for asset in selected_assets:
            # Use adjusted prices if the checkbox is checked
            price_column = f'{asset}_Adjusted' if adjust_for_inflation else asset
            asset_data = merged_asset_data[['DateTime', price_column, 'Regime']].copy()
            asset_data = asset_data.dropna(subset=[price_column]).copy()
            asset_data['Regime'] = asset_data['Regime'].fillna('Unknown')
        
            if asset_data.empty:
                st.warning(f"No data available for asset {asset} in the selected date range.")
                continue
        
            # Store actual prices
            asset_data['Actual Price'] = asset_data[price_column]
        
            # Normalize prices so that the first valid point is 100
            first_valid_value = asset_data[price_column].iloc[0]
            asset_data['Normalized Price'] = (asset_data[price_column] / first_valid_value) * 100
        
            # Prepare customdata with actual prices and regimes
            asset_data['Regime Label'] = asset_data['Regime'].map(regime_labels_dict)
            customdata = np.stack((
                asset_data['Actual Price'],
                asset_data['Regime Label']
            ), axis=-1)
        
            # Update hovertemplate to indicate whether prices are adjusted
            price_label = 'Adjusted Price' if adjust_for_inflation else 'Actual Price'
        
            # Corrected hovertemplate without f-strings for format specifiers
            hovertemplate=(
                asset + "<br>"
                "Date: %{x|%Y-%m-%d}<br>"
                "Regime: %{customdata[1]}<br>"
                "Normalized Price: %{y:.2f}<br>"
                + price_label + ": %{customdata[0]:.2f}<extra></extra>"
            )
        
            fig2.add_trace(go.Scatter(
                x=asset_data['DateTime'],
                y=asset_data['Normalized Price'],
                mode='lines',
                name=asset + (' (Adjusted)' if adjust_for_inflation else ''),
                customdata=customdata,
                connectgaps=False,  # Do not connect gaps
                hovertemplate=hovertemplate
            ))
        
        # Update layout
        fig2.update_layout(
            title='Asset Performance Over Time (Normalized to 100 at First Available Date)' + (' (Adjusted for Inflation)' if adjust_for_inflation else ''),
            xaxis=dict(title='Date', range=[start_date, end_date]),
            yaxis=dict(
                title='Normalized Adjusted Price' if adjust_for_inflation else 'Normalized Price',
                type='log' if log_scale_normalized else 'linear'
            ),
            hovermode='x unified',
            width=1200,
            height=700,
            margin=dict(l=50, r=50, t=100, b=100),
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
                font_family="Arial"
            )
        )
        
        # Display the plot
        st.plotly_chart(fig2, use_container_width=False)
        print("DEBUG: Tab 2 Plotting complete.") # Added debug print
        
        # Export plot as image
        buffer = io.BytesIO()
        fig2.write_image(buffer, format='png')
        st.download_button(
            label="Download Plot as PNG",
            data=buffer,
            file_name='asset_performance_plot.png',
            mime='image/png'
        )
        
        # Provide a download button for the asset data
        # Merge all selected asset data for download
        if adjust_for_inflation:
            adjusted_columns = [f'{asset}_Adjusted' for asset in selected_assets]
            all_asset_data = merged_asset_data[['DateTime'] + selected_assets + adjusted_columns + ['Regime']].copy()
        else:
            all_asset_data = merged_asset_data[['DateTime'] + selected_assets + ['Regime']].copy()
        csv = all_asset_data.to_csv(index=False)
        st.download_button(
            label="Download Asset Data as CSV",
            data=csv,
            file_name='asset_data.csv',
            mime='text/csv',
        )

# Tab 3: Performance Metrics per Regime
with tabs[2]:
    st.subheader("Performance Metrics per Regime")
    print("DEBUG: Rendering Tab 3: Performance Metrics.") # Added debug print
    
    # Sidebar for Performance Metrics Settings
    st.sidebar.header("Performance Metrics Settings")
    # Sidebar Performance Metrics Selection
    metric_options = ['Average Return', 'Volatility', 'Sharpe Ratio', 'Max Drawdown']
    selected_metrics = st.sidebar.multiselect("Select Performance Metrics to Display:", metric_options, default=metric_options)
    
    # Check if assets and metrics are selected
    if not selected_assets or not selected_metrics:
        st.warning("Please select at least one asset and one performance metric to display.")
    else:
        # Merge asset data with regimes (include CPI for inflation adjustment)
        @st.cache_data
        def merge_asset_with_regimes(asset_ts_df, sp_inflation_df):
            merged = pd.merge(
                asset_ts_df,
                sp_inflation_df[['DateTime', 'Regime', 'CPI']],
                on='DateTime',
                how='left'
            )
            return merged
        
        with st.spinner('Merging asset data with regimes...'):
            merged_asset_data = merge_asset_with_regimes(asset_ts_filtered, sp_inflation_filtered)
            print(f"DEBUG: Tab 3 - Asset data merged. Shape: {merged_asset_data.shape}") # Added debug print
        
        # Adjust asset prices for inflation if checkbox is checked
        if adjust_for_inflation:
            # Adjust prices
            price_columns = selected_assets  # List of asset columns to adjust
            merged_asset_data = adjust_prices_for_inflation(merged_asset_data, price_columns, cpi_column='CPI')
        
        # Ensure 'DateTime' is datetime type in merged_asset_data
        merged_asset_data['DateTime'] = pd.to_datetime(merged_asset_data['DateTime'])
        
        # Initialize list to store performance metrics
        performance_results = []
        
        for asset in selected_assets:
            # Use adjusted prices if the checkbox is checked
            price_column = f'{asset}_Adjusted' if adjust_for_inflation else asset
            # Get the asset data with regimes
            asset_data = merged_asset_data[['DateTime', price_column, 'Regime']].copy()
            asset_data = asset_data.dropna(subset=[price_column, 'Regime']).copy()
            asset_data['Regime'] = asset_data['Regime'].fillna('Unknown')
            asset_data['Regime Label'] = asset_data['Regime'].map(regime_labels_dict)
            
            # Compute daily returns
            asset_data['Return'] = asset_data[price_column].pct_change()
            asset_data = asset_data.dropna(subset=['Return']).copy()
            
            for regime in asset_data['Regime'].unique():
                regime_data = asset_data[asset_data['Regime'] == regime].copy()
                
                if len(regime_data) < 2:
                    # Not enough data to compute metrics
                    performance_results.append({
                        'Asset': asset + (' (Adjusted)' if adjust_for_inflation else ''),
                        'Regime': regime_labels_dict.get(regime, 'Unknown'),
                        'Average Return': np.nan,
                        'Volatility': np.nan,
                        'Sharpe Ratio': np.nan,
                        'Max Drawdown': np.nan
                    })
                    continue
                
                # Compute performance metrics
                avg_return = regime_data['Return'].mean() * 252  # Annualized
                volatility = regime_data['Return'].std() * np.sqrt(252)  # Annualized
                sharpe_ratio = avg_return / volatility if volatility != 0 else np.nan
                
                # Compute Max Drawdown
                cumulative = (1 + regime_data['Return']).cumprod()
                cumulative_max = cumulative.cummax()
                drawdown = cumulative / cumulative_max - 1
                max_drawdown = drawdown.min()
                
                # Append to results
                performance_results.append({
                    'Asset': asset + (' (Adjusted)' if adjust_for_inflation else ''),
                    'Regime': regime_labels_dict.get(regime, 'Unknown'),
                    'Average Return': avg_return,
                    'Volatility': volatility,
                    'Sharpe Ratio': sharpe_ratio,
                    'Max Drawdown': max_drawdown
                })
        
        # Convert to DataFrame
        perf_data_filtered = pd.DataFrame(performance_results)
        
        # Check if data is available
        if perf_data_filtered.empty:
            st.warning("No performance data available for the selected options.")
        else:
            # Display the table
            st.dataframe(perf_data_filtered)
        
            # Bar Charts for each metric
            for metric in selected_metrics:
                st.markdown(f"#### {metric} by Asset and Regime")
                fig3 = go.Figure()
                
                for asset in selected_assets:
                    asset_name = asset + (' (Adjusted)' if adjust_for_inflation else '')
                    asset_perf = perf_data_filtered[perf_data_filtered['Asset'] == asset_name]
                    fig3.add_trace(go.Bar(
                        x=asset_perf['Regime'],
                        y=asset_perf[metric],
                        name=asset_name
                    ))
                
                # Update layout
                fig3.update_layout(
                    barmode='group',
                    xaxis=dict(title='Regime'),
                    yaxis=dict(title=metric),
                    title=f'{metric} by Asset and Regime',
                    width=800,
                    height=500
                )
                
                # Display the plot
                st.plotly_chart(fig3, use_container_width=False)
            
            # Provide a download button for the performance data
            csv = perf_data_filtered.to_csv(index=False)
            st.download_button(
                label="Download Performance Metrics Data as CSV",
                data=csv,
                file_name='performance_metrics.csv',
                mime='text/csv',
            )

print("DEBUG: End of script execution.") # Added debug print
