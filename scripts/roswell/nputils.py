class DirectoryEntry(object):
	def __init__(self, data):
		self.directory_index   = data[0]
		self.first_flash_block = data[1]
		self.first_sram_block  = data[2]
		self.flash_blocks      = ((data[4] << 6) | data[3] >> 2)
		self.sram_blocks       = ((data[6] << 4) | data[5] >> 4)
		self.gamecode          = data[0x007:0x013].tobytes().decode('ascii',     'replace').strip("\x00")
		self.title             = data[0x013:0x03F].tobytes().decode('shift-jis', 'replace').strip("\x00")
		self.date              = data[0x1BF:0x1C9].tobytes().decode('ascii',     'replace').strip("\x00")
		self.time              = data[0x1C9:0x1D1].tobytes().decode('ascii',     'replace').strip("\x00")
		self.law               = data[0x1D1:0x1D9].tobytes().decode('ascii',     'replace').strip("\x00")

class SFMemory(object):

	def __init__(self, client):
		self.c = client

		tmp = self.read_byte(0x2400)
		if tmp == 0x7D:
			self.wakeup()
		elif tmp != 0x2A:
			raise ValueError("SF memory is not detected")

		print("SF memory is detected")

		#HIROM:ALL
		self.write_byte(0x2400, 0x04)
		self.read_reset()

	def write_byte(self, addr, value):
		self.c.write_cart(addr, value.to_bytes(1, 'little'))

	def write_byte2(self, addr, value):
		# write the same value to two chips
		self.write_byte(0xC00000 | addr, value)
		self.write_byte(0xE00000 | addr, value)

	def read_byte(self, addr):
		return self.c.read_cart(addr, 1)[0]

	def wait(self, addr):
		while True:
			status = self.read_byte(addr)
			if status & 0x80:
				return status

	def wakeup(self):
		self.write_byte(0x2400, 0x09)
		self.read_byte(0x2400)
		self.write_byte(0x2401, 0x28)
		self.write_byte(0x2401, 0x84)
		self.write_byte(0x2400, 0x06)
		self.write_byte(0x2400, 0x39)

	def read_reset(self):
		self.write_byte2(0xAAAA, 0xAA)
		self.write_byte2(0x5554, 0x55)
		self.write_byte2(0xAAAA, 0xF0)

	def show_hidden(self):
		self.write_byte2(0, 0x38)
		self.write_byte2(0, 0xD0)
		self.write_byte2(0, 0x71)
		self.wait(0xC00004)
		self.wait(0xE00004)
		self.write_byte2(0, 0x72)
		self.write_byte2(0, 0x75)

	def hidden_erase(self):
		self.write_byte2(0x1AAAA, 0xAA)
		self.write_byte2(0x15554, 0x55)
		self.write_byte2(0x1AAAA, 0x77)
		self.write_byte2(0x0AAAA, 0xAA)
		self.write_byte2(0x05554, 0x55)
		self.write_byte2(0x0AAAA, 0xE0)
		self.wait(0xC00000)
		self.wait(0xE00000)

	def chip_erase(self):
		self.write_byte2(0xAAAA, 0xAA)
		self.write_byte2(0x5554, 0x55)
		self.write_byte2(0xAAAA, 0x80)
		self.write_byte2(0xAAAA, 0xAA)
		self.write_byte2(0x5554, 0x55)
		self.write_byte2(0xAAAA, 0x10)
		self.wait(0xC00000)
		self.wait(0xE00000)

	def hidden_write(self, addr, data):
		assert(len(data) == 128)
		bank = addr & 0xE00000
		self.write_byte(bank | 0x1AAAA, 0xAA)
		self.write_byte(bank | 0x15554, 0x55)
		self.write_byte(bank | 0x1AAAA, 0x77)
		self.write_byte(bank | 0xAAAA, 0xAA)
		self.write_byte(bank | 0x5554, 0x55)
		self.write_byte(bank | 0xAAAA, 0x99)
		self.c.write_cart(addr, data)
		self.write_byte(addr + 0x7F, data[0x7F])
		return self.wait(bank) & 0x10

	def page_write(self, addr, data):
		assert(len(data) == 128)
		bank = addr & 0xE00000
		self.write_byte(bank | 0xAAAA, 0xAA)
		self.write_byte(bank | 0x5554, 0x55)
		self.write_byte(bank | 0xAAAA, 0xA0)
		self.c.write_cart(addr, data)
		self.write_byte(addr + 0x7F, data[0x7F])

	def is_multicassette(self):
		return self.c.read_cart(0xC61FF0, 16).tobytes() == b"MULTICASSETTE 32"

	def get_directory(self):
		for base in range(0xC60000, 0xC70000, 0x2000):
			entry = DirectoryEntry(self.c.read_cart(base, 0x1D9))
			if entry.directory_index != 0xFF:
				yield entry
