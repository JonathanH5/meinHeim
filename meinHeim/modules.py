import logging

log = logging.getLogger()  # the logger

##########################################################################################
# Collection of all Rules
##########################################################################################


from threading import Thread
import time


class Rule(object):
    def activate_rule(self):
        self.keep_alive = True
        if self.thread is not None:  # check whether already initialized
            if self.thread.isAlive():  # check whether was still alive
                log.info(self.tname + " was still alive!")
                return

        # not initialized or dead, does not matter
        log.info("Activated Rule " + self.tname + ".")
        self.thread = Thread(name=self.tname, target=self.rule)
        self.thread.setDaemon(True)
        self.thread.start()

    def rule(self):
        while self.keep_alive:
            self.rule_logic()
            time.sleep(self.sleep_time)

        log.info(self.tname + " was no longer kept alive.")

    def deactivate_rule(self):
        log.info("Rule " + self.tname + " will not be kept alive.")
        self.keep_alive = False

    def __init__(self, tname, rule_logic, sleep_time):
        self.tname = tname
        self.rule_logic = rule_logic  # a method that gets executed when alive
        self.sleep_time = sleep_time  # time after which the rule_logic is started again
        self.keep_alive = False  # if True, the rule gets repeated after sleep_time
        self.thread = None  # the thread used to repeat the rule_logic


##########################################################################################
# Tinkerforge Module
##########################################################################################


from tinkerforge.ip_connection import IPConnection
from tinkerforge.bricklet_remote_switch import BrickletRemoteSwitch
from tinkerforge.bricklet_ambient_light import BrickletAmbientLight
from tinkerforge.bricklet_distance_us import BrickletDistanceUS


class TinkerforgeConnection(object):
    # Connection to the Brick Daemon on localhost and port 4223
    ipcon = None
    current_entries = dict()

    # noinspection PyUnusedLocal
    def cb_enumerate(self, uid, connected_uid, position, hardware_version, firmware_version, device_identifier,
                     enumeration_type):

        if enumeration_type == IPConnection.ENUMERATION_TYPE_DISCONNECTED:
            del self.current_entries[uid]

        else:
            if device_identifier == 13:
                self.current_entries.update({uid: "Master Brick"})
            elif device_identifier == 21:
                self.current_entries.update({uid: "Ambient Light Bricklet"})
            elif device_identifier == 229:
                self.current_entries.update({uid: "Distance US Bricklet"})
            elif device_identifier == 235:
                self.current_entries.update({uid: "RemoteSwitchBricklet"})
            else:
                self.current_entries.update(
                    {uid: "device_identifier = {0}".format(device_identifier)})

    def switch_socket(self, uid, address, unit, state):
        rs = BrickletRemoteSwitch(uid, self.ipcon)
        rs.switch_socket_b(address, unit, state)

    def dim_socket(self, uid, address, unit, value):
        rs = BrickletRemoteSwitch(uid, self.ipcon)
        rs.dim_socket_b(address, unit, value)

    def get_illuminance(self, uid):
        try:
            al = BrickletAmbientLight(uid, self.ipcon)
            return al.get_illuminance() / 10
        except Exception:
            log.warn(uid + " not connected")
            return -1

    def get_distance(self, uid):
        try:
            dus = BrickletDistanceUS(uid, self.ipcon)
            return dus.get_distance_value()
        except Exception:
            log.warn(uid + " not connected")
            return -1

    def __init__(self, ip_address):
        self.ipcon = IPConnection()
        self.ipcon.connect(ip_address, 4223)
        self.ipcon.register_callback(IPConnection.CALLBACK_ENUMERATE, self.cb_enumerate)
        self.ipcon.enumerate()


##########################################################################################
# BVG Module
##########################################################################################


from bs4 import BeautifulSoup
import requests


class BVG(object):
    ACTUAL_API_ENDPOINT = (
        'http://mobil.bvg.de/Fahrinfo/bin/stboard.bin/dox?&boardType=depRT')

    def __init__(self, station, limit=5):
        if isinstance(station, str):
            self.station_enc = station.encode('iso-8859-1')
        elif isinstance(station, bytes):
            self.station_enc = station
        else:
            raise ValueError("Invalid type for station")
        self.station = station
        self.limit = limit

    def call(self):
        params = {
            'input': self.station_enc,
            'maxJourneys': self.limit,
            'start': 'suchen',
        }
        response = requests.get(self.ACTUAL_API_ENDPOINT, params=params)
        if response.ok:
            soup = BeautifulSoup(response.text, "html.parser")
            if soup.find_all('form'):
                log.error("The station" + self.station + " does not exist.")
                return None
            else:
                # The station seems to exist
                result = soup.find('div', {'id': '',
                                           'class': 'ivu_result_box'})
                if result is None:
                    return None
                rows = result.find_all('tr')
                departures = []
                for row in rows:
                    if row.parent.name == 'tbody':
                        td = row.find_all('td')
                        if td:
                            dep = [self.station, td[2].text.strip(), td[0].text.strip(),
                                   td[1].text.strip()]
                            departures.append(dep)
                return departures
        else:
            try:
                response.raise_for_status()
            except requests.RequestException as e:
                log.error(e)
            else:
                log.error("An unknown error occured.")
            return None
