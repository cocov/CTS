import time
import can
import numpy as np
from can.interfaces.socketcan import SocketcanNative_Bus


alladd = [((0b1101 << 7) | x + 1) for x in range(1, 108)]


class DictDiffer(object):
    """
    Calculate the difference between two dictionaries as:
    (1) items added
    (2) items removed
    (3) keys same in both but changed values
    (4) keys same in both and unchanged values
    """

    def __init__(self, current_dict, past_dict):
        self.current_dict, self.past_dict = current_dict, past_dict
        self.set_current, self.set_past = set(
            current_dict.keys()), set(
            past_dict.keys())
        self.intersect = self.set_current.intersection(self.set_past)

    def added(self):
        return self.set_current - self.intersect

    def removed(self):
        return self.set_past - self.intersect

    def changed(self):
        return set(o for o in self.intersect if self.past_dict[
            o] != self.current_dict[o])

    def unchanged(self):
        return set(o for o in self.intersect if self.past_dict[
            o] == self.current_dict[o])


def w2rAdd(w):
    return (0b1111111 & w) | (0b1101 << 7)


def r2wAdd(r):
    return (0b1111111 & r) | (0b1100 << 7)


def toMod(a):
    return (0b1111111 & a) - 1


def mod2r(m):
    return (m + 1 & 0b1111111) | (0b1101 << 7)


def mod2w(m):
    return (m + 1 & 0b1111111) | (0b1100 << 7)


def mod2chboard(m):
    return ((m - 1) % 4), int((m - 1) / 4)


def chboard2mod(c, b):
    return b * 4 + c + 1


def canID(
        masterID=0b110,
        slaveID=0b0,
        broadcastAnswer=False,
        answer=False,
        verbose=False):
    '''
    Form the can adressing as function of the:
       masterID: is the network ID of the master
       slaveID : is the slave can adress, if set to 0, it will be a broadcast
       isAnswer: is the adress used for a recieve function
       requiersAnswer : is the request expecting answer
    '''
    # Checks
    if slaveID > 0b1111111:
        raise Exception('Invalid slave address, >127')
    if masterID > 0b111:
        raise Exception('Invalid master address, >7')

    # Assign the parameters
    # Deal with broadcasting
    canid = 0b0
    if slaveID == 0b0 and not broadcastAnswer:
        canid = 0b1
    elif slaveID > 0:
        canid = slaveID + 1

    # Deal with slave address
    canid &= 0b1111111

    canid |= (masterID << 8)

    # Is it an answer or request
    if answer:
        canid |= (0b1 << 7)

    if verbose:
        print(bin(canid), hex(canid))

    return canid


def command(
        bus,
        slaveIDs,
        cmdtype,
        canmsg=[],
        waitanswer=True,
        broadcast=False,
        broadcastAnswer=False,
        masterID=0b110,
        verbose=False):
    msgID = None
    cmdtypes = {
        'Abort': 0x00,
        'SetCANAddress': 0x01,
        'SetDACLevel': 0x02,
        'SetLED': 0x03,
        'GetLEDandDAC': 0x04,
        'GetVersion': 0x1E,
    }
    msgID = cmdtypes[cmdtype]

    sendIDs, recieveIDs = [], []
    if broadcast:
        sendIDs.append(
            canID(
                masterID=masterID,
                slaveID=0b0,
                broadcastAnswer=broadcastAnswer,
                verbose=verbose))
        if broadcastAnswer:
            recieveIDs.append(
                [canID(masterID=masterID,
                       slaveID=slaveID,
                       answer=True,
                       verbose=verbose) for slaveID in slaveIDs]
            )
    else:
        for slaveID in slaveIDs:
            sendIDs.append(
                canID(
                    masterID=masterID,
                    slaveID=slaveID,
                    broadcastAnswer=broadcastAnswer,
                    verbose=verbose))
            if cmdtype == 'SetCANAddress' and canmsg[0] == 0x01:
                if slaveID != 126:
                    recieveIDs.append([
                        canID(
                            masterID=masterID,
                            slaveID=canmsg[1]+(slaveID-1) % 4,
                            broadcastAnswer=False,
                            answer=True,
                            verbose=verbose),
                        canID(
                            masterID=masterID,
                            slaveID=slaveID,
                            broadcastAnswer=broadcastAnswer,
                            answer=True,
                            verbose=verbose)
                    ])
                else:
                    recieveIDs.append([
                        canID(
                            masterID=masterID,
                            slaveID=canmsg[1],
                            broadcastAnswer=False,
                            answer=True,
                            verbose=verbose),
                        canID(
                            masterID=masterID,
                            slaveID=canmsg[1]+1,
                            broadcastAnswer=False,
                            answer=True,
                            verbose=verbose),
                        canID(
                            masterID=masterID,
                            slaveID=canmsg[1]+2,
                            broadcastAnswer=False,
                            answer=True,
                            verbose=verbose),
                        canID(
                            masterID=masterID,
                            slaveID=canmsg[1]+3,
                            broadcastAnswer=False,
                            answer=True,
                            verbose=verbose),
                        canID(
                            masterID=masterID,
                            slaveID=slaveID,
                            broadcastAnswer=broadcastAnswer,
                            answer=True,
                            verbose=verbose)
                    ])
            else:
                recieveIDs.append(
                    canID(
                        masterID=masterID,
                        slaveID=slaveID,
                        broadcastAnswer=broadcastAnswer,
                        answer=True,
                        verbose=verbose))

    r = []
    # empty the response cache
    flushAnswer(bus)
    # send messages ans listen to responses
    for i, sendID in enumerate(sendIDs):
        data_msg = [msgID]
        data_msg.extend(canmsg)
        msg = can.Message(arbitration_id=sendID,
                          data=data_msg,
                          extended_id=False)
        if verbose:
            print('sending:', msg)
        bus.send(msg)
        if waitanswer:
            resp = 0
            to_recieve = recieveIDs[i]
            if not isinstance(to_recieve, list):
                to_recieve = [to_recieve]
            while True:
                resp = bus.recv(1)
                if resp is None:
                    break
                if resp.data[0] & 0x1f != msgID:
                    print('WARNING: unexpected message ID:', resp)
                    continue
                if resp.arbitration_id in to_recieve:
                    r.append(resp)
                    if verbose:
                        print('recieved:', resp)
                else:
                    if resp.arbitration_id not in to_recieve:
                        print('WARNING: unexpected message source:',
                              resp.arbitration_id,
                              'expected one of:', to_recieve)
                        continue
    return r


