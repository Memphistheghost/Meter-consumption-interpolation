from flask import Flask, request, render_template, send_file
import pandas as pd
import requests
from io import StringIO
import matplotlib.pyplot as plt
import io
from datetime import datetime
from datetime import timedelta

app = Flask(__name__)

# Static list of available regions (cities) extracted from DWD files
available_regions = [
    'AACHEN', 'AUGSBURG', 'BERLIN', 'BREMEN', 'CHEMNITZ', 'DARMSTADT', 'DRESDEN',
    'ESSEN', 'FRANKFURT', 'FREIBURG', 'HAMBURG', 'HANNOVER', 'KARLSRUHE',
    'KIEL', 'KOELN', 'LEIPZIG', 'MAGDEBURG', 'MANNHEIM', 'MUEHLHAUSEN',
    'MUENCHEN-STADT', 'NUREMBERG', 'ROSTOCK', 'STUTTGART', 'TRIER', 'WIESBADEN'
]

# Seasonal coefficients for electricity and water (sum to 1 for proper scaling)
SEASONAL_COEFFICIENTS = {
    'electricity': [0.09, 0.09, 0.08, 0.08, 0.09, 0.10, 0.11, 0.11, 0.09, 0.08, 0.08, 0.09],  # Slight peaks in summer/winter
    'water': [0.08, 0.08, 0.08, 0.08, 0.09, 0.10, 0.11, 0.11, 0.09, 0.08, 0.08, 0.08]  # Consistent with a small summer peak
}

def adjust_coefficients_for_factors(season_type, coeffs, building_size=None, occupancy=None, cooling_factor=1.2, winter_lighting_factor=1.1):
    # Make a copy of the coefficients to avoid modifying the original
    adjusted_coeffs = coeffs[:]

    # Adjust coefficients for electricity based on building characteristics
    if season_type == 'electricity':
        # Apply cooling factor to summer months (June, July, August)
        for i in [5, 6, 7]:  # June (5), July (6), August (7)
            adjusted_coeffs[i] *= cooling_factor
        # Apply winter lighting factor to winter months (December, January, February)
        for i in [11, 0, 1]:  # December (11), January (0), February (1)
            adjusted_coeffs[i] *= winter_lighting_factor

    # Apply scaling based on building size and occupancy if both are provided
    if building_size is not None and occupancy is not None:
        scaling_factor = (building_size / 1000) * (occupancy / 100)
        adjusted_coeffs = [coeff * scaling_factor for coeff in adjusted_coeffs]

    # Normalize the coefficients to ensure they sum to 1
    total = sum(adjusted_coeffs)
    if total > 0:  # Avoid division by zero
        adjusted_coeffs = [coeff / total for coeff in adjusted_coeffs]

    return adjusted_coeffs

def adjust_coefficients_for_temperature(season_type, temperatures):
    # Adjust coefficients for heating/cooling based on temperature data
    if season_type == 'waerme':  # Heating: More consumption in colder temperatures
        return [(max(0, 18 - temp) / 18) for temp in temperatures]  # Adjust based on how much colder it is than 18°C

    elif season_type == 'kaelte':  # Cooling: More consumption in warmer temperatures
        return [(max(0, temp - 22) / 22) for temp in temperatures]  # Adjust based on how much warmer it is than 22°C

    elif season_type == 'water':  # Water: Slight increase in summer temperatures
        return [(0.8 + 0.02 * temp) for temp in temperatures]  # Simple increase based on temperature

    return [1] * len(temperatures)  # Default: No change for electricity

# Helper function to perform seasonal interpolation
def seasonal_interpolation(wert_jahr1, wert_jahr2, num_months, season_type):
    seasonal_coeffs = SEASONAL_COEFFICIENTS[season_type]
    monthly_values = []

    # Scale the annual consumption based on seasonal coefficients
    for i in range(num_months):
        monthly_value = wert_jahr1 * seasonal_coeffs[i % 12]
        monthly_values.append(monthly_value)

    # Calculate the sum of the interpolated monthly values
    total_interpolated = sum(monthly_values)

    # Adjust monthly values to match the input total (wert_jahr1)
    if total_interpolated > 0:
        scaling_factor = wert_jahr1 / total_interpolated
        monthly_values = [val * scaling_factor for val in monthly_values]

    return monthly_values

def get_historical_temperature_data(lat, lon, start_date, end_date, api_key):
    temperatures = []
    current_date = start_date
    
    # Loop through each day in the date range
    while current_date <= end_date:
        unix_timestamp = int(current_date.timestamp())
        
        url = f"http://api.openweathermap.org/data/2.5/onecall/timemachine?lat={lat}&lon={lon}&dt={unix_timestamp}&appid={api_key}&units=metric"
        
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # Extract daily average temperature (using hourly temperatures)
        daily_temps = [hour['temp'] for hour in data['hourly']]
        avg_temp = sum(daily_temps) / len(daily_temps)
        temperatures.append(avg_temp)

        # Move to the next day
        current_date += timedelta(days=1)
    
    return temperatures

# Helper function to download and parse DWD CSV for a given year/month and city name (for heating)
def get_heating_data(month, year, region):
    base_url = "https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/heating_degreedays/hdd_3807/recent/"
    file_name = f"gradtage_{year}{month:02d}.csv"
    file_url = base_url + file_name

    try:
        response = requests.get(file_url)
        response.raise_for_status()

        # Skip the first three metadata rows for heating
        try:
            data = pd.read_csv(StringIO(response.content.decode("utf-8")), delimiter=';', skiprows=3, engine='python')
        except pd.errors.ParserError:
            raise ValueError(f"Error reading the CSV file. Please check the file format for {file_name}.")

        # Search for the region (city) in the CSV
        region_data = data[data.iloc[:, 3].str.contains(region, case=False, na=False)]
        if region_data.empty:
            raise ValueError(f"No data found for region {region}")

        # Extract the heating degree days (HDD) for the region
        hdd_value = region_data.iloc[0, 6]  # Assuming the 7th column holds the HDD data
        return hdd_value

    except Exception as e:
        raise RuntimeError(f"Error fetching or parsing DWD data: {str(e)}")

