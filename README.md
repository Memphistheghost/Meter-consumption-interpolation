# Meter-consumption-interpolation

# Meter Consumption Interpolation

This project provides an **interpolation application** for estimating **electricity, water, heating, and cooling consumption** based on **seasonal coefficients** and historical temperature data. The application is built with **Flask**, utilizes **Pandas** for data processing, and fetches temperature data from **DWD** (German Weather Service) and **OpenWeather API**.

## Features

- **Seasonal interpolation** of meter consumption.
- **Integration with DWD** for heating and cooling degree days.
- **Temperature-based adjustment** for seasonal consumption.
- **Excel export** of interpolated monthly data.
- **User-friendly web interface** with form-based input.

## Requirements

Ensure you have the following installed:
- Python 3.x
- Pip
- Virtual environment (optional but recommended)

## Installation

1. Clone this repository:
   ```sh
   git clone https://github.com/Memphistheghost/Meter-consumption-interpolation.git
   cd Meter-consumption-interpolation
   ```

2. (Optional) Create a virtual environment and activate it:
   ```sh
   python -m venv venv
   source venv/bin/activate  # On Mac/Linux
   venv\Scripts\activate     # On Windows
   ```

3. Install required dependencies:
   ```sh
   pip install -r requirements.txt
   ```

4. Set up your **OpenWeather API Key** (needed for historical temperature data). You can obtain one from [OpenWeather](https://openweathermap.org/). Once you have it, add it to your environment variables:
   ```sh
   export OPENWEATHER_API_KEY="your_api_key_here"  # Mac/Linux
   set OPENWEATHER_API_KEY="your_api_key_here"  # Windows
   ```

## Running the Application

1. Start the Flask app:
   ```sh
   python app.py
   ```

2. Open your browser and go to:
   ```
   http://127.0.0.1:5000
   ```

## Usage

1. Select **energy type** (Electricity, Water, Heating, or Cooling).
2. Choose a **region/city** from the dropdown.
3. Enter the **start and end date** for interpolation.
4. Provide the **annual consumption value**.
5. (Optional) Enter **building size** and **occupancy** for better accuracy.
6. Click **"Interpolation starten"** to generate results.
7. The interpolated results can be downloaded as an **Excel file**.

## API Endpoints

| Endpoint      | Method | Description |
|--------------|--------|-------------|
| `/`          | GET    | Renders the main input form |
| `/interpolate` | POST | Processes the input and returns interpolated data |

## Project Structure
```
Meter-consumption-interpolation/
│── static/
│   ├── images/
│── templates/
│   ├── index.html
│── app.py
│── requirements.txt
│── README.md
```

## Dependencies

This project uses:
- Flask (Web Framework)
- Pandas (Data Processing)
- Requests (API Calls)
- Matplotlib (Plotting, if needed)
- OpenWeather API (Temperature Data)
- DWD (German Weather Service for HDD/CDH)

## Contributing

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-name`).
3. Commit your changes (`git commit -m "Add new feature"`).
4. Push to the branch (`git push origin feature-name`).
5. Create a pull request.
