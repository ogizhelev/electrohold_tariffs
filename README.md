# Electrohold Tariff Sensor for Home Assistant

The **Electrohold Tariffs** integration retrieves the current regulated **day** and **night** electricity prices from the [Electrohold](https://electrohold.bg) website and exposes them as Home Assistant sensors. Prices are refreshed automatically once per day and published with Bulgarian VAT (20%) already included.

## Features

- Fetches the regulated day/night tariffs directly from the Electrohold website.
- Exposes two sensors, grouped under a single **Electrohold Tariffs** device:
  - `sensor.electrohold_tariffs_day` — day rate (`EUR/kWh`, VAT incl.)
  - `sensor.electrohold_tariffs_night` — night rate (`EUR/kWh`, VAT incl.)
- Each sensor also exposes the pre-VAT base price, the VAT rate, and the source URL as attributes.
- A single daily download is shared by both sensors (via a data update coordinator).

## Architecture

The integration follows the standard layered Home Assistant design, which keeps each
concern isolated and independently testable:

| Module | Responsibility |
| --- | --- |
| [`api.py`](custom_components/electrohold_tariffs/api.py) | Fetch (aiohttp) and parse the provider page. The parser is Home-Assistant-free and fully unit-testable. |
| [`models.py`](custom_components/electrohold_tariffs/models.py) | Immutable `ElectroholdTariffs` value object. |
| [`coordinator.py`](custom_components/electrohold_tariffs/coordinator.py) | `DataUpdateCoordinator` that fetches once and shares the result with all entities. |
| [`sensor.py`](custom_components/electrohold_tariffs/sensor.py) | Description-driven `CoordinatorEntity` sensors (VAT math + presentation). |
| [`config_flow.py`](custom_components/electrohold_tariffs/config_flow.py) | UI setup that validates the source before creating the entry. |

Adding a new tariff sensor is a matter of appending one `ElectroholdSensorEntityDescription` to `SENSOR_DESCRIPTIONS`.

## Requirements

- Home Assistant **2025.1.4** or later.

## Installation

### Option 1 — HACS (recommended)

1. In Home Assistant, go to **HACS → Custom Repositories**.
2. Add `https://github.com/ogizhelev/electrohold_tariffs` as an **Integration**.
3. Search for **Electrohold Tariffs** in HACS and click **Install**.
4. Restart Home Assistant.

### Option 2 — Manual

1. Copy the `custom_components/electrohold_tariffs/` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

This integration is configured entirely through the UI — no YAML required.

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Electrohold Tariffs** and follow the prompt.

On setup the integration verifies that the tariff page can be reached and parsed before the entry is created.

## Example: current price helper

[`template_sensor_config.yaml`](template_sensor_config.yaml) contains a template sensor that selects the day or night rate based on the current time and season.

## Development

The HA-free parsing logic is covered by tests in [`tests/`](tests/):

```bash
pip install pytest beautifulsoup4
pytest tests/
```