# Helper function to download and parse DWD CSV for a given year/month and city name (for cooling)
def get_cooling_data(month, year, region):
    base_url = "https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/cooling_degreehours/cdh_18/recent/"
    file_name = f"kuehlgrade_18_0_{year}{month:02d}.csv"
    file_url = base_url + file_name

    try:
        response = requests.get(file_url)
        response.raise_for_status()

        # Skip the first five metadata rows for cooling
        try:
            data = pd.read_csv(StringIO(response.content.decode("utf-8")), delimiter=';', skiprows=5, engine='python')
        except pd.errors.ParserError:
            raise ValueError(f"Error reading the CSV file. Please check the file format for {file_name}.")

        # Search for the region (city) in the CSV
        region_data = data[data.iloc[:, 3].str.contains(region, case=False, na=False)]
        if region_data.empty:
            raise ValueError(f"No data found for region {region}")

        # Extract the cooling degree hours (CDH) for the region
        cdh_value = region_data.iloc[0, 7]  # Assuming the 8th column holds the CDH data
        return cdh_value

    except Exception as e:
        raise RuntimeError(f"Error fetching or parsing DWD data: {str(e)}")

# Function to perform interpolation over a range of months based on the HDD/CDH values
def saisonale_interpolation_range(wert_jahr1, wert_jahr2, gradtage_per_month):
    total_consumption = wert_jahr2 - wert_jahr1
    total_gradtage = sum(gradtage_per_month)
    consumption_per_month = []

    for gradtage in gradtage_per_month:
        month_consumption = (gradtage / total_gradtage) * total_consumption
        consumption_per_month.append(month_consumption)

    return consumption_per_month

@app.route('/')
def index():
    return render_template('index.html', regions=available_regions)

@app.route('/interpolate', methods=['POST'])
def interpolate():
    typ = request.form['typ']  # "waerme", "kaelte", "electricity", or "water"
    region = request.form['region']  # User-selected region
    start_date = datetime.strptime(request.form['start_date'], '%d.%m.%Y')
    end_date = datetime.strptime(request.form['end_date'], '%d.%m.%Y')

    # Get and convert `wert_jahr1` to float, handling empty values
    wert_jahr1 = request.form.get('wert_jahr1', '0').strip()
    try:
        wert_jahr1 = float(wert_jahr1)
    except ValueError:
        return "Error during interpolation: Invalid input for wert_jahr1. Please enter a valid number."

    # Static default values for cooling and lighting factors
    cooling_factor = 1.2
    winter_lighting_factor = 1.1

    # Get additional parameters for electricity and water with default values if empty
    building_size = request.form.get('building_size', '').strip()
    occupancy = request.form.get('occupancy', '').strip()

    try:
        # Convert building size and occupancy to float, using default values if empty
        building_size = float(building_size) if building_size else None
        occupancy = float(occupancy) if occupancy else None

        # Existing code for heating, cooling, electricity, and water interpolation
        raumtemperatur = float(request.form.get('raumtemperatur', 18)) if typ == "waerme" else 22

        # Generate list of months between start and end dates
        months = pd.date_range(start=start_date, end=end_date, freq='M').strftime("%m").tolist()
        years = pd.date_range(start=start_date, end=end_date, freq='M').year.tolist()
        num_months = len(months)

        gradtage_per_month = []

        if typ in ["waerme", "kaelte"]:
            # Fetch the correct data for heating or cooling
            for year, month in zip(years, months):
                if typ == "waerme":
                    hdd_value = get_heating_data(int(month), int(year), region)
                    gradtage_per_month.append(hdd_value)
                elif typ == "kaelte":
                    cdh_value = get_cooling_data(int(month), int(year), region)
                    gradtage_per_month.append(cdh_value)

            # Perform interpolation for heating/cooling using only `wert_jahr1`
            total_gradtage = sum(gradtage_per_month)
            consumption_per_month = [(gradtage / total_gradtage) * wert_jahr1 for gradtage in gradtage_per_month]

        elif typ in ["electricity", "water"]:
            # Adjust coefficients and perform seasonal interpolation
            adjusted_coeffs = adjust_coefficients_for_factors(typ, SEASONAL_COEFFICIENTS[typ], building_size, occupancy, cooling_factor, winter_lighting_factor)
            consumption_per_month = seasonal_interpolation(wert_jahr1, None, num_months, typ)
            # REMOVE this line to prevent double scaling
            # consumption_per_month = [val * coeff for val, coeff in zip(consumption_per_month, adjusted_coeffs)]

        # Prepare results for download
        result_df = pd.DataFrame({
            'Year': years,
            'Month': months,
            'Interpolated Consumption (kWh or m³)': consumption_per_month
        })

        # Get current date for filename
        current_date_str = datetime.now().strftime('%y%m%d')
        file_type_name = {
            'waerme': 'Wärmemenge',
            'kaelte': 'Kältemenge',
            'electricity': 'Stromverbrauch',
            'water': 'Wasserverbrauch'
        }
        file_name = f"{current_date_str}_{file_type_name.get(typ, 'Interpolation')}.xlsx"

        # Generate and send Excel file for download
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            result_df.to_excel(writer, index=False)

        output.seek(0)
        return send_file(output, download_name=file_name, as_attachment=True)

    except Exception as e:
        return f"Error during interpolation: {e}"

if __name__ == '__main__':
    app.run(debug=True)