#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import json
import logging
from pathlib import Path
import time

import coloredlogs
import continuous_threading
import RPi.GPIO as GPIO
import serial
# from gpiozero import DistanceSensor
import atexit
from helper import *
from threading import Thread;

# General
PI_LED_PIN = 17

# DHT11 (Temperature & Humidity Sensor) - Temperature + Humidity
# DHT11_PIN = 6

# HC-SR04 (Ultrasonic Sensor) - Distance (Ceiling to Floor)
# HCSR04_TRIGGER_PIN = 23
# HCSR04_ECHO_PIN = 24
# HCSR04_TRIGGER_PIN2 = 12
# HCSR04_ECHO_PIN2 = 16

# KW11 (Micro Switch) - Door Switch
# KW11_PIN = 27

# D6T (Thermal Sensor) - D6T-44L-06H
# No need

# ESP01 (250AC 10A Relay) - Light + Fan, UVC
ESP01_LIGHT_FAN_PIN = 25
ESP01_UVC_PIN = 18

# SIM7000E (NB IOT HAT) - Connection to NB IOT Internet
# SIM7000E_OUT_PIN = 4
# SIM7000E_IN_PIN = 26

# serial port handler variables
ser_timeout_seconds = 15
ser_timeout_timer = 0

# SIM7000E Variables
ser = None
ser_port_found = ""
api_key = ''
apn = ''
pod_id = ''
pi_id = ''
usb_port = ''
baud_rate = ''
url = ''
timestamp = ''

# HC-SR04
uss = ''
max_floor_distance = 1.1  # m
threshold_distance = 0.9  # m
threshold_distance1 = 0.9  # m Sonar #1
threshold_distance2 = 1.2  # m Sonar #2
current_floor_distance = 0  # m
current_floor_distance1 = 0  # m
current_floor_distance2 = 0  # m
uss_detected_count = 0   # variable to take care of glitch
is_uss_distance_detected = False

# KW11
is_door_opened = False
door_timestamp = time.time()
door_count = 0
door_close_movement = 0

# D6T
# d6t = ''
# highest_temp = 0.0
# thermal_occupancy1_count = 0  # variable to take care of glitch
# thermal_occupancy0_count = 0  # variable to take care of glitch
# is_d6t_thermal_detected = False

# DHT11 / BME280
temperature = 0
humidity = 0

# LOOP
loop_timestamp = time.time()
listing_data = {}
listing_id = '1013995107100112091'
disinfecting_count = 0
disinfecting_threshold = 176  # 1 count = 3 sec, Thus 176 : 10min
sense_movement_count = 0
reset_cycle_count = 0  # 1 cycle is 3 sec, thus, 15 : 45s changed, last recommended is 25
reset_cycle_threshold = 25
is_occupied = False
is_disinfecting = False
is_listing_status_changed = False
is_scheduled = False
start_disinfecting = False
is_send_data = False
force_off_flag = False  # make pod off after UVC

logger = logging.getLogger(__name__)
coloredlogs.install(level=logging.DEBUG, logger=logger,
                    fmt='%(name)s - %(levelname)s - %(message)s')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger().setLevel(logging.ERROR)

# Initialise config

config_data_directory = '/home/pi/Desktop/gomama-raspberrypi/'
# config_data_directory = '/Users/soonzhi/Projects/gomama_be' # soon zhi debug

def create_file_if_not_exists(file_path):
    if os.path.exists(file_path) is False:
        try:
            Path(file_path).touch()
        except:
            logger.info('Failed to create file')
    return file_path

