import matplotlib.pyplot as plt
from utils import mcevent
from opcua import ua
from astropy import units as u
import numpy as np
import time
from utils import logger
import logging
import sys

import cts_opcua.cts_opcua_client as cts_client
import cts_core.cameratestsetup as cameratestsetup
import setup_components.generator as gen

from ctapipe.io.hessio import hessio_event_source
from ctapipe.instrument.camera import (
    CameraGeometry,
    _find_neighbor_pixels as find_neighbor_pixels
)
from ctapipe import visualization


class CTSMaster:
    def __init__(self, angle_cts=0., plotting=True):
        # Get the CTS mapping
        logger.initialise_logger(logname=sys.modules['__main__'].__name__,
                                 logfile='test.log')
        self.log = logging.getLogger(sys.modules['__main__'].__name__)
        self.cts = cameratestsetup.CTS(
            'config/cts_config_' + str(int(angle_cts)) + '.cfg',
            'config/camera_config.cfg', angle=angle_cts, connected=False)
        # Get the CTS OpcUA client
        self.cts_client = cts_client.CTSClient()
        # Get the generator for triggering AC leds and digicam
        self.generator = gen.Generator(
            sys.modules['__main__'].__name__, url="0.0.0.0"  # "129.194.52.76"
        )
        self.generator.apply_config('burst')
        # Get the digicam OpcUA client
        self.digicam_client = None
        # Prepare plots
        self.plotting = plotting
        if self.plotting:
            self.plots = []
        # Prepare data cube
        self.dc_status = np.ones(1296, dtype=int) * 0
        self.ac_status = np.ones(1296, dtype=int) * 0
        self.dc_level = np.ones(1296, dtype=int) * 0
        self.ac_level = np.ones(1296, dtype=int) * 0
        if self.plotting:
            self.initialise_plots()
        # Make the plots interactive
        # plt.ion()
        if self.plotting:
            self.plot()

    def __exit__(self, exc_type, exc_val, exc_tb):
        print('---|> The client will be reset and turned off, wait...')
        self.reset()

    def initialise_plots(self):
        # first load in a very nasty way the camera geometry
        pix_x, pix_y, pix_id = [], [], []
        pixels = self.cts.camera.Pixels
        pixelspresent = list(self.cts.pixel_to_led['DC'].keys())
        for pix in pixels:
            if pix.ID in pixelspresent:
                pix_x.append(pix.center[0])
                pix_y.append(pix.center[1])
                pix_id.append(pix.ID)
            else:
                print('pixel', pix.ID, 'not in cts.pixel_to_led[\'DC\']')
                pix_x.append(-600.)
                pix_y.append(-600.)
                pix_id.append(pix.ID)
        pix_x = list(pix_x)
        pix_y = list(pix_y)
        pix_id = list(pix_id)
        neighbors_pix = find_neighbor_pixels(pix_x, pix_y, 30.)
        geom = CameraGeometry(0, pix_id, pix_x*u.mm, pix_y*u.mm,
                              np.ones((1296))*400., 'hexagonal',
                              neighbors=neighbors_pix)
        plt.figure(0, figsize=(20, 6))
        self.plots = []
        plt.subplot(1, 2, 1)
        self.plots.append(visualization.CameraDisplay(
            geom, title='AC status', norm='lin', cmap='coolwarm',
            autoscale=False
        ))
        self.plots[-1].add_colorbar()
        self.plots[-1].image = np.multiply(self.ac_status, self.ac_level)
        # self.plots[-1].overlay_pixels_id()
        self.plots[-1].axes.set_xlim([-500, 500])
        self.plots[-1].axes.set_ylim([-500, 500])
        plt.subplot(1, 2, 2)
        self.plots.append(visualization.CameraDisplay(
            geom, title='DC status', norm='lin', cmap='coolwarm',
            autoscale=False
        ))
        self.plots[-1].add_colorbar()
        self.plots[-1].image = np.multiply(self.dc_status, self.dc_level)
        self.plots[-1].axes.set_xlim([-500, 500])
        self.plots[-1].axes.set_ylim([-500, 500])

    # Helper functions
    def update(self):
        self.cts_client.update()

    def reset(self):
        """
        reset()

        A function to put back all led to 0

        """
        plotting = True if self.plotting else False
        self.plotting = False
        for led_type in ['AC', 'DC']:
            for pixel in self.cts.pixel_to_led[led_type].keys():
                self.turn_off(pixel, led_type)
        self.plotting = True if plotting else False

    def loop_over_dc_pixels(self, level, timeout=0.1,  n_triggers=-1,
                            start_pixel=None):
        print(self.plotting)
        """
        loop_over_dc_pixels(level,timeout)

        A function to light DC pixels one after the other in increasing
        software pixel id.

        Inputs :
                 - level   : the DAC level to apply (int)
                 - timeout : the amount of time, in s, to keep the pixels on
                             (float)
        """
        if n_triggers > 0:
            self.generator.configure_trigger(n_pulse=n_triggers)
        # loop over the boards and apply the DAC level
        for board in self.cts.LED_boards:
            self.cts_client.set_dc_level(board.internal_id, level)
        # loop over the pixels

        pixel_list = list(self.cts.pixel_to_led['DC'].keys())
        pixel_list.sort()
        for i, pix in enumerate(pixel_list):
            if start_pixel and pix < start_pixel:
                continue
            if i > 0:
                # turn off the previous pixel
                self.cts_client.set_led_status('DC', pixel_list[i - 1], False)
                self.dc_status[pixel_list[i - 1]] = 0
                self.dc_level[pixel_list[i - 1]] = 0
            # turn on this pixel
            self.cts_client.set_led_status('DC', pixel_list[i], True)
            self.dc_status[pixel_list[i]] = 1
            self.dc_level[pixel_list[i]] = level
            if n_triggers > 0:
                self.generator.start_trigger_sequence()
            if self.plotting:
                self.plot()
            time.sleep(timeout)
        # turn off the last pixel
        self.cts_client.set_led_status('DC', pixel_list[-1], False)
        self.dc_status[pixel_list[-1]] = 0
        self.dc_level[pixel_list[-1]] = level
        # put back all DAC level to 0
        for board in self.cts.LED_boards:
            self.cts_client.set_dc_level(board.internal_id, 0)
        if self.plotting:
            self.plot()

    def loop_over_ac_levels(self, levels=range(100, 600, 50), timeout=0.05,
                            n_triggers=1000, frequency=100):
        """
        loop_over_ac_pixels(level,timeout,trigger,n_trigger)

        A function to light AC pixels one after the other in increasing
        software pixel id

        Inputs :
                 - level   : the DAC level to apply (int)
                 - timeout : the amount of time, in s, to keep the pixels on
                             (float)
                 - n_trigger : number of consecutive trigger for AC (int)
                 - frequency: frequency of the trigger (float)
        """
        # Initialise the trigger
        self.generator.configure_trigger(n_pulse=n_triggers, freq=frequency)
        # set all led to ON
        self.all_on('AC', 0)
        # loop over the levels to set the DAC level
        for i, level in enumerate(levels):
            print('Setting level', level)
            for patch in self.cts.LED_patches:
                self.cts_client.set_ac_level(patch.camera_patch_id, level)
            self.generator.start_trigger_sequence()
            time.sleep(timeout)
        # put back the default trigger configruation
        self.generator.stop_trigger_sequence()
        # put all leds to 0
        self.all_off('AC')

    def loop_over_dc_levels(self, levels=range(100, 600, 50), timeout=0.05,
                            n_triggers=1000, frequency=100):
        """
        loop_over_ac_pixels(level,timeout,trigger,n_trigger)

        A function to light AC pixels one after the other in increasing
        software pixel id

        Inputs :
                 - level   : the DAC level to apply (int)
                 - timeout : the amount of time, in s, to keep the pixels on
                             (float)
                 - n_trigger : number of consecutive trigger for AC (int)
                 - frequency: frequency of the trigger (float)
        """
        # Initialise the trigger
        self.generator.configure_trigger(n_pulse=n_triggers, freq=frequency)
        # set all led to ON
        self.all_on('DC', 0)
        # loop over the levels to set the DAC level
        for i, level in enumerate(levels):
            print('Setting level', level)
            for board in self.cts.LED_boards:
                self.cts_client.set_dc_level(board.internal_id, level)
            self.generator.start_trigger_sequence()
            time.sleep(timeout)
        # put back the default trigger configruation
        self.generator.stop_trigger_sequence()
        # put all leds to 0
        self.all_off('DC')

    def loop_over_dc_levels_with_ac(self, levels=range(100, 600, 50),
                                    ac_level=300, timeout=0.05,
                                    n_triggers=1000, frequency=100):
        """
        loop_over_ac_pixels(level,timeout,trigger,n_trigger)

        A function to light AC pixels one after the other in increasing
        software pixel id

        Inputs :
                 - level   : the DAC level to apply (int)
                 - timeout : the amount of time, in s, to keep the pixels on
                             (float)
                 - n_trigger : number of consecutive trigger for AC (int)
                 - frequency: frequency of the trigger (float)
        """
        # Initialise the trigger
        self.generator.configure_trigger(n_pulse=n_triggers, freq=frequency)
        # set all led to ON
        self.all_on('DC', 0, trig_sequence=False)
        self.all_on('AC', ac_level, trig_sequence=False)
        # loop over the levels to set the DAC level
        for i, level in enumerate(levels):
            print('Setting level', level)
            for board in self.cts.LED_boards:
                self.cts_client.set_dc_level(board.internal_id, level)
            self.generator.start_trigger_sequence()
            time.sleep(timeout)
        # put back the default trigger configruation
        self.generator.stop_trigger_sequence()
        # put all leds to 0
        self.all_off('DC')
        self.all_off('AC')

    def loop_over_ac_pixels(self, level, timeout=0.05, n_triggers=10,
                            frequency=1000, start_pixel=None,
                            stop_pixel=None):
        """
        loop_over_ac_pixels(level,timeout,trigger,n_trigger)

        A function to light AC pixels one after the other in increasing
        software pixel id

        Inputs :
                 - level   : the DAC level to apply (int)
                 - timeout : the amount of time, in s, to keep the pixels on
                             (float)
                 - n_trigger : number of consecutive trigger for AC
                 - frequency: frequency of the trigger (float)
                 - start_pixel : the first pixel of the sequence
                 - stop_pixel : the last pixel of the sequence
        """
        # Initialise the trigger
        self.generator.configure_trigger(n_pulse=n_triggers, freq=frequency)
        # loop over the patches to set the DAC level
        for patch in self.cts.LED_patches:
            self.cts_client.set_ac_level(patch.camera_patch_id, level)
        # loop over the pixels
        pixel_list = list(self.cts.pixel_to_led['AC'].keys())
        pixel_list.sort()
        for i, pix in enumerate(pixel_list):
            if start_pixel and pix < start_pixel:
                continue
            if stop_pixel and pix > stop_pixel:
                continue
            if i > 0:
                # turn off the previous pixel
                self.cts_client.set_led_status('AC', pixel_list[i - 1], False)
                self.ac_status[pixel_list[i - 1]] = 0
                self.ac_level[pixel_list[i - 1]] = 0
            time.sleep(timeout)
            # turn on this pixel
            self.cts_client.set_led_status('AC', pixel_list[i], True)
            self.ac_status[pixel_list[i]] = 1
            self.ac_level[pixel_list[i]] = level
            self.generator.start_trigger_sequence()
            if self.plotting:
                self.plot()
            time.sleep(timeout)
        # turn off the last pixel
        self.cts_client.set_led_status('AC', pixel_list[-1], False)
        self.ac_status[pixel_list[-1]] = 0
        # loop over hte patches and put the DAC back to 0
        for patch in self.cts.LED_patches:
            self.cts_client.set_ac_level(patch.camera_patch_id, 0)
            self.ac_level[pixel_list[-1]] = level
        # put back the default trigger configruation
        self.generator.stop_trigger_sequence()

    def loop_over_dc_patches(self, level, timeout=0.5):
        """
        loop_over_dc_patches(level,timeout)

        A function to light DC patches one after the other in increasing
        software patch id

        Inputs :
                 - level   : the DAC level to apply (int)
                 - timeout : the amount of time, in s, to keep the patches on
                             (float)
        """

        # set the level on all LED boards
        for board in self.cts.LED_boards:
            self.cts_client.set_dc_level(board.internal_id, level)
        # loop over the patches

        patch_list = list(self.cts.patch_camera_to_patch_led.keys())
        patch_list.sort()

        for i, patch in enumerate(patch_list):
            patch_led = self.cts.patch_camera_to_patch_led[patch]
            ledpatch = self.cts.LED_patches[patch_led]
            if i > 0:
                # turn off the previous patch
                ledpatch_prev = self.cts.LED_patches[
                    self.cts.patch_camera_to_patch_led[
                        list(self.cts.patch_camera_to_patch_led.keys())[i - 1]
                    ]
                ]
                for pix in ledpatch_prev.leds_camera_pixel_id:
                    self.cts_client.set_led_status('DC', pix, False)
                    self.dc_status[pix] = 0
                    self.dc_level[pix] = 0
            # turn on the present patch
            for pix in ledpatch.leds_camera_pixel_id:
                self.cts_client.set_led_status('DC', pix, True)
                self.dc_status[pix] = 1
                self.dc_level[pix] = level

            if self.plotting:
                self.plot()
            time.sleep(timeout)

        # turn off last patch
        patch_led = self.cts.patch_camera_to_patch_led[patch_list[-1]]
        for pix in self.cts.LED_patches[patch_led].leds_camera_pixel_id:
            self.cts_client.set_led_status('DC', pix, False)
            self.dc_status[pix] = 0
            self.dc_level[pix] = 0
        # set back the level to 0
        for board in self.cts.LED_boards:
            self.cts_client.set_dc_level(board.internal_id, 0)

    def loop_over_ac_patches(self, level, timeout=0.5, n_triggers=10):
        """
        loop_over_ac_patches(level,timeout)

        A function to light AC patches one after the other in increasing
        software patch id

        Inputs :
                 - level   : the DAC level to apply (int)
                 - timeout : the amount of time, in s, to keep the patches on
                             (float)
                 - n_triggers: number of consecutive triggers
        """
        # configure the trigger
        self.generator.configure_trigger(n_pulse=n_triggers)
        # loop over the patches
        patch_list = list(self.cts.patch_camera_to_patch_led.keys())
        patch_list.sort()

        for i, patch in enumerate(patch_list):
            patch_led = self.cts.patch_camera_to_patch_led[patch]
            ledpatch = self.cts.LED_patches[patch_led]
            if i > 0:
                # turn off the previous patch
                ledpatch_prev = self.cts.LED_patches[
                    self.cts.patch_camera_to_patch_led[patch_list[i - 1]]]
                for pix in ledpatch_prev.leds_camera_pixel_id:
                    self.cts_client.set_led_status('AC', pix, False)
                # put back the DAC level to 0
                self.cts_client.set_ac_level(patch, 0)
            # turn on the present patch
            for pix in ledpatch.leds_camera_pixel_id:
                self.cts_client.set_led_status('AC', pix, True)
            # turn on the DAC level
            self.cts_client.set_ac_level(patch, level)
            self.generator.start_trigger_sequence()
            time.sleep(timeout)

        # turn off last patch
        patch_led = self.cts.patch_camera_to_patch_led[patch_list[-1]]
        for pix in self.cts.LED_patches[patch_led].leds_camera_pixel_id:
            self.cts_client.set_led_status('AC', pix, False)
        # set back the level to 0
        for patch in self.cts.LED_patches:
            self.cts_client.set_ac_level(patch.camera_patch_id, 0)

        self.generator.stop_trigger_sequence()

    def turn_on(self, pixel, led_type, level, enable_plot=True,
                enable_trigger=True, iscluster=False):
        """
        turn_on(pixel,led_type,level)

        A function to turn on the AC or DC led in front of a given pixel
        with a given level

        Input :
               - pixel : the software pixel id in front of which the led
                         should be turned on (int)
               - led_type : the type of led (str could be 'AC' or 'DC')
               - level : the DAC level
        """
        if led_type == 'AC':
            led_ac = self.cts.pixel_to_led['AC'][pixel]
            patch = self.cts.LEDs[led_ac].camera_patch_id
            self.cts_client.set_ac_level(patch, level)
            self.cts_client.set_led_status('AC', pixel, True)
            self.ac_level[pixel] = level
            self.ac_status[pixel] = 1
            if enable_trigger:
                self.generator.start_trigger_sequence()
            if self.plotting and enable_plot:
                self.plot()

        if led_type == 'DC':
            if isinstance(pixel, list) or iscluster:
                if iscluster:
                    pixel = self.cts.camera.Clusters_7[pixel].pixelsID
                    print('Cluster made of', pixel)
                for pix in pixel:
                    led_dc = self.cts.pixel_to_led['DC'][pix]
                    board = self.cts.LEDs[led_dc].led_board
                    self.cts_client.set_dc_level(board, level)
                    self.cts_client.set_led_status('DC', pix, True)
                    self.dc_level[pix] = level
                    self.dc_status[pix] = 1
                    if self.plotting and enable_plot:
                        self.plot()
            else:
                led_dc = self.cts.pixel_to_led['DC'][pixel]
                board = self.cts.LEDs[led_dc].led_board
                self.cts_client.set_dc_level(board, level)
                self.cts_client.set_led_status('DC', pixel, True)
                self.dc_level[pixel] = level
                self.dc_status[pixel] = 1
                if self.plotting and enable_plot:
                    self.plot()

    def turn_off(self, pixel, led_type, enable_plot=True,
                 enable_trigger=True):
        """
        turn_off(pixel,led_type)

        A function to turn off the AC or DC led in front of a given pixel

        Input :
               - pixel : the software pixel id in front of which the led
                         should be turned on (int)
               - led_type : the type of led (str could be 'AC' or 'DC')
        """
        if led_type == 'AC':
            if enable_trigger:
                self.generator.stop_trigger_sequence()
            led_ac = self.cts.pixel_to_led['AC'][pixel]
            patch = self.cts.LEDs[led_ac].camera_patch_id
            self.cts_client.set_ac_level(patch, 0)
            self.cts_client.set_led_status('AC', pixel, False)
            self.dc_level[pixel] = 0
            self.dc_status[pixel] = 0
            if self.plotting and enable_plot:
                self.plot()
        if led_type == 'DC':
            board = self.cts.LEDs[self.cts.pixel_to_led['DC'][pixel]].led_board
            self.cts_client.set_dc_level(board, 0)
            self.cts_client.set_led_status('DC', pixel, False)
            self.dc_level[pixel] = 0
            self.dc_status[pixel] = 0
            if self.plotting and enable_plot:
                self.plot()

    def all_on(self, led_type, level, trig_sequence=True):
        """
        all_on(led_type,level)

        A function to turn on all CTS led AC or DC

        Input:
              - led_type : type of the leds to be turned on 'AC' or 'DC' (str)
              - level    : the DAC level (int)

        """
        for pixel in self.cts.pixel_to_led[led_type].keys():
            self.turn_on(pixel, led_type, level, enable_plot=False,
                         enable_trigger=False)
        if trig_sequence:
            self.generator.start_trigger_sequence()

    def all_off(self, led_type):
        """
        all_on(led_type,level)

        A function to turn on all CTS led AC or DC

        Input:
              - led_type : type of the leds to be turned on 'AC' or 'DC' (str)
              - level    : the DAC level (int)

        """
        self.generator.stop_trigger_sequence()
        for pixel in self.cts.pixel_to_led[led_type].keys():
            self.turn_off(pixel, led_type, enable_plot=False)

    def dry_runs(self, n_batch=20, batch_size=1000, freq_pulse=300,
                 timeout=60):
        # first make sure the leds are at 0
        self.reset()
        # then configrue the trigger
        self.generator.configure_trigger(n_pulse=batch_size, freq=freq_pulse)
        i = 0
        while i < n_batch:
            self.generator.start_trigger_sequence()
            time.sleep(timeout)

    def print_status(self):
        """
        print_status()

        A function to visualise in command line the status of each LED

        It will print the values stored in the datapoints published by the
        server and should be representative of the values in hardware

        To force a reading of the values in the hardware first call update()
        which will update the datapoints with results of can request
        """
        pixel_list = list(self.cts.pixel_to_led['DC'].keys())
        pixel_list.sort()
        print('============================================== Status')
        for pix in pixel_list:
            board = self.cts.LEDs[self.cts.pixel_to_led['DC'][pix]].led_board
            ac_led = self.cts.pixel_to_led['AC'][pix]
            patch = self.cts.LEDs[ac_led].camera_patch_id
            nameb = 'CTS.DC.Board' + str(board)
            namep = 'CTS.AC.Patch' + str(patch)
            print('| pix patch ledboard:', "%04d" % pix, "%03d" % patch,
                  "%02d" % board, end=' ')
            self.dc_level[pix] = self.cts_client.client.get_node(
                ua.NodeId(nameb + '.DC_DAC')
            ).get_value()
            print('| DC_Level:', self.dc_level[pix], end=' ')
            self.ac_level[pix] = self.cts_client.client.get_node(
                ua.NodeId(namep + '.AC_DAC')
            ).get_value()
            print('| AC_Level:', self.ac_level[pix], end=' ')
            dc_dcdc = self.cts_client.client.get_node(
                ua.NodeId(nameb + '.DC_DCDC')
            ).get_value()
            print('| DC DCDC:', dc_dcdc, end=' ')
            ac_dcdc = self.cts_client.client.get_node(
                ua.NodeId(nameb + '.AC_DCDC')
            ).get_value()
            print('| AC DCDC:', 0 if ac_dcdc > 0.5 else 1, end=' ')  # opposite
            self.ac_status[pix] = int(
                self.cts_client.client.get_node(
                    ua.NodeId(namep + '.LED' + str(pix) + '.Status')
                ).get_value()
            )
            print('| AC Status:', self.ac_status[pix], end=' ')
            self.dc_status[pix] = int(
                self.cts_client.client.get_node(
                    ua.NodeId(nameb + '.LED' + str(pix) + '.Status')
                ).get_value()
            )
            print('| DC Status:', self.dc_status[pix])
        if self.plotting:
            self.plot()

    def write_event(self, patch_level, pix_status, level_dc):
        """
        write_event(patch_level,pix_status,level_dc)

        Write an event in the CTS out of a list of patches level, lighten
        pixels and NSB level

        Input :
               - patch_level : dictionnary conatining for each patch id (key)
                               the DAC level to apply (value)
               - pix_status  : dictionnary containing for each pixel id (key)
                               its status (True/False for ON/OFF)
               - level_dc    : DAC of the DC leds to emulate the NSB
        """
        # DC Logic: apply DC level to all board
        for board in self.cts.LED_boards:
            self.cts_client.set_dc_level(
                board.internal_id, int(round(level_dc))
            )
        # DC Logic: turn on all LED
        for pix_DC in self.cts.pixel_to_led['DC'].keys():
            self.cts_client.set_led_status('DC', pix_DC, True)
        # AC Logic: apply AC level to all patch
        for patch in patch_level.keys():
            self.cts_client.set_ac_level(patch, int(round(patch_level[patch])))
        # AC Logic: turn on all LED
        for pix_AC in self.cts.pixel_to_led['AC'].keys():
            self.cts_client.set_led_status('AC', pix_AC, pix_status[pix_AC])
        if self.plotting:
            self.plot()

    def write_mc_event(self, nsb_level=500, evtnum=0,
                       filename='/home/sterody/Documents/CTS/' +
                                'OpcUaCameraTestSetup/data/gamma_0.csv'):
        """
        write_event(nsb_level,evtnum,filename)

        Write an event in the CTS from MC event input

        Input :
               - nsb_level    : DAC of the DC leds to emulate the NSB
               - evtnum       : event number in the file
               - filename     : input file path
        """
        # Load the event from the file
        pixel_mc = mcevent.load_event(evtnum, filename)
        # Get the patch levels and pixel status
        camera_patches_mean, pixel_status = mcevent.compute_led_patches_mean(
            self.cts, pixel_mc
        )
        # Write the event in the CTS
        self.write_event(camera_patches_mean, pixel_status, nsb_level)

    def loop_mc_event(self, nevent, nsb_level=500,
                      filename='/home/sterody/Documents/CTS/' +
                               'OpcUaCameraTestSetup/data/gamma_0.csv',
                      n_triggers=1000):
        self.generator.configure_trigger(n_trigger=n_triggers)
        for i in range(nevent):
            self.write_mc_event(nsb_level, i, filename)
            # TODO Start run
            self.generator.start_trigger_sequence()
            time.sleep(1.)

    def plot(self):
        self.plots[0].image = np.multiply(self.ac_status, self.ac_level)
        self.plots[0].axes.set_xlim([-500, 500])
        self.plots[0].axes.set_ylim([-500, 500])
        self.plots[1].image = np.multiply(self.dc_status, self.dc_level)
        self.plots[1].axes.set_xlim([-500, 500])
        self.plots[1].axes.set_ylim([-500, 500])
        plt.show()


if __name__ == "__main__":
    ctsmaster = CTSMaster(240.)
