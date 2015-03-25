anycast-dns-monitor
===

[![Build Status](https://secure.travis-ci.org/spoofedpacket/anycast-dns-monitor.png)](http://travis-ci.org/spoofedpacket/anycast-dns-monitor)

## Description

anycast-dns-monitor checks nameserver health by  sending queries to nominated 
unicast addresses. The daemon can automatically bring down anycast loopback 
interfaces if errors are encountered. This effectively removes a machine from 
an anycast pool as BGP will automatically withdraw all routes.

debian package build files are in debian/

## Requirements

* Python
* Python modules: dnspython, argparse, daemon, IPy, lockfile

