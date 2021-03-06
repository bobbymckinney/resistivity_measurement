#! /usr/bin/python
# -*- coding: utf-8 -*-
"""
Created: 2015-03-31

@author: Bobby McKinney (bobbymckinney@gmail.com)

__Title__ : voltagepanel
Description:
Comments:
"""
import os
import sys
import wx
from wx.lib.pubsub import pub # For communicating b/w the thread and the GUI
import matplotlib
matplotlib.interactive(False)
matplotlib.use('WXAgg') # The recommended way to use wx with mpl is with WXAgg backend.

from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure
from matplotlib.pyplot import gcf, setp
import matplotlib.animation as animation # For plotting
import pylab
import numpy as np
import minimalmodbus as modbus # For communicating with the cn7500s
import omegacn7500 # Driver for cn7500s under minimalmodbus, adds a few easy commands
import visa # pyvisa, essential for communicating with the Keithley
from threading import Thread # For threading the processes going on behind the GUI
import time
from datetime import datetime # for getting the current date and time
# Modules for saving logs of exceptions
import exceptions
import sys
from logging_utils import setup_logging_to_file, log_exception

# for a fancy status bar:
import EnhancedStatusBar as ESB

# For finding sheet resistance:
import Hall_Processing_v1

#==============================================================================
# Keeps Windows from complaining that the port is already open:
modbus.CLOSE_PORT_AFTER_EACH_CALL = True

version = '1.0 (2015-04-06)'

'''
Global Variables:
'''

# Naming a data file:
dataFile = 'Data_Backup.csv'
finaldataFile = 'Data.csv'

thickness = '0.1' #placeholder for sample thickness in cm

current = '.001' # (A) Current that is sourced by the k2400
APP_EXIT = 1 # id for File\Quit
equil_tolerance = '1' # PID temp must not change by this value for a set time in order to reach an equilibrium
equil_time = '1' # How many measurements until the PID will change after reaching an equilibrium point
tolerance = '1' # Temperature must be within this temperature range of the PID setpoint in order to begin a measurement
measurement_time = '5' # Time for a measurement
measureList = []

maxLimit = 1000 # Restricts the user to a max temperature
maxCurrent = .01 # (A) Restricts the user to a max current

abort_ID = 0 # Abort method

# Global placers for instruments
k2700 = ''
k2400 = ''
k2182 = ''
heaterTC = ''
sampleTC = ''

# placer for directory
filePath = 'global file path'

# placer for files to be created
myfile = 'global file'

# Placers for the GUI plots:
sampletemp_list = [0]
tsampletemp_list = [0]
heatertemp_list = [0]
theatertemp_list = [0]
r_A_list = [0]
t_A_list = [0]
r_B_list = [0]
t_B_list = [0]
t_1234_list = [0]
r_1234_list = [0]
t_3412_list = [0]
r_3412_list = [0]
t_1324_list = [0]
r_1324_list = [0]
t_2413_list = [0]
r_2413_list = [0]
r_P_list = [0]
t_P_list = [0]
t_1423_list = [0]
r_1423_list = [0]
t_2314_list = [0]
r_2314_list = [0]

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
class PID(omegacn7500.OmegaCN7500):
    
    #--------------------------------------------------------------------------
    def __init__(self, portname, slaveaddress):
        omegacn7500.OmegaCN7500.__init__(self, portname, slaveaddress)
        
    #end init
        
    #--------------------------------------------------------------------------
    
    # Commands for easy reference:
    #    Use .write_register(command, value) and .read_register(command)
    #    All register values can be found in the Manual or Instruction Sheet.
    #    You must convert each address from Hex to Decimal.
    control = 4101 # Register for control method
    pIDcontrol = 0 # Value for PID control method
    pIDparam = 4124 # Register for PID parameter selection
    pIDparam_Auto = 4 # Value for Auto PID
    tCouple = 4100 # Register for setting the temperature sensor type
    tCouple_K = 0 # K type thermocouple
    heatingCoolingControl = 4102 # Register for Heating/Cooling control selection
    heating = 0 # Value for Heating setting 

#end class
###############################################################################

###############################################################################
class Setup:
    """
    Call this class to run the setup for the Keithley and the PID.
    """
    def __init__(self):
        """
        Prepare the Keithley to take data on the specified channels:
        """
        global k2700
        global k2400
        global k2182
        global sampleTC
        global heaterTC
        
        # Define Keithley instrument ports:
        self.k2700 = k2700 = Keithley_2700('GPIB2::16::INSTR') # MultiMeter for Matrix Card operation
        self.k2400 = k2400 = Keithley_2400('GPIB2::24::INSTR') # SourceMeter
        self.k2182 = k2182 = Keithley_2182('GPIB2::7::INSTR') # NanoVoltMeter
        # Define the ports for the PID
        self.sampleTC = sampleTC = PID('/dev/cu.usbserial', 1) # sample thermocouple
        self.heaterTC = heaterTC = PID('/dev/cu.usbserial', 2) # heater PID
            
        
        """
        Prepare the PID for operation:
        """
        # Set the control method to PID
        self.heaterTC.write_register(PID.control, PID.pIDcontrol)
        
        # Set the PID to auto parameter
        self.heaterTC.write_register(PID.pIDparam, PID.pIDparam_Auto)
        
        # Set the thermocouple type
        self.heaterTC.write_register(PID.tCouple, PID.tCouple_K)
        
        # Set the control to heating only
        self.heaterTC.write_register(PID.heatingCoolingControl, PID.heating)
        
        # Run the controllers
        self.heaterTC.run()

#end class
###############################################################################

###############################################################################
class ProcessThreadCheck(Thread):
    """
    Thread that runs the operations behind the GUI. This includes measuring
    and plotting.
    """
    
    #--------------------------------------------------------------------------
    def __init__(self):
        """ Init Worker Thread Class """
        Thread.__init__(self)
        self.start()
        
    #end init
        
    #--------------------------------------------------------------------------
    def run(self):
        """ Run Worker Thread """
        #Setup()
        ic = InitialCheck()
    #end def
        
#end class
###############################################################################

###############################################################################
class ProcessThreadRun(Thread):
    """
    Thread that runs the operations behind the GUI. This includes measuring
    and plotting.
    """
    
    #--------------------------------------------------------------------------
    def __init__(self):
        """ Init Worker Thread Class """
        Thread.__init__(self)
        self.start()
        
    #end init
        
    #--------------------------------------------------------------------------
    def run(self):
        """ Run Worker Thread """
        #Setup()
        td=TakeData()
        #td = TakeDataTest()
    #end def
        
#end class
###############################################################################

###############################################################################
class InitialCheck:
    """
    Intial Check of temperatures and voltages.
    """
    #--------------------------------------------------------------------------
    def __init__(self):
        global current
        self.current = current
        
        self.k2700 = k2700
        self.k2400 = k2400
        self.k2182 = k2182
        self.heaterTC = heaterTC
        self.sampleTC = sampleTC
        
        self.updateGUI(stamp='Status Bar', data='Checking')
        
        self.take_PID_Data()
        
        self.begin_measurement()
        
        self.updateGUI(stamp='Status Bar', data='Ready')
        #end init
    
    #--------------------------------------------------------------------------        
    def take_PID_Data(self):
        """ Takes data from the PID
        """
        
        # Take Data and time stamps:
        self.tH = self.heaterTC.get_pv()
        self.tS = self.sampleTC.get_pv()
        self.tHset = self.heaterTC.get_setpoint()
        
        self.updateGUI(stamp="Heater Temp Status", data=self.tH)
        self.updateGUI(stamp="Sample Temp Status", data=self.tS)
        self.updateGUI(stamp="Heater SP Status", data=self.tHset)
        
        print "Smaple Temp: %.2f C\nHeater Temp: %.2f C\nHeater Set Point: %.2f C" % (self.tS, self.tH, self.tHset)
        
    #end def
    
    #--------------------------------------------------------------------------
    def begin_measurement(self):
        
        print('Begin Measurement')
        
        self.delay = 2.5 # time for the keithley to take a steady measurement
        
        # short the matrix card
        self.k2700.closeChannels('117, 125, 126, 127, 128, 129, 130')
        time.sleep(self.delay)
        
        ### r_A: 
        # r_12,34
        self.k2700.openChannels('125, 127, 128, 129, 130')
        self.r_1234 = self.delta_method()
        self.r_1234 = abs(self.r_1234)
        self.k2700.closeChannels('125, 127, 128, 129, 130')
        print('R_1234 = %f Ohms' %self.r_1234)
        #self.updateGUI(stamp="R_1234 Status", data=self.r_1234*1000)
        
        time.sleep(self.delay)
        
        # r_34,12
        self.k2700.closeChannels('118')
        self.k2700.openChannels('117, 126, 127, 128, 129, 130')
        self.r_3412 = self.delta_method()
        self.r_3412 = abs(self.r_3412)
        self.k2700.closeChannels('117, 126, 127, 128, 129, 130')
        self.k2700.openChannels('118')
        print('R_3412 = %f Ohms' %self.r_3412)
        #self.updateGUI(stamp="R_3412 Status", data=self.r_3412*1000)
        
        time.sleep(self.delay)
        
        # Calculate r_A
        self.r_A = (self.r_1234 + self.r_3412)/2
        print('R_A = %f Ohms' %self.r_A)
        self.updateGUI(stamp="R_A Status", data=self.r_A*1000)
        
        ### r_B:
        # r_13,24
        self.k2700.closeChannels('119')
        self.k2700.openChannels('117, 125, 126, 127, 129, 130')
        self.r_1324 = self.delta_method()
        self.r_1324 = abs(self.r_1324)
        self.k2700.closeChannels('117, 125, 126, 127, 129, 130')
        self.k2700.openChannels('119')
        print('R_1324 = %f Ohms' %self.r_1324)
        #self.updateGUI(stamp="R_1324 Status", data=self.r_1324*1000)
        
        time.sleep(self.delay)
        
        # r_24,13
        self.k2700.closeChannels('120')
        self.k2700.openChannels('117, 125, 126, 128, 129, 130')
        self.r_2413 = self.delta_method()
        self.r_2413 = abs(self.r_2413)
        self.k2700.closeChannels('117, 125, 126, 128, 129, 130')
        self.k2700.openChannels('120')
        print('R_2413 = %f Ohms' %self.r_2413)
        #self.updateGUI(stamp="R_2413 Status", data=self.r_2413*1000)
        
        # Calculate r_B
        self.r_B = (self.r_1324 + self.r_2413)/2
        print('R_B = %f Ohms' %self.r_B)
        self.updateGUI(stamp="R_B Status", data=self.r_B*1000)
        
        # r_pn_14,23
        self.k2700.closeChannels('121')
        self.k2700.openChannels('117, 125, 126, 127, 128, 129')
        self.bfield(pos)
        time.sleep(self.delay)
        self.rp_1423 = self.delta_method()
        self.bfield(neg)
        time.sleep(self.delay)
        self.rn_1423 = self.delta_method()
        self.bfield(off)
        self.k2700.closeChannels('117, 125, 126, 127, 128, 129')
        self.k2700.openChannels('121')
        self.r_1423 = 1/2*(self.rp_1423-self.rn_1423)
        print('R_1423 = %f Ohms' %self.r_1423)
        
        # r_pn_23,14
        self.k2700.closeChannels('122')
        self.k2700.openChannels('117, 125, 126, 127, 128, 130')
        self.bfield(pos)
        time.sleep(self.delay)
        self.rp_2314 = self.delta_method()
        self.bfield(neg)
        time.sleep(self.delay)
        self.rn_2314 = self.delta_method()
        self.bfield(off)
        self.k2700.closeChannels('117, 125, 126, 127, 128, 130')
        self.k2700.openChannels('122')
        self.r_2314 = 1/2*(self.rp_2314-self.rn_2314)
        print('R_2314 = %f Ohms' %self.r_2314)
        
        # Calculate R_Perp
        self.r_P = (self.r1423+self.r2314)/2
        print('R_P = %f Ohms' %self.r_P)
        self.updateGUI(stamp="R_P Status", data=self.r_P*1000)
        
    #end def
    
    #--------------------------------------------------------------------------
    def delta_method(self):
        # delta method:
        # positive V1:
         
        self.k2400.turn_source_on()
        self.k2400.set_current(float(self.current))
        self.updateGUI(stamp="Current Status", data=float(self.current)*1000)
        time.sleep(self.delay) 
        v1p = float( self.k2182.fetch() )
         
        # negative V:
        self.k2400.set_current(-1*float(self.current))
        self.updateGUI(stamp="Current Status", data=-1*float(self.current)*1000)
        time.sleep(self.delay)
        vn = float( self.k2182.fetch() )
         
        # positive V2:
        self.k2400.set_current(float(self.current))
        self.updateGUI(stamp="Current Status", data=float(self.current)*1000)
        time.sleep(self.delay)
        v2p = float( self.k2182.fetch() )
         
        self.k2400.turn_source_off()
        self.updateGUI(stamp="Current Status", data=0)
         
        r = (v1p + v2p - 2*vn)/(4*float(self.current))
         
        return r
     
    #end def
    
    #--------------------------------------------------------------------------
    def bfield(self,direction):
        pass
    #end def
    
    #--------------------------------------------------------------------------
    def update_statusBar(self, msg):
        if msg == 'Running' or msg == 'Finished, Ready' or msg == 'Exception Occurred' or msg == 'Checking':
            wx.CallAfter(pub.sendMessage, "Status Bar", msg=msg)
        #end if
            
        elif len(msg) == 2:
            tol = msg[0] + 'tol'
            equil = msg[1] + 'equ'
            
            if tol[:2] == 'OK' and equil[:2] == 'OK':
                wx.CallAfter(pub.sendMessage, "Status Bar", msg=tol)
                wx.CallAfter(pub.sendMessage, "Status Bar", msg=equil)
                
                self.measurement_countdown()
                self.start_equil_timer()
                
                self.measurements_left = str(self.measurements_left) + 'mea'
                wx.CallAfter(pub.sendMessage, "Status Bar", msg=self.measurements_left)
                
                self.time_left = str(self.time_left) + 'tim'
                wx.CallAfter(pub.sendMessage, "Status Bar", msg=self.time_left)
            
            #end if
            
            else:
                self.time_left_ID = 0
                self.measurement_countdown_integer = 0
                
                wx.CallAfter(pub.sendMessage, "Status Bar", msg=tol)
                wx.CallAfter(pub.sendMessage, "Status Bar", msg=equil)
                wx.CallAfter(pub.sendMessage, "Status Bar", msg='-mea')
                wx.CallAfter(pub.sendMessage, "Status Bar", msg='-tim')
                
            #end else
                
        #end elif
        
    #end def
    
    #--------------------------------------------------------------------------
    def updateGUI(self, stamp, data):
        """
        Sends data to the GUI (main thread), for live updating while the process is running
        in another thread.
        
        There are 3 possible plots that correspond to their respective data.
        There are 11 possible types of data to send to the GUI, these include:
        
            - "PID A"
            - "PID B"
            - "PID Time"
            
            - "Voltage High"
            - "Voltage High Time"
            - "Voltage Low"
            - "Voltage Low Time"
            
            - "Temperature A"
            - "Temperature A Time"
            - "Temperature B"
            - "Temperature B Time"
        """
        time.sleep(0.1)
        wx.CallAfter(pub.sendMessage, stamp, msg=data)
        
    #end def
    
