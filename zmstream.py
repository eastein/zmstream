import select
import time

class ZMStreamer(object) :
	def __init__(self, timeout) :
		self.timeout = timeout
		self.chunk = 1024

	def discard_until(self, buf, fh, including) :
		while including not in buf :
			r, w, x = select.select([fh], [], [], self.timeout)
			buf += fh.read(self.chunk)
		offset = buf.find(including)
		discard_before = offset + len(including)
		buf = buf[discard_before:]
		return buf

	def generate(self, fh) :
		buf = ''
		# first, read until there's a --ZoneMinderFrame header
		while True :
			buf = self.discard_until(buf, fh, '--ZoneMinderFrame\r\n')
			print 'found zoneminder frame'
