import urlparse
import socket
import select
import time
import base64
import threading
import Queue

class Timeout(Exception) :
	pass

class ZMStreamer(object) :
	ST_FILE = 1
	ST_SOCKET = 2
	
	ZF_FRAME_HEADER = '--%s\r\n'

	def __init__(self, timeout, input_capture, failure_timeout=10, auth=None, boundary=None) :
		self.timeout = timeout
		self.input_capture = input_capture
		self.failure_timeout = failure_timeout
		self.ok = True
		self.auth = auth
		if boundary :
			self.boundary = boundary
		else :
			self.boundary = 'ZoneMinderFrame'
		
	def __del__(self) :
		if hasattr(self, 'fh') :
			try :
				self.fh.close()
			except :
				pass

	def rf(self, size) :
		if self.stream_type == self.ST_FILE :
			r = self.fh.read(size)
		if self.stream_type == self.ST_SOCKET :
			r = self.fh.recv(size)
		return r

	def send_all(self, sock, s) :
		now = 0
		need = len(s)
		# FIXME get some select action going here
		while now < need :
			self.abortcheck()
			now += sock.send(s[now:])

	def discard_until(self, buf, including) :
		buf, dat = self.read_until(buf, including)
		return buf

	def read_bytes(self, buf, n) :
		while len(buf) < n :
			self.abortcheck()
			r, w, x = select.select([self.fh], [], [], self.timeout)
			if r :
				buf += self.rf(min(self.chunk, n - len(buf)))
		dat = buf[0:n]
		buf = buf[n:]
		return buf, dat

	def read_until(self, buf, including) :
		while including not in buf :
			self.abortcheck()
			r, w, x = select.select([self.fh], [], [], self.timeout)
			if r :
				buf += self.rf(self.chunk)
		offset = buf.find(including)
		before_offset = offset + len(including)
		dat = buf[0:offset]
		buf = buf[before_offset:]
		return buf, dat

	def stop(self) :
		self.ok = False

	def abortcheck(self) :
		if not self.ok :
			raise StopIteration
		if hasattr(self, 'abort_ts') :
			if time.time() > self.abort_ts :
				raise Timeout

	def generate(self) :
		if self.input_capture.startswith('http') :
			o = urlparse.urlparse(self.input_capture)
			host = o.netloc.split(':')[0]
			port = o.port
			if not port :
				port = 80
			else :
				port = int(port)
			path = o.path
			netloc = o.netloc
			query = o.query

			if query :
				path = '%s?%s' % (path, query)

			basic_auth = ''
			if self.auth :
				basic_auth = '\r\nAuthorization: Basic %s' % base64.b64encode('%s:%s' % (self.auth[0], self.auth[1]))

			self.fh = socket.create_connection((host, port))
			request = 'GET %s HTTP/1.1\r\nHost: %s%s\r\n\r\n' % (path, netloc, basic_auth)

			self.send_all(self.fh, request)

			self.stream_type = self.ST_SOCKET
		else :
			self.fh = open(self.input_capture, 'r')
			self.stream_type = self.ST_FILE

		self.chunk = 1024


		try :
			buf = ''
			# first, read until there's a ZF_FRAME_HEADER
			while True :
				self.abort_ts = time.time() + self.failure_timeout
			
				# we haven't already aligned to a zoneminder frame. align now.
				buf = self.discard_until(buf, ZMStreamer.ZF_FRAME_HEADER % self.boundary)
				header = True
				headers = {}
				while header :
					self.abortcheck()
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
					buf, body = self.read_until(buf, (ZMStreamer.ZF_FRAME_HEADER % self.boundary))

				yield body

				self.abortcheck()
		finally :
			self.fh.close()

class TimestampingThrottle(threading.Thread) :
	SHUTDOWN=1
	TIMEOUT=2
	
	# FIXME add auto restart?
	def __init__(self, generator, generatorstop=None, failure_timeout=10) :
		self.failure_timeout = failure_timeout
		self.ok = True
		self.died = False
		self.generator = generator
		self.generatorstop = generatorstop
		self.q = Queue.Queue()
		threading.Thread.__init__(self)

	def stop(self) :
		self.ok = False
		self.generatorstop()

	def run(self) :
		try :
			# TODO catch exceptions here and offer a hook to call when this is dying
			for frame in self.generator :
				if not self.ok :
					self.q.put(ZMThrottle.SHUTDOWN)
					break
				self.q.put((time.time(), frame))
		except Timeout :
			self.q.put(ZMThrottle.TIMEOUT)

	def qcheck(self, v) :
		if not self.ok or v == ZMThrottle.SHUTDOWN :
			raise StopIteration
		elif v == ZMThrottle.TIMEOUT :
			raise Timeout

	def qg(self, real_timeout, parts) :
		# wait up to real_timeout total, but cut it into parts so we can quit in the middle.
		pt = real_timeout / float(parts)
		for i in range(parts) :
			try :
				return self.q.get(timeout=pt)
			except Queue.Empty :
				if not self.ok :
					raise StopIteration		

	def get(self) :
		if not self.ok :
			raise StopIteration
		
		try :
			v = self.qg(self.failure_timeout, 20)
			self.qcheck(v)
			while True :
				try :
					v = self.q.get(block=False)
					self.qcheck(v)
				except Queue.Empty :
					return v
		except Queue.Empty :
			if self.ok :
				raise Timeout
			raise StopIteration

	def generate(self) :
		while True :
			yield self.get()

class ZMThrottle(TimestampingThrottle) :
	def __init__(self, *args, **kwargs) :
		zms = ZMStreamer(*args, **kwargs)
		TimestampingThrottle.__init__(self, zms.generate(), zms.stop, failure_timeout=zms.failure_timeout)
