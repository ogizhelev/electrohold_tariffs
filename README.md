# Electrohold Tariff Sensor Component for Home Assistant

The **Electrohold Tariff Sensor** is a custom Home Assistant component designed to retrieve and display the current electricity tariffs for day and night rates from the **Electrohold** website. These tariffs are fetched and updated automatically every 24 hours, and presented as sensor entities within Home Assistant for easy access and automation use.

## Features

- Fetches real-time electricity tariff data from the Electrohold website.
- Exposes two sensors:
  - Day tariff sensor (`sensor.electrohold_tariff_day`)
  - Night tariff sensor (`sensor.electrohold_tariff_night`)
- Automatically updates the tariff values every 24 hours.
- The values are processed and converted to monetary values in `BGN/kWh` ( VAT incl. ) for use within Home Assistant.

## Requirements

- Home Assistant instance (version 2025.1.4 or later recommended).
- Python 3.8+.


## Installation

You can install the **Electrohold Tariff Sensor** component in your Home Assistant environment via **HACS** (Home Assistant Community Store) for easier management and updates.

### Option 1: Install via HACS (Recommended)

1. **Add the Custom Component to HACS:**
   - Open your Home Assistant dashboard.
   - Go to **HACS** > **Custom Repositories**.
   - Enter the following URL for the custom component repository:
     ```
     https://github.com/ogizhelev/electrohold_tariffs.git
     ```

   - Type ```Integration```
   - Click **Add** to add the repository to HACS.

2. **Install the Integration:**
   - Once the repository has been added, search for **Electrohold Tariffs** in the HACS integrations page.
   - Click on the integration, and then click **Install**.

3. **Configuration in Home Assistant:**
   - After installation, open your `configuration.yaml` file located in the Home Assistant configuration directory.
   - Add the following entry under the `sensor` platform:

   ```yaml
   sensor:
     - platform: electrohold_tariffs
4. **Restart Home Assistant (requried)**


### Option 2: Install manually

1. **Download the Custom Component:**
   - Download or clone the repository containing the `electrohold_tariffs` folder.
   - Copy the folder into your Home Assistant configuration directory, specifically under `config/custom_components/electrohold_tariffs/`.

2. **Configuration in Home Assistant:**
   - Open your `configuration.yaml` file located in the Home Assistant configuration directory.
   - Add the following entry under the `sensor` platform:

   ```yaml
   sensor:
     - platform: electrohold_tariffs
3. **Restart Home Assistant (requried)**