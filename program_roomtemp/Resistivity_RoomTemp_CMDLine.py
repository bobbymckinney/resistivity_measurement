#! /usr/bin/python
# -*- coding: utf-8 -*-
"""
Created: 2016-02-09
@author: Bobby McKinney (bobbymckinney@gmail.com)
"""
import os
import numpy as np
import visa # pyvisa, essential for communicating with the Keithley
import time
from datetime import datetime # for getting the current date and time
import exceptions

#==============================================================================
version = '1.0 (2016-02-09)'

#ResourceManager for visa instrument control
ResourceManager = visa.ResourceManager()

###############################################################################
class Keithley_2700:
    ''' Used for the matrix card operations. '''
    #--------------------------------------------------------------------------
    def __init__(self, instr):
        self.ctrl = ResourceManager.open_resource(instr)

        self.openAllChannels()
    #end init

    #--------------------------------------------------------------------------
    def closeChannels(self, channels):
        self.ctrl.write(":ROUT:MULT:CLOS (@ %s)" %channels)
    #end def

    #--------------------------------------------------------------------------
    def openChannels(self, channels):
        self.ctrl.write(":ROUT:MULT:OPEN (@ %s)" %channels)
    #end def

    #--------------------------------------------------------------------------
    def openAllChannels(self):
        self.ctrl.write("ROUTe:OPEN:ALL")
    #end def

    #--------------------------------------------------------------------------
    def get_closedChannels(self):
        return self.ctrl.query(":ROUT:MULT:CLOS?")
    #end def

#end class
###############################################################################

###############################################################################
class Keithley_2400:
    ''' SourceMeter '''
    #--------------------------------------------------------------------------
    def __init__(self, instr):
        self.ctrl = ResourceManager.open_resource(instr)

        self.ctrl.write(":ROUT:TERM REAR") # Use the rear output terminals
        self.current_mode()
        self.set_current_range(10.5*10**(-3)) # Default
        self.set_current(float(current))
    #end init

    #--------------------------------------------------------------------------
    def turn_source_on(self):
        self.ctrl.write(":OUTPut:STATe ON")
    #end def

    #--------------------------------------------------------------------------
    def turn_source_off(self):
        self.ctrl.write(":OUTPut:STATe OFF")
    #end def

    #--------------------------------------------------------------------------
    def query_state(self):
        state = self.ctrl.query(":OUTPut:STATe?")

        if state == '1':
            amplitude = self.ctrl.query(":SOURce:CURRent:LEVel:IMMediate:AMPLitude?") + ' Amps'

            if amplitude == '0.000000E+00 Amps':
                amplitude = self.ctrl.query(":SOURce:VOLTage:LEVel:IMMediate:AMPLitude?") + ' Volts'

            return 'state: %s, amplitude: %s ' % (state, amplitude)

        else:
            return 'state: %s' % state

    #end def

    #--------------------------------------------------------------------------
    def current_mode(self):
        self.ctrl.write(":SOURce:FUNCtion:MODE CURRent")
        self.ctrl.write(":SOURce:CURRent:MODE FIXed") # Fixed current mode
    #end def

    #--------------------------------------------------------------------------
    def set_current(self, current):
        self.change_current_range(current)
        #time.sleep(5)
        self.ctrl.write(":SOURce:CURRent:LEVel:IMMediate:AMPLitude %f" % current)
    #end def

    #--------------------------------------------------------------------------
    def change_current_range(self, current):
        #self.write(":SOURce:CURRent:LEVel:IMMediate:AMPLitude 0")
        if current > 0:
            if current > 105*10**(-3):
                    self.set_current_range(1.05)
            else:
                if current > 10.5*10**(-3):
                    self.set_current_range(105*10**(-3))
                else:
                    if current > 1.05*10**(-3):
                        self.set_current_range(10.5*10**(-3))
                    else:
                        if current > 105*10**(-6):
                            self.set_current_range(1.05*10**(-3))
                        else:
                            if current > 10.5*10**(-6):
                                self.set_current_range(105*10**(-6))
                            else:
                                if current > 1.05*10**(-6):
                                    self.set_current_range(10.5*10**(-6))
                                else:
                                    self.set_current_range(1.05*10**(-6))

        elif current < 0:
            if current < -105*10**(-3):
                    self.set_current_range(-1.05)
            else:
                if current < -10.5*10**(-3):
                    self.set_current_range(-105*10**(-3))
                else:
                    if current < -1.05*10**(-3):
                        self.set_current_range(-10.5*10**(-3))
                    else:
                        if current < -105*10**(-6):
                            self.set_current_range(-1.05*10**(-3))
                        else:
                            if current < -10.5*10**(-6):
                                self.set_current_range(-105*10**(-6))
                            else:
                                if current < -1.05*10**(-6):
                                    self.set_current_range(-10.5*10**(-6))
                                else:
                                    self.set_current_range(-1.05*10**(-6))

        else:
            self.set_current_range(1.05*10**(-6))

    #end def

    #--------------------------------------------------------------------------
    def set_current_range(self, current):
        self.ctrl.write(":SOURce:CURRent:RANGe %f" % current)

    #end def

    #--------------------------------------------------------------------------
    def voltage_mode(self):
        self.ctrl.write(":SOURce:FUNCtion:MODE VOLTage")
        self.ctrl.write(":SOURce:VOLTage:MODE FIXed") # Fixed voltage mode
    #end def

    #--------------------------------------------------------------------------
    def set_voltage(self, voltage):
        self.ctrl.write(":SOURce:VOLTage:LEVel:IMMediate:AMPLitude %f" % voltage)
    #end def

