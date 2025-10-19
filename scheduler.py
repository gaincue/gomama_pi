import logging
import time

import coloredlogs
import RPi.GPIO as GPIO
import schedule

from helper import *

# ESP01 (250AC 10A Relay) - UVC
ESP01_UVC_PIN = 18

is_init = True
is_occupied = False

logger = logging.getLogger('scheduler')
coloredlogs.install(level=logging.DEBUG, logger=logger,
                    fmt='%(name)s - %(levelname)s - %(message)s')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger().setLevel(logging.ERROR)

# Initialise GPIO


def init_gpio():
    logger.info("[INITIAL] initial gpio")
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(ESP01_UVC_PIN, GPIO.OUT)
    GPIO.output(ESP01_UVC_PIN, GPIO.HIGH)


def switch_uvc_lamp_on(is_on: True):
    if is_on:
        logger.warning("* [ESP01] uvc lamp switched on")
        GPIO.output(ESP01_UVC_PIN, GPIO.LOW)
    else:
        logger.warning("* [ESP01] uvc lamp switched off")
        GPIO.output(ESP01_UVC_PIN, GPIO.HIGH)


def start_disinfecting():
    logger.warning('* [ESP01] start disinfecting...')
    is_disinfecting, is_occupied = read_disinfecting_occupied_data()
    if not is_occupied and not is_disinfecting:
        switch_uvc_lamp_on(True)
        # write_is_disinfecting(True)
        # send_data()


def end_disinfecting():
    logger.warning('* [ESP01] end disinfecting...')
    is_disinfecting, _ = read_disinfecting_occupied_data()
    if is_disinfecting:
        switch_uvc_lamp_on(False)
        # write_is_disinfecting(False)
        # send_data()


def send_data():
    logger.warning('* [SIM7000E] send data...')
    write_is_send_data(True, True)


def init_data():
    global listing_data, timestamp, is_occupied
    with open('/home/pi/Desktop/gomama-pod/data.json') as f:
        try:
            data = json.load(f)
            listing_data = data
            if 'timestamp' in data:
                timestamp = data['timestamp']
            if 'is_occupied' in data:
                is_occupied = data['is_occupied']
        except json.decoder.JSONDecodeError as err:
            logger.error("JSON Decode Error", err)
            pass


def restart_pi_device():
    logger.warning('* [SUDO] restart pi device')
    init_data()
    if not is_occupied:
        command = "/usr/bin/sudo /sbin/shutdown -r now"
        import subprocess
        process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
        output = process.communicate()[0]
        logger.debug(f'[SUDO] {output}')


# schedule.every().day.at('05:00').do(restart_pi_device)
schedule.every().day.at('06:00').do(start_disinfecting)
schedule.every().day.at('06:10').do(end_disinfecting)

while 1:
    logger.info(f'[LOOP] running scheduler at {get_current_date_time()}...')
    if is_init:
        init_gpio()
        # send_data()
        is_init = False
    schedule.run_pending()
    all_jobs = schedule.get_jobs()
    logger.debug(f'[LOOP] current jobs: {all_jobs}')
    logger.debug(
        '\n==========================================================\n')
    time.sleep(1)