def setAddress(bus, origAdd, modnum):
    # disable protection on slave addresses
    resp = command(bus, [origAdd],
                   'SetCANAddress', [0x0, 0x07],
                   waitanswer=True,
                   broadcast=False,
                   broadcastAnswer=False)
    if resp[0].data[1] != 0:
        raise ConnectionError(
            'got error code %d while disabling protection' % resp[0].data[1]
        )
    resp = command(bus, [origAdd], 'SetCANAddress', [0x1, modnum],
                   waitanswer=True,
                   broadcast=False,
                   broadcastAnswer=False)
    if resp[0].data[1] != 0:
        raise ConnectionError(
            'got error code %d while setting new address' % resp[0].data[1]
        )


def setBoardAddresses(bus, boardnum):
    modnum = (boardnum - 1) * 4 + 1
    # get the adresses
    slaveID = list(range(1, 109))
    slaveID.append(126)
    resp = command(bus, slaveID, 'GetVersion',
                   verbose=False, broadcast=True, broadcastAnswer=True)
    if resp[0].arbitration_id == 0x6ff:
        # The board is uninitialized
        setAddress(bus, 126, modnum)
    else:
        addresses = sorted([r.arbitration_id for r in resp])
        if len(addresses) != 4:
            raise ConnectionAbortedError(
                'found %d adresses when expected 4.' % len(addresses) +
                'Are several cards attached to CAN ?'
            )
        modules = [toMod(add) for add in addresses]
        print('Original adresses:', addresses, ', modules:', modules)
        # change the addresses
        for mod in modules:
            setAddress(bus, mod, modnum)
    time.sleep(0.1)
    # check new address
    resp = command(bus, slaveID, 'GetVersion',
                   verbose=False, broadcast=True, broadcastAnswer=True)
    addresses = sorted([r.arbitration_id for r in resp])
    modules = [toMod(add) for add in addresses]
    print('New adresses:', addresses, ', modules:', modules)


def updateStatus(bus, statusdict):
    # Get the LED status
    statusdict.update(checkLEDStatus(bus))
    # Get the LED level
    statusdict.update(checkLEDLevel(bus))


def checkModules(bus, verbose=False):
    # Send a broadcast to get the version and see who is responding
    print('Get the modules list...')
    res = command(
        bus,
        range(1, 109),
        'GetVersion',
        broadcast=True,
        broadcastAnswer=True,
        verbose=verbose,
        waitanswer=True
    )
    modList = []
    for r in res:
        modList.append(toMod(r.arbitration_id))
    return {'ModuleList': modList}


