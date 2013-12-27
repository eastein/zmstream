# Purpose

ZMStream is a library for creating creating an iterable object for image frames from a ZoneMinder stream, other Motion JPEG stream, or anything FFMPEG can handle.  Frames are emitted as `PIL.Image.Image` objects.  Additionally, Motion JPEG server support is available as zmstream.Server.

# Dependencies

* PIL
* pyffmpeg (http://code.google.com/p/pyffmpeg/) if `Mode.FFMPEG` is used.

# Platforms

ZMStream has been tested to work on Ubuntu 10.04 and Debian Squeeze, using CPython 2.6.x and 2.7.x.  Centos 6 is known to work as well.

# Examples

* Please see test.py for an example.
* Another use case for zmstream is lidless (https://github.com/eastein/lidless).

# Camera / Source Compatibility

Known to work:

* ZoneMinder 1.22.x, 1.24.x
* Rosewill RXS-3211
* ABS MegaCam ABS-4210

# zmstream.Server

The zmstream.Server class transmits motion jpeg video.  You must create sockets and pass them to the server class, and then run the class. Regulary calling .send(img) on the server instance transmits your frames.  For convenience, 

# opencv pickup from raspberry pi hardware

http://www.techradar.com/news/computing-components/peripherals/how-to-install-the-raspberry-pi-camera-module-1172034

