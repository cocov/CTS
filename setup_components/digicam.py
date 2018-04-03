from subprocess import Popen, PIPE, STDOUT
import time
import os
import sys
from utils import logger
import logging
from threading import Thread, Event
from queue import Queue, Empty
from socket import socket


class DigiCam:

    def __init__(self, log_location):
        self.slow_interface = 'eth2'
        self.slow_ip = '192.168.0.0'
        self.slow_interface = 'eth3'
        self.slow_ip = '192.168.0.1'
        self.slow_trigger_port = None
        # self.t telescope ID
        self.threshold_7 = 2047
        self.enable_trigger = False
        self.auxiliary_trigger = False
        self.fake_trig_freq = 0
        self.readout_delay = 431
        self.readout_delay_backplane = 330
        self.patch_7_enable = True

    def trigger_configuration(self, config):
        """
        Config is a dictionnary whose key correspond to the private
        members of the ZFitsWriter
        :param config:
        :return:
        """
        for key, val in config.items():
            if hasattr(self, key):
                setattr(self, key, val)
        self.send_config_packet()

    def send_config_packet(self):
        s = socket(..., ...)
        s.connect((self.slow_ip, self.slow_trigger_port))
        message = s.sendall(message)  # TODO Fix that!
