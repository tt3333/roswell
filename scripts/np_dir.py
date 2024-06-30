#!/usr/bin/env python

import roswell.usbclient as usbclient
import roswell.nputils as nputils
import sys

c = usbclient.USBClient()
c.open()
print("opened USB device successfully")
np = nputils.SFMemory(c)

if not np.is_multicassette():
	print("Menu is not detected")
	sys.exit()

for entry in np.get_directory():
	print("")
	print("Directory index        : %d" % entry.directory_index)
	print("First FLASH block      : %d" % entry.first_flash_block)
	print("First SRAM block       : %d" % entry.first_sram_block)
	print("Number of FLASH blocks : %d" % entry.flash_blocks)
	print("Number of SRAM blocks  : %d" % entry.sram_blocks)
	print("Gamecode               : %s" % entry.gamecode)
	print("Title                  : %s" % entry.title)
	print("Date                   : %s" % entry.date)
	print("Time                   : %s" % entry.time)
	print("Law                    : %s" % entry.law)
