import zmstream
zms = zmstream.ZMStreamer(1)
fh = open('/home/eastein/Desktop/zoneminder', 'r')
zms.generate(fh)