def init_config():
    global api_key, apn, pod_id, pi_id, usb_port, baud_rate, url, timestamp
    
    # with open(os.path.join(config_data_directory, 'config.json')) as f:
    with open('/home/pi/Desktop/gomama-raspberrypi/config.json') as f:    
        try:
            data = json.load(f)
            if 'api_key' in data:
                api_key = data['api_key']
            if 'apn' in data:
                apn = data['apn']
            if 'pod_id' in data:
                pod_id = data['pod_id']
            if 'pi_id' in data:
                pi_id = data['pi_id']
            else:
                write_pi_config()
            if 'usb_port' in data:
                usb_port = data['usb_port']
            if 'baud_rate' in data:
                baud_rate = data['baud_rate']
            if 'url' in data:
                url = data['url']
            timestamp = get_current_timestamp()
        except json.decoder.JSONDecodeError as err:
            logger.error("JSON Decode Error", err)


def init_data():
    global listing_data, listing_id, timestamp, is_disinfecting, is_door_opened, is_occupied, is_led_light_on, is_fan_on, is_scheduled, is_uvc_lamp_on, temperature, humidity
    
    # with open(os.path.join(config_data_directory, 'data.json')) as f:
    with open('/home/pi/Desktop/gomama-raspberrypi/data.json') as f:
        try:
            data = json.load(f)
            listing_data = data
            if 'listing_id' in data:
                listing_id = data['listing_id']
            if 'timestamp' in data:
                timestamp = data['timestamp']
            if 'is_disinfecting' in data:
                is_disinfecting = data['is_disinfecting']
            if 'is_door_opened' in data:
                is_door_opened = data['is_door_opened']
            if 'is_occupied' in data:
                is_occupied = data['is_occupied']
            if 'is_led_light_on' in data:
                is_led_light_on = data['is_led_light_on']
            if 'is_fan_on' in data:
                is_fan_on = data['is_fan_on']
            if 'is_scheduled' in data:
                is_scheduled = data['is_scheduled']
            if 'is_uvc_lamp_on' in data:
                is_uvc_lamp_on = data['is_uvc_lamp_on']
            if 'temperature' in data:
                temperature = data['temperature']
            if 'humidity' in data:
                humidity = data['humidity']
        except json.decoder.JSONDecodeError as err:
            logger.error("JSON Decode Error", err)
            if listing_data:
                write_data(listing_data)


# Initialise serial comm
def init_serial_comm():
    global ser
    if ser != '':
        ser.close()
    try:
        ser = serial.Serial(usb_port, baud_rate)
        if ser == '':
            logger.error("[INITIAL] Check the serial port")
            exit(1)
        logger.debug(ser)
    except:
        logger.error("[INITIAL] Check the serial port")
        exit(1)


# Initialise GPIO  #need to configure this to output signal to gpio pin to esp32 hub via serial or gpio pins
def init_gpio():
    global is_door_opened       #need to check with Aaron this variable 
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    # # KW11
    #is_door_opened = GPIO.input(KW11_PIN) == 1 (changed to arduino val)


    # ESP01
    # GPIO.setup(ESP01_LIGHT_FAN_PIN, GPIO.OUT)
    # GPIO.setup(ESP01_UVC_PIN, GPIO.OUT)
    # GPIO.output(ESP01_LIGHT_FAN_PIN, GPIO.HIGH)
    # GPIO.output(ESP01_UVC_PIN, GPIO.HIGH)


# def init_http():
#     '''Check local IP is ready'''
#     '''Bearer Configure'''
#     AT(ser, 'SAPBR=3,1,"Contype","GPRS"')
#     AT(ser, f'SAPBR=3,1,"APN","{apn}"')
#     AT(ser, 'SAPBR=0,1')
#     AT(ser, 'SAPBR=1,1')
#     AT(ser, 'SAPBR=2,1')serial
#     AT(ser, 'HTTPPARA="CID",1')


def read_http():
    global ser
    AT(ser, 'HTTPREAD', 6)


def close_http():
    global ser
    AT(ser, 'HTTPTERM')


