#!/usr/bin/python

"""
IRC bot to display song changes made in Rhythmbox using twisted and dbus.

Updates are limited to every 5 minutes, to cut down on spam.

@author Peter Measham (http://github.com/moobert/)
@license MIT
"""

import dbus, dbus.glib

from twisted.internet import gtk2reactor
gtk2reactor.install()
from twisted.internet import reactor

from twisted.words.protocols import irc
from twisted.internet import protocol

import datetime
import logging

log = logging.getLogger('songbot')

class SongBot(irc.IRCClient):
    """
    Client class to handle joining the correct channel
    """
   
    @property
    def nickname(self):
        """
        Get nick from factory
        """
        return self.factory.nickname

    def signedOn(self):
        """
        Join channel when signed on to irc
        """
        log.info('Signed on')
        self.join(self.factory.channel)

    def joined(self, channel):
        """
        When in channel update factory class with intance of client
        """
        log.info('Joined channel: %s' %  channel)
        self.factory.client = self

class SongBotFactory(protocol.ClientFactory):
    """
    Handle client and send song infomation
    """
    protocol = SongBot
    client   = None

    def __init__(self, channel, nickname):
        self.channel  = channel
        self.nickname = nickname

    def clientConnectionLost(self, connector, reason):
        """
        Shutdown on connection close
        """
        shutdown()

    def clientConnectionFailed(self, connector, reason):
        """
        Display connection error and close
        """
        log.error('Could not connect: %s' % str(reason))
        shutdown()

    def sendSong(self, name):
        """
        Push song information to irc client
        """
        if self.client is not None:
            self.client.me(self.channel, str(name))

class Rhythmbox:
    """
    Loads dbus interfaces and signals to irc
    """
    sent = None

    def __init__(self, factory):
        self.irc  = factory
        session   = dbus.SessionBus()

        oplayer = session.get_object('org.gnome.Rhythmbox', \
            '/org/gnome/Rhythmbox/Player')
        
        self.player = dbus.Interface(oplayer, 'org.gnome.Rhythmbox.Player')

        oshell = session.get_object('org.gnome.Rhythmbox', \
            '/org/gnome/Rhythmbox/Shell')
        
        self.shell = dbus.Interface(oshell, 'org.gnome.Rhythmbox.Shell')

        session.add_signal_receiver(self.songChange, \
            dbus_interface='org.gnome.Rhythmbox.Player', \
            signal_name='playingUriChanged')

    def songChange(self, *args, **kwargs):
        """
        callback function for file uri updates in rhythmbox
        """
        try:
            uri = self.player.getPlayingUri()
            details = self.shell.getSongProperties(uri)
           
            if self.rateCheck():
                song = '%s - %s' % (details['artist'], details['title'])
                song = ' '.join(song.split())
            
                log.info('/me is now playing: %s' % song)
                self.irc.sendSong('is now playing: 3%s' % song)
        except Exception, exc:
            log.error('Could not access Rhythmbox closing: %s' % str(exc))
            shutdown()

    def rateCheck(self):
        """
        Check its been 5 minutes since last irc update
        """
        check = False
        now = datetime.datetime.today()
        if self.sent is None:
            check = True

        if not check:
            ago = now - datetime.timedelta(minutes=5)
            if self.sent < ago:
                check = True

        if check is True:
            self.sent = now

        return check

def setup_logging(options):
    """
    Setup log to output to terminal
    """
    logger = logging.getLogger('songbot')
    handler = logging.StreamHandler()

    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    logger.setLevel(logging.ERROR)
    if options.verbose:
        logger.setLevel(logging.DEBUG)

    return logger

def shutdown():
    """
    Add deferred to shutdown the twisted event loop
    """
    reactor.callLater(1, reactor.stop)	

def main():
    """
    Parse options and setup twisted
    """
    from optparse import OptionParser

    usage = 'usage: %prog [options] network port channel nick'
    parser = OptionParser(usage)
    parser.add_option('-v', '--verbose', action='store_true', dest='verbose')

    (options, args) = parser.parse_args()
    if len(args) != 4:
        parser.error("incorrect number of arguments")

    if not args[2].startswith('#'):
        args[2] = '#%s' % args[2]

    setup_logging(options)

    song = SongBotFactory(args[2], args[3])
    Rhythmbox(song)
    reactor.connectTCP(args[0], int(args[1]), song)

    reactor.run()

if __name__ == '__main__':
    main()
