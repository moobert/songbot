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
logger = logging.getLogger('songbot')

class SongBot(irc.IRCClient):
    
    @property
    def nickname(self):
        return self.factory.nickname

    def signedOn(self):
        logger.info('Signed on')
        self.join(self.factory.channel)

    def joined(self, channel):
        logger.info('Joined channel: %s' %  channel)
        self.factory.client = self

class SongBotFactory(protocol.ClientFactory):
    protocol = SongBot
    client   = None

    def __init__(self, channel, nickname):
        self.channel  = channel
        self.nickname = nickname

    def clientConnectionLost(self, connector, reason):
        exit()

    def clientConnectionFailed(self, connector, reason):
        logger.error('Could not connect: %s' % str(reason))
        exit()

    def sendSong(self, name):
        if self.client is not None:
            self.client.me(self.channel, str(name))

class Rhythmbox:
    lastSent = None

    def __init__(self, irc):
        self.irc  = irc
        session   = dbus.SessionBus()

        player = session.get_object('org.gnome.Rhythmbox', '/org/gnome/Rhythmbox/Player')
        self.rhythmPlayer = dbus.Interface(player, 'org.gnome.Rhythmbox.Player')

        shell = session.get_object('org.gnome.Rhythmbox', '/org/gnome/Rhythmbox/Shell')
        self.rhythmShell = dbus.Interface(shell, 'org.gnome.Rhythmbox.Shell')

        session.add_signal_receiver(self.songChange, dbus_interface='org.gnome.Rhythmbox.Player', signal_name='playingUriChanged')

    def songChange(self, *args, **kwargs):
        try:
            uri = self.rhythmPlayer.getPlayingUri()
            details = self.rhythmShell.getSongProperties(uri)
           
            if self.rateCheck():
                song = '%s - %s' % (details['artist'], details['title'])
                song = ' '.join(song.split())
            
                logger.info('/me is now playing: %s' % song)
                self.irc.sendSong('is now playing: 3%s' % song)
        except Exception, e:
            logger.error('Could not access Rhythmbox closing')
            exit()

    def rateCheck(self):
        check = False
        now = datetime.datetime.today()
        if self.lastSent is None:
            check = True

        if not check:
            ago = now - datetime.timedelta(minutes=5)
            if self.lastSent < ago:
                check = True

        if check is True:
            self.lastSent = now

        return check

def initializeLogging(options):
    logger = logging.getLogger('songbot')
    handler = logging.StreamHandler()

    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    logger.setLevel(logging.ERROR)
    if options.verbose:
        logger.setLevel(logging.DEBUG)

    return logger

def exit():
    reactor.callLater(1, reactor.stop)	

def main():
    from optparse import OptionParser

    usage = 'usage: %prog [options] network port channel nick'
    parser = OptionParser(usage)
    parser.add_option('-v', '--verbose', action='store_true', dest='verbose')

    (options, args) = parser.parse_args()
    if len(args) is not 4:
        parser.error("incorrect number of arguments")

    if not args[2].startswith('#'):
        args[2] = '#%s' % args[2]

    logger = initializeLogging(options)

    irc = SongBotFactory(args[2], args[3])
    player = Rhythmbox(irc)
    reactor.connectTCP(args[0], int(args[1]), irc)

    reactor.run()

if __name__ == '__main__':
    main()
