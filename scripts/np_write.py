#!/usr/bin/env python

from math import ceil
import roswell.usbclient as usbclient
import roswell.romutils as romutils
import argparse
import atexit
import os
import sys
import time

# -----------------------------------------------------------------------------

def write_byte(addr, value):
	c.write_cart(addr, value.to_bytes(1, 'little'))

def write_byte2(addr, value):
	# write the same value to two chips
	write_byte(0xC00000 | addr, value)
	write_byte(0xE00000 | addr, value)

def read_byte(addr):
	return c.read_cart(addr, 1)[0]

def wait(addr):
	while True:
		status = read_byte(addr)
		if status & 0x80:
			return status

def wakeup():
	write_byte(0x2400, 0x09)
	dummy = read_byte(0x2400)
	write_byte(0x2401, 0x28)
	write_byte(0x2401, 0x84)
	write_byte(0x2400, 0x06)
	write_byte(0x2400, 0x39)

def read_reset():
	write_byte2(0xAAAA, 0xAA)
	write_byte2(0x5554, 0x55)
	write_byte2(0xAAAA, 0xF0)

def show_hidden():
	write_byte2(0, 0x38)
	write_byte2(0, 0xD0)
	write_byte2(0, 0x71)
	wait(0xC00004)
	wait(0xE00004)
	write_byte2(0, 0x72)
	write_byte2(0, 0x75)

def hidden_erase():
	write_byte2(0x1AAAA, 0xAA)
	write_byte2(0x15554, 0x55)
	write_byte2(0x1AAAA, 0x77)
	write_byte2(0x0AAAA, 0xAA)
	write_byte2(0x05554, 0x55)
	write_byte2(0x0AAAA, 0xE0)
	wait(0xC00000)
	wait(0xE00000)

def chip_erase():
	write_byte2(0xAAAA, 0xAA)
	write_byte2(0x5554, 0x55)
	write_byte2(0xAAAA, 0x80)
	write_byte2(0xAAAA, 0xAA)
	write_byte2(0x5554, 0x55)
	write_byte2(0xAAAA, 0x10)
	wait(0xC00000)
	wait(0xE00000)

def hidden_write(addr, data):
	assert(len(data) == 128)
	bank = addr & 0xE00000
	write_byte(bank | 0x1AAAA, 0xAA)
	write_byte(bank | 0x15554, 0x55)
	write_byte(bank | 0x1AAAA, 0x77)
	write_byte(bank | 0xAAAA, 0xAA)
	write_byte(bank | 0x5554, 0x55)
	write_byte(bank | 0xAAAA, 0x99)
	c.write_cart(addr, data)
	write_byte(addr + 0x7F, data[0x7F])
	return wait(bank) & 0x10

def page_write(addr, data):
	assert(len(data) == 128)
	bank = addr & 0xE00000
	write_byte(bank | 0xAAAA, 0xAA)
	write_byte(bank | 0x5554, 0x55)
	write_byte(bank | 0xAAAA, 0xA0)
	c.write_cart(addr, data)
	write_byte(addr + 0x7F, data[0x7F])

# -----------------------------------------------------------------------------

def load_rom(path):
	if not os.path.isfile(path):
		raise argparse.ArgumentTypeError(f"{path}: No such file.")
	with open(path, 'rb') as file:
		data = file.read()

	if len(data) % 0x8000 == 0x200:
		# remove copier header
		data = data[0x200:]

	size = len(data)
	if size < 0x8000:
		raise argparse.ArgumentTypeError(f"{path}: ROM must be at least 32kb")
	if size > 0x400000:
		raise argparse.ArgumentTypeError(f"{path}: ROM cannot be larger than 4Mb (32Mbit)")

	# pad in the rest of the flash block
	data = data.ljust(ceil(len(data) / 0x80000) * 0x80000, b'\xFF')

	score_lo = romutils.score_header(data, 0x7FC0)
	score_hi = romutils.score_header(data, 0xFFC0)
	if score_lo <= 0 and score_hi <= 0:
		# unable to detect ROM mapping
		raise argparse.ArgumentTypeError(f"{path}: No valid ROM type detected")

	return data

def load_sram(path):
	if not os.path.isfile(path):
		raise argparse.ArgumentTypeError(f"{path}: No such file.")
	with open(path, 'rb') as file:
		data = file.read()
	if len(data) > 0x8000:
		raise argparse.ArgumentTypeError(f"{path}: SRAM cannot be larger than 32kb (256kbit)")
	return data

def load_map(path):
	if not os.path.isfile(path):
		raise argparse.ArgumentTypeError(f"{path}: No such file.")
	with open(path, 'rb') as file:
		data = file.read()
	if len(data) != 0x200:
		raise argparse.ArgumentTypeError(f"{path}: map must be 512 bytes")
	return data

# -----------------------------------------------------------------------------

def cleanup():
	read_reset()

	#/WP=LOW, force write protect
	write_byte(0x2400, 0x03)