#end class
###############################################################################

###############################################################################
class Keithley_2182:
    ''' NanoVoltMeter '''
    #--------------------------------------------------------------------------
    def __init__(self, instr):
        self.ctrl = ResourceManager.open_resource(instr)

        self.ctrl.write(":TRIGger:SEQuence1:COUNt 1")
        self.ctrl.write(":TRIGger:SEQuence1:DELay 0") # Set count rate
        self.ctrl.write(":SENSe:FUNCtion VOLTage")
        self.ctrl.write(":SENSe1:VOLTage:DC:NPLCycles 5") # Sets integration period based on frequency
    #end init

    #--------------------------------------------------------------------------
    def fetch(self):
        """
        Scan the channel and take a reading
        """
        #self.write(":ROUTe:SCAN:INTernal:CCOunt 1") # Specify number of readings on channel 1
        self.ctrl.write(":SENSe:CHANnel 1")
        data = self.ctrl.query(":SENSe:DATA:FRESh?")
        #print str(data)[0:15]
        #print data
        return str(data)[0:15] # Fetches Reading

    #end def

#end class
###############################################################################

###############################################################################
class Main:
    def __init__(self):

        self.Setup()
        self.Get_User_Input()
        self.open_files()
        
        self.abort_ID = 0
        self.start = time.time()
        self.delay = 2
        self.rAcalclist = []
        self.rBcalclist = []

        for n in range(self.measurement_number):
            # start measurement
            print 'measurement number: ', n
            self.take_resistivity_data()
            self.write_data_to_file('data')
        #end for
        self.process_data()
        self.save_files()
    #end def
    #--------------------------------------------------------------------------
    def Setup(self):
        # Define Keithley instrument ports:
        self.k2700 = Keithley_2700('GPIB0::16::INSTR') # MultiMeter for Matrix Card operation
        self.k2400 = Keithley_2400('GPIB0::24::INSTR') # SourceMeter
        self.k2182 = Keithley_2182('GPIB0::7::INSTR') # NanoVoltMeter
    #end def
    #--------------------------------------------------------------------------
    def Get_User_Input(self):
        print "Get Input From User"
    
        self.current = input("Please enter source current in mA (example: 20): ")
        self.current = float(self.current) / 1000
        if self.current > .1:
            self.current = .1
        #end if
        
        self.measurement_number = input("Please enter measurement number at each temp (example: 5): ")
        self.measurement_number = int(self.measurement_number)
    
        self.thickness = input("Please enter sample thickness in cm (example: .1): ")
        self.thickness = float(self.thickness)
    
        print "Your data folder will be saved to Desktop automatically"
        self.folder_name = input("Please enter name for folder: ")
        self.make_new_folder(self.folder_name)
    #end def
    
    #--------------------------------------------------------------------------
    def make_new_folder(self, folder_name):
        self.filePath = "~/Desktop/" + folder_name
        found = False
        if not os.path.exists(self.filePath):
            os.makedirs(self.filePath)
            os.chdir(self.filePath)
        #end if
        else:
            n = 1
            while found == False:
                path = self.filePath + ' - ' + str(n)
                if os.path.exists(path):
                    n = n + 1
                #end if
                else:
                    os.makedirs(path)
                    os.chdir(path)
                    n = 1
                    found = True
                #end else
            #end while
        #end else
        if found == True:
            self.filePath = path
        #end if
    #end def
    
    #--------------------------------------------------------------------------
    def open_files(self):
        
        self.datafile = open('Data.csv', 'w') # opens file for writing/overwriting
        self.voltagefile = open('Voltage.csv','w')
        self.resistivityfile = open('Resistivity.csv','w')
    
        begin = datetime.now() # Current date and time
        self.datafile.write('Start Time: ' + str(begin) + '\n')
        self.voltagefile.write('Start Time: ' +str(begin) + '\n')
        self.resistivityfile.write('Start Time: ' + str(begin) + '\n')

        dataheaders = 'time (s), temp (C), thickness (cm), R_A (mOhm), R_B (mOhm), resistivity (mOhm*cm)\n'
        self.datafile.write(dataheaders)
        
        voltageheaders = 'time (s), measurement, current (mA), voltage_1p (mV), voltage_n (mV), voltage_2p (mV)\n'
        self.voltagefile.write(tempheaders)

        resistivityheaders = 'time (s), temp (C),resistivity (mOhm*cm)\n'
        self.resistivityfile.write(resitivityheaders)
    #end def

    #--------------------------------------------------------------------------
    def take_resistivity_data(self):
        print('measure resistivity\n')
        # short the matrix card
        self.k2700.closeChannels('117, 125, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        time.sleep(self.delay)
    
        ### self.r_A:
        # r_12,34
        print('measure r_12,34')
        self.k2700.openChannels('125, 127, 128')
        print(self.k2700.get_closedChannels())
        self.r_1234, self.t_1234 = self.delta_method('1234')
        self.r_1234 = abs(self.r_1234)
        self.k2700.closeChannels('125, 127, 128')
        print(self.k2700.get_closedChannels())
        print "t_1234: %.2f s\tr_1234: %.2f Ohm" % (self.t_1234, self.r_1234)
        time.sleep(self.delay)

        # r_34,12
        print('measure r_34,12')
        self.k2700.closeChannels('118')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        self.r_3412, self.t_3412 = self.delta_method('3412')
        self.r_3412 = abs(self.r_3412)
        self.k2700.closeChannels('117, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('118')
        print(self.k2700.get_closedChannels())
        print "t_3412: %.2f s\tr_3412: %.2f Ohm" % (self.t_3412, self.r_3412)
        time.sleep(self.delay)

        # Calculate self.r_A
        self.r_A = (self.r_1234 + self.r_3412)/2
        self.t_A = (self.t_1234 + self.t_3412)/2
        print "t_A: %.2f s\tr_A: %.2f Ohm" % (self.t_A, self.r_A)

        ### self.r_B:
        # r_13,24
        print('measure r_13,24')
        self.k2700.closeChannels('119')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 125, 126, 127')
        print(self.k2700.get_closedChannels())
        self.r_1324, self.t_1324 = self.delta_method('1324')
        self.r_1324 = abs(self.r_1324)
        self.k2700.closeChannels('117, 125, 126, 127')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('119')
        print(self.k2700.get_closedChannels())
        print "t_1324: %.2f s\tr_1324: %.2f Ohm" % (self.t_1324, self.r_1324)
        time.sleep(self.delay)

        # r_24,13
        print('measure r_24,13')
        self.k2700.closeChannels('120')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 125, 126, 128')
        print(self.k2700.get_closedChannels())
        self.r_2413, self.t_2413 = self.delta_method('2413')
        self.r_2413 = abs(self.r_2413)
        self.k2700.closeChannels('117, 125, 126, 128')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('120')
        print(self.k2700.get_closedChannels())
        print "t_2413: %.2f s\tr_2413: %.2f Ohm" % (self.t_2413, self.r_2413)
    
        # Calculate self.r_B
        self.r_B = (self.r_1324 + self.r_2413)/2
        self.t_B = (self.t_1324 + self.t_2413)/2
        print "t_B: %.2f s\tr_B: %.2f Ohm" % (self.t_B, self.r_B)

        self.resistivity = self.resistivitycalc([self.r_A],[self.r_B])
        print "resistivity: %f" % (self.resistivity*1000)
    #end def

    #--------------------------------------------------------------------------
    def delta_method(self,measurement):
        print('Delta Method')
        t1 = time.time() - self.start
        # delta method:
        # positive V1:
        self.k2400.turn_source_on()
        self.k2400.set_current(float(self.current))
        time.sleep(self.delay)
        v1p = float( self.k2182.fetch() )
        time.sleep(self.delay)
        # negative V:
        self.k2400.set_current(-1*float(self.current))
        time.sleep(self.delay)
        vn = float( self.k2182.fetch() )
        time.sleep(self.delay)
        t2 = time.time() - self.start

        # positive V2:
        self.k2400.set_current(float(self.current))
        time.sleep(self.delay)
        v2p = float( self.k2182.fetch() )
        time.sleep(self.delay)
        self.k2400.turn_source_off()
        t3 = time.time() - self.start

        print 'Delta Method'
        print 'i: %f Amps' % float(self.current)
        print "v: %f V, %f V, %f V" % (v1p, vn, v2p)

        r = (v1p + v2p - 2*vn)/(4*float(self.current))

        avgt = (t3 + t2 + t1)/3
        self.voltagefile.write('%.1f,%s,%.3f,%.3f,%.3f,%.3f\n'%(avgt, measurement, self.current*1000, v1p*1000, vn*1000, v2p*1000))
        return r, avgt
    #end def

    #--------------------------------------------------------------------------
    def resistivitycalc(self,Alist,Blist):
        delta = 0.0005 # error limit (0.05%)
        lim = 1
        rA = np.average(Alist)
        rB = np.average(Blist)

        z1 = (2*np.log(2))/(np.pi*(rA + rB))

        # Algorithm taken from http://www.nist.gov/pml/div683/hall_algorithm.cfm
        while (lim > delta):
            y = 1/np.exp(np.pi*z1*rA) + 1/np.exp(np.pi*z1*rB)

            z2 = z1 - (1/np.pi)*((1-y)/(rA/np.exp(np.pi*z1*rA) + rB/np.exp(np.pi*z1*rB)))

            lim = abs(z2 - z1)/z2

            z1 = z2
        #end while

        rho = 1/z1*float(self.thickness)
        return rho
    #end def

    #--------------------------------------------------------------------------
    def process_data(self):
        time = np.average(self.timecalclist)
        resistivity = self.resistivitycalc(self.rAcalclist,self.rBcalclist)

        self.resistivityfile.write('%.1f,%.6f\n'%(time,resistivity*1000))
    #end def

    #--------------------------------------------------------------------------
    def write_data_to_file(self):
        print('\nWrite data to file\n')
        time = (self.t_1234 + self.t_3412 + self.t_1324 + self.t_2413)/4
        self.datafile.write('%.6f,%.6f,' %(time,self.thickness))
        self.datafile.write('%.6f,%.6f,' % (self.r_A*1000, self.r_B*1000) )
        self.datafile.write('%.6f\n' % (self.resistivity*1000))

        self.timecalclist.append(time)
        self.rAcalclist.append(self.r_A)
        self.rBcalclist.append(self.r_B)
    #end def

    #--------------------------------------------------------------------------
    def save_files(self):
        print('Save Files')
        self.datafile.close()
        self.voltagefile.close()
        self.resistivityfile.close()
    #end def
#end class
###############################################################################

#==============================================================================
if __name__=='__main__':
    runprogram = Main()
#end if