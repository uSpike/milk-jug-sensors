import time
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import paho.mqtt.client as mqtt
from smbus2 import SMBus


@dataclass
class SHT30Measurement:
    temp_c: float
    temp_f: float
    humidity: float


class SHT30:
    # single-shot, clock-stretching, low repeatability
    MEASURE_CMD = bytes([0x2c, 0x10])
    # read out of status register
    STATUS_CMD = bytes([0xf3, 0x2d])

    def __init__(self, bus: SMBus, addr: int = 0x44) -> None:
        self.bus = bus
        self.addr = addr

    def _send_cmd(self, request, response_size: int = 6, delay_ms: int = 100) -> bytearray:
        self.bus.write_i2c_block_data(self.addr, request[0], request[1:])
        time.sleep(delay_ms // 1000)
        data = self.bus.read_i2c_block_data(self.addr, 0x00, response_size)
        return bytearray(data)

    def measure(self) -> SHT30Measurement:
        data = self._send_cmd(self.MEASURE_CMD, 6)
        st = data [0] << 8 | data[1]
        srh = data[3] << 8 | data[4]
        temp_c = -45 + ((st * 175) / 0xffff)
        temp_f = -49 + ((st * 347) / 0xffff)
        rh = (srh * 100.0) / 0xffff
        return SHT30Measurement(temp_c, temp_f, rh)


class W1Temp:
    def __init__(self, id_str: str) -> None:
        self.id_str = id_str


    def measure(self) -> float:
        path = Path(f'/sys/bus/w1/devices/{self.id_str}/temperature')
        temp = float(path.read_text().strip())
        return temp / 1000



bus1 = SMBus(1)
bus2 = SMBus(11)

sh_sensors = {
    "humidity1": SHT30(bus1),
    "humidity2": SHT30(bus2),
}

w1_sensors = {
    "temperature1": W1Temp('28-00000fe73a2b'),
    "temperature2": W1Temp('28-00000fe755ba'),
    "temperature3": W1Temp('28-00000fe7e6dc'),
    "temperature4": W1Temp('28-00000fe845c0'),
}

USER = os.environ["MQTT_USERNAME"]
PASS = os.environ["MQTT_PASSWORD"]
HOST = os.environ["MQTT_HOST"]

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username = USER
client.password = PASS
client.connect(HOST)

client.loop_start()
try:
    while True:
        for name, sh in sh_sensors.items():
            m = sh.measure()
            client.publish(f"nursery/jugs/{name}/temp", m.temp_c)
            client.publish(f"nursery/jugs/{name}/rh", m.humidity)
            print(f"{name}: {m}")
    
        for name, w1 in w1_sensors.items():
            m = w1.measure()
            client.publish(f"nursery/jugs/{name}/temp", m)
            print(f"{name}: {m}")

        time.sleep(60)
finally:
    client.loop_stop()