#end class    
###############################################################################

###############################################################################
class TakeData:
    ''' Takes measurements and saves them to file. '''
    #--------------------------------------------------------------------------
    def __init__(self):
        global abort_ID
        global current
        
        self.k2400 = k2400
        self.k2700 = k2700
        self.k2182 = k2182
        self.heaterTC = heaterTC
        self.sampleTC = sampleTC
        
        self.current = current
        
        self.k2400.set_current(float(self.current))
        #k2400.turn_source_on()
        
        self.equil_timer_ID = 0
        self.equil_timer = 0
        
        self.check_measurement_iterator = 0  # Iterator in order to check each  
                                             # step individually, only checks 
                                             # one step at a time.
        
        self.measurement_timer_ID = 0
        self.measurement_timer = 0
        
        self.measurement_indicator = 'none' # Indicates the start of a
                                            # measurement
        
        self.run_ID = 0
        
        self.exception_ID = 0
        
        self.heaterTC.set_setpoint(measureList[0])
        
        self.updateGUI(stamp='Status Bar', data='Running')
        
        self.start = time.time()
        
        try:
            while abort_ID == 0:
                
                self.t = time.time() - self.start
                
                self.take_PID_Data()
                
                if ( self.measurement_indicator == 'start' ):
                    self.run_ID = 1
                                    
                elif (self.measurement_indicator == 'stop' ):
                    self.run_ID = 0
                    myfile.write('Stop Measurement,')
                    self.measurement_indicator = 'none'
                    
                    self.equil_timer_ID = 0
                    self.equil_timer = 0
                    self.equil_time_left = '-'
                    self.measurement_timer_ID = 0
                    self.measurement_timer = 0
                    self.measurement_time_left = '-'
                #end elif
                    
                    
                #if we've reached equilibrium:
                if ( self.run_ID == 1 ):
                    #if we came out of equilibrium:
                    if (self.tol == 'NO' or self.equil == 'NO'):
                        self.run_ID = 0
                        myfile.write('Left Equilibrium,')
                        self.measurement_indicator = 'none'
                        
                        self.equil_timer_ID = 0
                        self.equil_timer = 0
                        self.equil_time_left = '-'
                        self.measurement_timer_ID = 0
                        self.measurement_timer = 0
                        self.measurement_time_left = '-'
                    #end if
                        
                    else:
                        myfile.write('\n')
                        self.begin_measurement() # Resistance measurements
                
                #end if
            #end while
        #end try
                
        except exceptions.Exception as e:
            log_exception(e)
            
            abort_ID = 1
            
            self.exception_ID = 1
            
            print "Error Occurred, check error_log.log"
        #end except
            
        if self.exception_ID == 1:
            self.updateGUI(stamp='Status Bar', data='Exception Occurred')
        #end if    
        else:
            self.updateGUI(stamp='Status Bar', data='Finished, Ready')
        #end else
        
        self.save_files()
        
        self.heaterTC.stop()
        self.heaterTC.set_setpoint(15)
        
        self.k2400.turn_source_off()
        
        wx.CallAfter(pub.sendMessage, 'Post Process')        
        wx.CallAfter(pub.sendMessage, 'Enable Buttons')
        wx.CallAfter(pub.sendMessage, 'Join Thread')
        
    #end init
        
    #--------------------------------------------------------------------------        
    def take_PID_Data(self):
        """ Takes data from the PID and proceeds to a 
            function that checks the PID setpoints.
        """
        try: 
            # Take Data
            self.tS = float(self.sampleTC.get_pv())
            self.ttS = time.time() - self.start
            self.tH = float(self.heaterTC.get_pv())
            self.ttH = time.time() - self.start
            
            # Get the current setpoints on the PID:
            self.tHset = float(self.heaterTC.get_setpoint())
        
        except exceptions.ValueError as VE:
            print(VE)
            self.tS = float(self.sampleTC.get_pv())
            self.tH = float(self.heaterTC.get_pv())
            
            # Get the current setpoints on the PID:
            self.tHset = float(self.heaterTC.get_setpoint())
            
        print "t_sampletemp: %.2f s\tsampletemp: %s C\nt_heatertemp: %.2f s\theatertemp: %s C" % (self.ttS, self.tS, self.ttH, self.tH)
        self.check_status()
        self.check_PID_setpoint()
        
        self.safety_check()
        
        self.updateGUI(stamp="Time Heater Temp", data=self.ttH)
        self.updateGUI(stamp="Heater Temp", data=self.tH)
        self.updateGUI(stamp="Time Sample Temp", data=self.ttS)
        self.updateGUI(stamp="Sample Temp", data=self.tS)
        self.updateGUI(stamp="Heater SP", data=self.tHset)
        
        
        if ( self.equil_time_left < 0 ):
            self.updateGUI(stamp="Status Bar", data=[self.tol, self.equil, '-'])
        #end if
        
        else:
            self.updateGUI(stamp="Status Bar", data=[self.tol, self.equil, str(self.equil_time_left)])
        #end else
                            
        if ( self.measurement_time_left < 0 ):
            self.updateGUI(stamp="Status Bar", data='-mea')
        #end if
        else:
            self.updateGUI(stamp="Status Bar", data=str(self.measurement_time_left) + 'mea')
    #end def
   
    #--------------------------------------------------------------------------
    def safety_check(self):
        if float(self.tS) > float(self.tHset) + 50 or float(self.tH) > float(self.tHset)+50:
            abort_ID = 1
        
    #end def
        
    #--------------------------------------------------------------------------
    def check_status(self):
        if (self.tS <= self.tHset+tolerance and self.tS >= self.tHset-tolerance):
            
            tol = 'OK'
        #end if
            
        else:
            tol = 'NO'
            
        #end else
         
        if (self.tS < self.tHset + equil_tolerance and self.tS > self.tHset - equil_tolerance):
            
            equil = 'OK'
        #end if
            
        else:
            equil = 'NO'
        #end else
        
        if tol == 'OK' and equil == 'OK':
            self.run_equil_timer()
        #end if
            
        else:
            self.equil_timer_ID = 0
            self.equil_timer = 0
            self.equil_time_left = '-'
            
            self.measurement_timer_ID = 0
            self.measurement_timer = 0
        #end else
            
        self.measurement_time_left = '-'
            
        self.tol = tol
        self.equil = equil
            
    #end def
        
    #--------------------------------------------------------------------------
    def run_equil_timer(self):
        if self.equil_timer_ID == 0:
            self.equil_timer = time.time()
        #end if
            
        self.equil_timer_ID = 1
        
        time_passed = time.time() - self.equil_timer
        self.equil_time_left = int(equil_time - time_passed)
    
    #end def
        
    #--------------------------------------------------------------------------
    def check_PID_setpoint(self):
        """ Function that requires that all conditions must be met to change 
            the setpoints. 
        """
        
        # check_status already checks if we are within the equilibrium threshold
        #   and the tolerance threshold
            
        # if we have been within both thresholds for the set amount of equil_time:
        if (self.equil_time_left <= 0):
            
            n = self.check_measurement_iterator
            
            if n < len(measureList)-1:
                self.check_step(measureList[n], measureList[n+1])
            #end if
                
            elif n == len(measureList)-1:
                self.check_step(measureList[n], None)
            #end elif
            
        #end if
                
    #end def
                
    #--------------------------------------------------------------------------
    def check_step(self, step, nextStep):
        
        if (self.tS <= step+tolerance and self.tS >= step-tolerance and 
            self.tHset <= step+tolerance and self.tHset >= step-tolerance):
            
            if self.measurement_timer_ID == 0:
                self.measurement_indicator = 'start'
            #end if
            
            self.run_measurement_timer()
            
            # if we reach the time for measurement to complete:
            if ( self.measurement_time_left <= 0 ):
                self.measurement_indicator = 'stop'
                
                # if we're on the last element of the list:
                if ( self.check_measurement_iterator == len(measureList)-1 ):
                    global abort_ID
                    abort_ID = 1
                #end if
                
                else:
                    self.heaterTC.set_setpoint(nextStep)
                    self.check_measurement_iterator = self.check_measurement_iterator + 1
                #end else
                    
            #end if
                
        #end if
        
    #end def
        
    #--------------------------------------------------------------------------
    def run_measurement_timer(self):
        if self.measurement_timer_ID == 0:
            self.measurement_timer = time.time()
            
        self.measurement_timer_ID = 1
        
        time_passed = time.time() - self.measurement_timer
        self.measurement_time_left = int(measurement_time - time_passed)
        
    #end def
        
    #--------------------------------------------------------------------------
    def begin_measurement(self):
        
        print('Begin Measurement')
        
        self.delay = 2.5 # time for the keithley to take a steady measurement
        
        temp1 = float(sampleTC.get_pv())
        
        # short the matrix card
        self.k2700.closeChannels('117, 125, 126, 127, 128, 129, 130')
        print(self.k2700.get_closedChannels())
        time.sleep(self.delay)
        
        
        ### RESISTIVITY MEASUREMENTS ###
        
        ### r_A: 
        # r_12,34
        print('measure r_12,34')
        self.k2700.openChannels('125, 127, 128, 129, 130')
        print(self.k2700.get_closedChannels())
        self.r_1234, self.t_1234 = self.delta_method()
        self.r_1234 = abs(self.r_1234)
        self.k2700.closeChannels('125, 127, 128, 129, 130')
        print(self.k2700.get_closedChannels())
        print "t_r1234: %.2f s\tr1234: %.2f Ohm" % (self.t_1234, self.r_1234)
        
        time.sleep(self.delay)
        
        # r_34,12
        print('measure r_34,12')
        self.k2700.closeChannels('118')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 126, 127, 128, 129, 130')
        print(self.k2700.get_closedChannels())
        self.r_3412, self.t_3412 = self.delta_method()
        self.r_3412 = abs(self.r_3412)
        self.k2700.closeChannels('117, 126, 127, 128, 129, 130')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('118')
        print(self.k2700.get_closedChannels())
        print "t_r3412: %.2f s\tr3412: %.2f Ohm" % (self.t_3412, self.r_3412)
        
        time.sleep(self.delay)
        
        # Calculate r_A
        self.r_A = (self.r_1234 + self.r_3412)/2
        self.t_A = time.time()-self.start
        self.updateGUI(stamp="Time R_A", data=self.t_A)
        self.updateGUI(stamp="R_A", data=self.r_A*1000)
        print "t_rA: %.2f s\trA: %.2f Ohm" % (self.t_A, self.r_A)
        
        temp2 = float(self.sampleTC.get_pv())
        
        ### r_B:
        # r_13,24
        print('measure r_13,24')
        self.k2700.closeChannels('119')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 125, 126, 127, 129, 130')
        print(self.k2700.get_closedChannels())
        self.r_1324, self.t_1324 = self.delta_method()
        self.r_1324 = abs(self.r_1324)
        self.k2700.closeChannels('117, 125, 126, 127, 129, 130')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('119')
        print(self.k2700.get_closedChannels())
        print "t_r1324: %.2f s\tr1324: %.2f Ohm" % (self.t_1324, self.r_1324)
        
        time.sleep(self.delay)
        
        # r_24,13
        print('measure r_24,13')
        self.k2700.closeChannels('120')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 125, 126, 128, 129, 130')
        print(self.k2700.get_closedChannels())
        self.r_2413, self.t_2413 = self.delta_method()
        self.r_2413 = abs(self.r_2413)
        self.k2700.closeChannels('117, 125, 126, 128, 129, 130')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('120')
        print(self.k2700.get_closedChannels())
        print "t_r2413: %.2f s\tr2413: %.2f Ohm" % (self.t_2413, self.r_2413)
        
        # Calculate r_B
        self.r_B = (self.r_1324 + self.r_2413)/2
        self.t_B = time.time()-self.start
        self.updateGUI(stamp="Time R_B", data=self.t_B)
        self.updateGUI(stamp="R_B", data=self.r_B*1000)
        print "t_rB: %.2f s\trB: %.2f Ohm" % (self.t_B, self.r_B)
        
        
        ### HALL EFFECT MEASUREMENTS ###
        
        # r_pn_14,23
        print('measure rp_14,23')
        self.k2700.closeChannels('121')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 125, 126, 127, 128, 129')
        print(self.k2700.get_closedChannels())
        self.bfield(pos)
        time.sleep(self.delay)
        self.rp_1423, tp = self.delta_method()
        self.bfield(neg)
        time.sleep(self.delay)
        print('measure rn_14,23')
        self.rn_1423, tn = self.delta_method()
        self.bfield(off)
        self.k2700.closeChannels('117, 125, 126, 127, 128, 129')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('121')
        print(self.k2700.get_closedChannels())
        self.r_1423 = 1/2*(self.rp_1423-self.rn_1423)
        self.t_1423 = 1/2*(tp+tn)
        print "t_r1423: %.2f s\tr1423: %.2f Ohm" % (self.t_1423, self.r_1423)
        
        # r_pn_23,14
        print('measure rp_23,14')
        self.k2700.closeChannels('121')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 125, 126, 127, 128, 129')
        print(self.k2700.get_closedChannels())
        self.bfield(pos)
        time.sleep(self.delay)
        self.rp_2314, tp = self.delta_method()
        self.bfield(neg)
        time.sleep(self.delay)
        print('measure rn_23,14')
        self.rn_2314, tn = self.delta_method()
        self.bfield(off)
        self.k2700.closeChannels('117, 125, 126, 127, 128, 129')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('121')
        print(self.k2700.get_closedChannels())
        self.r_2314 = 1/2*(self.rp_2314-self.rn_2314)
        self.t_2314 = 1/2*(tp+tn)
        print "t_r2314: %.2f s\tr2314: %.2f Ohm" % (self.t_2314, self.r_2314)
        
        # Calculate r_Perp
        self.r_P = (self.r_1423 + self.r_2314)/2
        self.t_P = time.time()-self.start
        self.updateGUI(stamp="Time R_P", data=self.t_P)
        self.updateGUI(stamp="R_P", data=self.r_P*1000)
        print "t_rP: %.2f s\trP: %.2f Ohm" % (self.t_P, self.r_P)
        
        temp3 = float(self.sampleTC.get_pv())
        
        self.avgTemp = (temp1 + temp2 + temp3)/3
        
        self.all_time = (self.t_A+self.t_B)/2
        
        self.resistances = (self.t_1234, self.r_1234, self.t_3412, self.r_1324, self.t_1324, self.r_1324, self.t_2413, self.r_2413)
        
        self.write_data_to_file()
        
        #self.updateGUI(stamp='Resistance Raw', data=[t_1234, r_1234, t_3412, r_1324, t_1324, r_1324, t_2413, r_2413])
        #self.updateGUI(stamp='Resistance Processed', data=[self.r_A, self.r_B, all_time])
        

        
    #end def
    
    #--------------------------------------------------------------------------
    def delta_method(self):
        print('Delta Method')
        t1 = time.time() - self.start
        # delta method:
        # positive V1:
         
        self.k2400.turn_source_on()
        self.k2400.set_current(float(self.current))
        self.updateGUI(stamp="Current Status", data=float(self.current)*1000)
        time.sleep(self.delay) 
        v1p = float( self.k2182.fetch() )
         
        # negative V:
        self.k2400.set_current(-1*float(self.current))
        self.updateGUI(stamp="Current Status", data=-1*float(self.current)*1000)
        time.sleep(self.delay)
        vn = float( self.k2182.fetch() )
         
        t2 = time.time() - self.start
         
        # positive V2:
        self.k2400.set_current(float(self.current))
        self.updateGUI(stamp="Current Status", data=float(self.current)*1000)
        time.sleep(self.delay)
        v2p = float( self.k2182.fetch() )
         
        self.k2400.turn_source_off()
        self.updateGUI(stamp="Current Status", data=0)
         
        t3 = time.time() - self.start
        
        print 'Delta Method' 
        print 'i: %f Amps' % float(self.current)
        print "v: %f V, %f V, %f V" % (v1p, vn, v2p)
         
        r = (v1p + v2p - 2*vn)/(4*float(self.current))
         
        avgt = (t3 + t2 + t1)/3
         
        return r, avgt
     
    #end def
    
    #--------------------------------------------------------------------------
    def bfield(self, direction):
        pass
    #end def
    
    #--------------------------------------------------------------------------
    def updateGUI(self, stamp, data):
        """
        Sends data to the GUI (main thread), for live updating while the process is running
        in another thread.
        """
        time.sleep(0.1)
        wx.CallAfter(pub.sendMessage, stamp, msg=data)
        
    #end def
        
    #--------------------------------------------------------------------------
    def write_data_to_file(self):
        print('Write data to file')
        myfile.write('%.2f,%.1f,' % (self.all_time, self.avgTemp) )
        myfile.write('%.2f,%f,%.2f,%f,%.2f,%f,%.2f,%f,' % self.resistances)
        myfile.write('%f,%f,' % (self.r_A, self.r_B) )
        
        if self.measurement_indicator == 'start':
            measured_temp = measureList[self.check_measurement_iterator]
            myfile.write('Start Measurement,%d' % measured_temp)
            self.measurement_indicator = 'none'
            
        elif self.measurement_indicator == 'none':
            pass
        
    #end def
        
    #--------------------------------------------------------------------------
    def save_files(self):
        ''' Function saving the files after the data acquisition loop has been
            exited. 
        '''
        
        print('Save Files')
        
        global dataFile
        global finaldataFile
        global myfile
        
        stop = time.time()
        end = datetime.now() # End time
        totalTime = stop - self.start # Elapsed Measurement Time (seconds)
        
        myfile.close() # Close the file
        
        myfile = open(dataFile, 'r') # Opens the file for Reading
        contents = myfile.readlines() # Reads the lines of the file into python set
        myfile.close()
        
        # Adds elapsed measurement time to the read file list
        endStr = 'End Time: %s \nElapsed Measurement Time: %s Seconds \n \n' % (str(end), str(totalTime))
        contents.insert(1, endStr) # Specify which line and what value to insert
        # NOTE: First line is line 0
        
        # Writes the elapsed measurement time to the final file
        myfinalfile = open(finaldataFile,'w')
        contents = "".join(contents)
        myfinalfile.write(contents)
        myfinalfile.close()
        
        # Save the GUI plots
        global save_plots_ID
        save_plots_ID = 1
        self.updateGUI(stamp='Save_All', data='Save')
    
    #end def

