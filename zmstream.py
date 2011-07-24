import select
import time

class ZMStreamer(object) :
	ST_FILE = 1
	ST_SOCKET = 2
	
	ZF_FRAME_HEADER = '--ZoneMinderFrame\r\n'

	def __init__(self, timeout, fh, stream_type) :
		self.timeout = timeout
		self.fh = fh
		self.chunk = 1024
		self.stream_type = stream_type
		if self.stream_type == self.ST_FILE :
			self.rf = fh.read
		if self.stream_type == self.ST_SOCKET :
			self.rf = fh.recv

	def discard_until(self, buf, including) :
		buf, dat = self.read_until(buf, including)
		return buf

	def read_bytes(self, buf, n) :
		while len(buf) < n :
			r, w, x = select.select([self.fh], [], [], self.timeout)
			if r :
				buf += self.rf(min(self.chunk, n - len(buf)))
		dat = buf[0:n]
		buf = buf[n:]
		return buf, dat

	def read_until(self, buf, including) :
		while including not in buf :
			r, w, x = select.select([self.fh], [], [], self.timeout)
			if r :
				buf += self.rf(self.chunk)
		offset = buf.find(including)
		before_offset = offset + len(including)
		dat = buf[0:offset]
		buf = buf[before_offset:]
		return buf, dat

	def generate(self) :
		buf = ''
		# first, read until there's a ZF_FRAME_HEADER
		while True :
			# we haven't already aligned to a zoneminder frame. align now.
			buf = self.discard_until(buf, ZMStreamer.ZF_FRAME_HEADER)
			header = True
			headers = {}
			while header :
				buf, header = self.read_until(buf, '\r\n')
				if header :
					header = header.lower()
					point_offset = header.find(':')
					if point_offset > 0 :
						header_name = header[0:point_offset]
						header_value = header[point_offset+1:]
						while header_value.startswith(' ') :
							header_value = header_value[1:]
						headers[header_name] = header_value

			cl = None
			if 'content-length' in headers :
				try :
					cl = int(headers['content-length'])
				except ValueError :
					pass

			if cl is not None :
				buf, body = self.read_bytes(buf, cl)
			else :
				buf, body = self.read_until(buf, ZMStreamer.ZF_FRAME_HEADER)

			yield body