def write_rom(data):
	print("erasing ROM", end='\r');
	chip_erase()

	rom1 = data[0x000000:0x200000]
	rom2 = data[0x200000:0x400000]
	size1 = len(rom1)
	size2 = len(rom2)
	offset1 = 0
	offset2 = 0
	busy1 = False
	busy2 = False

	while (offset1 < size1) or (offset2 < size2):
		if offset1 < size1:
			if not busy1:
				print("writing ROM %u / %u bytes" % (offset1 + offset2, size1 + size2), end='\r')
				page_write(0xC00000 | offset1, rom1[offset1:offset1+0x80])
				busy1 = True
			else:
				status = read_byte(0xC00000)
				if status & 0x80:
					busy1 = False
					if status & 0x10:
						break
					offset1 += 0x80
		if offset2 < size2:
			if not busy2:
				print("writing ROM %u / %u bytes" % (offset1 + offset2, size1 + size2), end='\r')
				page_write(0xE00000 | offset2, rom2[offset2:offset2+0x80])
				busy2 = True
			else:
				status = read_byte(0xE00000)
				if status & 0x80:
					busy2 = False
					if status & 0x10:
						break
					offset2 += 0x80

	print("writing ROM %u / %u bytes" % (offset1 + offset2, size1 + size2))
	read_reset()
	return offset1 + offset2

def verify_rom(data):
	i = 0
	size = len(data)
	while i < size:
		print("verifying ROM %u / %u bytes" % (i, size), end='\r')
		tmp = c.read_cart(0xC00000 + i, 0x10000)
		if bytes(tmp) != data[i:i+0x10000]:
			break
		i += 0x10000

	print("verifying ROM %u / %u bytes" % (i, size))
	return i

def write_map(data):
	assert(len(data) == 512)
	print("erasing map", end='\r');
	hidden_erase()
	print("writing map", end='\r');
	status  = hidden_write(0xC0FF00, data[0x000:0x080])
	status |= hidden_write(0xC0FF80, data[0x080:0x100])
	status |= hidden_write(0xE0FF00, data[0x100:0x180])
	status |= hidden_write(0xE0FF80, data[0x180:0x200])
	return 0 if status else len(data)

def verify_map(data):
	assert(len(data) == 512)
	print("verifying map", end='\r');
	show_hidden()
	tmp = c.read_cart(0xC0FF00, 0x100) + c.read_cart(0xE0FF00, 0x100)
	read_reset()
	return 0 if bytes(tmp) != data else len(data)

def write_sram(data):
	print("writing SRAM", end='\r');
	c.write_cart(0x206000, data[0x0000:0x2000])
	c.write_cart(0x216000, data[0x2000:0x4000])
	c.write_cart(0x226000, data[0x4000:0x6000])
	c.write_cart(0x236000, data[0x6000:0x8000])
	return len(data)

def verify_sram(data):
	print("verifying SRAM", end='\r')
	tmp  = c.read_cart(0x206000, 0x2000)
	tmp += c.read_cart(0x216000, 0x2000)
	tmp += c.read_cart(0x226000, 0x2000)
	tmp += c.read_cart(0x236000, 0x2000)
	return 0 if bytes(tmp[0:len(data)]) != data else len(data)

def write_and_verify(write_func, verify_func, data, name):
	start = time.perf_counter()
	if write_func(data) == len(data):
		print("%s was successfully written in %.2f sec" % (name, time.perf_counter() - start))
	else:
		print("%s writing failed." % (name))
		sys.exit()

	start = time.perf_counter()
	if verify_func(data) == len(data):
		print("%s was successfully verified in %.2f sec" % (name, time.perf_counter() - start))
	else:
		print("%s verification failed." % (name))
		sys.exit()

# -----------------------------------------------------------------------------

parser = argparse.ArgumentParser()
parser.add_argument('-r', '--rom',  metavar='path', help='ROM file',  type=load_rom)
parser.add_argument('-m', '--map',  metavar='path', help='map file',  type=load_map)
parser.add_argument('-s', '--sram', metavar='path', help='SRAM file', type=load_sram)
parser.add_argument('--rewrite_serial', help='Rewrite the serial number to the value in the map file.', action='store_true')
args = parser.parse_args()
if (args.rom is None) and (args.map is None) and (args.sram is None):
	parser.error("At least one of ROM file, map file, or SRAM file must be specified.")

c = usbclient.USBClient()
c.open()
print("opened USB device successfully")

tmp = read_byte(0x2400)
if tmp == 0x7D:
	wakeup()
elif tmp != 0x2A:
	print("SF memory is not detected")
	sys.exit()

print("SF memory is detected")

atexit.register(cleanup)

#/WP=HIGH, release write protect
write_byte(0x2400, 0x02)

#HIROM:ALL
write_byte(0x2400, 0x04)

if args.rom is not None:
	write_and_verify(write_rom, verify_rom, args.rom, "ROM")

if args.map is not None:
	show_hidden()

	if not args.rewrite_serial:
		bootsect = c.read_cart(0xC0FF00, 0x100) + c.read_cart(0xE0FF00, 0x100)
		args.map = bytearray(args.map)
		for i in range(1,16,2):
			args.map[i] = bootsect[i]

	write_and_verify(write_map, verify_map, args.map, "map")

if args.sram is not None:
	write_and_verify(write_sram, verify_sram, args.sram, "SRAM")
