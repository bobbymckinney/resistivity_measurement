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
import matplotlib.pyplot as plt
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

#==============================================================================
# Keeps Windows from complaining that the port is already open:
modbus.CLOSE_PORT_AFTER_EACH_CALL = True

version = '5.0 (2015-08-30)'

'''
Global Variables:
'''

# Naming a data file:
dataFile = 'Data_Backup.csv'
finaldataFile = 'Data.csv'
statusFile = 'Status.csv'
resistivityFile = 'Resistivity.csv'
programFile = 'ProgramLog.txt'

thickness = 0.1 #placeholder for sample thickness in cm

current = .01 # (A) Current that is sourced by the k2400
APP_EXIT = 1 # id for File\Quit
stability_threshold = 0.1/60 # change in PID temp must be less than this value for a set time in order to reach an equilibrium
tolerance = 2 # Temperature must be within this temperature range of the PID setpoint in order to begin a measurement
measureList = []
measurement_number = 8

AbsoluteMaxLimit = 1000 # Restricts the user to an absolute max temperature
maxLimit = 600 # Restricts the user to a max temperature, changes based on input temps
maxCurrent = .04 # (A) Restricts the user to a max current

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
rawfile = 'global file'
processfile = 'global file'
logfile = 'global file'

# Placers for the GUI plots:
sampletemp_list = []
tsampletemp_list = []
heatertemp_list = []
theatertemp_list = []
rho_list = []
t_list = []

timecalclist = []
tempcalclist = []
rAcalclist = []
rBcalclist = []

