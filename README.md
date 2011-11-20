<A name="toc1-0" title="Purpose" />
# Purpose

ZMStream is a library for creating creating an iterable object for image frames from a ZoneMinder stream, other motion jpeg stream, or anything FFMPEG can handle.  Frames are emitted as `PIL.Image.Image` objects.

<A name="toc1-5" title="Dependencies" />
# Dependencies

* PIL
* pyffmpeg (http://code.google.com/p/pyffmpeg/) if `Mode.FFMPEG` is used.

<A name="toc1-11" title="Platforms" />
# Platforms

ZMStream has been tested to work on Ubuntu 10.04 and Debian Squeeze, using CPython 2.6.x and 2.7.x.  Centos 6 is known to work as well.

<A name="toc1-16" title="Examples" />
# Examples

* Please see test.py for an example.
* Another use case for zmstream is lidless (https://github.com/eastein/lidless).

<A name="toc1-22" title="Camera / Source Compatibility" />
# Camera / Source Compatibility

Known to work:

* ZoneMinder 1.22.x, 1.24.x
* Rosewill RXS-3211
* ABS MegaCam ABS-4210
