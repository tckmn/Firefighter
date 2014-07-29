#!/usr/bin/python

# The plan:
# 1. Send WebSocket request for every site in the network. TODO: maybe exclude per-site metas, but would be difficult
# 2. Wait for WebSocket responses, and then, when a response is received...
# 3. Check to see whether it was a new post or an edit. If a new post, add to the queue.
#
# The queue handling code should:
# 1. Invoke the API and grab the text.
# 2. Do some magic and generate a spamminess index.
# 3. If this spamminess index is over a certain threshold, report as possible spam. If it's over a huge threshold, SPAM SPAM SPAM
# 4. Save to a file for future machine learning data.
# 5. Observe the API's backoff and wait, if necessary.
# 6. Check to see if there are still items in the queue. If so, rinse and repeat. Else, wait for new items.


# SE interfacing
import websocket # websockets
import urllib2   # API
import gzip      # API returns gzipped data
import StringIO  # see above ^
import time      # API possibly returns backoff
import json      # websockets and API return json

# Spamminess detection
import Queue # for the spam detecty queue thingy
import re    # and now I have two problems

# Chat
from ChatExchange.chatexchange.client import * # thanks to @ManishEarth
import getpass                                 # for getting passwords, of course

# Etc.
import logging        # exactly what it says on the tin
from os import system # playing notification sound

class Firefighter:
	@staticmethod
	def init(username, password):
		Firefighter.site_ids_hsh = {}
		with open('sites.txt', 'r') as f:
			for line in f:
				Firefighter.site_ids_hsh[int(line.split()[0])] = line.split()[1]

		Firefighter.queue = Queue.Queue()
		Firefighter.queue_being_handled = False

		Firefighter.chat = Client('stackexchange.com')
		Firefighter.debug('Logging in to chat...')
		Firefighter.chat.login(username, password)
		Firefighter.debug('Logged in to chat')
		Firefighter.room = Firefighter.chat.get_room('11540')

	@staticmethod
	def debug(s):
		print '[debug] %s' % s

	@staticmethod
	def on_open(ws):
		Firefighter.debug('WebSocket opened')
		# Hinduism, the currently most recent site (Jul 26 2014), is #567, so this should give us plenty of breathing room
		for i in range(600):
			ws.send('%i-home-active' % i)
		Firefighter.debug('Sent {i}-home-active data')

	@staticmethod
	def on_message(ws, msg):
		data = json.loads(json.loads(msg)['data'])
		search_str = 'class="started-link">'
		action = data['body'][data['body'].index(search_str) + len(search_str):]
		siteid = Firefighter.site_ids_hsh[data['siteid']]
		postid = int(data['id'])

		if action.startswith('asked'):
			Firefighter.queue.put('http://api.stackexchange.com/2.2/questions/%i?order=desc&site=%s&filter=!Fcb8.OvNI39f8LgxZws3-f1LPA' % (postid, siteid))
			Firefighter.handle_queue()
		elif action.startswith('answered'):
			Firefighter.queue.put('http://api.stackexchange.com/2.2/questions/%i/answers?pagesize=1&order=desc&sort=creation&site=%s&filter=!1zNUM5.sthPdOGr(ULDb2' % (postid, siteid))
			Firefighter.handle_queue()

	@staticmethod
	def on_close(ws):
		Firefighter.debug('WebSocket closed')

	@staticmethod
	def on_error(ws, error):
		Firefighter.debug('WebSocket error: %s' % error)

	@staticmethod
	def handle_queue():
		if Firefighter.queue_being_handled: return
		Firefighter.queue_being_handled = True
		
		while not Firefighter.queue.empty():
			data = None
			qitem = Firefighter.queue.get()
			for _ in xrange(6): # wait a maximum of 1 minute before giving up
				req = urllib2.urlopen(qitem + '&key=Oij)9kWgsRogxL0fBwKdCw((')
				data = json.loads(gzip.GzipFile(fileobj = StringIO.StringIO(req.read())).read().decode('utf-8'))
				req.close()
				if len(data['items']) > 0: break
				time.sleep(10) # wait for 10 seconds before trying again (http://shouldiblamecaching.com)
				# (10 also happens to be the maximum backoff time, so don't need to worry about handling those)
			else:
				break

			postdata = data['items'][0]

			postdata['body'] = postdata.pop('title', '') + '\n' + postdata.pop('body_markdown').replace('\r\n', '\n')
			postdata['rep'] = postdata.pop('owner')['reputation']
			postdata['link'] = postdata.pop('link') # (for clarity)

			Firefighter.debug(json.dumps(postdata, indent = 4, sort_keys = True))
			reason = Firefighter.fight_fire(postdata)
			if reason:
				Firefighter.room.send_message(reason + ': ' + postdata['link'])
				Firefighter.debug('Extinguished (%s)' % reason)
			#if postdata['rep'] < 101: system('paplay /usr/share/sounds/ubuntu/stereo/dialog-information.ogg')

			if 'backoff' in data:
				Firefighter.debug('Backoff: ' + str(data['backoff']))
				time.sleep(data['backoff'])

		Firefighter.queue_being_handled = False

	@staticmethod
	def fight_fire(postdata):
		if re.compile("(?i)\\b(baba(ji)?|nike|[Vv]ashikaran|[Ss]umer|[Kk]olcak|porn|[Mm]olvi|[Jj]udi [Bb]ola|ituBola.com|[Ll]ost [Ll]over)\\b").search(postdata['body']):
			return 'Bad keyword'
		if re.compile("\\+\\d{10}|\\+?\\d{2}[\\s\\-]?\\d{8,1o}").search(postdata['body']):
			return 'Phone number'
		if re.compile("(?i)\\b([Nn]igga|[Nn]igger|niga|[Aa]sshole|crap|fag|[Ff]uck(ing?)?|idiot|[Ss]hit|[Ww]hore)s?\\b").search(postdata['body']):
			return 'Offensive'
		if re.compile("(?:\n(?=.*[A-Z])[^a-z]{15,}\n)|(?:^(?=.*[A-Z])[^a-z]*\n)").search(postdata['body']):
			return 'Allcaps title / long allcaps line'
		if postdata['rep'] < 6 and re.compile("http://").search(postdata['body']):
			return 'New user, link in post'
		return None


if __name__ == '__main__':
	logging.basicConfig()

	username = raw_input('Username: ')
	password = getpass.getpass('Password: ')

	Firefighter.init(username, password)
	ws = websocket.WebSocketApp('wss://qa.sockets.stackexchange.com/',
		on_open = Firefighter.on_open,
		on_message = Firefighter.on_message,
		on_close = Firefighter.on_close,
		on_error = Firefighter.on_error)
	ws.run_forever()