def checkLEDStatus(bus, module=None, verbose=False):
    print('Get AC and DC Status...')
    res = None
    if not module:
        res = command(
            bus,
            range(1, 109),
            'GetLEDandDAC',
            [0x00],
            broadcast=True,
            broadcastAnswer=True,
            verbose=False,
            waitanswer=True)
    else:
        res = command(bus, [module], 'GetLEDandDAC', [0x00], waitanswer=True)
    # check the response is the expected code:
    for r in res:
        if r.data[0] != 0x04:
            raise Exception('Answer code not aligned with request...')
    resdict = {}
    # Get the information per modules
    for r in res:
        mod = toMod(r.arbitration_id)
        # Get the DC LED status
        resdict['M_' + str(mod) + '_DCDC_Status'] = \
            'OFF' if r.data[4] == 0 else 'ON'
        resdict['M_' + str(mod) + '_ACLED_Status'] = []
        acstat = r.data[1] << 16 | r.data[2] << 8 | r.data[3]
        # Get the AC LED status
        for x in range(24):
            if ((1 << x) & acstat) >> x == 1:
                resdict['M_' + str(mod) + '_ACLED_Status'].append('ON')
            else:
                resdict['M_' + str(mod) + '_ACLED_Status'].append('OFF')
    if verbose:
        print('=================== LED STATUS =======================')
        for r in res:
            mod = toMod(r.arbitration_id)
            print('| Module: ', mod, 'DCDC convertor',
                  resdict['M_' + str(mod) + '_DCDC_Status'],
                  '| AC LED (0-23)',
                  resdict['M_' + str(mod) + '_ACLED_Status'])
        print('')
    return resdict


def checkLEDLevel(bus, module=None, verbose=False):
    print('Get the AC led level...')
    res = None
    if not module:
        res = command(
            bus,
            range(1, 109),
            'GetLEDandDAC',
            [0x01],
            broadcast=True,
            broadcastAnswer=True,
            verbose=False,
            waitanswer=True)
    else:
        res = command(bus, [module], 'GetLEDandDAC', [0x01], waitanswer=True)
    # check the response is the expected code:
    print('Get AC and DC levels')
    resdict = {}
    modules = []
    # Get the information per modules
    for r in res:
        # Get the DC LED status
        mod = toMod(r.arbitration_id)
        if mod not in modules:
            modules.append(mod)
        frame = r.data[0] >> 5
        channels = list(frame*3 + np.array([0, 1, 2]))
        data_channels = [(r.data[1] << 8) | r.data[2],
                         (r.data[3] << 8) | r.data[4],
                         (r.data[5] << 8) | r.data[6]]
        for ch, data in zip(channels, data_channels):
            resdict['M_' + str(mod) + '_ACLED_Ch_' + str(ch)] = data
    if verbose:
        print('=================== LED STATUS =======================')
        for mod in modules:
            print('|-----> Module:', str(mod), )
            for ch in range(8):
                print('| Ch:', ch, '-',
                      resdict['M_' + str(mod) + '_ACLED_Ch_' + str(ch)], )
            print('')
    return resdict


