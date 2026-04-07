# xDrip Local Bridge for Home Assistant

A 100% local, cloud-free Home Assistant integration that pulls real-time continuous glucose monitor (CGM) data directly from xDrip+ on your Android phone. 

By querying the xDrip local web server (`/pebble` endpoint), this integration completely bypasses the cloud. Your medical data stays strictly on your local network (or private Tailscale mesh), ensuring zero latency and maximum privacy.

## ✨ Features

* **Zero Cloud Dependency:** No need for Nightscout, Tidepool, or scraping commercial APIs. 
* **Rich Data Payload:** Pulls not just your Blood Glucose, but also your **Insulin on Board (IOB)**, **Carbs on Board (COB)**, and **Trend Direction**.
* **Smart Tiered Polling:** Designed to protect your phone's battery. The integration dynamically adjusts its fetch rate based on data freshness:
  * *Fresh (< 5 mins):* Sleeps exactly until the next 5-minute sensor window.
  * *Hunting (5 - 10 mins):* Polls every 15 seconds to catch the incoming reading instantly.
  * *Stale (10 - 30 mins):* Slows down to 1-minute polls if the phone is out of range.
  * *Offline (> 30 mins):* Drops to 5-minute hibernation polls to save battery until the connection is restored.
* **Tailscale Ready:** Designed to work perfectly over a Tailscale VPN, meaning Home Assistant can read your glucose even when you are out of the house on cellular data.

## ⚙️ Prerequisites

1. You must be running **xDrip+** on an Android phone.
2. In xDrip+, go to **Settings > Inter-App Settings > Local Web Server** and turn it **ON**.
3. *Optional but recommended:* Install Tailscale on both your phone and your Home Assistant server to maintain the connection when you leave the house.

## 📦 Installation (via HACS)

The easiest way to install this integration is using the [Home Assistant Community Store (HACS)](https://hacs.xyz/).

1. Open Home Assistant and navigate to **HACS**.
2. Click the three dots (top right) and select **Custom repositories**.
3. Paste the URL of this repository.
4. Select **Integration** as the category and click **Add**.
5. Search for "xDrip Local Bridge" in HACS, click **Download**, and then restart Home Assistant.

## 🚀 Configuration

Add the following to your `configuration.yaml` file. 

```yaml
sensor:
  - platform: xdrip_local
    ip_address: "192.168.X.X"  # Your phone's Local Wi-Fi or Tailscale IP
    api_secret: "your_xdrip_api_secret" # Must match the secret set in xDrip+
```

Note: If you have authentication disabled in xDrip (not recommended), you must still provide the api_secret key in the YAML, but you can leave the string empty "".

## 📊 Entities and Attributes
Once configured, the integration creates a primary sensor: sensor.macdrip_glucose.

State: The current blood glucose level in mmol/L.

Attributes:
You can extract these attributes to build custom dashboard cards or automations.

direction: The trend arrow (e.g., Flat, SingleUp, FortyFiveDown).

iob: Current Insulin on Board (extracted from companion apps or native xDrip treatments).

cob: Current Carbs on Board.

reading_age_min: Exactly how many minutes old the current data point is.

connection_status: The current state of the smart poller (Synchronized, Hunting, Stale, Offline).

## 💡 Example Automation
Flash a smart light red if your blood sugar is dropping below 4.5 mmol/L.

```YAML
alias: "Low Glucose Alert"
trigger:
  - platform: numeric_state
    entity_id: sensor.macdrip_glucose
    below: 4.5
condition:
  - condition: state
    entity_id: sensor.macdrip_glucose
    attribute: direction
    state: "SingleDown"
action:
  - service: light.turn_on
    target:
      entity_id: light.office_led
    data:
      color_name: red
      flash: short