#end class
###############################################################################

###############################################################################
class BoundControlBox(wx.Panel):
    """ A static box with a couple of radio buttons and a text
        box. Allows to switch between an automatic mode and a 
        manual mode with an associated value.
    """
    #--------------------------------------------------------------------------
    def __init__(self, parent, ID, label, initval):
        wx.Panel.__init__(self, parent, ID)
        
        self.value = initval
        
        box = wx.StaticBox(self, -1, label)
        sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        
        self.radio_auto = wx.RadioButton(self, -1, label="Auto", style=wx.RB_GROUP)
        self.radio_manual = wx.RadioButton(self, -1, label="Manual")
        self.manual_text = wx.TextCtrl(self, -1, 
            size=(30,-1),
            value=str(initval),
            style=wx.TE_PROCESS_ENTER)
        
        self.Bind(wx.EVT_UPDATE_UI, self.on_update_manual_text, self.manual_text)
        self.Bind(wx.EVT_TEXT_ENTER, self.on_text_enter, self.manual_text)
        
        manual_box = wx.BoxSizer(wx.HORIZONTAL)
        manual_box.Add(self.radio_manual, flag=wx.ALIGN_CENTER_VERTICAL)
        manual_box.Add(self.manual_text, flag=wx.ALIGN_CENTER_VERTICAL)
        
        sizer.Add(self.radio_auto, 0, wx.ALL, 10)
        sizer.Add(manual_box, 0, wx.ALL, 10)
        
        self.SetSizer(sizer)
        sizer.Fit(self)
        
    #end init
    
    #--------------------------------------------------------------------------
    def on_update_manual_text(self, event):
        self.manual_text.Enable(self.radio_manual.GetValue())
        
    #end def
    
    #--------------------------------------------------------------------------
    def on_text_enter(self, event):
        self.value = self.manual_text.GetValue()
        
    #end def
    
    #--------------------------------------------------------------------------
    def is_auto(self):
        return self.radio_auto.GetValue()
        
    #end def
    
    #--------------------------------------------------------------------------    
    def manual_value(self):
        return self.value
        
    #end def

