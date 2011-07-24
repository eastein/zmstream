import socket
import sys
import urlparse
import zmstream

input_capture = sys.argv[1]
output_prefix = sys.argv[2]
ext = 'jpg'

def send_all(sock, s) :
	now = 0
	need = len(s)
	# FIXME get some select action going here
	while now < need :
		now += sock.send(s[now:])

if input_capture.startswith('http') :
	o = urlparse.urlparse(input_capture)
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

	fh = socket.create_connection((host, port))
	request = 'GET %s HTTP/1.1\r\nHost: %s\r\n\r\n' % (path, netloc)

	send_all(fh, request)

	st = zmstream.ZMStreamer.ST_SOCKET
else :
	fh = open(input_capture, 'r')
	st = zmstream.ZMStreamer.ST_FILE
try :
	zms = zmstream.ZMStreamer(1, fh, st)

	s = zms.generate(fh)
	i = 0
	for frame in s :
		i += 1
		filename = '%s.%06d.%s' % (output_prefix, i, ext)
		fhw = open(filename, 'w')
		try :
			fhw.write(frame)
		finally :
			fhw.close()
finally :
	fh.close()
