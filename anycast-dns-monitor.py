#!/usr/bin/env python

'''
anycast-dns-monitor.py:

 Checks resolver health by sending DNS queries to the unicast addresses
 and downs the anycast interface if errors are encountered. Both IPv4 and
 IPv6 address families are checked.

'''

__author__ = "Robert Gallagher"
__version__ = "1.0"
__email__ = "rob@spoofedpacket.net"

##############################################################################################
# System modules.
##############################################################################################
import atexit
import errno
import logging
import logging.handlers
import os
import string
import subprocess
import sys
import time

##############################################################################################
# 3rd-party modules.
##############################################################################################
import argparse
import ConfigParser
import daemon
import lockfile.pidlockfile
import dns.resolver
import IPy

##############################################################################################
# Custom exception classes.
##############################################################################################
class admException(Exception):
    '''
    Base exception class for anycast-dns-monitor (adm) exceptions.
    '''
    pass

class admResolverFailedException(admException):
    '''
    A given resolver has completely failed all checks.
    '''
    pass

##############################################################################################
# Main class.
##############################################################################################
class anycastDNSMonitor:
      @staticmethod
      def checkResolver(resolver, primary_test_fqdn, secondary_test_fqdn):
          default_resolver = str(resolver.nameservers[0])
          try:
              answers = resolver.query(primary_test_fqdn, 'A')
          except dns.exception.DNSException:
		 # Attempt one more query for a different host before taking any further action.
                 try:
                     answers = resolver.query(secondary_test_fqdn, 'A')
                     # Something is broken, bring down anycast interfaces.
                 except dns.exception.DNSException, e:
                     raise admResolverFailedException("Resolver %s has failed all checks: %s, %s (%s)" % (default_resolver, primary_test_fqdn, secondary_test_fqdn, type(e)))
                     # Otherwise something is wrong with name resolution for our primary test host.
                 else:
                     return True
          else:
               return True

      @staticmethod
      def lowerAnycastInterfaces(anycast_interfaces):
          for interface in anycast_interfaces:
              try:
                  subprocess.check_call(['/sbin/ifdown', interface]) 
                  log.info('Lowering anycast interface %s.' % interface)
              except subprocess.CalledProcessError, e:
                  log.exception('%s %s' % (type(e), e.output))

      @staticmethod
      def raiseAnycastInterfaces(anycast_interfaces):
          for interface in anycast_interfaces:
              try:
                  subprocess.check_call(['/sbin/ifup', interface]) 
                  log.info('Raising anycast interface %s.' % interface)
              except subprocess.CalledProcessError, e:
                  log.exception('%s %s' % (type(e), e.output))

      @staticmethod
      def ipReachable(ip):
          ip = IPy.IP(ip)
          try:
              if ip.version() == 4: 
                 subprocess.check_call(['/bin/ping', '-c', '1', '-t', '1', str(ip)])
              else:        
                 subprocess.check_call(['/bin/ping6', '-c', '1', '-t', '1', str(ip)])
          except subprocess.CalledProcessError:
                 return False
          else:
                 return True

      @staticmethod
      def cleanup(stop_files):
          for stop_file in stop_files:
              if os.path.exists(stop_file):
                 try:
                     os.remove(stop_file)
                 except OSError, e:
                     log.exception('%s %s' % (type(e), e.args))
              else:
                   continue
          log.info("Stopping monitor.")

