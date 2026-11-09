# Electrohold Tariff Sensor for Home Assistant

The **Electrohold Tariffs** integration retrieves the current regulated **day** and **night** electricity prices from the [Electrohold](https://electrohold.bg) website and exposes them as Home Assistant sensors. Prices are refreshed automatically once per day and published with Bulgarian VAT (20%) already included.

## Features

- Fetches the regulated day/night tariffs directly from the Electrohold website.
- Exposes three sensors, grouped under a single **Electrohold Tariffs** device:
  - `sensor.electrohold_tariffs_day` — day rate (`EUR/kWh`, VAT incl.)
  - `sensor.electrohold_tariffs_night` — night rate (`EUR/kWh`, VAT incl.)
  - `sensor.electrohold_tariffs_current_price` — the rate that applies **right now**, automatically switching between day and night using the regulated seasonal windows (below).
- The current-price sensor also exposes `active_tariff` (day/night), `season` (summer/winter) and both the `day_price` and `night_price` as attributes; the day/night sensors expose the pre-VAT base price and VAT rate.
- A single daily download is shared by all sensors (via a data update coordinator).

### Day/night windows

The current-price sensor follows the regulated two-rate schedule (Europe/Sofia local time):

| Season | Night zone | Day zone |
| --- | --- | --- |
| Summer (01.04–31.10) | 23:00–07:00 | 07:00–23:00 |
| Winter (01.11–31.03) | 22:00–06:00 | 06:00–22:00 |

This replaces the manual template-sensor recipe that earlier versions documented.

## Architecture

The integration follows the standard layered Home Assistant design, which keeps each
concern isolated and independently testable:

| Module | Responsibility |
| --- | --- |
| [`api.py`](custom_components/electrohold_tariffs/api.py) | Fetch (aiohttp) and parse the provider page. The parser is Home-Assistant-free and fully unit-testable. |
| [`models.py`](custom_components/electrohold_tariffs/models.py) | Immutable `ElectroholdTariffs` value object. |
| [`schedule.py`](custom_components/electrohold_tariffs/schedule.py) | Home-Assistant-free day/night window rules (also unit-tested). |
| [`coordinator.py`](custom_components/electrohold_tariffs/coordinator.py) | `DataUpdateCoordinator` that fetches once and shares the result with all entities. |
| [`sensor.py`](custom_components/electrohold_tariffs/sensor.py) | Description-driven `CoordinatorEntity` sensors (VAT math + presentation). |
| [`config_flow.py`](custom_components/electrohold_tariffs/config_flow.py) | UI setup that validates the source before creating the entry. |

Adding a new fixed tariff sensor is a matter of appending one `ElectroholdSensorEntityDescription` to `TARIFF_SENSOR_DESCRIPTIONS`.

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

## Current price

Use `sensor.electrohold_tariffs_current_price` directly — it already reflects the day or night rate for the current time and season, so no template helper is needed. Its `active_tariff` and `season` attributes are handy for automations and dashboards.

## Development

The HA-free parsing logic is covered by tests in [`tests/`](tests/):

```bash
pip install pytest beautifulsoup4
pytest tests/
```

