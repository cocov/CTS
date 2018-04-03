import sys
import CameraAPI as C

class ConfigMTS_module:
    def __init__(self, modules_list=['113', '114', '116', '120']):

        self.MUT = modules_list
        self.ModulesUnderTests = {'109': {}, '110': {}, '111': {}, '112': {}, '113': {}, '114': {}, '115': {}, '116': {},
                             '117': {}, '118': {}, '119': {}, '120': {}}

        self.ModulesUnderTests['109']['Vref'] = [57.8925, 57.85, 58.0325, 57.9775, 57.84, 57.7325, 57.7925, 57.63, 57.7725, 58.0225,
                                      58.1975, 58.21]
        self.ModulesUnderTests['109']['node'] = 36

        self.ModulesUnderTests['110']['Vref'] = [57.8975, 57.715, 57.6475, 57.92, 57.805, 57.515, 57.7725, 57.755, 58.215, 57.9175,
                                      57.6075, 57.6825]
        self.ModulesUnderTests['110']['node'] = 26

        self.ModulesUnderTests['111']['Vref'] = [57.56, 57.405, 57.3725, 57.1575, 57.1525, 58.03, 57.5975, 57.59, 57.675, 57.5625,
                                      57.6275, 57.75]
        self.ModulesUnderTests['111']['node'] = 27

        self.ModulesUnderTests['112']['Vref'] = [57.59, 58.185, 57.3675, 57.6275, 57.88, 57.8125, 57.305, 57.545, 57.4325, 57.54,
                                      57.4275, 57.8]
        self.ModulesUnderTests['112']['node'] = 28

        self.ModulesUnderTests['113']['Vref'] = [56.74, 56.9575, 56.85, 57.0425, 57.0875, 56.8925, 56.8, 56.9475, 56.925, 57.1725,
                                      56.915, 57.12]
        self.ModulesUnderTests['113']['node'] = 29

        self.ModulesUnderTests['114']['Vref'] = [57.075, 57.1675, 57.185, 56.7775, 56.7175, 57.02, 56.73, 57.065, 57.1275, 57.23,
                                      57.42, 57.13]
        self.ModulesUnderTests['114']['node'] = 30

        self.ModulesUnderTests['115']['Vref'] = [57.5175, 57.0275, 57.3475, 57.4075, 57.4575, 57.51, 57.385, 57.5675, 57.115, 56.975,
                                      57.255, 57.09]
        self.ModulesUnderTests['115']['node'] = 31

        self.ModulesUnderTests['116']['Vref'] = [57.0125, 57.3275, 57.085, 57.1725, 57.2525, 56.805, 57.1525, 56.715, 56.6975, 56.705,
                                      56.7475, 56.4125]
        self.ModulesUnderTests['116']['node'] = 32

        self.ModulesUnderTests['117']['Vref'] = [56.4225, 56.6725, 56.7675, 56.8725, 56.575, 56.9725, 56.9875, 57.185, 57.105, 56.81,
                                      56.6825, 56.9675]
        self.ModulesUnderTests['117']['node'] = 33

        self.ModulesUnderTests['118']['Vref'] = [57.27, 56.935, 57.3725, 56.935, 56.8225, 57.2575, 56.91, 56.7125,56.76, 56.8975,
                                      56.6725, 56.91]
        self.ModulesUnderTests['117']['node'] = 34

        self.ModulesUnderTests['119']['Vref'] = [56.925, 56.8275, 56.855, 56.8075, 56.9425, 57.0025, 56.9475, 57.26, 57.2475, 57.1925,
                                      56.905, 56.995]
        self.ModulesUnderTests['117']['node'] = 35

        self.ModulesUnderTests['120']['Vref'] = [56.8975, 57.0475, 56.7, 57.2175, 56.795, 56.8275, 57.09, 57.1225, 57.36, 57.1525,
                                      56.8375, 56.8425]
        self.ModulesUnderTests['120']['node'] = 36

        self.node_list = []
        for i in range(4):
            self.node_list.append(self.ModulesUnderTests[modules_list[i]]['node'])

        print("Node list:", self.node_list)

        self.csc = C.CameraSlowControlApplication(xml="CameraSlowControl.xml", crates=1, boards=4, verbose=1,
                                                  nodeIDs= self.node_list)

    def setGHV(self, status):
        self.csc.GHV.set(status)

    def setHV(self, status):
        self.csc.HV.set(status)

    def setLowHV(self):
        self.csc.HV.set([54]*12)

    def setAllVref(self):
        for i in range(4):
            self.csc.Vref.set(self.ModulesUnderTests[self.MUT[i]]['Vref'], slave=i)

    def existMTS(self):
        self.csc.close()

MTSinstance = ConfigMTS_module([sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]])