##############################################################################################
# Default invocation.
##############################################################################################
if __name__ == "__main__":
   # Get pid file and config file paths from the command line.
   argparser = argparse.ArgumentParser()
   argparser.add_argument('-p', action='store', dest='PID', help='PID file location.')
   argparser.add_argument('-c', action='store', dest='CFG', help='Config file location.')
   arguments  = argparser.parse_args()
   PID = arguments.PID
   CFG = arguments.CFG

   # Ensure PID and CFG are set, if the user hasn't supplied them.
   if PID == None:
      PID = "/var/run/anycast-dns-monitor.pid"
   if CFG == None:
      CFG = "/usr/local/etc/anycast-dns-monitor.cfg"

   # Grab lock and open pid file
   pidlock = lockfile.pidlockfile.TimeoutPIDLockFile(PID, 10) 

   # Start as a daemon - this is something akin to a chroot.
   with daemon.DaemonContext(pidfile=pidlock):
        # Configure logging to syslog.
        log = logging.getLogger('anycast-dns-monitor')
        # TODO: Configure logging levels properly (eg: print exceptions only at debug level).
        log.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(name)s: %(message)s')
        handler = logging.handlers.SysLogHandler(address = '/dev/log')
        handler.setFormatter(formatter)
        log.addHandler(handler)
   
        log.info('Starting Monitor. Reading config from %s.' % CFG)
   
        # Pull in config file, requires absolute path (daemon can't read CWD).
        config = ConfigParser.RawConfigParser()
        config.read(CFG)
        # Read our variables from the config file.
        try:
            unicast_v4 = config.get('Main', 'unicast_v4')
            unicast_v6 = config.get('Main', 'unicast_v6')
            anycast_v4_if = config.get('Main','anycast_v4_if')
            anycast_v6_if = config.get('Main','anycast_v6_if')
            v4_stop_file = config.get('Main', 'v4_stop_file')
            v6_stop_file = config.get('Main', 'v6_stop_file')
            primary_test_fqdn = config.get('Tests', 'primary_test_fqdn')
            secondary_test_fqdn = config.get('Tests', 'secondary_test_fqdn')
            query_lifetime = config.getfloat('Tests', 'query_lifetime')
            test_interval = config.getfloat('Tests', 'test_interval')
        except ConfigParser.Error, e:
            log.exception('%s %s' % (type(e), e.args))
            log.error('Error reading configuration file %s.' % CFG)
            sys.exit()
        else:   
            v4_resolver = dns.resolver.Resolver()
            v4_resolver.nameservers = [unicast_v4]
            v6_resolver = dns.resolver.Resolver()
            v6_resolver.nameservers = [unicast_v6]
            # Set the default lifetime for queries sent to both resolvers (in seconds).
            v4_resolver.lifetime = query_lifetime
            v6_resolver.lifetime = query_lifetime
   
        # Unpack comma-seperated list of anycast interfaces from our config file.
        # TODO: Strip spaces.
        anycast_v4_if = string.split(anycast_v4_if, ",")
        anycast_v6_if = string.split(anycast_v6_if, ",")
   
        for ip in [unicast_v4,unicast_v6]:
            if not anycastDNSMonitor.ipReachable(ip):
               log.error('Unicast address %s is unreachable or not locally configured.' % ip)
               sys.exit()
            else:
               log.info('Checking unicast address %s' % ip)
               continue

        # Housekeeping - remove any lingering stop files upon exit.
        atexit.register(anycastDNSMonitor.cleanup, [v4_stop_file,v6_stop_file])
   
        # Main daemon loop.
        while True:
              for resolver in [v4_resolver,v6_resolver]:
                  ip = IPy.IP(str(resolver.nameservers[0]))
                  if ip.version() == 4:
                      stop_file = v4_stop_file
                      anycast_if = anycast_v4_if
                  else:
                      stop_file = v6_stop_file
                      anycast_if = anycast_v6_if
   
                  try:
                      anycastDNSMonitor.checkResolver(resolver, primary_test_fqdn, secondary_test_fqdn)
                  except admResolverFailedException, e:
                      if os.path.exists(stop_file):
                         pass 
                      else:
                         log.exception('%s' % type(e))
                         anycastDNSMonitor.lowerAnycastInterfaces(anycast_if) 
                         try:
                            open(stop_file, 'w')
                         except IOError, e:
                            log.exception('%s %s' % (type(e), e.args))
                  else:
                      if os.path.exists(stop_file):
                         log.info('Resolver %s has recovered.' % str(resolver.nameservers[0]))
                         anycastDNSMonitor.raiseAnycastInterfaces(anycast_if) 
                         try:
                            os.remove(stop_file)
                         except OSError, e:
                            log.exception('%s %s' % (type(e), e.args))
                      else:
                         pass
              time.sleep(test_interval)
   
