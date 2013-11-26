anycast-dns-monitor
=============================================================================

anycast-dns-monitor checks nameserver health by  sending queries to nominated 
unicast addresses. The daemon can automatically bring down anycast loopback 
interfaces if errors are encountered. This effectively removes a machine from 
an anycast pool as BGP will automatically withdraw all routes.

Note: debian package build files in debian/

Prerequisites (python modules): dnspython, argparse, daemon, IPy, lockfile

Author: Robert Gallagher <rob@spoofedpacket.net>
