#! /usr/bin/python
# -*- coding: utf-8 -*-
"""
Created: 2016-02-09
@author: Bobby McKinney (bobbymckinney@gmail.com)
"""
import os
import numpy as np
import matplotlib.pyplot as plt
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
    #--------------------------------------------------------------------------
    def __init__(self):
        self.Setup()
        self.delay = .5
        self.voltage = .1
        self.Data = {}

        # short the matrix card
        self.k2700.closeChannels('117, 125, 126, 127, 128')
        print(self.k2700.get_closedChannels())
        time.sleep(self.delay)

        self.measure_contacts()

        self.resetSourcemeter()
        self.create_plot()
    #end init
    
    #--------------------------------------------------------------------------
    def Setup(self):
        # Define Keithley instrument ports:
        self.k2700 = Keithley_2700('GPIB0::16::INSTR') # MultiMeter for Matrix Card operation
        self.k2400 = Keithley_2400('GPIB0::24::INSTR') # SourceMeter
        
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
    def resetSourcemeter(self):
        self.k2400.current_mode()
        self.k2400.set_current_range(10.5*10**(-3)) # Default
        self.k2400.set_current(float(current))
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
        plt.show()
    #end def

#end class
###############################################################################

#==============================================================================
if __name__=='__main__':
    runprogram = Main()
#end if