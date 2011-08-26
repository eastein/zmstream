import sys
import zmstream

output_prefix = sys.argv[1]
input_capture = sys.argv[2]

auth = None
try :
	auth = (sys.argv[3], sys.argv[4])
except IndexError :
	pass

try :
	boundary = sys.argv[5]
except IndexError :
	pass

ext = 'jpg'

zms = zmstream.ZMStreamer(1, input_capture, auth=auth, boundary=boundary)

try :
	s = zms.generate()
	i = 0
	for frame in s :
		i += 1
		filename = '%s.%06d.%s' % (output_prefix, i, ext)
		print 'writing %s' % filename
		fhw = open(filename, 'w')
		try :
			fhw.write(frame)
		finally :
			fhw.close()
finally :
	zms.fh.close()
