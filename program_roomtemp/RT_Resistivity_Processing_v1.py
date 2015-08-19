# -*- coding: utf-8 -*-
"""
Created on 2015-06-29

@author: Bobby McKinney (rmckinne@mines.edu)

__Title__

Description:
    
    
Comments:
    
"""

import numpy as np

#--------------------------------------------------------------------------
def output_file(inFile, outFile):
    
    ohm = u"\u2126"
    perp = u"\u27c2"
    
    data = import_Data(inFile)
    
    avg_d = np.average(data[0])
    avg_B = np.average(data[1])
    avg_r1234 = np.average(data[2])
    avg_r3412 = np.average(data[3])
    avg_r1324 = np.average(data[4])
    avg_r2413 = np.average(data[5])
    
    avg_rA = (avg_r1234 + avg_r3412)/2
    avg_rB = (avg_r1324 + avg_r2413)/2
            
    measurement = [avg_d, avg_rA, avg_rB]
    
    ### Create a file to save the data to:
    file = outFile
    myfile = open(outFile, 'w')
    myfile.write('Thickness (cm),Sheet Resistance (Ohm),Resistivity (Ohm*cm)\n')
    ### Get final data:
    d = measurement[0]
    rs = calculate_sheet_resistance(measurement[1], measurement[2])
    rho = d*rs
    final_data = [d, rs, rho]
    myfile.write('%f,%f,%f\n' % (d,rs,rho))
    print '\nthickness (cm): %.2f\nsheet resistance (Ohm): %.5f\nresistivity (Ohm*cm): %.5f\n' % (d,rs,rho)
    
    myfile.close()

#end def

#--------------------------------------------------------------------------
def import_Data(filePath):
    
    f = open(filePath)
    loadData = f.read()
    f.close()
    
    loadDataByLine = loadData.split('\n')
    numericData = loadDataByLine[5:]
    
    length = len(numericData)-1
    d      = [None]*length
    r_1234 = [None]*length
    r_3412 = [None]*length
    r_1324 = [None]*length
    r_2413 = [None]*length
    r_A    = [None]*length
    r_B    = [None]*length
    
    for x in xrange(length):
        line = numericData[x].split(',')
        d[x] = float(line[1])
        r_1234[x] = float(line[3])
        r_3412[x] = float(line[5])
        r_1324[x] = float(line[7])
        r_2413[x] = float(line[9])
        r_A[x] = float(line[10])
        r_B[x] = float(line[11])

    #end for
    
    return d,r_1234, r_3412, r_1324, r_2413, r_A, r_B
            
#end def


#--------------------------------------------------------------------------
def calculate_sheet_resistance(rA, rB):
    delta = 0.0005 # error limit (0.05%)
    
    z1 = (2*np.log(2))/(np.pi*(rA + rB))

    condition = 'not met'
    
    # Algorithm taken from http://www.nist.gov/pml/div683/hall_algorithm.cfm
    while condition == 'not met':
        y = 1/np.exp(np.pi*z1*rA) + 1/np.exp(np.pi*z1*rB)
        
        z2 = z1 - (1/np.pi)*((1-y)/(rA/np.exp(np.pi*z1*rA) + rB/np.exp(np.pi*z1*rB)))
        
        lim = abs(z2 - z1)/z2
        
        if lim < delta:
            condition = 'met'
        else:
            z1 = z2
            
    #end while
    
    return 1/z2
    
#end def    
    
#==============================================================================
            
def main():
    #directory = 'E:\Google Drive\Toberer Lab\Resistivity System\Data\R Test 14\\'
    directory = '/Users/bobbymckinney/Google Drive/rwm-tobererlab/Resistivity Data 2015-05-27 16.36.15'
    inFile = directory + '/Data.csv'
    outFile = directory + '/Final Data.csv'
    
    output_file(inFile, outFile)
    
#end def
    
if __name__ == '__main__':
    main()
#end if
