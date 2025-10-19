# gomama-pod

# Setup and configure Raspberry Pi

`sudo raspi-config` #Interfacing Options -> Serial login -> no, Serial hardware -> yes

`sudo nano /boot/config.txt` #add==> enable_uart=1

`sudo nano /boot/cmdline.txt` #deleted "console=ttyAMA0,115200 kgdboc=ttyAMA0,115200"

`sudo apt-get install minicom` #for try AT command

`minicom -D /dev/ttyUSB3 -b115200` #Run minicom for Raspberry pi3 pi4

`pip3 install RPi.GPIO`

`sudo apt-get install python-smbus`

`sudo apt-get install python-serial`

`sudo python setup.py install`

download the latest version of the library, say bcm2835-1.xx.tar.gz, then `tar zxvf bcm2835-1.xx.tar.gz`

`cd bcm2835-1.xx`

`./configure`

`make`

`sudo make check`

`sudo make install`

`cat /proc/cpuinfo | grep --ignore-case serial`

`pip3 install py-cpuinfo`

# Raspberry Pi Workflow

2 Workflows

1. Event-Based for 1 Cycle:
  1a. Event 1: Pod not occupied and ready for use - Pod light/fan is off and UVC is off.
  1b. Event 2: Motion detected and pod set to occupied and not for use by others - Pod light/fan is on and UVC is off.
  1c. Event 3: Pod occupied status changed to not occupied after 45 cycles of checks (every 15 cycle about 1 min)
       1ci. After 3 minutes of check/confirmation of not occupied,  send pod status to backend with is_disinfecting = true and is_occupied = false and backend reply if session still going on or not.
       1cii. If the session is still going on, send pod status to backend with is_disinfecting = false and is_occupied = false - Pod light/fan is on and UVC is off.
       1ciii. If there is no ongoing session, UVC disinfection will turn on for 10 minutes, send pod status to backend with is_disinfecting = true and is_occupied = false. - Pod light/fan is off and UVC is on.
       1civ. After 10 minutes of UVC disinfection, send pod status to backend with is_disinfecting = false and is_occupied = false and go back to Event 1 to repeat the cycle.
  1d. Whenever motion is detected or door switch is opened, pod will trigger Event 2 straight away.

2. Routine-Based:
2a. Send pod status (occupied, temperature/humidity, hardware) to backend every 2 hours starting at 6am everyday. - Create pod_logs collection and data model
2b. Trigger UVC disinfection at 6am (Block the pod from allowing access by user for 10 minutes - send pod status to backend with is_disinfecting = true and is_occupied = false) and send pod status to backend with is_disinfecting = false and is_occupied = false after 10 minutes

# Instructions to configure each pod's config.data

1. To get pi_id, type: `cat /proc/cpuinfo | perl -n -e '/^Serial\s*:\s([0-9a-f]{16})$/ && print "$1\n"'`
2. Pass all the raspberry pi's pid_id to us to update the respective listings in the backend database.
3. Update the pi_id in the config.data file.
4. Update the api_key for each listing in the config.data file.
5. Update the cloud function url to the following respective environments:
   5a. gomama-dev: <http://asia-southeast1-gomama-dev.cloudfunctions.net/processListingRaspberryPiLogs>
   5b. gomama-prod: <http://asia-southeast1-gomama-prod.cloudfunctions.net/processListingRaspberryPiLogs>
6. Update the listing_id in the config.data file.
7. The final config.data file should resemble the following:
{
    "api_key": "<API_KEY>",
    "listing_id": "<LISTING_ID>",
    "pi_id": "<PI_ID>",
    "apn": "M1-NBIOT",
    "usb_port": "/dev/ttyUSB3",
    "baud_rate": 115200,
    "url": "http://asia-southeast1-gomama-prod.cloudfunctions.net/processListingRaspberryPiLogs"
}
