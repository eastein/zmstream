import sys
import zmstream

input_capture = sys.argv[1]
output_prefix = sys.argv[2]
ext = 'jpg'

zms = zmstream.ZMStreamer(1)
fh = open(input_capture, 'r')
try :
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