#end class            
###############################################################################

###############################################################################
class UserPanel(wx.Panel):
    ''' User Input Panel '''
    
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)
        
        global current
        global thickness
        
        self.current = current
        
        self.create_title("User Panel") # Title
        
        self.celsius = u"\u2103"
        self.font2 = wx.Font(11, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        
        self.current_control()
        self.pid_tolerance_control()
        self.equil_time_control()
        self.equil_threshold_control()
        self.thickness_control()
        self.measurement_time_control()
        
        self.measurementListBox()
        self.maxCurrent_label()
        self.maxLimit_label()
        
        self.linebreak1 = wx.StaticLine(self, pos=(-1,-1), size=(300,1))
        self.linebreak2 = wx.StaticLine(self, pos=(-1,-1), size=(300,1))
        self.linebreak3 = wx.StaticLine(self, pos=(-1,-1), size=(300,1))
        self.linebreak4 = wx.StaticLine(self, pos=(-1,-1), size=(600,1), style=wx.LI_HORIZONTAL)
        
        self.run_stop() # Run and Stop buttons
        
        self.create_sizer() # Set Sizer for panel
        
        pub.subscribe(self.post_process_data, "Post Process")
        pub.subscribe(self.enable_buttons, "Enable Buttons")
        
    #end init 
    
    #--------------------------------------------------------------------------    
    def create_title(self, name):
        self.titlePanel = wx.Panel(self, -1)
        title = wx.StaticText(self.titlePanel, label=name)
        font_title = wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        title.SetFont(font_title)
        
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add((0,-1))
        hbox.Add(title, 0, wx.LEFT, 5)
        
        self.titlePanel.SetSizer(hbox)    
    #end def
    
    #--------------------------------------------------------------------------
    def run_stop(self):
        self.run_stopPanel = wx.Panel(self, -1)
        rs_sizer = wx.GridBagSizer(3, 3)

        self.btn_check = btn_check = wx.Button(self.run_stopPanel, label='check', style=0, size=(60,30)) # Initial Status Button
        btn_check.SetBackgroundColour((0,0,255))
        caption_check = wx.StaticText(self.run_stopPanel, label='*check inital status')
        self.btn_run = btn_run = wx.Button(self.run_stopPanel, label='run', style=0, size=(60,30)) # Run Button
        btn_run.SetBackgroundColour((0,255,0))
        caption_run = wx.StaticText(self.run_stopPanel, label='*run measurement')
        self.btn_stop = btn_stop = wx.Button(self.run_stopPanel, label='stop', style=0, size=(60,30)) # Stop Button
        btn_stop.SetBackgroundColour((255,0,0))
        caption_stop = wx.StaticText(self.run_stopPanel, label = '*quit operation')
        
        btn_check.Bind(wx.EVT_BUTTON, self.check)
        btn_run.Bind(wx.EVT_BUTTON, self.run)
        btn_stop.Bind(wx.EVT_BUTTON, self.stop)
        
        controlPanel = wx.StaticText(self.run_stopPanel, label='Control Panel')
        controlPanel.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        
        rs_sizer.Add(controlPanel,(0,0), span=(1,3),flag=wx.ALIGN_CENTER_HORIZONTAL)
        rs_sizer.Add(btn_check,(1,0),flag=wx.ALIGN_CENTER_HORIZONTAL)
        rs_sizer.Add(caption_check,(2,0),flag=wx.ALIGN_CENTER_HORIZONTAL)
        rs_sizer.Add(btn_run,(1,1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        rs_sizer.Add(caption_run,(2,1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        rs_sizer.Add(btn_stop,(1,2),flag=wx.ALIGN_CENTER_HORIZONTAL)
        rs_sizer.Add(caption_stop,(2,2),flag=wx.ALIGN_CENTER_HORIZONTAL)
        
        self.run_stopPanel.SetSizer(rs_sizer)
        
        btn_stop.Disable()
        
    # end def
    
    #--------------------------------------------------------------------------   
    def check(self, event):
        
        thread = ProcessThreadCheck()
        
    #end def
    
    #--------------------------------------------------------------------------
    def run(self, event):
        global measureList
        measureList = [None]*self.listbox.GetCount()
        for k in xrange(self.listbox.GetCount()):
            measureList[k] = int(self.listbox.GetString(k))
        #end for
            
        if len(measureList) > 0:
            
            try:
                global k2700, k2400, k2182, heaterTC, sampleTC
                
                self.name_folder()
                
                if self.run_check == wx.ID_OK:
                    
                    global dataFile
                    global finaldataFile
                    global myfile
                    
                    file = dataFile # creates a data file
                    myfile = open(dataFile, 'w') # opens file for writing/overwriting
                    begin = datetime.now() # Current date and time
                    myfile.write('Start Time: ' + str(begin) + '\n')
                    
                    resistances = 't_1234,r_1234,t_3412,r_3412,t_1324,r_1324,t_2413,r_2413'
                    headers = ( 'time (s),Temperature (C),%s,' % resistances +
                                'r_A,r_B,' +
                                'Measurement Start/Stop,Measurement Temp' )
                              
                    myfile.write(headers)
                    myfile.write('\n')
                    
                    global abort_ID
                    abort_ID = 0
                    
                    # Global variables:
                    global current, equil_tolerance, equil_time, tolerance
                    global measurement_time
                    current = float(current) #Amps for the Keithley
                    equil_tolerance = float(equil_tolerance)
                    equil_time = float(equil_time)*60 # seconds conversion
                    tolerance = float(tolerance)
                    measurement_time = float(measurement_time)*60 # seconds conversion
                    
                    # Placers for the GUI plots:
                    global sampletemp_list, tsampletemp_list, heatertemp_list, theatertemp_list
                    global r_A_list, t_A_list, r_B_list, t_B_list, r_P_list, t_P_list
                    global r_1234_list, r_3412_list, r_1324_list, r_2413_list, r_1423_list, r_2314_list
                    global t_1234_list, t_3412_list, t_1324_list, t_2413_list, t_1423_list, t_2314_list
                    sampletemp_list = [0]
                    tsampletemp_list = [0]
                    heatertemp_list = [0]
                    theatertemp_list = [0]
                    r_A_list = [0]
                    t_A_list = [0]
                    r_B_list = [0]
                    t_B_list = [0]
                    t_1234_list = [0]
                    r_1234_list = [0]
                    t_3412_list = [0]
                    r_3412_list = [0]
                    t_1324_list = [0]
                    r_1324_list = [0]
                    t_2413_list = [0]
                    r_2413_list = [0]
                    t_P_list = [0]
                    r_P_list = [0]
                    t_1423_list = [0]
                    r_1423_list = [0]
                    t_2314_list = [0]
                    r_2314_list = [0]
                    
                    #start the threading process
                    thread = ProcessThreadRun()
                    
                    self.btn_run.Disable()
                    self.btn_new.Disable()
                    self.btn_ren.Disable()
                    self.btn_dlt.Disable()
                    self.btn_clr.Disable()
                    self.btn_stop.Enable()
                    
                #end if
                
            #end try
                
            except visa.VisaIOError:
                wx.MessageBox("Not all instruments are connected!", "Error")
            #end except
                
        else:
            wx.MessageBox('No measurements were specified!', 'Error', wx.OK | wx.ICON_INFORMATION)
        #end else
            
    #end def
     
    #-------------------------------------------------------------------------- 
    def name_folder(self):
        question = wx.MessageDialog(None, 'The data files are saved into a folder upon ' + \
                    'completion. \nBy default, the folder will be named with a time stamp.\n\n' + \
                    'Would you like to name your own folder?', 'Question', 
                    wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        answer = question.ShowModal()
        
        if answer == wx.ID_YES:
            self.folder_name = wx.GetTextFromUser('Enter the name of your folder.\n' + \
                                                'Only type in a name, NOT a file path.')
            if self.folder_name == "":
                wx.MessageBox("Canceled")
            else:
                self.choose_dir()
        
        #end if
            
        else:
            date = str(datetime.now())
            self.folder_name = 'Resistivity Data %s.%s.%s' % (date[0:13], date[14:16], date[17:19])
            
            self.choose_dir()
            
        #end else
            
    #end def
            
    #--------------------------------------------------------------------------    
    def choose_dir(self):
        found = False
        
        dlg = wx.DirDialog (None, "Choose the directory to save your files.", "",
                    wx.DD_DEFAULT_STYLE)
        
        self.run_check = dlg.ShowModal()
        
        if self.run_check == wx.ID_OK:
            global filePath
            filePath = dlg.GetPath()
            
            filePath = filePath + '/' + self.folder_name
            
            if not os.path.exists(filePath):
                os.makedirs(filePath)
                os.chdir(filePath)
            else:
                n = 1
                
                while found == False:
                    path = filePath + ' - ' + str(n)
                    
                    if os.path.exists(path):
                        n = n + 1
                    else:
                        os.makedirs(path)
                        os.chdir(path)
                        n = 1
                        found = True
                        
                #end while
                        
            #end else
                        
        #end if
        
        # Set the global path to the newly created path, if applicable.
        if found == True:
            filePath = path
        #end if
    #end def
    
    #--------------------------------------------------------------------------
    def stop(self, event):
        global abort_ID
        abort_ID = 1
        
        self.enable_buttons
        
    #end def        
        
    #--------------------------------------------------------------------------
    def current_control(self):
        self.current_Panel = wx.Panel(self, -1)        
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        
        self.label_current = wx.StaticText(self, label="Current:")
        self.label_current.SetFont(self.font2)
        self.text_current = text_current = wx.StaticText(self.current_Panel, label=str(float(self.current)*1000) + ' mA')
        text_current.SetFont(self.font2)
        self.edit_current = edit_current = wx.TextCtrl(self.current_Panel, size=(40, -1))
        self.btn_current = btn_current = wx.Button(self.current_Panel, label="Save", size=(40, -1))
        text_guide = wx.StaticText(self.current_Panel, label="The current sourced to \nthe sample.")
        
        btn_current.Bind(wx.EVT_BUTTON, self.save_current)
        
        hbox.Add((0, -1))
        #hbox.Add(self.label_current, 0 , wx.LEFT, 5)
        hbox.Add(text_current, 0, wx.LEFT, 5)
        hbox.Add(edit_current, 0, wx.LEFT, 11)
        hbox.Add(btn_current, 0, wx.LEFT, 5)
        hbox.Add(text_guide, 0, wx.LEFT, 5)
        
        self.current_Panel.SetSizer(hbox)
        
    #end def  
    
    #--------------------------------------------------------------------------
    def save_current(self, e):
        
        try:
            self.k2400 = k2400 # SourceMeter
            
            val = self.edit_current.GetValue()
            
            if float(val)/1000 > maxCurrent:
                current = str(maxCurrent)
            if float(val)/1000 < -maxCurrent:
                current = str(-maxCurrent)
                
            self.text_current.SetLabel(val + ' mA')
            
            current = float(val)/1000
            self.current = current
            
            self.k2400.set_current(self.current)
            
        except ValueError:
            wx.MessageBox("Invalid input. Must be a number.", "Error")
            
        except visa.VisaIOError:
            wx.MessageBox("The SourceMeter is not connected!", "Error")
        #end except
        
    #end def
    
    #--------------------------------------------------------------------------
    def pid_tolerance_control(self):
        self.pid_tol_Panel = wx.Panel(self, -1)        
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        
        self.label_pid_tolerance = wx.StaticText(self, 
                                            label="PID Tolerance:"
                                            )
        self.label_pid_tolerance.SetFont(self.font2)
        self.text_pid_tolerance = text_pid_tolerance = wx.StaticText(self.pid_tol_Panel, label=tolerance + ' ' + self.celsius)
        text_pid_tolerance.SetFont(self.font2)
        self.edit_pid_tolerance = edit_pid_tolerance = wx.TextCtrl(self.pid_tol_Panel, size=(40, -1))
        self.btn_pid_tolerance = btn_pid_tolerance = wx.Button(self.pid_tol_Panel, label="Save", size=(40, -1))
        text_guide = wx.StaticText(self.pid_tol_Panel, label="How close the temperature \nhas to be to the PID setpoint.")
        
        btn_pid_tolerance.Bind(wx.EVT_BUTTON, self.save_pid_tolerance)
        
        hbox.Add((0, -1))
        #hbox.Add(self.label_pid_tolerance, 0 , wx.LEFT, 5)
        hbox.Add(text_pid_tolerance, 0, wx.LEFT, 5)
        hbox.Add(edit_pid_tolerance, 0, wx.LEFT, 40)
        hbox.Add(btn_pid_tolerance, 0, wx.LEFT, 5)
        hbox.Add(text_guide, 0, wx.LEFT, 5)
        
        self.pid_tol_Panel.SetSizer(hbox)
        
    #end def  
    
    #--------------------------------------------------------------------------
    def save_pid_tolerance(self, e):
        global tolerance
        try:
            val = self.edit_pid_tolerance.GetValue()
            if float(val) > maxLimit:
                tolerance = str(maxLimit)
            self.text_pid_tolerance.SetLabel(val + ' ' + self.celsius)
            tolerance = float(val)
            
        except ValueError:
            wx.MessageBox("Invalid input. Must be a number.", "Error")
    #end def
        
    #--------------------------------------------------------------------------
    def equil_time_control(self):
        self.equil_time_Panel = wx.Panel(self, -1)        
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        
        self.label_equil_time = wx.StaticText(self, 
                                            label="Equilibrium Time:"
                                            )
        self.label_equil_time.SetFont(self.font2)
        self.text_equil_time = text_equil_time = wx.StaticText(self.equil_time_Panel, label=equil_time + ' min')
        text_equil_time.SetFont(self.font2)
        self.edit_equil_time = edit_equil_time = wx.TextCtrl(self.equil_time_Panel, size=(40, -1))
        self.btn_equil_time = btn_equil_time = wx.Button(self.equil_time_Panel, label="Save", size=(40, -1))
        text_guide = wx.StaticText(self.equil_time_Panel, label=('The PID must be within \nthe equilibrium threshold \nfor this much time before \na measurement begins.' 
                                                                      )
                                   )
        
        btn_equil_time.Bind(wx.EVT_BUTTON, self.save_equil_time)
        
        hbox.Add((0, -1))
        #hbox.Add(self.label_equil_threshold, 0 , wx.LEFT, 5)
        hbox.Add(text_equil_time, 0, wx.LEFT, 5)
        hbox.Add(edit_equil_time, 0, wx.LEFT, 32)
        hbox.Add(btn_equil_time, 0, wx.LEFT, 5)
        hbox.Add(text_guide, 0, wx.LEFT, 5)
        
        self.equil_time_Panel.SetSizer(hbox)
        
    #end def  
    
    #--------------------------------------------------------------------------
    def save_equil_time(self, e):
        global equil_time
        try:
            val = self.edit_equil_time.GetValue()
            
            equil_time = float(val)
            
            self.text_equil_time.SetLabel(val + ' min')
            self.equil_text_guide.SetLabel('The PID must stay within this \nrange for %s minutes \nbefore a measurement will \nbegin.' % val)
            
        except ValueError:
            wx.MessageBox("Invalid input. Must be a number.", "Error")
        
    #end def
        
    #--------------------------------------------------------------------------
    def equil_threshold_control(self):
        self.equil_threshold_Panel = wx.Panel(self, -1)        
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        
        self.label_equil_threshold = wx.StaticText(self, 
                                            label="Equilibrium Threshold:"
                                            )
        self.label_equil_threshold.SetFont(self.font2)
        self.text_equil_threshold = text_equil_threshold= wx.StaticText(self.equil_threshold_Panel, label=equil_tolerance + ' ' + self.celsius)
        text_equil_threshold.SetFont(self.font2)
        self.edit_equil_threshold = edit_equil_threshold = wx.TextCtrl(self.equil_threshold_Panel, size=(40, -1))
        self.btn_equil_threshold = btn_equil_threshold = wx.Button(self.equil_threshold_Panel, label="Save", size=(40, -1))
        self.equil_text_guide = text_guide = wx.StaticText(self.equil_threshold_Panel, label=('The PID must stay within this\n' +
                                                                      'range for the equilibrium time \nbefore a measurement will \nbegin.' 
                                                                      )
                                                            )
        
        btn_equil_threshold.Bind(wx.EVT_BUTTON, self.save_equil_threshold)
        
        hbox.Add((0, -1))
        #hbox.Add(self.label_equil_threshold, 0 , wx.LEFT, 5)
        hbox.Add(text_equil_threshold, 0, wx.LEFT, 5)
        hbox.Add(edit_equil_threshold, 0, wx.LEFT, 40)
        hbox.Add(btn_equil_threshold, 0, wx.LEFT, 5)
        hbox.Add(text_guide, 0, wx.LEFT, 5)
        
        self.equil_threshold_Panel.SetSizer(hbox)
        
    #end def  
    
    #--------------------------------------------------------------------------
    def save_equil_threshold(self, e):
        global equil_tolerance
        
        try:
            val = self.edit_equil_threshold.GetValue()
            if float(val) > maxLimit:
                equil_tolerance = str(maxLimit)
            self.text_equil_threshold.SetLabel(val + ' ' + self.celsius)
            equil_tolerance = float(val)
            
        except ValueError:
            wx.MessageBox("Invalid input. Must be a number.", "Error")
    #end def
    
    #--------------------------------------------------------------------------
    def thickness_control(self):
        self.thickness_Panel = wx.Panel(self, -1)        
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        
        self.label_thickness = wx.StaticText(self, label="Sample Thickness:")
        self.label_thickness.SetFont(self.font2)
        self.text_thickness = text_thickness = wx.StaticText(self.thickness_Panel, label=thickness + ' cm')
        text_thickness.SetFont(self.font2)
        self.edit_thickness = edit_thickness = wx.TextCtrl(self.thickness_Panel, size=(40, -1))
        self.btn_thickness = btn_thickness = wx.Button(self.thickness_Panel, label="Save", size=(40, -1))
        text_guide = wx.StaticText(self.thickness_Panel, label="The thickness of \nthe sample.")
        
        btn_thickness.Bind(wx.EVT_BUTTON, self.save_thickness)
        
        hbox.Add((0, -1))
        #hbox.Add(self.label_current, 0 , wx.LEFT, 5)
        hbox.Add(text_thickness, 0, wx.LEFT, 5)
        hbox.Add(edit_thickness, 0, wx.LEFT, 11)
        hbox.Add(btn_thickness, 0, wx.LEFT, 5)
        hbox.Add(text_guide, 0, wx.LEFT, 5)
        
        self.thickness_Panel.SetSizer(hbox)
        
    #end def  
    
    #--------------------------------------------------------------------------
    def save_thickness(self, e):
        
        
        val = self.edit_thickness.GetValue()    
        self.text_thickness.SetLabel(val + ' cm')
        thickness = val
        wx.CallAfter(pub.sendMessage, "Sample Thickness", msg=thickness)

        #end except
        
    #end def
    
    #--------------------------------------------------------------------------
    def measurement_time_control(self):
        self.measurement_time_Panel = wx.Panel(self, -1)        
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        
        self.label_measurement_time = wx.StaticText(self, 
                                            label="Measurement Time:"
                                            )
        self.label_measurement_time.SetFont(self.font2)
        self.text_measurement_time = text_measurement_time = wx.StaticText(self.measurement_time_Panel, label=measurement_time + ' min')
        text_measurement_time.SetFont(self.font2)
        self.edit_measurement_time = edit_measurement_time = wx.TextCtrl(self.measurement_time_Panel, size=(40, -1))
        self.btn_measurement_time = btn_measurement_time = wx.Button(self.measurement_time_Panel, label="Save", size=(40, -1))
        text_guide = wx.StaticText(self.measurement_time_Panel, label=('How long each measurement \nwill take in minutes.' 
                                                                      )
                                   )
        
        btn_measurement_time.Bind(wx.EVT_BUTTON, self.save_measurement_time)
        
        hbox.Add((0, -1))
        #hbox.Add(self.label_equil_threshold, 0 , wx.LEFT, 5)
        hbox.Add(text_measurement_time, 0, wx.LEFT, 5)
        hbox.Add(edit_measurement_time, 0, wx.LEFT, 32)
        hbox.Add(btn_measurement_time, 0, wx.LEFT, 5)
        hbox.Add(text_guide, 0, wx.LEFT, 5)
        
        self.measurement_time_Panel.SetSizer(hbox)
        
    #end def  
    
    #--------------------------------------------------------------------------
    def save_measurement_time(self, e):
        global measurement_time
        
        try:
            val = self.edit_measurement_time.GetValue()
            measurement_time = float(val)
            self.text_measurement_time.SetLabel(val + ' min')
            
        except ValueError:
            wx.MessageBox("Invalid input. Must be a number.", "Error")
            
    #end def
    
    #--------------------------------------------------------------------------
    def measurementListBox(self):
        # ids for measurement List Box
        ID_NEW = 1
        ID_CHANGE = 2
        ID_CLEAR = 3
        ID_DELETE = 4

        self.measurementPanel = wx.Panel(self, -1)
        hbox = wx.BoxSizer(wx.HORIZONTAL)        
        
        self.label_measurements = wx.StaticText(self, 
                                             label="Measurements (%s):"
                                             % self.celsius
                                             )        
        self.label_measurements.SetFont(self.font2)
        
        self.listbox = wx.ListBox(self.measurementPanel, size=(75,150))
         
        btnPanel = wx.Panel(self.measurementPanel, -1)
        vbox = wx.BoxSizer(wx.VERTICAL)
        self.btn_new = new = wx.Button(btnPanel, ID_NEW, 'New', size=(50, 20))
        self.btn_ren = ren = wx.Button(btnPanel, ID_CHANGE, 'Change', size=(50, 20))
        self.btn_dlt = dlt = wx.Button(btnPanel, ID_DELETE, 'Delete', size=(50, 20))
        self.btn_clr = clr = wx.Button(btnPanel, ID_CLEAR, 'Clear', size=(50, 20))
        
        self.Bind(wx.EVT_BUTTON, self.NewItem, id=ID_NEW)
        self.Bind(wx.EVT_BUTTON, self.OnRename, id=ID_CHANGE)
        self.Bind(wx.EVT_BUTTON, self.OnDelete, id=ID_DELETE)
        self.Bind(wx.EVT_BUTTON, self.OnClear, id=ID_CLEAR)
        self.Bind(wx.EVT_LISTBOX_DCLICK, self.OnRename)
        
        vbox.Add((-1, 5))
        vbox.Add(new)
        vbox.Add(ren, 0, wx.TOP, 5)
        vbox.Add(dlt, 0, wx.TOP, 5)
        vbox.Add(clr, 0, wx.TOP, 5)
        
        btnPanel.SetSizer(vbox)
        #hbox.Add(self.label_measurements, 0, wx.LEFT, 5)
        hbox.Add(self.listbox, 1, wx.ALL, 5)
        hbox.Add(btnPanel, 0, wx.RIGHT, 5)
        
        self.measurementPanel.SetSizer(hbox)
        
    #end def
    
    #--------------------------------------------------------------------------
    def NewItem(self, event):
        text = wx.GetTextFromUser('Enter a new measurement', 'Insert dialog')
        if text != '':
            self.listbox.Append(text)
            
            time.sleep(0.2)
            
            self.listbox_max_limit(maxLimit)
            
    #end def

    #--------------------------------------------------------------------------
    def OnRename(self, event):
        sel = self.listbox.GetSelection()
        text = self.listbox.GetString(sel)
        renamed = wx.GetTextFromUser('Rename item', 'Rename dialog', text)
        if renamed != '':
            self.listbox.Delete(sel)
            self.listbox.Insert(renamed, sel)
            
            self.listbox_max_limit(maxLimit)
            
    #end def

    #--------------------------------------------------------------------------
    def OnDelete(self, event):
        sel = self.listbox.GetSelection()
        if sel != -1:
            self.listbox.Delete(sel)
            
            self.listbox_max_limit(maxLimit)
    #end def

    #--------------------------------------------------------------------------
    def OnClear(self, event):
        self.listbox.Clear()
        
        self.listbox_max_limit(maxLimit)
    
    #end def
    
    #--------------------------------------------------------------------------
    def listbox_max_limit(self, limit):
        """ Sets user input to only allow a maximum temperature. """
        mlist = [None]*self.listbox.GetCount()
        for i in xrange(self.listbox.GetCount()):
            mlist[i] = int(self.listbox.GetString(i))
            
            if mlist[i] > limit:
                self.listbox.Delete(i)
                self.listbox.Insert(str(limit), i)
                    
    #end def
    
    #--------------------------------------------------------------------------                
    def maxCurrent_label(self):
        self.maxCurrent_Panel = wx.Panel(self, -1)
        maxCurrent_label = wx.StaticText(self.maxCurrent_Panel, label='Max Current:')
        maxCurrent_text = wx.StaticText(self.maxCurrent_Panel, label='%s mA' % str(maxCurrent*1000))
    
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add((0,-1))
        hbox.Add(maxCurrent_label, 0, wx.LEFT, 5)
        hbox.Add(maxCurrent_text, 0, wx.LEFT, 5)
        
        self.maxCurrent_Panel.SetSizer(hbox)
    
    #edn def
                    
    #--------------------------------------------------------------------------                
    def maxLimit_label(self):
        self.maxLimit_Panel = wx.Panel(self, -1)
        maxLimit_label = wx.StaticText(self.maxLimit_Panel, label='Max Limit Temp:')
        maxLimit_text = wx.StaticText(self.maxLimit_Panel, label='%s %s' % (str(maxLimit), self.celsius))
    
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add((0,-1))
        hbox.Add(maxLimit_label, 0, wx.LEFT, 5)
        hbox.Add(maxLimit_text, 0, wx.LEFT, 5)
        
        self.maxLimit_Panel.SetSizer(hbox)
    
    #edn def
    
    #--------------------------------------------------------------------------
    def create_sizer(self):
      
        sizer = wx.GridBagSizer(12,2)
        sizer.Add(self.titlePanel, (0, 1), span=(1,2), flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.label_current, (1, 1))
        sizer.Add(self.current_Panel, (1, 2))
        sizer.Add(self.label_pid_tolerance, (2, 1))
        sizer.Add(self.pid_tol_Panel, (2, 2))       
        sizer.Add(self.label_equil_time, (3,1))
        sizer.Add(self.equil_time_Panel, (3, 2))
        sizer.Add(self.label_equil_threshold, (4,1))
        sizer.Add(self.equil_threshold_Panel, (4, 2))
        sizer.Add(self.label_thickness, (5, 1))
        sizer.Add(self.thickness_Panel, (5, 2))
        sizer.Add(self.label_measurement_time, (6,1))
        sizer.Add(self.measurement_time_Panel, (6, 2))
        sizer.Add(self.label_measurements, (7,1))
        sizer.Add(self.measurementPanel, (7, 2))
        sizer.Add(self.maxCurrent_Panel, (8, 1), span=(1,2))
        sizer.Add(self.maxLimit_Panel, (9, 1), span=(1,2))
        sizer.Add(self.linebreak4, (10,1),span = (1,2))
        sizer.Add(self.run_stopPanel, (11,1),span = (1,2), flag=wx.ALIGN_CENTER_HORIZONTAL)
        
        self.SetSizer(sizer)
        
    #end def
    
    #--------------------------------------------------------------------------
    def post_process_data(self):
        inFile = filePath + '/Data.csv'
        outFile = filePath + '/Sheet Resistance.csv'
        Hall_Processing_v1.output_file(inFile, outFile)
   #end def
        
    def enable_buttons(self):
        self.btn_check.Enable()
        self.btn_run.Enable()
        self.btn_new.Enable()
        self.btn_ren.Enable()
        self.btn_dlt.Enable()
        self.btn_clr.Enable()
        
        self.btn_stop.Disable()
        
    #end def
        
#end class
###############################################################################

###############################################################################                       
class StatusPanel(wx.Panel):
    """
    Current Status of Measurements
    """
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)
        
        global current
        
        self.t=str(0.0)
        self.d=str(0.00)
        self.rA=str(0.00)
        self.rB=str(0.00)
        self.rP=str(0.00)
        self.tS=str(30.0)
        self.tH=str(30.0)
        self.tHset=str(30.0)
        self.i = str(0.00)
        self.b = str(0.00)
        
        self.celsius = u"\u2103"
        self.ohm = u"\u2126"
        self.perp = u"\u27c2"

        self.create_title("Status Panel")
        self.linebreak1 = wx.StaticLine(self, pos=(-1,-1), size=(300,1))
        self.create_status()
        self.linebreak2 = wx.StaticLine(self, pos=(-1,-1), size=(300,1))
        
        self.linebreak3 = wx.StaticLine(self, pos=(-1,-1), size=(1,300), style=wx.LI_VERTICAL)
        
        # Updates from running program
        pub.subscribe(self.OnTime, "Time R_B")
        pub.subscribe(self.OnTime, "Time R_A")
        pub.subscribe(self.OnTime, "Time R_P")
        pub.subscribe(self.OnTime, "Time Heater Temp")
        pub.subscribe(self.OnTime, "Time Sample Temp")
        
        pub.subscribe(self.OnThickness, "Sample Thickness")
        
        pub.subscribe(self.OnR_A, "R_A")
        pub.subscribe(self.OnR_B, "R_B")
        pub.subscribe(self.OnR_P, "R_P")
        
        pub.subscribe(self.OnHeaterSP, "Heater SP")
        pub.subscribe(self.OnHeaterTemp, "Heater Temp")
        pub.subscribe(self.OnSampleTemp, "Sample Temp")
        
        pub.subscribe(self.OnCurrent, "Current")
        pub.subscribe(self.OnBfield, "Bfield")
         
        
        # Updates from inital check
        pub.subscribe(self.OnR_A, "R_A Status")
        pub.subscribe(self.OnR_B, "R_B Status")
        pub.subscribe(self.OnR_P, "R_P Status")
        
        pub.subscribe(self.OnHeaterSP, "Heater SP Status")
        pub.subscribe(self.OnHeaterTemp, "Heater Temp Status")
        pub.subscribe(self.OnSampleTemp, "Sample Temp Status")
        
        pub.subscribe(self.OnCurrent, "Current Status")
        pub.subscribe(self.OnBfield, "Bfield Status")
        
        #self.update_values()
        
        self.create_sizer()
        
    #end init

    #--------------------------------------------------------------------------
    def OnR_A(self, msg):
        self.rA = '%.2f'%(float(msg)) 
        self.update_values()  
    #end def

    #--------------------------------------------------------------------------
    def OnR_B(self, msg):
        self.rB = '%.2f'%(float(msg)) 
        self.update_values()  
    #end def

    #--------------------------------------------------------------------------
    def OnR_P(self, msg):
        self.rp = '%.2f'%(float(msg)) 
        self.update_values()  
    #end def

    #--------------------------------------------------------------------------
    def OnSampleTemp(self, msg):
        self.tS = '%.1f'%(float(msg)) 
        self.update_values()  
    #end def

    #--------------------------------------------------------------------------
    def OnHeaterTemp(self, msg):
        self.tH = '%.1f'%(float(msg)) 
        self.update_values()  
    #end def
    
    #--------------------------------------------------------------------------
    def OnHeaterSP(self, msg):
        self.tHset = '%.1f'%(float(msg)) 
        self.update_values()  
    #end def

    #--------------------------------------------------------------------------
    def OnCurrent(self, msg):
        self.i = '%.2f'%(float(msg))  
        self.update_values()    
    #end def
    
    #--------------------------------------------------------------------------
    def OnTime(self, msg):
        self.t = '%.1f'%(float(msg))  
        self.update_values()    
    #end def
    
    #--------------------------------------------------------------------------
    def OnThickness(self, msg):
        self.d = '%.2f'%(float(msg))  
        self.update_values()    
    #end def
    
    #--------------------------------------------------------------------------
    def OnBfield(self, msg):
        self.b = '%.2f'%(float(msg))  
        self.update_values()    
    #end def
    
    #--------------------------------------------------------------------------    
    def create_title(self, name):
        self.titlePanel = wx.Panel(self, -1)
        title = wx.StaticText(self.titlePanel, label=name)
        font_title = wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        title.SetFont(font_title)
        
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add((0,-1))
        hbox.Add(title, 0, wx.LEFT, 5)
        
        self.titlePanel.SetSizer(hbox)    
    #end def
    
    #-------------------------------------------------------------------------- 
    def create_status(self):
        self.label_t = wx.StaticText(self, label="run time (s):")
        self.label_t.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_d = wx.StaticText(self, label="smaple thickness (cm):")
        self.label_d.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_tS = wx.StaticText(self, label="sample temp ("+self.celsius+ "):")
        self.label_tS.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_tH = wx.StaticText(self, label="heater temp ("+self.celsius+ "):")
        self.label_tH.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_tHset = wx.StaticText(self, label="heater set point ("+self.celsius+ "):")
        self.label_tHset.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_rA = wx.StaticText(self, label="resistance_A (m"+self.ohm+"):")
        self.label_rA.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_rB = wx.StaticText(self, label="resistance_B (m"+self.ohm+"):")
        self.label_rB.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_rP = wx.StaticText(self, label="resistance_"+self.perp+" (m"+self.ohm+"):")
        self.label_rP.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_i = wx.StaticText(self, label="current (mA):")
        self.label_i.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_b = wx.StaticText(self, label="B-field (mT):")
        self.label_b.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        
        self.tcurrent = wx.StaticText(self, label=self.t)
        self.tcurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.dcurrent = wx.StaticText(self, label=self.d)
        self.dcurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.tScurrent = wx.StaticText(self, label=self.tS)
        self.tScurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.tHcurrent = wx.StaticText(self, label=self.tH)
        self.tHcurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.tHsetcurrent = wx.StaticText(self, label=self.tHset)
        self.tHsetcurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.rAcurrent = wx.StaticText(self, label=self.rA)
        self.rAcurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.rBcurrent = wx.StaticText(self, label=self.rB)
        self.rBcurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.rPcurrent = wx.StaticText(self, label=self.rP)
        self.rPcurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.icurrent = wx.StaticText(self, label=self.i)
        self.icurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.bcurrent = wx.StaticText(self, label=self.b)
        self.bcurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        
        
    #end def
        
    #-------------------------------------------------------------------------- 
    def update_values(self):
        self.tcurrent.SetLabel(self.t)
        self.dcurrent.SetLabel(self.t)
        self.tScurrent.SetLabel(self.tS)
        self.tHcurrent.SetLabel(self.tH)
        self.tHsetcurrent.SetLabel(self.tHset)
        self.rAcurrent.SetLabel(self.rA)
        self.rBcurrent.SetLabel(self.rB)
        self.rPcurrent.SetLabel(self.rP)
        self.icurrent.SetLabel(self.i)
        self.bcurrent.SetLabel(self.b)

    #end def
       
    #--------------------------------------------------------------------------
    def create_sizer(self):    
        sizer = wx.GridBagSizer(13,2)
        
        sizer.Add(self.titlePanel, (0, 0), span = (1,2), border=5, flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.linebreak1,(1,0), span = (1,2))
        
        sizer.Add(self.label_t, (2,0))
        sizer.Add(self.tcurrent, (2, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.label_d, (3,0))
        sizer.Add(self.dcurrent, (3, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        
        sizer.Add(self.label_tS, (4,0))
        sizer.Add(self.tScurrent, (4, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.label_tH, (5,0))
        sizer.Add(self.tHcurrent, (5, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.label_tHset, (6,0))
        sizer.Add(self.tHsetcurrent, (6, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        
        sizer.Add(self.label_rA, (7,0))
        sizer.Add(self.rAcurrent, (7, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.label_rB, (8,0))
        sizer.Add(self.rBcurrent, (8, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.label_rP, (9,0))
        sizer.Add(self.rPcurrent, (9, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        
        sizer.Add(self.label_i, (10,0))
        sizer.Add(self.icurrent, (10, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.label_b, (11,0))
        sizer.Add(self.bcurrent, (11, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)

        
        sizer.Add(self.linebreak2, (12,0), span = (1,2))
        
        self.SetSizer(sizer)
    #end def
          
#end class     
###############################################################################

###############################################################################
class ResistancePanel(wx.Panel):
    """
    GUI Window for plotting voltage data.
    """
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)
        
        global filePath
        
        global t_A_list
        global r_A_list
        global t_b_list
        global r_B_list
        global t_P_list
        global r_P_list
        
        self.create_title("Resistance Panel")
        self.init_plot()
        self.canvas = FigureCanvasWxAgg(self, -1, self.figure)
        self.create_control_panel()
        self.create_sizer()
        
        pub.subscribe(self.OnR_A, "R_A")
        pub.subscribe(self.OnR_ATime, "Time R_A")
        pub.subscribe(self.OnR_B, "R_B")
        pub.subscribe(self.OnR_BTime, "Time R_B")
        pub.subscribe(self.OnR_B, "R_P")
        pub.subscribe(self.OnR_BTime, "Time R_P")
        
        # For saving the plots at the end of data acquisition:
        pub.subscribe(self.save_plot, "Save_All")
        
        self.animator = animation.FuncAnimation(self.figure, self.draw_plot, interval=2000, blit=False)
    #end init
    
    #--------------------------------------------------------------------------    
    def create_title(self, name):
        self.titlePanel = wx.Panel(self, -1)
        title = wx.StaticText(self.titlePanel, label=name)
        font_title = wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        title.SetFont(font_title)
        
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add((0,-1))
        hbox.Add(title, 0, wx.LEFT, 5)
        
        self.titlePanel.SetSizer(hbox)    
    #end def
    
    #--------------------------------------------------------------------------
    def create_control_panel(self):
        
        self.xmin_control = BoundControlBox(self, -1, "t min", 0)
        self.xmax_control = BoundControlBox(self, -1, "t max", 100)
        self.ymin_control = BoundControlBox(self, -1, "R min", 0)
        self.ymax_control = BoundControlBox(self, -1, "R max", 100)
        
        self.hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        self.hbox1.AddSpacer(10)
        self.hbox1.Add(self.xmin_control, border=5, flag=wx.ALL)
        self.hbox1.Add(self.xmax_control, border=5, flag=wx.ALL)
        self.hbox1.AddSpacer(10)
        self.hbox1.Add(self.ymin_control, border=5, flag=wx.ALL)
        self.hbox1.Add(self.ymax_control, border=5, flag=wx.ALL)     
    #end def
        
    #--------------------------------------------------------------------------
    def OnR_A(self, msg):
        self.rA = float(msg)
        r_A_list.append(self.rA)
        print 'r_A_list:'
        print r_A_list   
    #end def

    #--------------------------------------------------------------------------
    def OnR_ATime(self, msg):
        self.tA = float(msg)   
        t_A_list.append(self.tA)
        print 't_A_list:'
        print t_A_list
    #end def

    #--------------------------------------------------------------------------
    def OnR_B(self, msg):
        self.rB = float(msg)
        r_B_list.append(self.rB)  
    #end def

    #--------------------------------------------------------------------------
    def OnR_BTime(self, msg):
        self.tB = float(msg)   
        t_B_list.append(self.tB)
    #end def

    #--------------------------------------------------------------------------
    def OnR_P(self, msg):
        self.rP = float(msg)
        r_P_list.append(self.rP)  
    #end def

    #--------------------------------------------------------------------------
    def OnR_PTime(self, msg):
        self.tP = float(msg)   
        t_P_list.append(self.tP)
    #end def


    #--------------------------------------------------------------------------
    def init_plot(self):
        self.dpi = 100
        self.colorA = 'g'
        self.colorB = 'y'
        self.colorP = 'k'
        
        self.figure = Figure((6,2), dpi=self.dpi)
        self.subplot = self.figure.add_subplot(111)
        self.linerA, = self.subplot.plot(t_A_list,r_A_list, color=self.colorA, linewidth=1)
        self.linerB, = self.subplot.plot(t_B_list,r_B_list, color=self.colorB, linewidth=1)
        self.linerP, = self.subplot.plot(t_P_list,r_P_list, color=self.colorP, linewidth=1)

        #self.subplot.text(0.05, .95, r'$X(f) = \mathcal{F}\{x(t)\}$', \
            #verticalalignment='top', transform = self.subplot.transAxes)
    #end def

    #--------------------------------------------------------------------------
    def draw_plot(self,i):
        self.subplot.clear()
        #self.subplot.set_title("voltage vs. time", fontsize=12)
        
        self.subplot.set_ylabel(r"resistance (m$\Omega$)",fontsize=8)
        self.subplot.set_xlabel("time (s)", fontsize = 8)
        
        # Adjustable scale:
        if self.xmax_control.is_auto():
            xmax = max(t_A_list+t_B_list+t_P_list)
        else:
            xmax = float(self.xmax_control.manual_value())    
        if self.xmin_control.is_auto():            
            xmin = 0
        else:
            xmin = float(self.xmin_control.manual_value())
        if self.ymin_control.is_auto():
            minV = min(r_A_list+r_B_list+r_P_list)
            ymin = minV - abs(minV)*0.3
        else:
            ymin = float(self.ymin_control.manual_value())
        if self.ymax_control.is_auto():
            maxV = max(r_A_list+r_B_list+r_P_list)
            ymax = maxV + abs(maxV)*0.3
        else:
            ymax = float(self.ymax_control.manual_value())
        
        if len(t_A_list) != len(r_A_list):
            time.sleep(0.5)
        if len(t_B_list) != len(r_B_list):
            time.sleep(0.5)
        if len(t_P_list) != len(r_P_list):
            time.sleep(0.5)
        
        self.subplot.set_xlim([xmin, xmax])
        self.subplot.set_ylim([ymin, ymax])
        
        pylab.setp(self.subplot.get_xticklabels(), fontsize=8)
        pylab.setp(self.subplot.get_yticklabels(), fontsize=8)
        
        self.linerA, = self.subplot.plot(t_A_list,r_A_list, color=self.colorA, linewidth=1)
        self.linerB, = self.subplot.plot(t_B_list,r_B_list, color=self.colorB, linewidth=1)
        self.linerP, = self.subplot.plot(t_P_list,r_P_list, color=self.colorP, linewidth=1)
        
        return (self.linerA, self.linerB, self.linerP)
        #return (self.subplot.plot( thighV_list, highV_list, color=self.colorH, linewidth=1),
            #self.subplot.plot( tlowV_list, lowV_list, color=self.colorL, linewidth=1))
        
    #end def
    
    #--------------------------------------------------------------------------
    def save_plot(self, msg):
        path = filePath + "/Resistance_Plot.png"
        self.canvas.print_figure(path)
        
    #end def
    
    #--------------------------------------------------------------------------
    def create_sizer(self):    
        sizer = wx.GridBagSizer(3,1)
        sizer.Add(self.titlePanel, (0, 0), flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.canvas, ( 1,0), flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.hbox1, (2,0), flag=wx.ALIGN_CENTER_HORIZONTAL)
        
        self.SetSizer(sizer)
    #end def
    
#end class
###############################################################################

###############################################################################
class TemperaturePanel(wx.Panel):
    """
    GUI Window for plotting temperature data.
    """
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)
        
        global filePath
        
        global tsampletemp_list
        global sampletemp_list
        global theatertemp_list 
        global heatertemp_list
        
        self.create_title("Temperature Panel")
        self.init_plot()
        self.canvas = FigureCanvasWxAgg(self, -1, self.figure)
        self.create_control_panel()
        self.create_sizer()
        self.celsius = u"\u2103"
        
        
        pub.subscribe(self.OnSampleTemp, "Sample Temp")
        pub.subscribe(self.OnTimeSampleTemp, "Time Sample Temp")
        pub.subscribe(self.OnHeaterTemp, "Heater Temp")
        pub.subscribe(self.OnTimeHeaterTemp, "Time Heater Temp")
        
        # For saving the plots at the end of data acquisition:
        pub.subscribe(self.save_plot, "Save_All")
        
        self.animator = animation.FuncAnimation(self.figure, self.draw_plot, interval=5000, blit=False)
    #end init
    
    #--------------------------------------------------------------------------    
    def create_title(self, name):
        self.titlePanel = wx.Panel(self, -1)
        title = wx.StaticText(self.titlePanel, label=name)
        font_title = wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        title.SetFont(font_title)
        
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add((0,-1))
        hbox.Add(title, 0, wx.LEFT, 5)
        
        self.titlePanel.SetSizer(hbox)    
    #end def
    
    #--------------------------------------------------------------------------
    def create_control_panel(self):
        
        self.xmin_control = BoundControlBox(self, -1, "t min", 0)
        self.xmax_control = BoundControlBox(self, -1, "t max", 100)
        self.ymin_control = BoundControlBox(self, -1, "T min", 0)
        self.ymax_control = BoundControlBox(self, -1, "T max", 500)
        
        self.hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        self.hbox1.AddSpacer(10)
        self.hbox1.Add(self.xmin_control, border=5, flag=wx.ALL)
        self.hbox1.Add(self.xmax_control, border=5, flag=wx.ALL)
        self.hbox1.AddSpacer(10)
        self.hbox1.Add(self.ymin_control, border=5, flag=wx.ALL)
        self.hbox1.Add(self.ymax_control, border=5, flag=wx.ALL)     
    #end def

    #--------------------------------------------------------------------------
    def OnTimeSampleTemp(self, msg):
        self.ttS = float(msg)   
        tsampletemp_list.append(self.ttS)
    #end def
        
    #--------------------------------------------------------------------------
    def OnSampleTemp(self, msg):
        self.tS = float(msg)
        sampletemp_list.append(self.tS)    
    #end def
    
    #--------------------------------------------------------------------------
    def OnTimeHeaterTemp(self, msg):
        self.ttH = float(msg)    
        theatertemp_list.append(self.ttH)
    #end def
        
    #--------------------------------------------------------------------------
    def OnHeaterTemp(self, msg):
        self.tH = float(msg)
        heatertemp_list.append(self.tH)  
    #end def

    #--------------------------------------------------------------------------
    def init_plot(self):
        self.dpi = 100
        self.colorTH = 'r'
        self.colorTS = 'b'
        
        self.figure = Figure((6,2), dpi=self.dpi)
        self.subplot = self.figure.add_subplot(111)
        
        self.lineTH, = self.subplot.plot(theatertemp_list,heatertemp_list, color=self.colorTH, linewidth=1)
        self.lineTS, = self.subplot.plot(tsampletemp_list,sampletemp_list, color=self.colorTS, linewidth=1)
        

        #self.subplot.text(0.05, .95, r'$X(f) = \mathcal{F}\{x(t)\}$', \
            #verticalalignment='top', transform = self.subplot.transAxes)
    #end def

    #--------------------------------------------------------------------------
    def draw_plot(self,i):
        self.subplot.clear()
        self.subplot.set_ylabel(r"temperature ($\degree$C)",fontsize=8)
        self.subplot.set_xlabel("time (s)", fontsize = 8)
        
        # Adjustable scale:
        if self.xmax_control.is_auto():
            xmax = max(tsampletemp_list+theatertemp_list)
        else:
            xmax = float(self.xmax_control.manual_value())    
        if self.xmin_control.is_auto():            
            xmin = 0
        else:
            xmin = float(self.xmin_control.manual_value())
        if self.ymin_control.is_auto():
            ymin = 0
        else:
            ymin = float(self.ymin_control.manual_value())
        if self.ymax_control.is_auto():
            maxT = max(sampletemp_list+heatertemp_list)
            ymax = maxT + abs(maxT)*0.3
        else:
            ymax = float(self.ymax_control.manual_value())
        
        if len(tsampletemp_list) != len(sampletemp_list):
            time.sleep(0.5)
        if len(theatertemp_list) != len(heatertemp_list):
            time.sleep(0.5)
        
        self.subplot.set_xlim([xmin, xmax])
        self.subplot.set_ylim([ymin, ymax])
        
        pylab.setp(self.subplot.get_xticklabels(), fontsize=8)
        pylab.setp(self.subplot.get_yticklabels(), fontsize=8)
        
        self.lineTH, = self.subplot.plot(theatertemp_list,heatertemp_list, color=self.colorTH, linewidth=1)
        self.lineTS, = self.subplot.plot(tsampletemp_list,sampletemp_list, color=self.colorTS, linewidth=1)
        
        return (self.lineTH, self.lineTS)
        
    #end def
    
    #--------------------------------------------------------------------------
    def save_plot(self, msg):
        path = filePath + "/Temperature plot.png"
        #path = filePath + '/Raw Data/' + 'Plots/' + "Temperature_Plot.png"
        self.canvas.print_figure(path)
        
    #end def
    
    #--------------------------------------------------------------------------
    def create_sizer(self):    
        sizer = wx.GridBagSizer(3,1)
        sizer.Add(self.titlePanel, (0, 0),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.canvas, ( 1,0),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.hbox1, (2,0),flag=wx.ALIGN_CENTER_HORIZONTAL)
        
        self.SetSizer(sizer)
    #end def
    
#end class
###############################################################################

###############################################################################
class Frame(wx.Frame):
    """
    Main frame window in which GUI resides
    """
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)
        self.init_UI()
        self.create_statusbar()
        self.create_menu()
        
        pub.subscribe(self.update_statusbar, "Status Bar")

    #end init
    
    #--------------------------------------------------------------------------       
    def init_UI(self):
        self.SetBackgroundColour('#E0EBEB')
        self.userpanel = UserPanel(self, size=wx.DefaultSize)
        self.statuspanel = StatusPanel(self,size=wx.DefaultSize)
        self.resistancepanel = ResistancePanel(self, size=wx.DefaultSize)
        self.temperaturepanel = TemperaturePanel(self, size=wx.DefaultSize)
        
        self.statuspanel.SetBackgroundColour('#ededed')
        
        sizer = wx.GridBagSizer(2, 3)
        sizer.Add(self.userpanel, (0,0),flag=wx.ALIGN_CENTER_HORIZONTAL, span = (2,1))
        sizer.Add(self.statuspanel, (0,2),flag=wx.ALIGN_CENTER_HORIZONTAL, span = (2,1))
        sizer.Add(self.resistancepanel, (0,1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.temperaturepanel, (1,1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Fit(self)
        
        self.SetSizer(sizer)
        self.SetTitle('Room Temp Hall Effect/Resistivity GUI')
        self.Centre() 
    #end def
        
    #--------------------------------------------------------------------------
    def create_menu(self):
        # Menu Bar with File, Quit
        menubar = wx.MenuBar()
        fileMenu = wx.Menu()
        qmi = wx.MenuItem(fileMenu, APP_EXIT, '&Quit\tCtrl+Q')
        #qmi.SetBitmap(wx.Bitmap('exit.png'))
        fileMenu.AppendItem(qmi)
    
        self.Bind(wx.EVT_MENU, self.onQuit, id=APP_EXIT)
    
        menubar.Append(fileMenu, 'File')
        self.SetMenuBar(menubar)
    #end def
    
    #--------------------------------------------------------------------------    
    def onQuit(self, e):
        global abort_ID
        
        abort_ID=1
        self.Destroy()
        self.Close()
        
        sys.stdout.close()
        sys.stderr.close()     
    #end def
    
    #--------------------------------------------------------------------------
    def create_statusbar(self):
        self.statusbar = ESB.EnhancedStatusBar(self, -1)
        self.statusbar.SetSize((-1, 23))
        self.statusbar.SetFieldsCount(12)
        self.SetStatusBar(self.statusbar)
        
        self.space_between = 10
        
        ### Create Widgets for the statusbar:
        # Status:
        self.status_text = wx.StaticText(self.statusbar, -1, "Ready")
        self.width0 = 105
        
        # Placer 1:
        placer1 = wx.StaticText(self.statusbar, -1, " ")
        
        # Title:
        #measurement_text = wx.StaticText(self.statusbar, -1, "Measurement Indicators:")
        #boldFont = wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        #measurement_text.SetFont(boldFont)
        #self.width1 = measurement_text.GetRect().width + self.space_between
        
        # PID Tolerance:
        pidTol_text = wx.StaticText(self.statusbar, -1, "Within PID Tolerance:")
        self.width2 = pidTol_text.GetRect().width + self.space_between
        
        self.indicator_tol = wx.StaticText(self.statusbar, -1, "-")
        self.width3 = 25
        
        # Equilibrium Threshold:
        equilThresh_text = wx.StaticText(self.statusbar, -1, "Within Equilibrium Threshold:")
        self.width4 = equilThresh_text.GetRect().width + 5
        
        self.indicator_equil = wx.StaticText(self.statusbar, -1, "-")
        self.width5 = self.width3
        
        # Equilibrium Time:
        equil_time_text = wx.StaticText(self.statusbar, -1, "Time Until Measurement Start:")
        self.width6 = equil_time_text.GetRect().width + self.space_between
        
        self.indicator_equil_time = wx.StaticText(self.statusbar, -1, "-")
        self.width7 = 40
        
        # Measurement Time:
        measurement_time_text = wx.StaticText(self.statusbar, -1, "Time Until Measurement Complete:")
        self.width8 = measurement_time_text.GetRect().width + self.space_between
        
        self.indicator_measurement_time = wx.StaticText(self.statusbar, -1, "-")
        self.width9 = self.width7
        
        # Placer 2:
        placer2 = wx.StaticText(self.statusbar, -1, " ")
        
        # Version:
        version_label = wx.StaticText(self.statusbar, -1, "Version: %s" % version)
        self.width10 = version_label.GetRect().width + self.space_between
        
        # Set widths of each piece of the status bar:
        self.statusbar.SetStatusWidths([self.width0, 50, self.width2, self.width3, self.width4, self.width5, self.width6, self.width7, self.width8, self.width9, -1, self.width10])
        
        ### Add the widgets to the status bar:
        # Status:
        self.statusbar.AddWidget(self.status_text, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)
        
        # Placer 1:
        self.statusbar.AddWidget(placer1)
        
        # Title:
        #self.statusbar.AddWidget(measurement_text, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)
        
        # PID Tolerance:
        self.statusbar.AddWidget(pidTol_text, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)
        self.statusbar.AddWidget(self.indicator_tol, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)
        
        # Equilibrium Threshold:
        self.statusbar.AddWidget(equilThresh_text, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)
        self.statusbar.AddWidget(self.indicator_equil, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)
        
        # Equilibrium Time:
        self.statusbar.AddWidget(equil_time_text, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)
        self.statusbar.AddWidget(self.indicator_equil_time, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)
        
        # Measurement Time:
        self.statusbar.AddWidget(measurement_time_text, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)
        self.statusbar.AddWidget(self.indicator_measurement_time, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)
        
        # Placer 2
        self.statusbar.AddWidget(placer2)
        
        # Version:
        self.statusbar.AddWidget(version_label, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)
        
    #end def
        
    #--------------------------------------------------------------------------
    def update_statusbar(self, msg):
        string = msg
        
        # Status:
        if string == 'Running' or string == 'Finished, Ready' or string == 'Exception Occurred':
            self.status_text.SetLabel(string)
            self.status_text.SetBackgroundColour(wx.NullColour)
            
            if string == 'Exception Occurred':
                self.status_text.SetBackgroundColour("RED")
            #end if
        
        #end if
                
        # Measurement Timer:
        elif string[-3:] == 'mea':
            self.indicator_measurement_time.SetLabel(string[:-3] + ' (s)')
            
        #end elif
            
        else:
            tol = string[0]
            equil = string[1]
            equil_time_left = string[2]
            
            # PID Tolerance indicator:
            self.indicator_tol.SetLabel(tol)
            if tol == 'OK':
                self.indicator_tol.SetBackgroundColour("GREEN")
            #end if
            else:
                self.indicator_tol.SetBackgroundColour("RED")
            #end else
                
            # Equilibrium Threshold indicator:
            self.indicator_equil.SetLabel(equil)
            if equil == 'OK':
                self.indicator_equil.SetBackgroundColour("GREEN")
            #end if
            else:
                self.indicator_equil.SetBackgroundColour("RED")
            #end else
            
            # Equilibrium Timer:
            self.indicator_equil_time.SetLabel(equil_time_left + ' (s)')
            
        #end else
         
    #end def
        
    
#end class
###############################################################################

###############################################################################
class App(wx.App):
    """
    App for initializing program
    """
    #--------------------------------------------------------------------------
    def OnInit(self):
        self.frame = Frame(parent=None, title="Room Temp Hall Effect/Resistivity GUI", size=(1350,1350))
        self.frame.Show()
        
        #setup = Setup()
        return True
    #end init
    
#end class
###############################################################################

#==============================================================================
if __name__=='__main__':
    app = App()
    app.MainLoop()
    
#end if