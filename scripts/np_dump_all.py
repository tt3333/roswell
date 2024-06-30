#!/usr/bin/env python

import roswell.usbclient as usbclient
import roswell.nputils as nputils

def save(filename, data):
	with open(filename, 'wb') as f:
		data.tofile(f)
		print("wrote %s successfully" % filename)

c = usbclient.USBClient()
c.open()
print("opened USB device successfully")
np = nputils.SFMemory(c)

# dump boot sector in bank $C0,E0
np.show_hidden()
data = c.read_cart(0xC0FF00, 256) + c.read_cart(0xE0FF00, 256)
save("np.map", data)

# dump $0000-FFFF in banks $C0-FF
np.read_reset()
data = c.read_banks(0xC0, 0xFF, 0x0000, 0xFFFF)
save("np.sfc", data)

# dump $6000-7FFF in banks $20-23
data = c.read_banks(0x20, 0x23, 0x6000, 0x7FFF)
save("np.srm", data)