async def post_http(api_key_hashed):
    '''Check local IP is ready'''
    try:
        global is_listing_status_changed
        global ser
        payload = json.dumps(listing_data)
        close_http()
        init_http()
        AT(ser, f'HTTPPARA="URL","{url}"')
        AT(ser, 'HTTPPARA="CONTENT","application/json"')
        AT(ser,
           f'HTTPPARA="USERDATA","Authorization: Bearer {api_key_hashed}"')
        AT(ser, f'HTTPDATA={len(payload)},5000')
        time.sleep(0.5)
        read_serial_output(ser)
        ser.write((payload+'\r\n').encode('utf-8'))
        read_serial_output(ser, 3.8)
        AT(ser, 'HTTPACTION=1', 0.5)
        read_http()
        logger.debug(payload)
        is_listing_status_changed = False
    except:
        GPIO.cleanup()

# This one will need to add signal feedback to ESP32 hub
def switch_light_fan_on(is_on: True):
    global is_led_light_on, is_fan_on
    if (is_on):
        logger.warning("* [ESP01] light and fan switched on")
        # GPIO.output(ESP01_LIGHT_FAN_PIN, GPIO.LOW)
        #add a v6 something
    else:
        logger.warning("* [ESP01] light and fan switched off")
        # GPIO.output(ESP01_LIGHT_FAN_PIN, GPIO.HIGH)
        #add a v6 something
    is_led_light_on = is_on
    is_fan_on = is_on

# This one will need to add signal feedback to ESP32 hub
def switch_uvc_lamp_on(is_on: True):
    global is_uvc_lamp_on
    if is_on:
        logger.warning("* [ESP01] uvc lamp switched on")
        # v5 = int(values[6])     # relay for UV
        is_uvc_lamp_on = True
    else:
        logger.warning("* [ESP01] uvc lamp switched off")
        # v5 = int(values[6])     # relay for UV
        is_uvc_lamp_on = False


def init_pod():
    switch_light_fan_on(False)
    switch_uvc_lamp_on(False)



## read temperature from serial port coming from the esp32 hub
# parallel process
# def read_temperature_humidity():
#     global humidity, temperature
#     temp = float(values[0][:-2])
#     percentage = float(values[1][:-1])

#     humidity, temperature = percentage, temp
#     logger.debug(f'[BME280] current temperature: {temperature}°C')
#     logger.debug(f'[BME280] current humidity: {humidity}%')


# parallel process
def read_door_status():
    global door_timestamp, is_door_opened, door_count, door_close_movement, force_off_flag, is_listing_status_changed
    try:
        time_now = time.time()
        if(time_now - door_timestamp) >= 0.3:
            is_door_opened = GPIO.input(KW11_PIN) == 1
            logger.debug(f'[KW11] current door opened: {is_door_opened}')
        door_timestamp = time_now
        if (is_door_opened == True):
            logger.debug("[KW11] door is open")
            door_count = 0
            door_close_movement = 0
            force_off_flag = False
            is_listing_status_changed = True
        else:
            door_count = door_count + 1
            logger.debug("[KW11] door_count: %d" % door_count)
        time.sleep(2)
    except:
        logger.error("[KW11] error has occurred")
        pass


def set_occupied_status(is_set: True):
    global is_occupied, is_disinfecting, start_disinfecting, is_listing_status_changed, disinfecting_count
    logger.info(f'[LISTING] set occupied status: {is_set}')
    if is_occupied and not is_set and not is_door_opened:
        start_disinfecting = True
    is_listing_status_changed = True
    is_occupied = is_set
    if is_set:
        start_disinfecting = False
        is_disinfecting = False
        disinfecting_count = 0
        switch_uvc_lamp_on(False)
    switch_light_fan_on(is_set)


def set_disinfecting_status(is_set: True):
    global is_occupied, is_disinfecting, is_listing_status_changed
    logger.info(f'[LISTING] set disinfecting status: {is_set}')
    is_listing_status_changed = True
    is_disinfecting = is_set
    if is_occupied:
        switch_light_fan_on(not is_set)
    # switch_light_fan_on(is_set)
    switch_uvc_lamp_on(is_set)


def get_disinfecting_status():
    return is_disinfecting


