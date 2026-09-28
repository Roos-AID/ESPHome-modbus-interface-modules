# modbus-ESPHome-interfaces
# This repo contains modbus interfaces for Home Assistant based on ESPHome and uses a RS485 to WiFi/Zigbee Bridge (ESP32‑C6) from 
# https://elecram.com/products/esp32-c6-wifi-zigbee-to-rs485-bridge
#
# The following have been created and are used in production on my own Home Assistant dashboards
# 
# kWh meter ABB B23
#   the implementation reads the most important registers from 2 ABB B23 kWh meters with different polling intervals
#   Please note that this only works correctly with ESPHome 9.0 or later due to dual Modbus devices being polled 
#
# Eastron SDM630 kWh meter emulator ,  Modbus server function
#   This implementation uses different sensors from Home Assistant (eg from a P1 meter) to feed the different emulated registers for a SDM630 kWh meter
#   It is used as SDM630 kWh meter for an Eplucon / Ecoforest heatpump.  This heatpump requires actual energy / power information from the main utility meter to optimize the energy consumption of the Ecoforest heatpump.
#
# Varme or Vesttherm heatpump boiler VT100WW, VT180WW and probably others (VT100C, VT180C, VT3120 etc)
#   It can read Boiler temp, all diagnostic info and set different registers (eg. Boost) 