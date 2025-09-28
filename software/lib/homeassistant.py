"""Home Assistant MQTT integration for the BSides badge.

The integration is optional and only activates when a configuration file
(`homeassistant.json`) is present on the badge filesystem.  The configuration
file should look similar to:

```
{
  "wifi": {
    "ssid": "MyNetwork",
    "password": "secret"
  },
  "mqtt": {
    "broker": "192.168.1.10",
    "port": 1883,
    "username": "mqtt_user",
    "password": "mqtt_pass",
    "discovery_prefix": "homeassistant"
  }
}
```

Both WiFi and MQTT credentials are optional – the badge will fall back to the
default BSides WiFi credentials when `wifi` is omitted.  When the file is
missing, the module silently does nothing.
"""

import json

import uasyncio as asyncio

try:
    import network
    from umqtt.simple import MQTTClient
except ImportError:
    # When running unit tests on CPython we gracefully fall back.
    network = None     # type: ignore
    MQTTClient = None  # type: ignore


_bridge = None


def initialize(device_id, state_cb, command_cb, effects_cb, wifi_defaults):
    """Initialise the Home Assistant integration.

    Returns a bridge instance (which exposes ``run()``) or ``None`` when the
    configuration file does not exist or MQTT support is unavailable.
    """

    global _bridge

    if MQTTClient is None or network is None:
        print("Home Assistant: MQTT client not available")
        return None

    try:
        with open("homeassistant.json", "r") as fp:
            config = json.load(fp)
    except OSError:
        # No configuration present – skip integration silently.
        return None

    _bridge = _HomeAssistantBridge(config, device_id, state_cb, command_cb,
                                   effects_cb, wifi_defaults)
    return _bridge


def notify_led_state():
    """Schedule a state publish when the LED parameters change."""

    if _bridge:
        _bridge.request_state_sync()


def notify_effect_list():
    """Inform Home Assistant that the list of effects has changed."""

    if _bridge:
        _bridge.request_config_sync()


class _HomeAssistantBridge:
    def __init__(self, config, device_id, state_cb, command_cb, effects_cb,
                 wifi_defaults):
        self._config = config
        self._device_id = device_id
        self._state_cb = state_cb
        self._command_cb = command_cb
        self._effects_cb = effects_cb
        self._wifi_defaults = wifi_defaults

        self._wlan = network.WLAN(network.STA_IF)
        self._client = None
        self._connected = False

        self._state_dirty = True
        self._config_dirty = True
        self._availability_sent = False

        self._command_topic = self._topic("light/set")
        self._state_topic = self._topic("light/state")
        self._availability_topic = self._topic("availability")

    def _topic(self, suffix):
        base = "bsides_badge/{}".format(self._device_id.lower())
        return "{}/{}".format(base, suffix)

    async def run(self):
        """Main worker loop."""

        while True:
            try:
                await self._ensure_connections()
                if self._client:
                    try:
                        self._client.check_msg()
                    except OSError:
                        # Mark as disconnected and try again next loop.
                        self._connected = False
                        await asyncio.sleep(1)
                        continue

                if self._config_dirty:
                    await self._publish_discovery()
                    self._config_dirty = False

                if self._state_dirty:
                    await self._publish_state()
                    self._state_dirty = False

            except Exception as exc:
                print("Home Assistant error:", exc)
                self._connected = False

            await asyncio.sleep_ms(250)

    def request_state_sync(self):
        self._state_dirty = True

    def request_config_sync(self):
        self._config_dirty = True

    async def _ensure_connections(self):
        if not self._wlan.active():
            self._wlan.active(True)

        if not self._wlan.isconnected():
            ssid, password = self._wifi_credentials()
            if ssid:
                print("Home Assistant: connecting WiFi {}".format(ssid))
                self._wlan.connect(ssid, password)
                for _ in range(40):
                    if self._wlan.isconnected():
                        break
                    await asyncio.sleep(0.25)

        if not self._wlan.isconnected():
            raise RuntimeError("WiFi connection failed")

        if not self._connected:
            self._connect_mqtt()
            self._connected = True
            self._state_dirty = True
            self._config_dirty = True
            self._availability_sent = False

    def _wifi_credentials(self):
        wifi_cfg = self._config.get("wifi", {})
        ssid = wifi_cfg.get("ssid")
        password = wifi_cfg.get("password")

        if ssid:
            return ssid, password
        return self._wifi_defaults

    def _connect_mqtt(self):
        mqtt_cfg = self._config.get("mqtt", {})
        broker = mqtt_cfg.get("broker")
        if not broker:
            raise RuntimeError("MQTT broker missing in configuration")

        port = mqtt_cfg.get("port", 1883)
        client_id = "bsides_badge_{}".format(self._device_id.lower())
        self._client = MQTTClient(client_id=client_id,
                                  server=broker,
                                  port=port,
                                  user=mqtt_cfg.get("username"),
                                  password=mqtt_cfg.get("password"),
                                  keepalive=60)
        self._client.set_callback(self._on_message)
        self._client.connect()
        self._client.subscribe(self._command_topic)
        print("Home Assistant: connected to MQTT {}:{}".format(broker, port))

    async def _publish_discovery(self):
        discovery_prefix = self._config.get("mqtt", {}).get(
            "discovery_prefix", "homeassistant")
        unique_id = "bsides_badge_{}".format(self._device_id.lower())
        topic = "{}/light/{}/config".format(discovery_prefix, unique_id)

        payload = {
            "name": "BSides Badge {}".format(self._device_id[-4:]),
            "uniq_id": unique_id,
            "cmd_t": self._command_topic,
            "stat_t": self._state_topic,
            "schema": "json",
            "brightness": True,
            "hs": True,
            "availability_topic": self._availability_topic,
            "json_attr_t": self._topic("light/attributes"),
        }

        effects = self._effects_cb() or []
        if effects:
            payload["effect"] = True
            payload["effect_list"] = effects

        self._publish(topic, json.dumps(payload))

    async def _publish_state(self):
        state = self._state_cb()
        if not state:
            return

        payload = {
            "state": "ON" if state.get("effect_index", 0) else "OFF",
            "brightness": state.get("brightness", 0),
            "hs_color": [state.get("hue", 0), state.get("saturation", 0)],
            "effect": state.get("effect_name"),
        }

        self._publish(self._state_topic, json.dumps(payload))

        attrs = {
            "speed": state.get("speed", 0),
            "effect_index": state.get("effect_index", 0),
        }
        self._publish(self._topic("light/attributes"), json.dumps(attrs))

        if not self._availability_sent:
            self._publish(self._availability_topic, "online")
            self._availability_sent = True

    def _publish(self, topic, payload):
        if not self._client:
            return
        try:
            self._client.publish(topic, payload, retain=True)
        except OSError:
            self._connected = False
            raise

    def _on_message(self, topic, msg):
        if isinstance(topic, bytes):
            topic = topic.decode()
        if isinstance(msg, bytes):
            msg = msg.decode()

        if topic != self._command_topic:
            return

        try:
            data = json.loads(msg or "{}")
        except ValueError:
            print("Home Assistant: invalid JSON command")
            return

        changed = False

        state = data.get("state")
        if state == "OFF":
            data.setdefault("effect", "Off")
        elif state == "ON":
            # no explicit effect means keep current
            pass

        if self._command_cb(data):
            changed = True

        if changed:
            self._state_dirty = True