def setDACLevel(
        bus,
        level,
        module=None,
        channel=None,
        verbose=False,
        waitanswer=True):
    '''
    Change the DAC led level

    bus: the CAN bus (type Protocole)
    level : the required level
    module :  None will broadcast to all module (AC and DC)
              a module value will send to this module only
              (0 and 2 are for AC, 1 and 3 for DC)
    channel : None will set the same level to all channel (AC and DC)
              a channel will set the level to this channel
              (note that for DC only channel 0x0 is available)
    '''
    if verbose:
        print('Set the DAC led level...')
    res = None
    tmp_cmd = 0x8
    # print level
    level &= 0x3FF
    level_LSB = level & 0xFF
    level_MSB = (level & 0x300) >> 8
    # print level_LSB,level_MSB
    # print level,(level_MSB << 8) | level_LSB

    if channel is not None:
        tmp_cmd = channel
    if not module:
        # Set a single value everywhere
        if tmp_cmd == 8:
            # First broadcast on channel 0 such that the module for DC gets set
            res = command(
                bus,
                range(1, 109),
                'SetDACLevel',
                [0x0, level_MSB, level_LSB],
                broadcast=True,
                broadcastAnswer=True,
                waitanswer=waitanswer,
                verbose=verbose
            )
            if waitanswer:
                for r in res:
                    mod = toMod(r.arbitration_id)
                    ch, board = mod2chboard(mod)
                    if ch != 3 and r.data[1] != 0:
                        print('ERROR setting DAC on channel', ch,
                              'on board', board, 'Hw addr', ch)
            # Then broadcast on channel 8 such that all the module for AC
            # gets set
            res = command(
                bus, range(1, 109),
                'SetDACLevel',
                [tmp_cmd, level_MSB, level_LSB],
                broadcast=True,
                broadcastAnswer=True,
                waitanswer=waitanswer,
                verbose=verbose
            )
            if waitanswer:
                for r in res:
                    mod = toMod(r.arbitration_id)
                    ch, board = mod2chboard(mod)
                    if ch < 2 and r.data[1] != 0:
                        print('ERROR setting DAC on channel', tmp_cmd,
                              'on board', board, 'Hw addr', ch)
        else:
            res = command(
                bus,
                range(1, 109),
                'SetDACLevel',
                [tmp_cmd, level_MSB, level_LSB],
                broadcast=True,
                broadcastAnswer=True,
                waitanswer=waitanswer,
                verbose=verbose
            )
            if waitanswer:
                for r in res:
                    mod = toMod(r.arbitration_id)
                    ch, board = mod2chboard(mod)
                    if ch < 2 and r.data[1] != 0:
                        print('ERROR setting DAC on channel', tmp_cmd,
                              'on board', board)
                    if tmp_cmd == 0 and ch == 2 and r.data[1] != 0:
                        print('ERROR setting DAC on channel', tmp_cmd,
                              'on board', board, 'Hw addr', ch)
    else:
        ch, board = mod2chboard(module)
        if ch == 3:
            print('WARNING, setting DAC level on hw addr 3 is not allowed')
        if ch == 2 and tmp_cmd != 0:
            print('WARNING, setting DAC level on hw addr 2 is ' +
                  'only allowed on channel 0')
        res = command(
            bus,
            [module],
            'SetDACLevel',
            [tmp_cmd, level_MSB, level_LSB],
            waitanswer=waitanswer,
            verbose=verbose)
        if waitanswer:
            if len(res) == 0:
                print('WARNING, got no answer while setting the DAC level')
            elif res[0].data[1] != 0:
                raise Exception(
                    'Error setting the DAC level, code=',
                    res[0].data[1]
                )


def setLED(
        bus,
        module=None,
        led_mask=None,
        globalCmd=None,
        verbose=False,
        waitanswer=True):
    if verbose:
        print('Set the LED ON/OFF...')
        print('Set the LED ON/OFF...')
    res = None
    if led_mask is None:
        led_mask = 0xFFFFFF
    led_LSB = led_mask & 0xFF
    led_MSB = (led_mask & 0xFF00) >> 8
    led_HSB = (led_mask & 0xFF0000) >> 16
    if not module:
        # Then broadcast on channel 8 such that all the module for AC gets set
        if globalCmd is None:
            res = command(
                bus, range(1, 109), 'SetLED',
                [led_HSB, led_MSB, led_LSB, False],
                broadcast=True, broadcastAnswer=True
            )
        else:
            res = command(
                bus, range(1, 109), 'SetLED',
                [led_HSB, led_MSB, led_LSB, globalCmd],
                broadcast=True, broadcastAnswer=True
            )
    else:
        if globalCmd is None:
            res = command(
                bus, [module], 'SetLED',
                [led_HSB, led_MSB, led_LSB, False], waitanswer=waitanswer
            )
        else:
            ch, board = mod2chboard(module)
            if globalCmd == 1 and ch % 2 == 1:
                print('WARNING: enabling DC/DC convertor on Hw addr', ch,
                      'is not allowed so it was disabled')
                globalCmd = 0
            res = command(
                bus, [module], 'SetLED',
                [led_HSB, led_MSB, led_LSB, globalCmd], waitanswer=waitanswer
            )

    if waitanswer:
        if module and len(res) == 0:
            print('WARNING: module', module, 'did not respond')
        for r in res:
            mod = toMod(r.arbitration_id)
            ch, board = mod2chboard(mod)
            if globalCmd is not None and ch % 2 == 0 and r.data[1] != 0:
                raise Exception(
                    'Error in setting the LED on board',
                    board, 'on channel', ch
                )
            if globalCmd is None and r.data[1] != 0:
                raise Exception(
                    'Error in setting the LED on board',
                    board, 'on channel', ch
                )


def flushAnswer(bus, verbose=False):
    resp = bus.recv(0)
    if verbose:
        print(resp)
    while resp is not None:
        resp = bus.recv(0)
        if verbose:
            print(resp)


def initialise_can(cts):
    # First open the device
    cts.bus = SocketcanNative_Bus(channel='can0',
                                  receive_own_messages=False,
                                  can_filters=[])
    cts.canstatus = 2
    return