def get_occupied_status():
    return is_occupied


def get_led_light_status():
    return is_led_light_on


def get_fan_status():
    return is_fan_on


def get_uvc_lamp_status():
    return is_uvc_lamp_on


def get_temperature_status():
    return temperature


def get_humidity_status():
    return humidity


def get_door_status():
    return is_door_opened


def start_module():  #sense_movement_count = humanState
    global is_uvc_lamp_on, is_send_data, is_door_opened, is_d6t_thermal_detected, sense_movement_count
    global reset_cycle_count, pi_key_hashed, is_disinfecting, disinfecting_count, start_disinfecting
    global is_listing_status_changed, door_close_movement, door_count, force_off_flag, is_occupied
    global ser, ser_timeout_timer
    '''
    init_pod()
    
    # th1 = continuous_threading.ContinuousThread(target=detect_movement)
    # th1 = continuous_threading.ContinuousThread(
    #     target=read_temperature_humidity)
    # th3 = continuous_threading.ContinuousThread(
    #     target=measure_floor_distance)
    # th4 = continuous_threading.ContinuousThread(      #not sure whether this one will need, check if it affects the rasp reading
    #     target=read_door_status)
    # th1.start()
    # th2.start()
    # th3.start()
    # th4.start()
    '''
    loop_timestamp = time.time()

    v1 = 0
    v3 = 0
    v4 = 0
    v5 = 0
    v8 = 0
    v9 = 0
    v10 = 0
    v11 = 0
    v12 = 0
    v13 = 0
    temp = 0.00
    percentage = 0.00
    print_counter = 0
    while 1:
        try:
            if ser is not None and ser.inWaiting() > 0:
                ser_timeout_timer = 0 # clear the serial watch dog timer when serial receive data
                line = ser.readline().decode('utf-8').rstrip()
                if print_counter > 10:
                    print(line) # can comment this out to not show the serial reading on terminal
                    print_counter = 0
                print_counter += 1
                # example line values: 29.30*C; 62.41%; 1 ;0 ;0 ;1 ;0 ;1 ;humanSense2 ;humanSense3; humanState

                values = line.split(';')
                # write values into log file
                # f.write(line)
                # example assignment of values
                temp = float(values[0][:-2])
                percentage = float(values[1][:-1])
                v1 = int(values[2])     # doorState
                v2 = int(values[3])     # relay for ventilation fan
                v3 = int(values[4])     # relay for AC
                v4 = int(values[5])     # relay for Surrouding light
                v5 = int(values[6])     # relay for UV
                #v6 = int(values[7])     # relay for RED Light
                #v7 = int(values[8])     # relay for GREEN Light
                v6 = int(values[7])     # Human presence sense1
                #v9 = int(values[11])    # Human presence sense2
                v7 = int(values[8])     # Human presence sense3
                v8 = int(values[9])     # Human presence state
                v9 = int(values[10])     # StateMachine
                v10 = int(values[11])    # m counter
                # v13 = int(values[14])    # TimerActive
                # v14 = int(values[15])    # duration taken
                # if statement for human presence
                # if v11 == 1:
                #    print("Human detected")
                # is_door_opened = v1  
        
        except Exception as e:
            print(e)

        time.sleep(0.001) # try not get too frequent first. must keep this!

        if time.time() >= loop_timestamp + 1:
            logger.info(
                f'[LOOP] start listing check status cycle at {loop_timestamp}...')
            init_data()
            # measure_floor_distance()
            # if is_door_opened:
            #     sense_movement_count += 1
            #     door_close_movement += 1
            #     reset_cycle_count = 0
            #     disinfecting_count = 0
            #     switch_light_fan_on(True)
            #     set_disinfecting_status(False)

            # if is_d6t_thermal_detected:
            #     sense_movement_count += 1
            #     door_close_movement += 1
            #     is_d6t_thermal_detected = False
            #     reset_cycle_count = 0
            #     disinfecting_count = 0

            # # if (door_count >= 25):      ##need to modify this section##
            #     is_listing_status_changed = True
            #     logger.debug("[LOOP] door close movement:%d" %
            #                  (door_close_movement))
            #     logger.debug(
            #         "[LOOP] 1st 25 cycle door is closed: %d" % door_count)


            is_listing_status_changed = True
            is_d6t_thermal_detected = False
            # is_uvc_lamp_on = v5
            # is_door_opened = v1 
            # is_led_light_on = v4
            # is_fan_on = v3
            sense_movement_count = v9
            door_close_movement = 0
            force_off_flag = False

            #Door sensor
            if v1 == 0:
                is_door_opened = False
            elif v1 ==1:
                is_door_opened = True

            if (is_door_opened == True):
                reset_cycle_count = 0
                
            if (sense_movement_count == 1): # sense_movement_count = humanState
                is_occupied = True
                reset_cycle_count += 1
            else:
                is_occupied = False
            
            #     sense_movement_count += 1
            #     door_close_movement += 1
            #     reset_cycle_count = 0
            #     disinfecting_count = 0
            #     set_disinfecting_status(False)

            # occupied meed to swap and led light on and fan need to swap
            # is uvc_lamp is not toggling.

            # LED lighting
            if v4 == 0:
                is_led_light_on = True
            elif v4 == 1:
                is_led_light_on = False

            # AC
            if v3 == 0:
                is_fan_on = True
            elif v3 == 1:
                is_fan_on = False
            
            # UV light
            if v5 == 0:
                is_uvc_lamp_on = True
            elif v5 == 1:
                is_uvc_lamp_on = False


            if is_uvc_lamp_on == True:
                start_disinfecting = True
            else:
                is_uvc_lamp_on = False

            if is_disinfecting:
                disinfecting_count += 1
                # added to see dinsinfection count
                logger.debug("[LOOP] disinfecting count: %d" %
                             disinfecting_count)
                if not is_uvc_lamp_on:
                    is_disinfecting = False
                    start_disinfecting = False
                    disinfecting_count = 0


            if reset_cycle_count > reset_cycle_threshold:
                # sense_movement_count = 0
                reset_cycle_count = 0
                logger.debug("[LOOP] reset cycle count : %d" %
                             reset_cycle_count)

            logger.debug(
                f'[LOOP] check sense movement count - {sense_movement_count}...')
            # logger.debug(
            #     f'[LOOP] check reset cycle count - {reset_cycle_count}...')
            # logger.debug(
            #     f'[LOOP] check disinfecting count - {disinfecting_count}...')

            logger.info(
                f'[LOOP] occupied status changed: {is_listing_status_changed}...')
            logger.info(
                f'[LOOP] Current State: {v12}')
            if is_listing_status_changed:
                logger.warning('* [LOOP] occupied status changed.')
                if start_disinfecting:
                    logger.warning('* [LOOP] disinfecting active.')
                    set_disinfecting_status(True)

            # if get_current_time() == "06:00":
            #     is_uvc_lamp_on = True
            #     is_disinfecting = True
            # elif get_current_time() == "06:10":
            #     is_uvc_lamp_on = False
            #     is_disinfecting = False

            listing_data['listing_id'] = listing_id
            listing_data['timestamp'] = loop_timestamp
            listing_data['is_disinfecting'] = is_disinfecting
            listing_data['is_door_opened'] = is_door_opened
            listing_data['is_occupied'] = is_occupied
            listing_data['is_led_light_on'] = is_led_light_on
            listing_data['is_fan_on'] = is_fan_on
            listing_data['is_scheduled'] = is_scheduled
            listing_data['is_uvc_lamp_on'] = is_uvc_lamp_on

            if temperature is not None:
                listing_data['temperature'] = temp
            if humidity is not None:
                listing_data['humidity'] = percentage

            pi_key_hashed = generate_api_key_hashed(
                api_key, pi_id, loop_timestamp)
            if is_listing_status_changed:
                is_send_data = True
                listing_data['is_send_data'] = is_send_data
                logger.warning(f'* [LOOP] to send data: {is_send_data}')
                is_listing_status_changed = False
                write_data(listing_data)
            loop_timestamp = time.time()
            logger.info(
                f'[LOOP] end listing check status cycle at {loop_timestamp}...')
            logger.debug(
                '\n==========================================================\n')
        
        time.sleep(0.001) # sleep to reduce loop resource, must keep this!


