import FreeSimpleGUI as sg
import pandas as pd
import json
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.ticker import FuncFormatter 
import matplotlib.dates as mdates 
import numpy as np
import requests
import datetime
import webbrowser
import os
import time
import re

# --- Configuration File Management ---
CONFIG_FILE = 'config.json'
ITEM_NAMES_FILE = 'item_names.json'
HISTORICAL_DATA_FILE = 'historical_data.json'
COLD_STORAGE_FILE = 'historical_data_archive.json' # New: Cold storage file

def load_config():
    """Loads configuration (e.g., API keys) from config.json)."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_config(config_data):
    """Saves configuration (e.g., API keys) to config.json)."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=4)

def load_historical_data():
    """Loads all historical data from historical_data.json."""
    try:
        with open(HISTORICAL_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {HISTORICAL_DATA_FILE} not found. Returning empty list.")
        return []
    except json.JSONDecodeError:
        print(f"Warning: {HISTORICAL_DATA_FILE} is corrupted or empty. Starting with empty historical data.")
        return []
    except Exception as e:
        print(f"Error loading historical data from {HISTORICAL_DATA_FILE}: {e}")
        return []

def save_historical_data(data):
    """Saves all historical data to historical_data.json."""
    try:
        with open(HISTORICAL_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving historical data to {HISTORICAL_DATA_FILE}: {e}")

def append_to_cold_storage(data_to_archive):
    """Appends data to the cold storage JSON file."""
    if not data_to_archive:
        return

    existing_archive_data = []
    if os.path.exists(COLD_STORAGE_FILE):
        try:
            with open(COLD_STORAGE_FILE, 'r', encoding='utf-8') as f:
                existing_archive_data = json.load(f)
            if not isinstance(existing_archive_data, list): # Ensure it's a list
                existing_archive_data = [] # Reset if corrupted
        except json.JSONDecodeError:
            print(f"Warning: {COLD_STORAGE_FILE} is corrupted or empty. Starting fresh for archive.")
            existing_archive_data = []
        except Exception as e:
            print(f"Error loading existing cold storage data from {COLD_STORAGE_FILE}: {e}")
            existing_archive_data = []

    existing_archive_data.extend(data_to_archive)

    try:
        with open(COLD_STORAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing_archive_data, f, indent=4)
        print(f"Successfully archived {len(data_to_archive)} entries to {COLD_STORAGE_FILE}.")
    except Exception as e:
        print(f"Error saving cold storage data to {COLD_STORAGE_FILE}: {e}")


def save_new_item_names(new_ids_to_add):
    """
    Appends newly discovered item IDs to the item_names.json file.
    """
    if not new_ids_to_add:
        return # Nothing to save

    existing_items = []
    if os.path.exists(ITEM_NAMES_FILE):
        try:
            with open(ITEM_NAMES_FILE, 'r', encoding='utf-8') as f:
                existing_items = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: {ITEM_NAMES_FILE} is corrupted or empty. Starting fresh for new IDs.")
            existing_items = []
        except Exception as e:
            print(f"Error loading existing item_names.json for update: {e}")
            existing_items = []

    # Ensure existing_ids is robust to missing 'id' keys or non-integer IDs
    existing_ids = set()
    for item in existing_items:
        try:
            if "id" in item:
                existing_ids.add(int(item["id"]))
        except (ValueError, TypeError):
            print(f"Warning: Skipping malformed entry in existing_items: {item}")


    items_added_count = 0
    for item_id in new_ids_to_add:
        if item_id not in existing_ids:
            # Add with name "missing" as requested
            existing_items.append({"name": "missing", "id": str(item_id)})
            existing_ids.add(item_id)
            items_added_count += 1

    try:
        with open(ITEM_NAMES_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing_items, f, indent=4)
    except Exception as e:
        print(f"Error saving new item IDs to {ITEM_NAMES_FILE}: {e}")

# --- Helper Function: Format Copper to Gold/Silver/Copper ---
def format_copper_to_gold(copper_price):
    """Converts a price in copper to a 'Xg Ys Zc' format."""
    if copper_price is None or pd.isna(copper_price): # Also check for pandas NaN
        return "N/A"
    try:
        copper_price = int(copper_price)
        gold = copper_price // 10000
        silver = (copper_price % 10000) // 100
        copper = copper_price % 100
        return f"{gold}g {silver}s {copper}c"
    except (ValueError, TypeError): # Catch TypeError for non-numeric types
        return "Invalid Price"

# --- Matplotlib Graph Drawing Function (for embedding) ---
# Global/persistent references for the graph
fig = None
figure_canvas_agg = None
ax1 = None
ax2 = None

def draw_figure_with_toolbar(canvas, fig, toolbar_canvas):
    """Draws a matplotlib figure onto a PySimpleGUI canvas and adds a toolbar."""
    global figure_canvas_agg # Ensure we modify the global reference

    # Clear previous widgets in canvas and toolbar_canvas
    for child in canvas.winfo_children():
        child.destroy()
    for child in toolbar_canvas.winfo_children():
        child.destroy()

    figure_canvas_agg = FigureCanvasTkAgg(fig, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)

    toolbar = NavigationToolbar2Tk(figure_canvas_agg, toolbar_canvas)
    toolbar.update()
    toolbar_canvas.pack(side='bottom', fill='x', expand=0)
    return figure_canvas_agg # Return the updated canvas for potential future use

def update_graph_display(item_data, historical_df, current_theme_bg):
    """
    Updates the embedded graph with new data, focusing on X-axis formatting
    and data aggregation for the current day.
    """
    global fig, ax1, ax2, figure_canvas_agg

    if fig is None:
        return

    # Clear the existing figure and recreate axes
    fig.clf() 
    ax1 = fig.add_subplot(111)
    ax2 = ax1.twinx()

    # Set background and text colors based on theme
    fig.patch.set_facecolor(current_theme_bg)
    ax1.set_facecolor(current_theme_bg)
    
    # Adjust text/tick colors based on whether theme is light or dark (heuristic)
    if current_theme_bg and (
        current_theme_bg.lower() == '#2b2b2b' or 
        current_theme_bg.lower().startswith('#3') or 
        current_theme_bg.lower().startswith('#2') or 
        current_theme_bg.lower() == 'black'
    ): 
        text_color = 'white'
        line_color_ax1 = 'lightblue'
        line_color_ax2 = 'lightgreen'
    else: 
        text_color = 'black'
        line_color_ax1 = 'blue'
        line_color_ax2 = 'green'

    ax1.tick_params(axis='x', colors=text_color)
    ax1.tick_params(axis='y', colors=line_color_ax1, labelcolor=line_color_ax1)
    ax2.tick_params(axis='y', colors=line_color_ax2, labelcolor=line_color_ax2)
    ax1.spines['bottom'].set_color(text_color)
    ax1.spines['top'].set_color(text_color)
    ax1.spines['right'].set_color(text_color)
    ax1.spines['left'].set_color(text_color)
    ax1.xaxis.label.set_color(text_color)
    ax1.yaxis.label.set_color(line_color_ax1)
    ax2.yaxis.label.set_color(line_color_ax2)

    # Apply custom formatter for the price axis (ax1)
    def gsc_formatter(x, pos):
        return format_copper_to_gold(x)

    ax1.yaxis.set_major_formatter(FuncFormatter(gsc_formatter))

    # --- Data Preparation (Always for current day, hourly aggregation) ---
    data_to_plot = historical_df.copy() 
    
    # Ensure 'Date' is datetime and 'Price', 'Quantity' are numeric
    if not data_to_plot.empty:
        # 'Date', 'Price', 'Quantity' columns are already created and populated in get_historical_commodity_data
        # We just need to ensure they are the correct dtypes and drop NaNs
        try:
            data_to_plot['Date'] = pd.to_datetime(data_to_plot['Date'], errors='coerce') 
        except Exception as e:
            data_to_plot['Date'] = pd.NaT 
        
        data_to_plot['Price'] = pd.to_numeric(data_to_plot['Price'], errors='coerce') 
        data_to_plot['Quantity'] = pd.to_numeric(data_to_plot['Quantity'], errors='coerce') 
        data_to_plot.dropna(subset=['Date', 'Price', 'Quantity'], inplace=True)

        # Ensure Date column is timezone-naive for consistent resampling
        if pd.api.types.is_datetime64_any_dtype(data_to_plot['Date']):
            if data_to_plot['Date'].dt.tz is not None:
                data_to_plot['Date'] = data_to_plot['Date'].dt.tz_localize(None)
        
        # Filter for current day and aggregate hourly
        today = datetime.datetime.now().date()
        data_to_plot = data_to_plot[data_to_plot['Date'].dt.date == today].copy()

        if not data_to_plot.empty:
            # Set 'Date' as index for resampling
            data_to_plot_indexed = data_to_plot.set_index('Date')

            # Perform resampling
            resampled_data = data_to_plot_indexed.resample('h').agg({
                'Price': 'mean',
                'Quantity': 'sum'
            })

            # Create a full hourly range for the current day
            start_of_today = datetime.datetime.combine(today, datetime.time.min)
            hourly_range = pd.date_range(start=start_of_today, periods=24, freq='h')
            
            # Reindex to ensure all 24 hours are present
            data_to_plot = resampled_data.reindex(hourly_range).reset_index()
            data_to_plot = data_to_plot.rename(columns={'index': 'Date'}) # reindex renames the index column to 'index'
        else:
            data_to_plot = pd.DataFrame(columns=['Date', 'Price', 'Quantity']) # Explicitly empty it with expected columns
    else: # If data_to_plot was empty from the start
        data_to_plot = pd.DataFrame(columns=['Date', 'Price', 'Quantity']) # Explicitly empty it with expected columns

    # Always apply hourly formatter and locators
    date_form = mdates.DateFormatter('%I:%M %p') # e.g., "03:00 PM"
    major_locator = mdates.HourLocator(interval=3) # Every 3 hours
    minor_locator = mdates.HourLocator(interval=1) # Every hour

    ax1.xaxis.set_major_formatter(date_form)
    ax1.xaxis.set_major_locator(major_locator)
    ax1.xaxis.set_minor_locator(minor_locator)
    
    fig.autofmt_xdate() # Auto-formats date labels to prevent overlap
    
    if item_data and item_data['name'] != "Blank": # Plot actual data if provided
        fig.suptitle(f"Market Data for {item_data['name']} (Current Day View)", color=text_color) # Updated title
        if not data_to_plot.empty: # Check if there's data after potential filtering/aggregation
            # Plot directly without dropping NaNs, so all 24 hours are represented
            # ADDED MARKERS HERE: marker='o'
            line1, = ax1.plot(data_to_plot['Date'], data_to_plot['Price'], color=line_color_ax1, label='Lowest Price', marker='o')
            line2, = ax2.plot(data_to_plot['Date'], data_to_plot['Quantity'], color=line_color_ax2, linestyle='--', label='Volume', marker='o')
            
            # Filter out NaN values for the legend to only show labels for actual data
            legend_handles = []
            legend_labels = []
            if not data_to_plot['Price'].dropna().empty:
                legend_handles.append(line1)
                legend_labels.append('Lowest Price')
            if not data_to_plot['Quantity'].dropna().empty:
                legend_handles.append(line2)
                legend_labels.append('Volume')

            if legend_handles:
                fig.legend(handles=legend_handles, loc="upper left", bbox_to_anchor=(0.1, 0.9), frameon=False,
                           labels=legend_labels,
                           labelcolor=[line_color_ax1, line_color_ax2])
            
        else:
            ax1.text(0.5, 0.5, "No historical data to display for this period.", horizontalalignment='center',
                     verticalalignment='center', transform=ax1.transAxes, color=text_color, fontsize=14)
    else: # Draw blank graph
        ax1.text(0.5, 0.5, "Double-click an item to view its historical data", horizontalalignment='center',
                 verticalalignment='center', transform=ax1.transAxes, color=text_color, fontsize=12)
        fig.suptitle("Historical Market Data", color=text_color)

    ax1.set_xlabel('Time of Day') # Changed label to reflect hourly view
    ax1.set_ylabel('Lowest Price', color=line_color_ax1)
    ax2.set_ylabel('Volume', color=line_color_ax2)
    
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    if figure_canvas_agg: # Ensure canvas exists before drawing
        figure_canvas_agg.draw()

# --- WoW API Client Class (Moved to before main_app) ---
class WoWAPIClient:
    def __init__(self, client_id, client_secret, region="us", locale="en_US"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region
        self.locale = locale
        self.access_token = None
        self._last_token_refresh = None
        self._token_expires_in = 0

        self.COMMODITIES_API_ENDPOINT = f"https://{self.region}.api.blizzard.com/data/wow/auctions/commodities"
        self.WOW_TOKEN_API_ENDPOINT = f"https://{self.region}.api.blizzard.com/data/wow/token/index"

        self.DYNAMIC_NAMESPACE = f"dynamic-{self.region}"

        self.item_name_cache = {}
        self._new_item_ids_to_add = set()
        self._load_item_names_cache()

    def _load_item_names_cache(self):
        """Loads item ID to name mapping from a local JSON file."""
        try:
            with open(ITEM_NAMES_FILE, 'r', encoding='utf-8') as f:
                raw_item_list = json.load(f)
                
                self.item_name_cache = {}
                for item in raw_item_list:
                    try:
                        item_id = int(item.get("id"))
                        item_name = item.get("name")
                        if item_id is not None and item_name is not None:
                            self.item_name_cache[item_id] = item_name
                    except (ValueError, TypeError):
                        print(f"Warning: Skipping malformed entry in {ITEM_NAMES_FILE}: {item}")
                
            print(f"Loaded {len(self.item_name_cache)} item names from {ITEM_NAMES_FILE}")
        except FileNotFoundError:
            print(f"Warning: {ITEM_NAMES_FILE} not found. Starting with empty name cache.")
            self.item_name_cache = {}
        except json.JSONDecodeError:
            print(f"Error decoding {ITEM_NAMES_FILE}. Please check its format. Starting with empty name cache.")
            self.item_name_cache = {}
        except Exception as e:
            print(f"An unexpected error occurred loading item names: {e}. Starting with empty name cache.")
            self.item_name_cache = {}

    def get_new_item_ids_to_add(self):
        """Returns the set of new item IDs found during the session."""
        return self._new_item_ids_to_add

    def _should_refresh_token(self):
        if not self.access_token:
            return True
        if (datetime.datetime.now() - self._last_token_refresh).total_seconds() >= (self._token_expires_in - 300):
            return True
        return False

    def get_access_token(self):
        if not self._should_refresh_token():
            return self.access_token

        token_url = f"https://{self.region}.battle.net/oauth/token"
        try:
            auth_response = requests.post(token_url,
                                          data={"grant_type": "client_credentials"},
                                          auth=(self.client_id, self.client_secret))
            auth_response.raise_for_status()
            token_data = auth_response.json()
            self.access_token = token_data["access_token"] 
            self._token_expires_in = token_data["expires_in"]
            self._last_token_refresh = datetime.datetime.now()
            return self.access_token
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get access token: {e}")

    def _make_api_request(self, url, namespace):
        if not self.access_token:
            self.get_access_token()

        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {"namespace": namespace, "locale": self.locale}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error {e.response.status_code} for {url}: {e.response.text}")
            raise
        except requests.exceptions.ConnectionError as e:
            print(f"Connection Error for {url}: {e}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred for {url}: {e}")
            raise

    def get_item_display_name(self, item_id):
        """
        Retrieves item name from cache. If not found, adds to a list for later saving
        and returns "missing" as the name for the DataFrame.
        """
        name = self.item_name_cache.get(item_id)
        if name:
            return name
        else:
            self._new_item_ids_to_add.add(item_id)
            return "missing"

    def get_current_commodity_data(self):
        """Fetches current commodity auction data and processes it into a DataFrame."""
        print(f"Fetching current commodities from: {self.COMMODITIES_API_ENDPOINT}")
        data = self._make_api_request(self.COMMODITIES_API_ENDPOINT, self.DYNAMIC_NAMESPACE)
        auctions = data.get("auctions", [])

        processed_data = []
        for auction in auctions:
            item_id = auction['item']['id']
            buyout = auction.get('buyout')
            unit_price = auction.get('unit_price')
            quantity = auction.get('quantity')

            # Use unit_price if available, otherwise buyout. This represents the effective price.
            effective_price_copper = unit_price if unit_price is not None else buyout

            if effective_price_copper is not None: # Ensure price is not None
                processed_data.append({
                    'item_id': item_id,
                    'effective_price_copper': effective_price_copper,
                    'quantity': quantity,
                    'last_updated': datetime.datetime.now()
                })

        if not processed_data:
            return pd.DataFrame()

        df = pd.DataFrame(processed_data)

        df_aggregated = df.groupby('item_id').agg(
            # Calculate the minimum price instead of the average price
            lowest_price_today=('effective_price_copper', lambda x: x.dropna().min() if not x.dropna().empty else np.nan),
            volume_today=('quantity', 'sum'),
            last_updated=('last_updated', 'max')
        ).reset_index()

        df_aggregated['name'] = df_aggregated['item_id'].apply(self.get_item_display_name)
        
        # Ensure that rows with NaN prices or volumes are dropped, as they are not valid for display
        df_aggregated = df_aggregated.dropna(subset=['lowest_price_today', 'volume_today'])
        
        # Ensure item names are not empty or just whitespace
        df_aggregated = df_aggregated[df_aggregated['name'].str.strip() != '']

        df_aggregated = df_aggregated.sort_values(by='name').reset_index(drop=True)

        # Rename the price column to match the new aggregation logic
        df_aggregated = df_aggregated.rename(columns={'lowest_price_today': 'current_price'})

        return df_aggregated


    def get_wow_token_price(self):
        """Fetches the current WoW Token price from the API."""
        print(f"Fetching WoW Token price from: {self.WOW_TOKEN_API_ENDPOINT}")
        try:
            data = self._make_api_request(self.WOW_TOKEN_API_ENDPOINT, self.DYNAMIC_NAMESPACE)
            token_price_copper = data.get('price')
            if token_price_copper is not None:
                return int(token_price_copper)
            return None
        except Exception as e:
            print(f"Error fetching WoW Token price: {e}")
            return None

    def get_historical_commodity_data(self, item_id):
        """
        Retrieves historical data for a specific item_id from the historical_data.json file.
        This function now expects historical_data.json to contain only current day's data.
        """
        all_historical_data = load_historical_data()
        
        filtered_data = [
            entry for entry in all_historical_data 
            if entry.get('item_id') == item_id and 
               entry.get('price') is not None and 
               entry.get('quantity') is not None and
               entry.get('timestamp') is not None
        ]

        if not filtered_data:
            return pd.DataFrame()

        # Convert to DataFrame
        historical_df = pd.DataFrame(filtered_data)
        # The 'Date', 'Price', 'Quantity' columns are now created directly here
        # to ensure they exist before being used in update_graph_display
        historical_df['Date'] = pd.to_datetime(historical_df['timestamp'])
        historical_df['Price'] = historical_df['price']
        historical_df['Quantity'] = historical_df['quantity']
        
        # Sort by date to ensure correct plotting order
        historical_df = historical_df.sort_values(by='Date').reset_index(drop=True)

        return historical_df[['Date', 'Price', 'Quantity', 'timestamp', 'item_id']] # Include original columns for consistency


# --- API Key Input Layout ---
def get_api_keys_layout(client_id, client_secret):
    return [
        [sg.Text("Enter your Blizzard Battle.net API Client ID and Secret:", font=('Arial', 12))],
        [sg.Text("You can get these from Blizzard Developer Portal", font=('Arial', 10), text_color='blue', enable_events=True, key='-BLIZZARD_PORTAL-')],
        [sg.Text("Client ID:", font=('Arial', 12)), sg.Input(default_text=client_id, key='-CLIENT_ID-', password_char='*', font=('Arial', 12))],
        [sg.Text("Client Secret:", font=('Arial', 12)), sg.Input(default_text=client_secret, key='-CLIENT_SECRET-', password_char='*', font=('Arial', 12))],
        [sg.Button("Save API Keys", key='-SAVE_API_KEYS-', font=('Arial', 12))]
    ]

# --- Main Application Logic ---
def main_app():
    global fig, figure_canvas_agg, ax1, ax2 # Declare globals for modification

    config = load_config()
    client_id = config.get("CLIENT_ID", "")
    client_secret = config.get("CLIENT_SECRET", "")
    
    api_client = WoWAPIClient(client_id, client_secret)

    # Updated DataFrame columns to reflect lowest price instead of average
    df_commodities = pd.DataFrame(columns=['name', 'item_id', 'current_price', 'volume_today', 'last_updated']) 
    df_commodities_filtered = pd.DataFrame() # New DataFrame to hold filtered data for the table

    current_table_display_data = [] 
    current_commodity_count = "0"
    current_wow_token_price = "N/A"
    current_status_message = ""
    current_status_color = 'green'

    # Updated table header to reflect lowest price
    table_headers = ['Item Name', 'Lowest Price (G/S/C)', 'Volume (Today)'] 

    # Set default theme to TealMono
    current_theme = config.get("LAST_THEME", "TealMono")
    sg.theme(current_theme) 

    # --- MAIN LAYOUT DEFINITION (Centralized for Recreation) ---
    def get_main_layout():
        return [
            [sg.Frame("Blizzard API Configuration", get_api_keys_layout(client_id, client_secret), expand_x=True, font=('Arial', 14, 'bold'))],
            [sg.HSeparator()],
            [sg.Text("WoW Auction House Commodity Data", font=('Arial', 18, 'bold'), expand_x=True, justification='center')],
            [sg.Column([
                [sg.Text("Total Commodity Types: ", font=('Arial', 12, 'bold')), sg.Text(current_commodity_count, size=(5,1), key='-COMMODITY_COUNT-', font=('Arial', 12))],
                [sg.Text("Current WoW Token Price:", font=('Arial', 12, 'bold')), sg.Text(current_wow_token_price, size=(15,1), key='-WOW_TOKEN_PRICE-', font=('Arial', 12))],
            ]),
            sg.Push(),
            [sg.Button("Refresh Data", key='-REFRESH_DATA-', font=('Arial', 12)),
            sg.Button("Toggle Dark Mode", key='-TOGGLE_DARK_MODE-', font=('Arial', 12))]
            ],
            [sg.Text(current_status_message, size=(40, 1), key='-STATUS_MESSAGE-', font=('Arial', 10), text_color=current_status_color)],
            # NEW: Search bar added here, just above the table
            [sg.Text("Search:", font=('Arial', 12)), sg.Input(size=(30, 1), enable_events=True, key='-SEARCH_INPUT-', font=('Arial', 12)), sg.Push()],
            [sg.Table(values=current_table_display_data, headings=table_headers,
                    auto_size_columns=True, display_row_numbers=False,
                    justification='left', key='-COMMODITY_TABLE-',
                    enable_events=True, # Keep this for row clicks (event is just the key string)
                    enable_click_events=True, # Enable header click events (event is a tuple)
                    select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                    vertical_scroll_only=False,
                    expand_x=True, expand_y=True,
                    font=('Arial', 11),
                    header_font=('Arial', 12, 'bold'),
                    right_click_menu=['&Table', ['Copy Table', '---', 'Copy Item ID', 'Save Table to CSV::CSV']]
                    )],
            [sg.HorizontalSeparator()], 
            # Removed Graph View Options frame
            [sg.Canvas(key='-MAIN_GRAPH_CANVAS-', size=(800, 600), expand_x=True, expand_y=True)], 
            [sg.Canvas(key='-MAIN_TOOLBAR_CANVAS-', expand_x=True)], 
            [sg.Button("Exit", key='-EXIT-', font=('Arial', 12))]
        ]

    # Initialize the main window
    main_window = sg.Window("WoW AH Monitor", get_main_layout(), resizable=True, finalize=True)

    # State variable for currently selected item for graph
    selected_item_for_graph = {"name": "Blank", "item_id": None}

    # Initial setup for the embedded graph
    fig = plt.Figure(figsize=(8, 6), dpi=100) 
    figure_canvas_agg = draw_figure_with_toolbar(
        main_window['-MAIN_GRAPH_CANVAS-'].TKCanvas, 
        fig, 
        main_window['-MAIN_TOOLBAR_CANVAS-'].TKCanvas
    )
    update_graph_display(selected_item_for_graph, pd.DataFrame(), sg.theme_background_color())

    # --- Search Bar Logic Variables ---
    last_key_press_time = datetime.datetime.now() # Initialize to current time
    SEARCH_DEBOUNCE_MS = 500  # Time in milliseconds to wait after last key press
    current_search_query = "" # Holds the text from the search input field
    last_applied_search_query = None # Holds the query that was actually applied to the filter

    # --- Table Sorting State Variables ---
    # Default sort: by name, ascending. 'name' is column 0, 'current_price' is column 1 (in df_commodities_filtered)
    current_sort_column_key = 'name' # Can be 'name', 'current_price', or 'volume_today'
    current_sort_ascending = True     # True for ascending, False for descending

    # --- Helper to update the table display applying current sort ---
    def update_table_display_with_sort():
        nonlocal current_table_display_data

        if df_commodities_filtered.empty:
            current_table_display_data = []
        else:
            # Create a sorted copy for display
            # Ensure 'current_price' and 'volume_today' are numeric for proper sorting
            # Use .loc to avoid SettingWithCopyWarning if df_commodities_filtered is a slice
            df_temp_sorted = df_commodities_filtered.copy()
            df_temp_sorted['current_price'] = pd.to_numeric(df_temp_sorted['current_price'], errors='coerce')
            df_temp_sorted['volume_today'] = pd.to_numeric(df_temp_sorted['volume_today'], errors='coerce')
            
            df_display_sorted = df_temp_sorted.sort_values(
                by=current_sort_column_key,
                ascending=current_sort_ascending
            ).copy()

            current_table_display_data = []
            for _, row in df_display_sorted.iterrows():
                item_id = row['item_id']
                display_name = row['name']
                if display_name == "missing":
                    display_name = str(item_id)
                formatted_price = format_copper_to_gold(row['current_price'])
                current_table_display_data.append([display_name, formatted_price, row['volume_today']])
        
        main_window['-COMMODITY_TABLE-'].update(values=current_table_display_data)


    # --- Filtering Function ---
    def apply_search_filter(query):
        nonlocal current_table_display_data, df_commodities_filtered, last_applied_search_query, \
                   current_sort_column_key, current_sort_ascending

        # Always reset to default sort (by name, ascending) when search changes or is applied
        current_sort_column_key = 'name'
        current_sort_ascending = True

        if df_commodities.empty:
            df_commodities_filtered = pd.DataFrame()
        elif query:
            # Split the query by commas, strip whitespace, and filter out empty strings
            search_terms = [term.strip() for term in query.split(',') if term.strip()]
            
            if not search_terms: # If no valid terms after splitting
                df_commodities_filtered = df_commodities.copy()
            else:
                # Construct a regex pattern for ORing multiple whole-word searches
                # \b ensures whole word match, re.escape handles special regex characters in terms
                # re.IGNORECASE makes the regex match case-insensitively
                regex_patterns = [r'\b' + re.escape(term) + r'\b' for term in search_terms]
                combined_regex = '|'.join(regex_patterns)
                
                # Apply the combined regex to filter the DataFrame
                df_commodities_filtered = df_commodities[
                    df_commodities['name'].str.contains(combined_regex, case=False, na=False, regex=True)
                ].copy()
        else:
            df_commodities_filtered = df_commodities.copy() # If query is empty, show all

        # After filtering, update the table display with the default sort applied
        update_table_display_with_sort()
        last_applied_search_query = query

    # --- WoW Token Refresh Function ---
    def update_wow_token_display():
        nonlocal current_wow_token_price, current_status_message, current_status_color, last_wow_token_refresh_time
        try:
            token_price = api_client.get_wow_token_price()
            if token_price is not None:
                current_wow_token_price = format_copper_to_gold(token_price)
                main_window['-WOW_TOKEN_PRICE-'].update(current_wow_token_price)
                last_wow_token_refresh_time = datetime.datetime.now() # Update timestamp on successful fetch
            else:
                # Keep existing price if error, just update status
                current_status_message = "Error fetching WoW Token price."
                current_status_color = 'orange'
                main_window['-STATUS_MESSAGE-'].update(current_status_message, text_color=current_status_color)
        except Exception as e:
            current_status_message = f"Error updating WoW Token: {e}"
            current_status_color = 'red'
            main_window['-STATUS_MESSAGE-'].update(current_status_message, text_color=current_status_color)

    # --- Automatic Refresh Logic ---
    def calculate_next_refresh_timeout_ms():
        """Calculates milliseconds until the next whole hour."""
        now = datetime.datetime.now()
        # Calculate next whole hour
        next_hour = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
        
        # If it's already past the current hour's "on the hour" mark, schedule for the next one
        if now.minute >= 0 or now.second > 0 or now.microsecond > 0:
             if now.minute == 0 and now.second == 0 and now.microsecond == 0:
                 # If we are *exactly* on the hour, next refresh is 1 hour from now
                 next_hour = now + datetime.timedelta(hours=1)
             else:
                 # Otherwise, it's the next full hour
                 next_hour = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
        
        # Calculate difference in seconds
        time_until_next_hour = (next_hour - now).total_seconds()
        
        # Minimum timeout to ensure it doesn't try to go negative or too small
        # Cap at 5 seconds minimum to avoid high CPU usage with very short timeouts
        timeout_ms = max(5000, int(time_until_next_hour * 1000)) 
        
        return timeout_ms

    last_auto_refresh_time = None # Initialize to None to allow immediate check/refresh if needed
    last_wow_token_refresh_time = None # New: Initialize for WoW Token refresh
    WOW_TOKEN_REFRESH_INTERVAL_MINS = 10 # New: 10-minute interval for WoW Token

    # New: Track the last date data was archived
    last_archive_date_str = config.get("last_archive_date")
    last_archive_date = None
    if last_archive_date_str:
        try:
            last_archive_date = datetime.date.fromisoformat(last_archive_date_str)
        except ValueError:
            print(f"Warning: Invalid last_archive_date in config: {last_archive_date_str}. Resetting.")
            last_archive_date = None

    # Function to handle data refresh and saving
    def perform_data_refresh_and_save(triggered_by_auto_refresh=False):
        nonlocal df_commodities, df_commodities_filtered, current_table_display_data, current_commodity_count, \
                   current_status_message, current_status_color, last_auto_refresh_time, selected_item_for_graph, \
                   config, last_archive_date # Added config and last_archive_date to nonlocal
        
        if not api_client.client_id or not api_client.client_secret:
            current_status_message = "Please save your API Client ID and Secret first!"
            current_status_color = 'red'
            main_window['-STATUS_MESSAGE-'].update(current_status_message, text_color=current_status_color)
            return

        current_status_message = "Refreshing data..."
        current_status_color = 'blue'
        main_window['-STATUS_MESSAGE-'].update(current_status_message, text_color=current_status_color)
        
        try:
            df_commodities_new = api_client.get_current_commodity_data()

            # --- Archiving Logic ---
            all_existing_data_from_file = load_historical_data() # Load everything currently in HISTORICAL_DATA_FILE
            
            current_day_entries_to_keep = []
            old_entries_to_archive = []
            today = datetime.date.today()
            current_date_str = today.isoformat()

            for entry in all_existing_data_from_file:
                try:
                    entry_timestamp_str = entry.get('timestamp')
                    if entry_timestamp_str:
                        entry_date = datetime.datetime.fromisoformat(entry_timestamp_str).date()
                        if entry_date == today:
                            current_day_entries_to_keep.append(entry)
                        else:
                            old_entries_to_archive.append(entry)
                except (ValueError, TypeError) as e:
                    print(f"Warning: Skipping malformed historical entry during archiving: {entry}. Error: {e}")

            # Check if a new day has started since the last archiving operation
            should_archive_now = False
            if last_archive_date is None: # First run or config missing
                should_archive_now = True
            elif today > last_archive_date: # New day
                should_archive_now = True

            if should_archive_now and old_entries_to_archive:
                append_to_cold_storage(old_entries_to_archive)
                config["last_archive_date"] = current_date_str # Update the last archived date in config
                save_config(config)
                last_archive_date = today # Update the nonlocal variable

            # --- End Archiving Logic ---

            if not df_commodities_new.empty:
                df_commodities = df_commodities_new # Update the main commodities DataFrame
                
                # After data refresh, apply search filter which also resets sort to default
                apply_search_filter(current_search_query) 

                current_commodity_count = str(len(df_commodities))
                main_window['-COMMODITY_COUNT-'].update(current_commodity_count)
                
                # Update status message with refresh time
                refresh_type = "Auto" if triggered_by_auto_refresh else "Manual"
                current_status_message = f"{refresh_type} data refreshed successfully! ({datetime.datetime.now().strftime('%I:%M:%S %p')})"
                current_status_color = 'green'
                main_window['-STATUS_MESSAGE-'].update(current_status_message, text_color=current_status_color)

                if triggered_by_auto_refresh:
                    last_auto_refresh_time = datetime.datetime.now() # Record successful auto-refresh time

                # Add new entries from the current API fetch
                new_historical_entries_from_api = []
                for _, row in df_commodities.iterrows():
                    item_id = row['item_id']
                    current_price = row['current_price'] # Use 'current_price' for historical saving
                    current_quantity = row['volume_today']

                    new_historical_entries_from_api.append({
                        'timestamp': datetime.datetime.now().isoformat(),
                        'item_id': item_id,
                        'price': current_price,
                        'quantity': current_quantity
                    })
                
                # Combine current day's data from file with newly fetched data
                final_data_for_main_file = current_day_entries_to_keep + new_historical_entries_from_api
                save_historical_data(final_data_for_main_file)

                # --- MODIFIED: Clear graph and reset selected item on refresh ---
                selected_item_for_graph = {"name": "Blank", "item_id": None}
                update_graph_display(selected_item_for_graph, pd.DataFrame(), sg.theme_background_color())
                main_window['-STATUS_MESSAGE-'].update(f"{refresh_type} data refreshed. Please select an item to view its graph.", text_color='green')
                # --- END MODIFIED ---


            else:
                # No data from API, clear main file and graph
                save_historical_data([]) # Clear main historical data file
                df_commodities = pd.DataFrame()
                apply_search_filter("") # Clear table if no data
                current_commodity_count = "0"
                main_window['-COMMODITY_COUNT-'].update(current_commodity_count)
                current_status_message = "No auction data found. Server might be down or API issue."
                current_status_color = 'orange'
                main_window['-STATUS_MESSAGE-'].update(current_status_message, text_color=current_status_color)
                # Clear graph if no data
                update_graph_display({"name": "Blank", "item_id": None}, pd.DataFrame(), sg.theme_background_color())


            # Manually trigger WoW Token display update here (part of full refresh)
            update_wow_token_display()

        except requests.exceptions.HTTPError as e:
            current_status_message = f"API Error during refresh (HTTP {e.response.status_code}): {e.response.text}"
            current_status_color = 'red'
            main_window['-STATUS_MESSAGE-'].update(current_status_message, text_color=current_status_color)
        except requests.exceptions.ConnectionError as e:
            current_status_message = f"Network Error during refresh: {e}"
            current_status_color = 'red'
            main_window['-STATUS_MESSAGE-'].update(current_status_message, text_color=current_status_color)
        except Exception as e:
            current_status_message = f"An unexpected error occurred during refresh: {e}"
            current_status_color = 'red'
            main_window['-STATUS_MESSAGE-'].update(current_status_message, text_color=current_status_color)

    # Initial Data Load and Token Price Fetch (Adjusted for new archiving logic)
    # Perform initial data separation and archiving on startup
    all_existing_data_on_startup = load_historical_data()
    current_day_entries_on_startup = []
    old_entries_to_archive_on_startup = []
    today_on_startup = datetime.date.today()
    current_date_str_on_startup = today_on_startup.isoformat()

    for entry in all_existing_data_on_startup:
        try:
            entry_timestamp_str = entry.get('timestamp')
            if entry_timestamp_str:
                entry_date = datetime.datetime.fromisoformat(entry_timestamp_str).date()
                if entry_date == today_on_startup:
                    current_day_entries_on_startup.append(entry)
                else:
                    old_entries_to_archive_on_startup.append(entry)
        except (ValueError, TypeError) as e:
            print(f"Warning: Skipping malformed historical entry during startup archiving: {entry}. Error: {e}")

    should_archive_on_startup = False
    if last_archive_date is None:
        should_archive_on_startup = True
    elif today_on_startup > last_archive_date:
        should_archive_on_startup = True

    if should_archive_on_startup and old_entries_to_archive_on_startup:
        append_to_cold_storage(old_entries_to_archive_on_startup)
        config["last_archive_date"] = current_date_str_on_startup
        save_config(config)
        last_archive_date = today_on_startup # Update the nonlocal variable

    # Now, save only current day's data back to HISTORICAL_DATA_FILE for initial state
    save_historical_data(current_day_entries_on_startup)

    # Then proceed with the first API refresh for the current day's data
    if client_id and client_secret:
        perform_data_refresh_and_save(triggered_by_auto_refresh=False) 
        last_auto_refresh_time = datetime.datetime.now()
        # last_wow_token_refresh_time is already updated by update_wow_token_display call within perform_data_refresh_and_save

    # Calculate initial timeout for the first hourly refresh
    next_timeout_ms = calculate_next_refresh_timeout_ms()

    # --- Main Event Loop ---
    while True:
        # Determine the smallest timeout needed for either auto-refresh or search debounce
        now = datetime.datetime.now()
        
        # Calculate remaining time for search debounce
        search_time_since_last_key = (now - last_key_press_time).total_seconds() * 1000
        remaining_debounce_time = max(0, SEARCH_DEBOUNCE_MS - int(search_time_since_last_key))

        # Calculate remaining time for WoW Token refresh
        if last_wow_token_refresh_time:
            time_since_last_token_refresh = (now - last_wow_token_refresh_time).total_seconds()
            remaining_token_time = max(0, (WOW_TOKEN_REFRESH_INTERVAL_MINS * 60) - time_since_last_token_refresh)
            next_token_timeout_ms = int(remaining_token_time * 1000)
        else:
            next_token_timeout_ms = 0 # If never refreshed, trigger immediately

        # The actual timeout for window.read() should be the minimum of all relevant timers
        # Ensure it's never zero or negative in case of very quick events
        current_read_timeout_ms = min(next_timeout_ms, remaining_debounce_time + 10, next_token_timeout_ms + 10)

        # Ensure a minimum timeout to prevent excessive CPU usage
        if current_read_timeout_ms < 50: # Set a practical minimum, e.g., 50ms
             current_read_timeout_ms = 50

        event, values = main_window.read(timeout=current_read_timeout_ms)

        if event == sg.WIN_CLOSED or event == '-EXIT-':
            break
        
        # Handle search input events
        if event == '-SEARCH_INPUT-':
            current_search_query = values['-SEARCH_INPUT-']
            last_key_press_time = datetime.datetime.now() # Reset debounce timer
            
        # Handle TIMEOUT_KEY for all timed events
        if event == sg.TIMEOUT_KEY:
            now = datetime.datetime.now()

            # --- Check for Search Debounce ---
            if (current_search_query != last_applied_search_query and
                (now - last_key_press_time).total_seconds() * 1000 >= SEARCH_DEBOUNCE_MS):
                
                apply_search_filter(current_search_query)

            # --- Check for WoW Token Auto-Refresh ---
            if last_wow_token_refresh_time is None or \
               (now - last_wow_token_refresh_time).total_seconds() >= (WOW_TOKEN_REFRESH_INTERVAL_MINS * 60):
                update_wow_token_display()

            # --- Check for Commodity Data Auto-Refresh (hourly) ---
            if (last_auto_refresh_time is None or 
                (now.hour != last_auto_refresh_time.hour and now.minute == 0 and now.second < 5)):
                
                perform_data_refresh_and_save(triggered_by_auto_refresh=True)
            
            # Recalculate timeout for the next cycle after any potential refreshes
            next_timeout_ms = calculate_next_refresh_timeout_ms()


        if event == '-BLIZZARD_PORTAL-':
            webbrowser.open("https://develop.battle.net/")

        if event == '-SAVE_API_KEYS-':
            new_client_id = values['-CLIENT_ID-']
            new_client_secret = values['-CLIENT_SECRET-']
            if new_client_id and new_client_secret:
                config["CLIENT_ID"] = new_client_id
                config["CLIENT_SECRET"] = new_client_secret
                save_config(config)
                api_client.client_id = new_client_id
                api_client.client_secret = new_client_secret
                api_client.access_token = None
                sg.popup_ok("API Keys saved successfully!")
                perform_data_refresh_and_save(triggered_by_auto_refresh=False) # This will also update the token
                last_auto_refresh_time = datetime.datetime.now()
                # last_wow_token_refresh_time is already updated by update_wow_token_display call within perform_data_refresh_and_save
                next_timeout_ms = calculate_next_refresh_timeout_ms()
                apply_search_filter(current_search_query) 
            else:
                sg.popup_error("Please enter both Client ID and Client Secret.")

        if event == '-REFRESH_DATA-':
            perform_data_refresh_and_save(triggered_by_auto_refresh=False) # This will also update the token
            next_timeout_ms = calculate_next_refresh_timeout_ms()
            apply_search_filter(current_search_query) 
            # Save item names on refresh data button click
            save_new_item_names(api_client.get_new_item_ids_to_add())


        if event == '-TOGGLE_DARK_MODE-':
            if current_theme == "TealMono":
                new_theme = "DarkGray8"
            else:
                new_theme = "TealMono"
            
            current_theme = new_theme
            config["LAST_THEME"] = current_theme
            save_config(config)

            sg.theme(current_theme) 

            # Need to re-initialize the main window to apply theme changes to all widgets
            main_window.close() 
            
            # Recreate the window with the new theme
            main_window = sg.Window("WoW AH Monitor", get_main_layout(), resizable=True, finalize=True)
            
            # Re-establish graph on the new canvas
            fig = plt.Figure(figsize=(8, 6), dpi=100)
            figure_canvas_agg = draw_figure_with_toolbar(
                main_window['-MAIN_GRAPH_CANVAS-'].TKCanvas, 
                fig, 
                main_window['-MAIN_TOOLBAR_CANVAS-'].TKCanvas
            )
            # When recreating, ensure the graph is updated with the previously selected item and period
            update_graph_display(selected_item_for_graph, 
                                 api_client.get_historical_commodity_data(selected_item_for_graph['item_id']) if selected_item_for_graph['item_id'] else pd.DataFrame(), 
                                 sg.theme_background_color())

            # Update all elements of the new window with current data/status
            main_window['-COMMODITY_COUNT-'].update(current_commodity_count)
            main_window['-WOW_TOKEN_PRICE-'].update(current_wow_token_price)
            main_window['-STATUS_MESSAGE-'].update(current_status_message, text_color=current_status_color)
            main_window['-SEARCH_INPUT-'].update(current_search_query) # Set search bar text
            update_table_display_with_sort() # Re-apply the current sort to the new table instance
            

        # --- Corrected Table Event Handling Logic ---
        # Handle table HEADER click events for sorting
        if isinstance(event, tuple) and len(event) == 3 and event[0] == '-COMMODITY_TABLE-' and event[1] == '+CLICKED+':
            clicked_row_index, clicked_col_index = event[2] # Unpack the tuple to get row and column
            
            if clicked_row_index == -1: # This confirms it's a header click
                # Column index 0 is 'Item Name' (DataFrame column 'name')
                # Column index 1 is 'Lowest Price (G/S/C)' (DataFrame column 'current_price')
                # Column index 2 is 'Volume (Today)' (DataFrame column 'volume_today')

                if clicked_col_index == 1: # 'Lowest Price (G/S/C)' column
                    if current_sort_column_key == 'current_price':
                        # If already sorting by price, toggle direction
                        current_sort_ascending = not current_sort_ascending
                    else:
                        # If not currently sorting by price, start sorting by price ascending
                        current_sort_column_key = 'current_price'
                        current_sort_ascending = True
                    
                    update_table_display_with_sort()
                elif clicked_col_index == 0: # 'Item Name' column
                    if current_sort_column_key == 'name':
                        # If already sorting by name, toggle direction
                        current_sort_ascending = not current_sort_ascending
                    else:
                        # If not currently sorting by name, switch to name ascending
                        current_sort_column_key = 'name'
                        current_sort_ascending = True
                    update_table_display_with_sort()
                elif clicked_col_index == 2: # 'Volume (Today)' column
                    if current_sort_column_key == 'volume_today':
                        # If already sorting by volume, toggle direction
                        current_sort_ascending = not current_sort_ascending
                    else:
                        # If not currently sorting by volume, start sorting by volume ascending
                        current_sort_column_key = 'volume_today'
                        current_sort_ascending = True
                    update_table_display_with_sort()
                else:
                    # If any other header is clicked, revert to default sort (name ascending)
                    if current_sort_column_key != 'name' or not current_sort_ascending:
                        current_sort_column_key = 'name'
                        current_sort_ascending = True
                        update_table_display_with_sort()

        # Handle table ROW selection events (for graphing/selection)
        # This event occurs when a row is selected/clicked.
        # It's a simple string event, and `values['-COMMODITY_TABLE-']` contains the selected row indices.
        # This condition is now an `elif` to ensure it's only processed if it wasn't a header click.
        elif event == '-COMMODITY_TABLE-':
            selected_row_indices = values['-COMMODITY_TABLE-'] 
            if not selected_row_indices: # No row selected, clear graph
                selected_item_for_graph = {"name": "Blank", "item_id": None}
                update_graph_display(selected_item_for_graph, pd.DataFrame(), sg.theme_background_color())
                main_window['-STATUS_MESSAGE-'].update("No item selected for graph.", text_color='orange')
                continue

            row_index_in_df = selected_row_indices[0] 
            
            # IMPORTANT: Use df_commodities_filtered for selection, not df_commodities
            # Ensure we select from the *currently displayed and sorted* data
            if df_commodities_filtered.empty or row_index_in_df >= len(df_commodities_filtered):
                main_window['-STATUS_MESSAGE-'].update("No data or invalid row selected for graph.", text_color='orange')
            else:
                # Get the item from the currently sorted/filtered DataFrame
                # Re-sort just to be absolutely sure the index matches the visual table
                # Ensure 'current_price' and 'volume_today' are numeric for proper sorting
                df_temp_sorted_for_selection = df_commodities_filtered.copy()
                df_temp_sorted_for_selection['current_price'] = pd.to_numeric(df_temp_sorted_for_selection['current_price'], errors='coerce')
                df_temp_sorted_for_selection['volume_today'] = pd.to_numeric(df_temp_sorted_for_selection['volume_today'], errors='coerce')

                df_display_sorted = df_temp_sorted_for_selection.sort_values(
                    by=current_sort_column_key,
                    ascending=current_sort_ascending
                )
                # Update selected_item_for_graph global
                selected_item_for_graph = df_display_sorted.iloc[row_index_in_df].to_dict()
                item_internal_name = selected_item_for_graph.get('name', 'Unknown Item') 
                item_id = selected_item_for_graph.get('item_id')

                if not item_id:
                    main_window['-STATUS_MESSAGE-'].update(f"Could not get item ID for {item_internal_name}.", text_color='red')
                else:
                    graph_display_name = item_internal_name
                    if item_internal_name == "missing":
                        graph_display_name = f"Item {item_id}" 

                    main_window['-STATUS_MESSAGE-'].update(f"Fetching historical data for {graph_display_name}...", text_color='blue')

                    try:
                        historical_df_for_graph = api_client.get_historical_commodity_data(item_id)
                        
                        update_graph_display(
                            {"name": graph_display_name, "item_id": item_id}, 
                            historical_df_for_graph, 
                            sg.theme_background_color())

                        main_window['-STATUS_MESSAGE-'].update(f"Historical data for {graph_display_name} loaded.", text_color='green') 

                    except Exception as e:
                        main_window['-STATUS_MESSAGE-'].update(f"Error fetching historical data: {e}", text_color='red')

        # Handle right-click menu events (these are separate string events)
        if event == 'Copy Table':
            try:
                # This should copy what's currently displayed in the table (which is filtered and sorted)
                full_table_display_values = main_window['-COMMODITY_TABLE-'].get()
                selected_row_indices = values['-COMMODITY_TABLE-'] 
                if not selected_row_indices:
                    sg.popup_quick_message("No rows selected to copy.", no_titlebar=True)
                    continue

                selected_display_data = [full_table_display_values[i] for i in selected_row_indices]

                headers = table_headers
                temp_df = pd.DataFrame(selected_display_data, columns=headers)
                temp_df.to_clipboard(index=False, header=True)
                sg.popup_quick_message(f"{len(selected_display_data)} row(s) copied to clipboard!")
            except Exception as e:
                sg.popup_error(f"Error copying selected table row(s): {e}")

        if event == 'Copy Item ID':
            try:
                selected_row_indices = values['-COMMODITY_TABLE-']
                if not selected_row_indices:
                    sg.popup_quick_message("No row selected to copy ID.", no_titlebar=True)
                    continue

                selected_df_index = selected_row_indices[0]
                # IMPORTANT: Get item_id from the filtered and currently sorted DataFrame
                # Ensure 'current_price' and 'volume_today' are numeric for proper sorting
                df_temp_sorted_for_copy = df_commodities_filtered.copy()
                df_temp_sorted_for_copy['current_price'] = pd.to_numeric(df_temp_sorted_for_copy['current_price'], errors='coerce')
                df_temp_sorted_for_copy['volume_today'] = pd.to_numeric(df_temp_sorted_for_copy['volume_today'], errors='coerce')

                df_display_sorted = df_temp_sorted_for_copy.sort_values(
                    by=current_sort_column_key,
                    ascending=current_sort_ascending
                )
                item_id_to_copy = df_display_sorted.iloc[selected_df_index]['item_id']

                sg.clipboard_set(str(item_id_to_copy))
                sg.popup_quick_message(f"Item ID {item_id_to_copy} copied to clipboard!")

            except Exception as e:
                sg.popup_error(f"Error copying Item ID: {e}")

        if event == 'Save Table to CSV::CSV':
            try:
                file_path = sg.popup_save_as_file(f'wow_ah_data_{pd.Timestamp.now().strftime("%Y%m%d")}.csv',
                                                  file_types=(("CSV Files", "*.csv"), ("All Files", "*.*")))
                if file_path:
                    # Save currently displayed (filtered and sorted) table values
                    current_table_values = main_window['-COMMODITY_TABLE-'].get()
                    headers = table_headers
                    temp_df = pd.DataFrame(current_table_values, columns=headers)
                    temp_df.to_csv(file_path, index=False)
                    sg.popup_ok(f"Table saved to {file_path}")
            except Exception as e:
                sg.popup_error(f"Error saving table: {e}")

    main_window.close()
    if fig:
        plt.close(fig)

if __name__ == "__main__":
    main_app()