cycle = 'Heating'

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
        self.k2700 = k2700 = Keithley_2700('GPIB0::16::INSTR') # MultiMeter for Matrix Card operation
        self.k2400 = k2400 = Keithley_2400('GPIB0::24::INSTR') # SourceMeter
        self.k2182 = k2182 = Keithley_2182('GPIB0::7::INSTR') # NanoVoltMeter
        # Define the ports for the PID
        self.sampleTC = sampleTC = PID("/dev/cu.usbserial", 1) # sample thermocouple
        self.heaterTC = heaterTC = PID("/dev/cu.usbserial", 2) # heater PID



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
class InitialCheck:
    #--------------------------------------------------------------------------
    def __init__(self):
        global k2700
        global k2400

        self.k2700 = k2700
        self.k2400 = k2400


        self.delay = .5
        self.voltage = .1



        self.setupIV()

        self.Data = {}

        # short the matrix card
        self.k2700.closeChannels('117, 125, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        time.sleep(self.delay)

        self.measure_contacts()

        self.create_plot()


    #end init
    #--------------------------------------------------------------------------

    #--------------------------------------------------------------------------
    def setupIV(self):
        self.k2400.ctrl.write(":SOUR:FUNC VOLT")
        self.k2400.ctrl.write(":SOUR:VOLT:MODE FIXED")
        self.k2400.ctrl.write(":SOUR:VOLT:RANG 20")
        self.k2400.ctrl.write(":SOUR:VOLT:LEV "+str(self.voltage))
        self.k2400.ctrl.write(":SENS:CURR:PROT 10E-2")
        self.k2400.ctrl.write(":SENS:FUNC CURR")
        self.k2400.ctrl.write(":SENS:CURR:RANG 10E-2")
        self.k2400.ctrl.write(":FORM:ELEM CURR")
    #end def
    #--------------------------------------------------------------------------


    #--------------------------------------------------------------------------
    def measure_contacts(self):

        # r_12
        print('measure r_12')
        self.k2700.openChannels('125, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        self.r_12 = self.checkIV('A','B')
        self.k2700.closeChannels('125, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        print "r12: %f Ohm" % (self.r_12)

        time.sleep(self.delay)

        # r_13
        print('measure r_13')
        self.k2700.closeChannels('119')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 125, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        self.r_13 = self.checkIV('A','C')
        self.k2700.closeChannels('117, 125, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('119')
        print(self.k2700.get_closedChannels())
        print "r13: %f Ohm" % (self.r_13)

        time.sleep(self.delay)

        # r_24
        print('measure r_24')
        self.k2700.closeChannels('120')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 125, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        self.r_24 = self.checkIV('B','D')
        self.k2700.closeChannels('117, 125, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('120')
        print(self.k2700.get_closedChannels())
        print "r24: %f Ohm" % (self.r_24)

        time.sleep(self.delay)

        # r_34
        print('measure r_34')
        self.k2700.closeChannels('118')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 125, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        self.r_34 = self.checkIV('C','D')
        self.k2700.closeChannels('117, 125, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('118')
        print(self.k2700.get_closedChannels())
        print "r34: %f Ohm" % (self.r_34)

    #end def
    #--------------------------------------------------------------------------

    #--------------------------------------------------------------------------
    def checkIV(self,p1,p2):
        print('check IV')
        n = 6
        I = []
        V = [1000*self.voltage*(x)/n for x in range(-n,n+1)]

        for v in V:
            self.k2400.ctrl.write(":SOUR:VOLT:LEV "+str(float(v)/1000))
            self.k2400.ctrl.write(":OUTP ON")
            time.sleep(self.delay)
            i = float(self.k2400.ctrl.query(":READ?"))
            time.sleep(self.delay)
            self.k2400.ctrl.write(":OUTP OFF")
            print 'v: %f\ni: %f'%(v,i)
            I.append(i)
            time.sleep(self.delay)
        #end for


        fit = self.polyfit(V,I,1)

        self.Data[p1+p2] = fit

        self.Data[p1+p2]['current'] = I
        self.Data[p1+p2]['voltage'] = V

        r = 1/(fit['polynomial'][0])

        return r
    #end def
    #--------------------------------------------------------------------------

    #--------------------------------------------------------------------------
    def polyfit(self, x, y, degree):
        '''
        Returns the polynomial fit for x and y of degree degree along with the
        r^2 and the temperature, all in dictionary form.
        '''
        results = {}

        coeffs = np.polyfit(x, y, degree)

        # Polynomial Coefficients
        results['polynomial'] = coeffs.tolist()

        # Calculate coefficient of determination (r-squared):
        p = np.poly1d(coeffs)
        # fitted values:
        yhat = p(x)                      # or [p(z) for z in x]
        # mean of values:
        ybar = np.sum(y)/len(y)          # or sum(y)/len(y)
        # regression sum of squares:
        ssreg = np.sum((yhat-ybar)**2)   # or sum([ (yihat - ybar)**2 for yihat in yhat])
        # total sum of squares:
        sstot = np.sum((y - ybar)**2)    # or sum([ (yi - ybar)**2 for yi in y])
        results['r-squared'] = ssreg / sstot

        return results

    #end def

    #--------------------------------------------------------------------------
    def create_plot(self):
        plt.figure(num='IV Curves', figsize=(12,9),dpi=100)
        fitData = {}
        sp = 221
        for key in self.Data.keys():
            fitData[key] = {}
            i = np.poly1d(self.Data[key]['polynomial'])
            v = np.linspace(min(self.Data[key]['voltage']), max(self.Data[key]['voltage']), 500)

            fitData[key]['current'] = i(v)
            fitData[key]['voltage'] = v
            fitData[key]['equation'] = 'I = %.7f*(V) + %.7f' % (self.Data[key]['polynomial'][0], self.Data[key]['polynomial'][1])

            plt.subplot(sp)
            sp = sp + 1
            plt.plot(self.Data[key]['voltage'],self.Data[key]['current'],'r.',fitData[key]['voltage'],fitData[key]['current'],'b--')
            plt.xlabel("V (mV)")
            plt.ylabel("I (mA)")
            plt.title('IV curve - '+key)
            plt.legend(('i-v data: r^2 %.4f'%(self.Data[key]['r-squared']),'fit: '+fitData[key]['equation']),loc=4,fontsize=10)
            #plt.axis([ , , , ])
            plt.grid(True)
        #end for


        #fig.savefig('%s.png' % (plot_folder + title) , dpi=dpi)
        #plt.savefig('%s.png' % ('IV Curves') )
        plt.show()

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
class TakeData:
    ''' Takes measurements and saves them to file. '''
    #--------------------------------------------------------------------------
    def __init__(self):
        global abort_ID
        global k2700
        global k2400
        global k2182
        global heaterTC
        global sampleTC

        global tolerance
        global stability_threshold
        global measureList
        global measurement_number
        global current
        global cycle
        global thickness

        global logfile

        global timecalclist, tempcalclist, rAcalclist, rBcalclist

        self.k2400 = k2400
        self.k2700 = k2700
        self.k2182 = k2182
        self.heaterTC = heaterTC
        self.sampleTC = sampleTC

        self.current = float(current)
        self.tolerance = tolerance
        self.stability_threshold = stability_threshold
        self.cycle = 'Heating'
        self.updateGUI(stamp="Cycle", data=self.cycle)
        self.thickness = thickness
        self.k2400.set_current(float(self.current))
        logfile.write('Set k2400 current to %f\n'% (self.current))
        self.exception_ID = 0

        self.start = time.time()
        #time initializations
        logfile.write('%f Start time.\n' %(self.start))
        self.ttS = 0
        self.ttH = 0

        self.delay = 1
        self.tempdelay = 5

        self.tol = 'NO'
        self.stable = 'NO'
        self.measurement = 'OFF'
        self.updateGUI(stamp='Measurement', data=self.measurement)
        self.updateGUI(stamp='Status Bar', data='Running')
        print "start take data"
        logfile.write("%f Start take data routine\n" %(time.time()-self.start))
        self.Tnum = 0
        try:
            while abort_ID == 0:
                for temp in measureList:
                    print "Set temp tp %f" %(temp)
                    if self.cycle == 'Heating':
                        currenttemp = temp - 3 * self.tolerance
                        self.heaterTC.set_setpoint(currenttemp)
                        logfile.write('%f Next point in heating cycle. Set heater temp to %f\n'%(time.time()-self.start, currenttemp))
                    #end if
                    elif self.cycle == 'Cooling':
                        if temp > 45:
                            self.heaterTC.set_setpoint(temp - 30)
                            logfile.write('%f Next point in cooling cycle. Set heater temp to %f\n'%(time.time()-self.start, temp-30))
                        #end if
                        else:
                            self.heaterTC.set_setpoint(15)
                            logfile.write('%f Next point in cooling cycle. Set heater temp to %f\n'%(time.time()-self.start, 15))
                        #end else
                    #end elif

                    timecalclist = []
                    tempcalclist = []
                    rAcalclist = []
                    rBcalclist = []

                    self.recentPID = []
                    self.recentPIDtime=[]
                    self.stability = '-'
                    self.updateGUI(stamp="Stability", data=self.stability)
                    self.pidset = float(self.heaterTC.get_setpoint())

                    self.take_PID_Data()
                    self.updateStats()

                    n=0
                    condition = False
                    while (not condition):
                        n = n+1
                        self.take_PID_Data()
                        time.sleep(3)
                        if n%7 == 0:
                            self.updateStats()
                        if abort_ID == 1: break

                        if (self.cycle == 'Heating'):
                            condition = (self.tol == 'OK' and self.stable == 'OK')
                            if (self.stable == 'OK' and self.tol != 'OK'):
                                if (temp - self.tS > 2*self.tolerance and temp - self.tS < 4*self.tolerance):
                                    currenttemp = currenttemp + self.tolerance
                                    self.heaterTC.set_setpoint(currenttemp)
                                    logfile.write('%f Stable but below set temp, reset heater temp to %f\n'%(time.time()-self.start,currenttemp))
                                    self.recentPID = []
                                    self.recentPIDtime=[]
                                    self.stability = '-'
                                    self.stable == 'NO'
                                    self.tol = 'NO'
                                    self.updateGUI(stamp="Stability", data=self.stability)
                                #end if
                                elif (self.tS - temp < self.tolerance and temp-currenttemp < 8*self.tolerance):
                                    currenttemp = currenttemp - 4*self.tolerance
                                    self.heaterTC.set_setpoint(currenttemp)
                                    logfile.write('%f Stable but above set temp, reset heater temp to %f\n'%(time.time()-self.start,currenttemp))
                                    self.recentPID = []
                                    self.recentPIDtime=[]
                                    self.stability = '-'
                                    self.stable == 'NO'
                                    self.tol = 'NO'
                                    self.updateGUI(stamp="Stability", data=self.stability)
                                #end if
                        elif (self.cycle == 'Cooling'):
                            condition = (self.tol == 'OK')
                    # end while

                    if abort_ID == 1: break
                    # start measurement
                    if (condition):
                        self.measurement = 'ON'
                        self.updateGUI(stamp='Measurement', data=self.measurement)
                        logfile.write('%f Condition for measurement met. Begin resistivity measurement.\n' %(time.time()-self.start))

                        for i in range(measurement_number):
                            self.data_measurement()
                            self.write_data_to_file()
                            if abort_ID == 1: break
                        #end for

                        if abort_ID == 1: break
                        self.measurement = 'OFF'
                        logfile.write('%f Resistivity Measurement Complete.\n' %(time.time()-self.start))

                        self.tol = 'NO'
                        self.stable = 'NO'
                        self.updateGUI(stamp='Measurement', data=self.measurement)
                    #end if
                    if abort_ID == 1: break
                    self.process_data()

                    #Check/Change cycle
                    if (self.cycle == 'Heating' and (measureList[self.Tnum+1] < temp)):
                        self.cycle = 'Cooling'
                        self.stable = 'N/A'
                        self.updateGUI(stamp='Cycle', data=self.cycle)
                        logfile.write('%f Change cycle from heating to cooling.\n' % (time.time()-self.start))
                    #end if
                    self.Tnum = self.Tnum + 1

                    if abort_ID == 1: break
                #end for
                abort_ID = 1
            #end while
        #end try

        except exceptions.Exception as e:
            log_exception(e)
            logfile.write('%f Exception occured. %s\n' % (time.time()-self.start, e))
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
        logfile.write('%f Take data routine finished. Set heater to %f\n'%(time.time()-self.start, 20))
        self.heaterTC.set_setpoint(20)

        self.save_files()

        wx.CallAfter(pub.sendMessage, 'Enable Buttons')

    #end init

    #--------------------------------------------------------------------------
    def take_PID_Data(self):
        """ Takes data from the PID and proceeds to a
            function that checks the PID setpoints.
        """
        global logfile
        logfile.write('%f Take PID Data\n' %(time.time()-self.start))
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
        logfile.write('%f SampleTemp: %f C\nHeaterTemp: %f C\n' %(time.time()-self.start, self.tS, self.tH))
        #check stability of PID
        if (len(self.recentPID)<7):
            self.recentPID.append(self.tS)
            self.recentPIDtime.append(self.ttS)
        #end if
        else:
            self.recentPID.pop(0)
            self.recentPIDtime.pop(0)
            self.recentPID.append(self.tS)
            self.recentPIDtime.append(self.ttS)

            self.stability = self.getStability(self.recentPID,self.recentPIDtime)
            logfile.write('%f Stability: %fC/min\n' % (time.time()-self.start, self.stability*60))
            print "stability: %.4f C/min" % (self.stability*60)
            print "stability threshold: %.4f C/min" % (self.stability_threshold*60)
            self.updateGUI(stamp="Stability", data=self.stability*60)
        #end else
        self.updateGUI(stamp="Time Heater Temp", data=self.ttH)
        self.updateGUI(stamp="Heater Temp", data=self.tH)
        self.updateGUI(stamp="Time Sample Temp", data=self.ttS)
        self.updateGUI(stamp="Sample Temp", data=self.tS)
        self.updateGUI(stamp="Heater SP", data=self.tHset)

        self.safety_check()
        self.check_status()
    #end def

    #--------------------------------------------------------------------------
    def safety_check(self):
        global maxLimit
        global abort_ID
        global logfile

        logfile.write('%f Safety Check\n' % (time.time()-self.start))
        if float(self.tS) > maxLimit or float(self.tH) > maxLimit:
            abort_ID = 1
    #end def

    #--------------------------------------------------------------------------
    def getStability(self, temps, times):
        coeffs = np.polyfit(times, temps, 1)

        # Polynomial Coefficients
        results = coeffs.tolist()
        return results[0]
    #end def

    #--------------------------------------------------------------------------
    def check_status(self):
        global measureList
        global logfile
        logfile.write('%f Check Status\n' %(time.time()-self.start))
        if (self.cycle == 'Heating'):
            current_measurement = measureList[self.Tnum]
            if (np.abs(self.tS-current_measurement) < self.tolerance):
                self.tol = 'OK'
            #end if
            else:
                self.tol = 'NO'
            #end else

            if (self.stability!='-'):
                if (np.abs(self.stability) < self.stability_threshold):
                    self.stable = 'OK'
                #end if
                else:
                    self.stable = 'NO'
            #end if
            else:
                self.stable = 'NO'
            #end else
        #end if

        elif (self.cycle == 'Cooling'):
            current_measurement = measureList[self.Tnum]
            if (np.abs(self.tS-current_measurement) < self.tolerance):
                self.tol = 'OK'
            #end if

            else:
                self.tol = 'NO'
            #end else
        #end elif

        print "cycle: %s\ntolerance: %s\nstable: %s\n" % (self.cycle, self.tol, self.stable)
        logfile.write("%f cycle: %s\ntolerance: %s\nstable: %s\n" % (time.time()-self.start,self.cycle, self.tol, self.stable))

        self.updateGUI(stamp="Status Bar", data=[self.tol, self.stable])
    #end def

    #--------------------------------------------------------------------------
    def updateStats(self):
        global logfile
        print('update all stats\n')
        logfile.write('%f Update all stats\n'% (time.time()-self.start))
        # short the matrix card
        self.k2700.closeChannels('117, 125, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        time.sleep(self.delay)

        ### r_A:
        # r_12,34
        print('measure r_12,34')
        self.k2700.openChannels('125, 127, 128')
        print(self.k2700.get_closedChannels())
        self.r_1234, self.t_1234 = self.delta_method()
        self.r_1234 = abs(self.r_1234)
        self.k2700.closeChannels('125, 127, 128')
        print(self.k2700.get_closedChannels())
        print "t_r1234: %.2f s\tr1234: %.2f Ohm" % (self.t_1234, self.r_1234)
        if abort_ID == 1: return
        time.sleep(self.delay)

        # r_34,12
        print('measure r_34,12')
        self.k2700.closeChannels('118')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        self.r_3412, self.t_3412 = self.delta_method()
        self.r_3412 = abs(self.r_3412)
        self.k2700.closeChannels('117, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('118')
        print(self.k2700.get_closedChannels())
        print "t_r3412: %.2f s\tr3412: %.2f Ohm" % (self.t_3412, self.r_3412)
        if abort_ID == 1: return
        time.sleep(self.delay)

        # Calculate r_A
        self.r_A = (self.r_1234 + self.r_3412)/2
        self.t_A = time.time()-self.start
        self.updateGUI(stamp="Time R_A", data=self.t_A)
        self.updateGUI(stamp="R_A", data=self.r_A*1000)
        print "t_rA: %.2f s\trA: %.2f Ohm" % (self.t_A, self.r_A)

        ### r_B:
        # r_13,24
        print('measure r_13,24')
        self.k2700.closeChannels('119')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 125, 126, 127')
        print(self.k2700.get_closedChannels())
        self.r_1324, self.t_1324 = self.delta_method()
        self.r_1324 = abs(self.r_1324)
        self.k2700.closeChannels('117, 125, 126, 127')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('119')
        print(self.k2700.get_closedChannels())
        print "t_r1324: %.2f s\tr1324: %.2f Ohm" % (self.t_1324, self.r_1324)
        if abort_ID == 1: return
        time.sleep(self.delay)

        # r_24,13
        print('measure r_24,13')
        self.k2700.closeChannels('120')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 125, 126, 128')
        print(self.k2700.get_closedChannels())
        self.r_2413, self.t_2413 = self.delta_method()
        self.r_2413 = abs(self.r_2413)
        self.k2700.closeChannels('117, 125, 126, 128')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('120')
        print(self.k2700.get_closedChannels())
        print "t_r2413: %.2f s\tr2413: %.2f Ohm" % (self.t_2413, self.r_2413)
        if abort_ID == 1: return
        # Calculate r_B
        self.r_B = (self.r_1324 + self.r_2413)/2
        self.t_B = time.time()-self.start
        self.updateGUI(stamp="Time R_B", data=self.t_B)
        self.updateGUI(stamp="R_B", data=self.r_B*1000)
        print "t_rB: %.2f s\trB: %.2f Ohm" % (self.t_B, self.r_B)

        self.resistivity = self.resistivitycalc([self.r_A],[self.r_B])
        print "resistivity: %f" % (self.resistivity*1000)
        self.updateGUI(stamp = "Time Resistivity", data = self.t_B)
        self.updateGUI(stamp = "Resistivity", data = self.resistivity*1000)

        global rawfile
        print('\nWrite status to file\n')
        rawfile.write('%.1f,'%(self.t_B))
        rawfile.write('%.4f,'%(self.thickness))
        rawfile.write('%.2f,%.2f,%.2f,' %(self.tS,self.tH,self.tHset))
        rawfile.write('%s,'%(self.cycle))
        rawfile.write('%.2f,%.2f,'%(self.r_A*1000,self.r_B*1000))
        rawfile.write('%.3f\n'%(self.resistivity))

        logfile.write('%f rA: %f mOhm\nrB: %f mOhm\n'% (time.time()-self.start,self.r_A*1000,self.r_B*1000))

    #end def

    #--------------------------------------------------------------------------
    def delta_method(self):
        global logfile
        logfile.write('%f Delta Method\n'% (time.time()-self.start))
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
    def resistivitycalc(self,Alist,Blist):
        global thickness
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

        rho = 1/z1*float(thickness)
        return rho
    #end def

    #--------------------------------------------------------------------------
    def data_measurement(self):
        global logfile
        logfile.write('%f Data Measurement\n'% (time.time()-self.start))

        self.delay = 2.5 # time for the keithley to take a steady measurement

        temp1 = float(sampleTC.get_pv())

        # short the matrix card
        self.k2700.closeChannels('117, 125, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        time.sleep(self.delay)

        ### r_A:
        # r_12,34
        print('measure r_12,34')
        logfile.write('%f Measure R_12,34\n'% (time.time()-self.start))
        self.k2700.openChannels('125, 127, 128')
        print(self.k2700.get_closedChannels())
        self.r_1234, self.t_1234 = self.delta_method()
        self.r_1234 = abs(self.r_1234)
        self.k2700.closeChannels('125, 127, 128')
        print(self.k2700.get_closedChannels())
        print "t_r1234: %.2f s\tr1234: %.2f Ohm" % (self.t_1234, self.r_1234)
        if abort_ID == 1: return
        time.sleep(self.delay)

        # r_34,12
        print('measure r_34,12')
        logfile.write('%f Measure R_34,12\n'% (time.time()-self.start))
        self.k2700.closeChannels('118')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        self.r_3412, self.t_3412 = self.delta_method()
        self.r_3412 = abs(self.r_3412)
        self.k2700.closeChannels('117, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('118')
        print(self.k2700.get_closedChannels())
        print "t_r3412: %.2f s\tr3412: %.2f Ohm" % (self.t_3412, self.r_3412)
        if abort_ID == 1: return
        time.sleep(self.delay)

        # Calculate r_A
        logfile.write('%f Calculate R_A\n'% (time.time()-self.start))
        self.r_A = (self.r_1234 + self.r_3412)/2
        self.t_A = time.time()-self.start
        self.updateGUI(stamp="Time R_A", data=self.t_A)
        self.updateGUI(stamp="R_A", data=self.r_A*1000)
        print "t_rA: %.2f s\trA: %.2f Ohm" % (self.t_A, self.r_A)

        temp2 = float(self.sampleTC.get_pv())

        ### r_B:
        # r_13,24
        print('measure r_13,24')
        logfile.write('%f Measure R_13,24\n'% (time.time()-self.start))
        self.k2700.closeChannels('119')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 125, 126, 127')
        print(self.k2700.get_closedChannels())
        self.r_1324, self.t_1324 = self.delta_method()
        self.r_1324 = abs(self.r_1324)
        self.k2700.closeChannels('117, 125, 126, 127')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('119')
        print(self.k2700.get_closedChannels())
        print "t_r1324: %.2f s\tr1324: %.2f Ohm" % (self.t_1324, self.r_1324)
        if abort_ID == 1: return
        time.sleep(self.delay)

        # r_24,13
        print('measure r_24,13')
        logfile.write('%f Measure R_24,13\n'% (time.time()-self.start))
        self.k2700.closeChannels('120')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('117, 125, 126, 128')
        print(self.k2700.get_closedChannels())
        self.r_2413, self.t_2413 = self.delta_method()
        self.r_2413 = abs(self.r_2413)
        self.k2700.closeChannels('117, 125, 126, 128')
        print(self.k2700.get_closedChannels())
        self.k2700.openChannels('120')
        print(self.k2700.get_closedChannels())
        print "t_r2413: %.2f s\tr2413: %.2f Ohm" % (self.t_2413, self.r_2413)
        if abort_ID == 1: return
        # Calculate r_B
        logfile.write('%f Calculate R_B\n'% (time.time()-self.start))
        self.r_B = (self.r_1324 + self.r_2413)/2
        self.t_B = time.time()-self.start
        self.updateGUI(stamp="Time R_B", data=self.t_B)
        self.updateGUI(stamp="R_B", data=self.r_B*1000)
        print "t_rB: %.2f s\trB: %.2f Ohm" % (self.t_B, self.r_B)

        temp3 = float(self.sampleTC.get_pv())

        self.avgTemp = (temp1 + temp2 + temp3)/3
    #end def

    #--------------------------------------------------------------------------
    def write_data_to_file(self):
        global timecalclist, tempcalclist, rAcalclist, rBcalclist
        global myfile
        global logfile


        print('\nWrite data to file\n')
        logfile.write('%fWrite Data to File\n'% (time.time()-self.start))
        time = (self.t_1234 + self.t_3412 + self.t_1324 + self.t_2413)/4
        temp = self.avgTemp
        thickness = self.thickness
        rA = self.r_A
        rB = self.r_B
        resistivity = self.resistivitycalc([rA],[rB])
        myfile.write('%f,%.2f,%.4f,' %(time,temp,thickness))
        myfile.write('%.3f,%.3f,' % (rA*1000, rB*1000) )
        myfile.write('%.3f\n' % (resistivity*1000))

        timecalclist.append(time)
        tempcalclist.append(temp)
        rAcalclist.append(rA)
        rBcalclist.append(rB)

        logfile.write('%f Average Temp: %f C\nrA: %f mOhm\nrB: %f mOhm\nresistivity: %f mOhm*cm\n'% (time.time()-self.start,temp, rA*1000,rB*1000,resistivity*1000))

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
    def process_data(self):
        global timecalclist, tempcalclist, rAcalclist, rBcalclist
        global processfile
        global logfile

        logfile.write('%f Process Data\n'% (time.time()-self.start))
        time = np.average(timecalclist)
        thickness = self.thickness
        temp = np.average(tempcalclist)

        resistivity = self.resistivitycalc(rAcalclist,rBcalclist)

        processfile.write('%.1f,%.2f,%.3f\n'%(time,temp,resistivity*1000))
    #end def

    #--------------------------------------------------------------------------
    def save_files(self):
        ''' Function saving the files after the data acquisition loop has been
            exited.
        '''
        global logfile
        print('Save Files')
        logfile.write('%f Save Files\n'% (time.time()-self.start))

        global dataFile
        global finaldataFile
        global myfile
        global rawfile
        global processfile

        stop = time.time()
        end = datetime.now() # End time
        totalTime = stop - self.start # Elapsed Measurement Time (seconds)
        endStr = 'end time: %s \nelapsed measurement time: %s seconds \n \n' % (str(end), str(totalTime))

        myfile.close() # Close the file
        rawfile.close()
        processfile.close()

        myfile = open(dataFile, 'r') # Opens the file for Reading
        contents = myfile.readlines() # Reads the lines of the file into python set
        myfile.close()

        # Adds elapsed measurement time to the read file list
        contents.insert(1, endStr) # Specify which line and what value to insert
        # NOTE: First line is line 0

        # Writes the elapsed measurement time to the final file
        myfinalfile = open(finaldataFile,'w')
        contents = "".join(contents)
        myfinalfile.write(contents)
        myfinalfile.close()

        logfile.close()
        # Save the GUI plots
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
        global stability_threshold
        global measurement_number
        global tolerance

        self.current = current*1000
        self.tolerance = tolerance
        self.stability_threshold = stability_threshold*60
        self.measurement_number = measurement_number
        self.thickness = thickness

        self.create_title("User Panel") # Title

        self.celsius = u"\u2103"
        self.font2 = wx.Font(11, wx.DEFAULT, wx.NORMAL, wx.NORMAL)

        self.current_control()
        self.pid_tolerance_control()
        self.stability_threshold_control()
        self.thickness_control()
        self.measurement_number_control()

        self.measurementListBox()
        self.maxCurrent_label()
        self.maxLimit_label()

        self.linebreak1 = wx.StaticLine(self, pos=(-1,-1), size=(300,1))
        self.linebreak2 = wx.StaticLine(self, pos=(-1,-1), size=(300,1))
        self.linebreak3 = wx.StaticLine(self, pos=(-1,-1), size=(300,1))
        self.linebreak4 = wx.StaticLine(self, pos=(-1,-1), size=(600,1), style=wx.LI_HORIZONTAL)

        self.run_stop() # Run and Stop buttons

        self.create_sizer() # Set Sizer for panel

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
        caption_check = wx.StaticText(self.run_stopPanel, label='*check IV curve and temp')
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

        ic = InitialCheck()

    #end def

    #--------------------------------------------------------------------------
    def run(self, event):
        global k2700, k2400, k2182, heaterTC, sampleTC
        global dataFile
        global finaldataFile
        global myfile
        global rawfile
        global processfile
        global statusFile
        global resistivityFile
        global programFile
        global logfile
        global measureList
        global abort_ID

        measureList = [None]*self.listbox.GetCount()
        for k in xrange(self.listbox.GetCount()):
            measureList[k] = int(self.listbox.GetString(k))
        #end for

        if len(measureList) > 0:

            try:

                self.name_folder()

                if self.run_check == wx.ID_OK:
                    myfile = open(dataFile, 'w') # opens file for writing/overwriting
                    rawfile = open(statusFile,'w')
                    processfile = open(resistivityFile,'w')
                    logfile = open(programFile,'w')
                    begin = datetime.now() # Current date and time
                    myfile.write('Start Time: ' + str(begin) + '\n')
                    rawfile.write('Start Time: ' + str(begin) + '\n')
                    processfile.write('Start Time: ' + str(begin) + '\n')
                    logfile.write('Start Time: ' +str(begin) + '\n')
                    logfile.write("Sample thickness: %f cm\nSet Current: %f\nPID Tolerance: %f C\nStability Threshold: %fC/min\nMeasuremennt Number: %d\n" % (thickness,current,tolerance,stability_threshold,measurement_number))

                    dataheaders = 'time (s), temp (C), thickness (cm), R_A (mOhm), R_B (mOhm), resistivity (mOhm*cm)\n'
                    myfile.write(dataheaders)

                    rawheaders = 'time (s), thickness (cm), sampletemp (C), heatertemp (C), heatersetpoint (C), cycle, R_A (mOhm), R_B (mOhm), resistivity (mOhm*cm)\n'
                    rawfile.write(rawheaders)

                    processheaders = 'time (s), temp (C),resistivity (mOhm*cm)\n'
                    processfile.write(processheaders)

                    abort_ID = 0

                    self.btn_pid_tolerance.Disable()
                    self.btn_stability_threshold.Disable()
                    self.btn_current.Disable()
                    self.btn_thickness.Disable()
                    self.btn_measurement_number.Disable()
                    self.btn_new.Disable()
                    self.btn_ren.Disable()
                    self.btn_dlt.Disable()
                    self.btn_clr.Disable()
                    self.btn_check.Disable()
                    self.btn_run.Disable()
                    self.btn_stop.Enable()

                    #start the threading process
                    thread = ProcessThreadRun()

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
        self.text_current = text_current = wx.StaticText(self.current_Panel, label=str(self.current) + ' mA')
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
        global current
        try:
            self.k2400 = k2400 # SourceMeter

            val = self.edit_current.GetValue()

            if float(val)/1000 > maxCurrent:
                current = str(maxCurrent)
            if float(val)/1000 < -maxCurrent:
                current = str(-maxCurrent)

            self.text_current.SetLabel(val + ' mA')

            current = float(val)/1000
            self.current = current*1000

            self.k2400.set_current(current)

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
        self.text_pid_tolerance = text_pid_tolerance = wx.StaticText(self.pid_tol_Panel, label=str(self.tolerance) + ' ' + self.celsius)
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
                self.tolerance = str(maxLimit)
            else:
                self.tolerance = float(val)
            self.text_pid_tolerance.SetLabel(val + ' ' + self.celsius)

            tolerance = self.tolerance

        except ValueError:
            wx.MessageBox("Invalid input. Must be a number.", "Error")
    #end def

    #--------------------------------------------------------------------------
    def stability_threshold_control(self):
        global stability_threshold
        self.stability_threshold_Panel = wx.Panel(self, -1)
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        self.label_stability_threshold = wx.StaticText(self,
                                            label="Stability Threshold:"
                                            )
        self.label_stability_threshold.SetFont(self.font2)
        self.text_stability_threshold = text_stability_threshold= wx.StaticText(self.stability_threshold_Panel, label=str(self.stability_threshold) + ' ' + self.celsius + '/min')
        text_stability_threshold.SetFont(self.font2)
        self.edit_stability_threshold = edit_stability_threshold = wx.TextCtrl(self.stability_threshold_Panel, size=(40, -1))
        self.btn_stability_threshold = btn_stability_threshold = wx.Button(self.stability_threshold_Panel, label="Save", size=(40, -1))
        self.stability_text_guide = text_guide = wx.StaticText(self.stability_threshold_Panel, label=('The change in the PID must\n' +
                                                                      'be below this threshold range\nbefore a measurement will \nbegin.'
                                                                      )
                                                            )

        btn_stability_threshold.Bind(wx.EVT_BUTTON, self.save_stability_threshold)

        hbox.Add((0, -1))
        #hbox.Add(self.label_equil_threshold, 0 , wx.LEFT, 5)
        hbox.Add(text_stability_threshold, 0, wx.LEFT, 5)
        hbox.Add(edit_stability_threshold, 0, wx.LEFT, 40)
        hbox.Add(btn_stability_threshold, 0, wx.LEFT, 5)
        hbox.Add(text_guide, 0, wx.LEFT, 5)

        self.stability_threshold_Panel.SetSizer(hbox)

    #end def

    #--------------------------------------------------------------------------
    def save_stability_threshold(self, e):
        global stability_threshold

        try:
            val = self.edit_stability_threshold.GetValue()
            self.text_stability_threshold.SetLabel(val + ' ' + self.celsius +'/min')
            self.stability_threshold = float(val)
            stability_threshold = self.stability_threshold/60

        except ValueError:
            wx.MessageBox("Invalid input. Must be a number.", "Error")
    #end def

    #--------------------------------------------------------------------------
    def thickness_control(self):
        self.thickness_Panel = wx.Panel(self, -1)
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        self.label_thickness = wx.StaticText(self, label="Sample Thickness:")
        self.label_thickness.SetFont(self.font2)
        self.text_thickness = text_thickness = wx.StaticText(self.thickness_Panel, label=str(self.thickness) + ' cm')
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
        global thickness
        val = self.edit_thickness.GetValue()
        self.text_thickness.SetLabel(val + ' cm')
        self.thickness = float(val)
        thickness = self.thickness
        wx.CallAfter(pub.sendMessage, "Sample Thickness", msg=thickness)

    #end def

    #--------------------------------------------------------------------------
    def measurement_number_control(self):
        self.measurement_number_Panel = wx.Panel(self, -1)
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        self.label_measurement_number = wx.StaticText(self,
                                            label="Measurement Number:"
                                            )
        self.label_measurement_number.SetFont(self.font2)
        self.text_measurement_number = text_measurement_number = wx.StaticText(self.measurement_number_Panel, label=str(self.measurement_number))
        text_measurement_number.SetFont(self.font2)
        self.edit_measurement_number = edit_measurement_number = wx.TextCtrl(self.measurement_number_Panel, size=(40, -1))
        self.btn_measurement_number = btn_measurement_number = wx.Button(self.measurement_number_Panel, label="Save", size=(40, -1))
        text_guide = wx.StaticText(self.measurement_number_Panel, label=('How many measurements \nto take at each temp.'
                                                                      )
                                   )

        btn_measurement_number.Bind(wx.EVT_BUTTON, self.save_measurement_number)

        hbox.Add((0, -1))
        #hbox.Add(self.label_equil_threshold, 0 , wx.LEFT, 5)
        hbox.Add(text_measurement_number, 0, wx.LEFT, 5)
        hbox.Add(edit_measurement_number, 0, wx.LEFT, 32)
        hbox.Add(btn_measurement_number, 0, wx.LEFT, 5)
        hbox.Add(text_guide, 0, wx.LEFT, 5)

        self.measurement_number_Panel.SetSizer(hbox)

    #end def

    #--------------------------------------------------------------------------
    def save_measurement_number(self, e):
        global measurement_number

        try:
            val = self.edit_measurement_number.GetValue()
            self.measurement_number = float(val)
            self.text_measurement_number.SetLabel(val)
            measurement_number = int(self.measurement_number)

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
        global maxLimit
        global AbsoluteMaxLimit
        """ Sets user input to only allow a maximum temperature. """
        mlist = [None]*self.listbox.GetCount()
        for i in xrange(self.listbox.GetCount()):
            mlist[i] = int(self.listbox.GetString(i))

        if max(mlist) > AbsoluteMaxLimit-100:
            maxLimit = AbsoluteMaxLimit
            for i in range(len(mlist)):
                if mlist[i]>AbsoluteMaxLimit-100:
                    self.listbox.Delete(i)
                    self.listbox.Insert(str(AbsoluteMaxLimit-100), i)
        else:
            limit = max(mlist)+100
            maxLimit = limit
            self.maxLimit_text.SetLabel('%s %s' % (str(maxLimit), self.celsius))

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
        self.maxLimit_text = wx.StaticText(self.maxLimit_Panel, label='%s %s' % (str(maxLimit), self.celsius))

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add((0,-1))
        hbox.Add(maxLimit_label, 0, wx.LEFT, 5)
        hbox.Add(self.maxLimit_text, 0, wx.LEFT, 5)

        self.maxLimit_Panel.SetSizer(hbox)

    #end def

    #--------------------------------------------------------------------------
    def create_sizer(self):

        sizer = wx.GridBagSizer(11,2)
        sizer.Add(self.titlePanel, (0, 1), span=(1,2), flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.label_current, (1, 1))
        sizer.Add(self.current_Panel, (1, 2))
        sizer.Add(self.label_pid_tolerance, (2, 1))
        sizer.Add(self.pid_tol_Panel, (2, 2))
        sizer.Add(self.label_stability_threshold, (3,1))
        sizer.Add(self.stability_threshold_Panel, (3, 2))
        sizer.Add(self.label_thickness, (4, 1))
        sizer.Add(self.thickness_Panel, (4, 2))
        sizer.Add(self.label_measurement_number, (5,1))
        sizer.Add(self.measurement_number_Panel, (5, 2))
        sizer.Add(self.label_measurements, (6,1))
        sizer.Add(self.measurementPanel, (6, 2))
        sizer.Add(self.maxCurrent_Panel, (7, 1), span=(1,2))
        sizer.Add(self.maxLimit_Panel, (8, 1), span=(1,2))
        sizer.Add(self.linebreak4, (9,1),span = (1,2))
        sizer.Add(self.run_stopPanel, (10,1),span = (1,2), flag=wx.ALIGN_CENTER_HORIZONTAL)

        self.SetSizer(sizer)

    #end def

    #--------------------------------------------------------------------------
    def enable_buttons(self):
        self.btn_pid_tolerance.Enable()
        self.btn_stability_threshold.Enable()
        self.btn_current.Enable()
        self.btn_thickness.Enable()
        self.btn_measurement_number.Enable()
        self.btn_new.Enable()
        self.btn_ren.Enable()
        self.btn_dlt.Enable()
        self.btn_clr.Enable()
        self.btn_check.Enable()
        self.btn_run.Enable()
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
        global cycle

        self.ctime = str(datetime.now())[11:19]
        self.time = 0
        self.t='0:00:00'
        self.d=str(0.00)
        self.rA=str(0.00)
        self.rB=str(0.00)
        self.rho = str(0.00)
        self.tS=str(30.0)
        self.tH=str(30.0)
        self.tHset=str(30.0)
        self.stability = '-'
        self.i = str(0.00)
        self.cycle = 'None'
        self.measurement = 'OFF'

        self.celsius = u"\u2103"
        self.ohm = u"\u2126"
        #self.perp = u"\u27c2"

        self.create_title("Status Panel")
        self.linebreak1 = wx.StaticLine(self, pos=(-1,-1), size=(300,1))
        self.create_status()
        self.linebreak2 = wx.StaticLine(self, pos=(-1,-1), size=(300,1))

        self.linebreak3 = wx.StaticLine(self, pos=(-1,-1), size=(1,300), style=wx.LI_VERTICAL)

        # Updates from running program
        pub.subscribe(self.OnTime, "Time R_B")
        pub.subscribe(self.OnTime, "Time R_A")
        pub.subscribe(self.OnTime, "Time Heater Temp")
        pub.subscribe(self.OnTime, "Time Sample Temp")
        pub.subscribe(self.OnTime, "Time Resistivity")

        pub.subscribe(self.OnThickness, "Sample Thickness")

        pub.subscribe(self.OnR_A, "R_A")
        pub.subscribe(self.OnR_B, "R_B")
        pub.subscribe(self.OnResistivity, "Resistivity")

        pub.subscribe(self.OnHeaterSP, "Heater SP")
        pub.subscribe(self.OnHeaterTemp, "Heater Temp")
        pub.subscribe(self.OnSampleTemp, "Sample Temp")
        pub.subscribe(self.OnStability, "Stability")

        pub.subscribe(self.OnCurrent, "Current")

        pub.subscribe(self.OnCycle, "Cycle")
        pub.subscribe(self.OnMeasurement, "Measurement")


        # Updates from inital check
        pub.subscribe(self.OnR_A, "R_A Status")
        pub.subscribe(self.OnR_B, "R_B Status")

        pub.subscribe(self.OnHeaterSP, "Heater SP Status")
        pub.subscribe(self.OnHeaterTemp, "Heater Temp Status")
        pub.subscribe(self.OnSampleTemp, "Sample Temp Status")

        pub.subscribe(self.OnCurrent, "Current Status")
        pub.subscribe(self.OnMeasurement, "Measurement Status")

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
    def OnStability(self, msg):
        if msg != '-':
            self.stability = '%.3f'%(float(msg))
        else:
            self.stability = msg
        self.update_values()
    #end def

    #--------------------------------------------------------------------------
    def OnCurrent(self, msg):
        self.i = '%.2f'%(float(msg))
        self.update_values()
    #end def

    #--------------------------------------------------------------------------
    def OnCycle(self, msg):
        self.cycle = msg
        self.update_values()
    #end def

    #--------------------------------------------------------------------------
    def OnMeasurement(self, msg):
        self.measurement = msg
        self.update_values()
    #end def

    #--------------------------------------------------------------------------
    def OnTime(self, msg):
        self.time = int(float(msg))

        hours = str(self.time/3600)
        minutes = int(self.time%3600/60)
        if (minutes < 10):
            minutes = '0%i'%(minutes)
        else:
            minutes = '%i'%(minutes)
        seconds = int(self.time%60)
        if (seconds < 10):
            seconds = '0%i'%(seconds)
        else:
            seconds = '%i'%(seconds)

        self.t = '%s:%s:%s'%(hours,minutes,seconds)
        self.ctime = str(datetime.now())[11:19]
        self.update_values()
    #end def

    #--------------------------------------------------------------------------
    def OnThickness(self, msg):
        self.d = '%.2f'%(float(msg))
        self.update_values()
    #end def

    #--------------------------------------------------------------------------
    def OnResistivity(self,msg):
        self.rho = '%.2f'%(float(msg))
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
        self.label_ctime = wx.StaticText(self, label="current time:")
        self.label_ctime.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_t = wx.StaticText(self, label="run time (s):")
        self.label_t.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_d = wx.StaticText(self, label="sample thickness (cm):")
        self.label_d.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_tS = wx.StaticText(self, label="sample temp ("+self.celsius+ "):")
        self.label_tS.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_tH = wx.StaticText(self, label="heater temp ("+self.celsius+ "):")
        self.label_tH.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_tHset = wx.StaticText(self, label="heater set point ("+self.celsius+ "):")
        self.label_tHset.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_stability = wx.StaticText(self, label="stability ("+self.celsius+ "/min):")
        self.label_stability.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_rA = wx.StaticText(self, label="resistance_A (m"+self.ohm+"):")
        self.label_rA.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_rB = wx.StaticText(self, label="resistance_B (m"+self.ohm+"):")
        self.label_rB.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_rho = wx.StaticText(self, label="resistivity (m"+self.ohm+"cm):")
        self.label_rho.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_i = wx.StaticText(self, label="current (mA):")
        self.label_i.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_cycle = wx.StaticText(self, label="cycle:")
        self.label_cycle.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.label_measurement = wx.StaticText(self, label="measurement:")
        self.label_measurement.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))

        self.ctimecurrent = wx.StaticText(self, label=self.ctime)
        self.ctimecurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
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
        self.stabilitycurrent = wx.StaticText(self, label=self.stability)
        self.stabilitycurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.rAcurrent = wx.StaticText(self, label=self.rA)
        self.rAcurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.rBcurrent = wx.StaticText(self, label=self.rB)
        self.rBcurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.rhocurrent = wx.StaticText(self, label=self.rho)
        self.rhocurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.icurrent = wx.StaticText(self, label=self.i)
        self.icurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.cyclecurrent = wx.StaticText(self, label=self.cycle)
        self.cyclecurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))
        self.measurementcurrent = wx.StaticText(self, label=self.cycle)
        self.measurementcurrent.SetFont(wx.Font(16, wx.DEFAULT, wx.NORMAL, wx.NORMAL))

    #end def

    #--------------------------------------------------------------------------
    def update_values(self):
        self.ctimecurrent.SetLabel(self.ctime)
        self.tcurrent.SetLabel(self.t)
        self.dcurrent.SetLabel(self.d)
        self.tScurrent.SetLabel(self.tS)
        self.tHcurrent.SetLabel(self.tH)
        self.tHsetcurrent.SetLabel(self.tHset)
        self.stabilitycurrent.SetLabel(self.stability)
        self.rAcurrent.SetLabel(self.rA)
        self.rBcurrent.SetLabel(self.rB)
        self.rhocurrent.SetLabel(self.rho)
        self.icurrent.SetLabel(self.i)
        self.cyclecurrent.SetLabel(self.cycle)
        self.measurementcurrent.SetLabel(self.measurement)

    #end def

    #--------------------------------------------------------------------------
    def create_sizer(self):
        sizer = wx.GridBagSizer(16,2)

        sizer.Add(self.titlePanel, (0, 0), span = (1,2), border=5, flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.linebreak1,(1,0), span = (1,2))

        sizer.Add(self.label_ctime, (2,0))
        sizer.Add(self.ctimecurrent, (2, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.label_t, (3,0))
        sizer.Add(self.tcurrent, (3, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.label_d, (4,0))
        sizer.Add(self.dcurrent, (4, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)

        sizer.Add(self.label_tS, (5,0))
        sizer.Add(self.tScurrent, (5, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.label_tH, (6,0))
        sizer.Add(self.tHcurrent, (6, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.label_tHset, (7,0))
        sizer.Add(self.tHsetcurrent, (7, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.label_stability, (8,0))
        sizer.Add(self.stabilitycurrent, (8, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)

        sizer.Add(self.label_rA, (9,0))
        sizer.Add(self.rAcurrent, (9, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.label_rB, (10,0))
        sizer.Add(self.rBcurrent, (10, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)

        sizer.Add(self.label_rho, (11,0))
        sizer.Add(self.rhocurrent, (11,1),flag=wx.ALIGN_CENTER_HORIZONTAL)

        sizer.Add(self.label_i, (12,0))
        sizer.Add(self.icurrent, (12, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)

        sizer.Add(self.label_cycle, (13,0))
        sizer.Add(self.cyclecurrent, (13, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.label_measurement, (14,0))
        sizer.Add(self.measurementcurrent, (14, 1),flag=wx.ALIGN_CENTER_HORIZONTAL)


        sizer.Add(self.linebreak2, (15,0), span = (1,2))

        self.SetSizer(sizer)
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
#end class
###############################################################################

###############################################################################
class ResistivityPanel(wx.Panel):
    """
    GUI Window for plotting voltage data.
    """
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)

        global filePath

        global t_list
        global rho_list

        self.rhochar = u"\u03c1"

        self.create_title("Resistivity Panel")
        self.init_plot()
        self.canvas = FigureCanvasWxAgg(self, -1, self.figure)
        self.create_control_panel()
        self.create_sizer()

        pub.subscribe(self.OnResistivity, "Resistivity")
        pub.subscribe(self.OnResistivityTime, "Time Resistivity")

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
        self.ymin_control = BoundControlBox(self, -1, self.rhochar + " min", 0)
        self.ymax_control = BoundControlBox(self, -1, self.rhochar + " max", 10)

        self.hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        self.hbox1.AddSpacer(10)
        self.hbox1.Add(self.xmin_control, border=5, flag=wx.ALL)
        self.hbox1.Add(self.xmax_control, border=5, flag=wx.ALL)
        self.hbox1.AddSpacer(10)
        self.hbox1.Add(self.ymin_control, border=5, flag=wx.ALL)
        self.hbox1.Add(self.ymax_control, border=5, flag=wx.ALL)
    #end def

    #--------------------------------------------------------------------------
    def OnResistivity(self, msg):
        self.rho = float(msg)
        rho_list.append(self.rho)
        t_list.append(self.t)
    #end def

    #--------------------------------------------------------------------------
    def OnResistivityTime(self, msg):
        self.t = float(msg)
    #end def

    #--------------------------------------------------------------------------
    def init_plot(self):
        self.dpi = 100
        self.colorrho = 'g'

        self.figure = Figure((6,2), dpi=self.dpi)
        self.subplot = self.figure.add_subplot(111)
        self.linerho, = self.subplot.plot(t_list,rho_list, color=self.colorrho, linewidth=1)

        self.legend = self.figure.legend( (self.linerho,), (r"$\rho$",), (0.15,0.70),fontsize=8)
        #self.subplot.text(0.05, .95, r'$X(f) = \mathcal{F}\{x(t)\}$', \
            #verticalalignment='top', transform = self.subplot.transAxes)
    #end def

    #--------------------------------------------------------------------------
    def draw_plot(self,i):
        self.subplot.clear()
        #self.subplot.set_title("voltage vs. time", fontsize=12)

        self.subplot.set_ylabel(r"$\rho$ ($m\Omega cm$)",fontsize=8)
        self.subplot.set_xlabel("t (s)", fontsize = 8)

        # Adjustable scale:
        if self.xmax_control.is_auto():
            xmax = max(t_list)
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
            maxR = max(rho_list)
            ymax = maxR + abs(maxR)*0.3
        else:
            ymax = float(self.ymax_control.manual_value())

        self.subplot.set_xlim([xmin, xmax])
        self.subplot.set_ylim([ymin, ymax])

        pylab.setp(self.subplot.get_xticklabels(), fontsize=8)
        pylab.setp(self.subplot.get_yticklabels(), fontsize=8)

        self.linerho, = self.subplot.plot(t_list,rho_list, color=self.colorrho, linewidth=1)

        return (self.linerho,)
        #return (self.subplot.plot( thighV_list, highV_list, color=self.colorH, linewidth=1),
            #self.subplot.plot( tlowV_list, lowV_list, color=self.colorL, linewidth=1))

    #end def

    #--------------------------------------------------------------------------
    def save_plot(self, msg):
        path = filePath + "/Resistivity_Plot.png"
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

    #end def

    #--------------------------------------------------------------------------
    def OnSampleTemp(self, msg):
        self.tS = float(msg)
        sampletemp_list.append(self.tS)
        tsampletemp_list.append(self.ttS)
    #end def

    #--------------------------------------------------------------------------
    def OnTimeHeaterTemp(self, msg):
        self.ttH = float(msg)

    #end def

    #--------------------------------------------------------------------------
    def OnHeaterTemp(self, msg):
        self.tH = float(msg)
        heatertemp_list.append(self.tH)
        theatertemp_list.append(self.ttH)
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

        self.legend = self.figure.legend( (self.lineTH, self.lineTS), (r"$T_{heater}$",r"$T_{sample}$"), (0.15,0.70),fontsize=8)

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
        self.resistivitypanel = ResistivityPanel(self, size=wx.DefaultSize)
        self.temperaturepanel = TemperaturePanel(self, size=wx.DefaultSize)

        self.statuspanel.SetBackgroundColour('#ededed')

        sizer = wx.GridBagSizer(2, 3)
        sizer.Add(self.userpanel, (0,0),flag=wx.ALIGN_CENTER_HORIZONTAL, span = (2,1))
        sizer.Add(self.statuspanel, (0,2),flag=wx.ALIGN_CENTER_HORIZONTAL, span = (2,1))
        sizer.Add(self.resistivitypanel, (0,1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.temperaturepanel, (1,1),flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Fit(self)

        self.SetSizer(sizer)
        self.SetTitle('High Temp Resistivity GUI')
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
        self.statusbar.SetFieldsCount(10)
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

        # Stability Threshold:
        stableThresh_text = wx.StaticText(self.statusbar, -1, "Within Stability Threshold:")
        self.width4 = stableThresh_text.GetRect().width + 5

        self.indicator_stable = wx.StaticText(self.statusbar, -1, "-")
        self.width5 = self.width3

        # Measurement Time:
        measurement_number_text = wx.StaticText(self.statusbar, -1, "Time Until Measurement Complete:")
        self.width6 = measurement_number_text.GetRect().width + self.space_between

        self.indicator_measurement_number = wx.StaticText(self.statusbar, -1, "-")
        self.width7 = 40

        # Placer 2:
        placer2 = wx.StaticText(self.statusbar, -1, " ")

        # Version:
        version_label = wx.StaticText(self.statusbar, -1, "Version: %s" % version)
        self.width8 = version_label.GetRect().width + self.space_between

        # Set widths of each piece of the status bar:
        self.statusbar.SetStatusWidths([self.width0, 50, self.width2, self.width3, self.width4, self.width5, self.width6, self.width7, -1, self.width8])

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

        # Stability Threshold:
        self.statusbar.AddWidget(stableThresh_text, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)
        self.statusbar.AddWidget(self.indicator_stable, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)

        # Measurement Time:
        self.statusbar.AddWidget(measurement_number_text, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)
        self.statusbar.AddWidget(self.indicator_measurement_number, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)

        # Placer 2
        self.statusbar.AddWidget(placer2)

        # Version:
        self.statusbar.AddWidget(version_label, ESB.ESB_ALIGN_CENTER_HORIZONTAL, ESB.ESB_ALIGN_CENTER_VERTICAL)

    #end def

    #--------------------------------------------------------------------------
    def update_statusbar(self, msg):
        string = msg

        # Status:
        if string == 'Running' or string == 'Finished, Ready' or string == 'Exception Occurred' or string=='Checking':
            self.status_text.SetLabel(string)
            self.status_text.SetBackgroundColour(wx.NullColour)

            if string == 'Exception Occurred':
                self.status_text.SetBackgroundColour("RED")
            #end if

        #end if

        # Measurement Timer:
        elif string[-3:] == 'mea':
            self.indicator_measurement_number.SetLabel(string[:-3] + ' (s)')

        #end elif

        else:
            tol = string[0]
            stable = string[1]

            # PID Tolerance indicator:
            self.indicator_tol.SetLabel(tol)
            if tol == 'OK':
                self.indicator_tol.SetBackgroundColour("GREEN")
            #end if
            else:
                self.indicator_tol.SetBackgroundColour("RED")
            #end else

            # Stability Threshold indicator:
            self.indicator_stable.SetLabel(stable)
            if stable == 'OK':
                self.indicator_stable.SetBackgroundColour("GREEN")
            #end if
            elif stable =='N/A':
                self.indicator_stable.SetBackgroundColour("BLACK")
            #end elif
            else:
                self.indicator_stable.SetBackgroundColour("RED")
            #end else
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
        self.frame = Frame(parent=None, title="High Temp Resistivity GUI", size=(1350,1350))
        self.frame.Show()

        setup = Setup()
        return True
    #end init

#end class
###############################################################################

#==============================================================================
if __name__=='__main__':
    app = App()
    app.MainLoop()

#end if