# def shut_module():
#     AT(ser, 'CIPSHUT', 4)
#     logger.debug(read_serial_output(ser, ))


def init_serial_port(ser_port_override=None, baud_rate=115200, timeout=10):
    global ser, ser_timeout_timer, ser_port_found
    # make sure serial is close, before init port
    close_serial_port()
    ser_port_found = ""
    if ser_port_override is None:
        for i in range(0, 99):
            try:
                if ser is None:
                    ser = serial.Serial('/dev/ttyUSB' + str(i), baud_rate, timeout=timeout)
                    ser_port_found = '/dev/ttyUSB' + str(i)
                    print("Serial Port opened: /dev/ttyUSB" + str(i))
                    break # exit loop if port found
            except Exception as e:
                logger.warning("Failed to open port no: /dev/ttyUSB" + str(i))
                print(e) # can remove if too many prints
    else:
        ser = serial.Serial(ser_port_override, baud_rate, timeout=timeout)
        logger.info("Serial Port opened: " + ser_port_override)
        ser_port_found = ser_port_override
    if ser is not None:
        ser.flush()
        # ser.reset_input_buffer()
    
    ser_timeout_timer = 0
    return True


def close_serial_port():
    # safe method to close port
    global ser
    if ser is not None:
        try:
            ser.close()
            ser = None
        except Exception as e:
            print(e) # can remove if too many prints


