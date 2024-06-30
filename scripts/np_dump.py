#!/usr/bin/env python

import roswell.usbclient as usbclient
import roswell.nputils as nputils
import sys

def save(filename, data):
	with open(filename, 'wb') as f:
		data.tofile(f)
		print("wrote %s successfully" % filename)

c = usbclient.USBClient()
c.open()
print("opened USB device successfully")
np = nputils.SFMemory(c)

if not np.is_multicassette():
	print("Menu is not detected")
	sys.exit()

sram = c.read_banks(0x20, 0x23, 0x6000, 0x7FFF)

for entry in np.get_directory():
	if entry.directory_index == 0 and entry.flash_blocks == 0:
		# ROMs created by SF Memory Binary Maker have the first directory entry filled with zeros.
		# To enable dumping of the menu program, if the number of blocks used in the first entry is 0, it is considered to be 1 block.
		entry.flash_blocks = 1

	if entry.flash_blocks and (entry.first_flash_block + entry.flash_blocks <= 8) and (entry.first_sram_block + entry.sram_blocks <= 16):
		if entry.title != "":
			filename = entry.title
		else:
			filename = str(entry.directory_index)

		first_bank = 0xC0 + (entry.first_flash_block << 3)
		last_bank = first_bank + (entry.flash_blocks << 3) - 1
		data = c.read_banks(first_bank, last_bank, 0x0000, 0xFFFF)
		save(filename + ".sfc", data)

		if entry.sram_blocks:
			sram_start = entry.first_sram_block << 11
			sram_end = sram_start + (entry.sram_blocks << 11)
			data = sram[sram_start:sram_end]
			save(filename + ".srm", data)