def init_serial_port_watchdog():
    # this module is not check on serial port every second
    # if timeout happen, restart the serial port
    global ser, ser_timeout_timer
    logger.info('serialTimeoutWatchdogTimer started')
    while True:
        try:
            # condition 1, if serial created but no data come in mean hung
            if ser is not None and ser.inWaiting() <= 0:
                ser_timeout_timer += 1
                logger.info("Serial port watchdog timer: {0}/{1}".format(str(ser_timeout_timer),str(ser_timeout_seconds)))
            elif ser is None:
                # TODO: condition 2: do we want to start check the serial if no serial is created            
                ser_timeout_timer += 1
                logger.info("Serial port watchdog timer: {0}/{1}".format(str(ser_timeout_timer),str(ser_timeout_seconds)))
            
            if ser_timeout_timer >= ser_timeout_seconds:
                ser_timeout_timer = 0
                # if watchdog timer hit timeout seconds, means no data come in, reinit serial.
                # reinit port here.
                logger.warning("Serial port hung/closed, reinitilize serial port")
                init_serial_port()
        except Exception as e:
            print(e)
        time.sleep(1)


if __name__ == '__main__':
    # for debug purpose, specified port for
    # init_serial_port(ser_port_override='/dev/ttyUSB0', baud_rate=9600, timeout=10)
    # init_serial_port(ser_port_override='/dev/ttyUSB1', baud_rate=9600, timeout=10)
    init_serial_port()
    init_config()
    init_gpio()
    init_data()
    # init the threads
    serial_watchdog_thread = Thread(target=init_serial_port_watchdog)
    module_thread = Thread(target=start_module)
    # start the threads
    module_thread.start() # thread 1 to start the thread module
    serial_watchdog_thread.start() # thread 2 to monitor the serial and restart if needed.
    atexit.register(close_serial_port)
    
    # the code below still need?
    
    # except KeyboardInterrupt:
    #     shut_module()
    #     except Exception as e:
    #         print(e)
    #         pass
    #     finally:
    # # GPIO.cleanup()
    #         start_module()            
    #         # start_module()   ## probably need it here