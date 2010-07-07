#!/usr/bin/env python
import sys
import urllib2
import urlparse
import cookielib
import os
import readline
import atexit
import json
import optparse
import gzip
import StringIO

import configopt
from pygments import highlight
from pygments.lexers import guess_lexer
from pygments.formatters import TerminalFormatter


class Pysty:

    # -------------------------------------------------------------------------
    # Initialisation
    # -------------------------------------------------------------------------

    def __init__(self, cfg):
        self._sane_defaults()
        self._cfg = cfg
        self._cookiejar = cookielib.CookieJar()
        self._opener = \
            urllib2.build_opener(urllib2.HTTPCookieProcessor(self._cookiejar))

        self._init_headers()
        self._init_readline()

    def _init_headers(self):
        self._hdr_path = os.path.expanduser(os.path.join('~', './pysty_headers'))
        try:
            self._headers = json.load(open(self._hdr_path))
        except IOError:
            self._headers['Accept'] = 'application/json'
            self._headers['Content-Type'] = 'application/json'

    def _save_headers(self):
        json.dump(self._headers, open(self._hdr_path, 'w'))

    def _sane_defaults(self):
        self._headers = {}
        self._cookiejar = None

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _process_request(self, args):
        path, json = self._split(args)
        full_url = urlparse.urljoin(self._cfg.base_url, path)
        return full_url, json

    def _split(self, str):
        bits = str.split(' ', 1)
        first = bits[0]
        try:
            second = bits[1]
        except IndexError:
            second = None
        return first, second

    def _draw_line(self):
        try:
            _, columns = os.popen('stty size', 'r').read().split()
        except:
            columns = 80

        print '-' * int(columns)

    def _generic_request(self, args, method):
        url, json = self._process_request(args)
        self._send_request(method, url, json)

    def _send_request(self, method, url, data):
        self._draw_line()
        print '%(method)s %(url)s %(data)s' % locals()
        request = urllib2.Request(url, data=data, headers=self._headers)
        request.get_method = lambda: method

        try:
            f = self._opener.open(request)
        except urllib2.HTTPError, f:
            print f

        # Print out the HTTP response headers
        headers = f.info()
        if self._cfg.headers:
            self._draw_line()
            print(headers)

        data = f.read()

        # Decompress if needed
        if headers.get('content-encoding', None) == 'gzip':
            data = gzip.GzipFile(fileobj=StringIO.StringIO(data)).read()

        self._draw_line()
        self._pretty_print(data)

    def _pretty_print(self, code):
        lexer = guess_lexer(code)
        try:
            code = json.dumps(json.loads(code), indent=2)
        except ValueError:
            pass
        print highlight(code, lexer, TerminalFormatter())

    # -------------------------------------------------------------------------
    # Command Execution
    # -------------------------------------------------------------------------

    def _cli_execute(self, cmd):
        command, args = self._split(cmd)
        try:
            method = getattr(self, command.lower())
        except AttributeError:
            print('%(cmd)s not found' % locals())
            return

        method(args)

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------

    def header_set(self, args):
        key, value = args.split(' ')
        self._headers[key] = value
        self._save_headers()

    def header_list(self, args):
        for k, v in self._headers.items():
            print k, v

    def config_set(self, args):
        key, value = args.split(' ')
        self._cfg.set(key, value)

    def config_get(self, args):
        try:
            print getattr(self._cfg, args)
        except KeyError:
            print 'Unknown config setting'

    def server(self, args):
        self._cfg.set('base_url', args)

    def quit(self, args):
        self._cfg.save()
        sys.exit(0)

    exit = quit

    def get(self, args):
        self._generic_request(args, 'GET')

    def post(self, args):
        self._generic_request(args, 'POST')

    def put(self, args):
        self._generic_request(args, 'PUT')

    def delete(self, args):
        self._generic_request(args, 'DELETE')

    # -------------------------------------------------------------------------
    # Readline
    # -------------------------------------------------------------------------

    def _init_readline(self):

        # settings for tab completion and reverse search
        if sys.platform == 'darwin':
            readline.parse_and_bind("bind ^I rl_complete")
            readline.parse_and_bind("bind ^r em-inc-search-prev")
        else:
            readline.parse_and_bind('tab: complete')

        # completion
        readline.set_completer(self._auto_complete)

        # save/load history
        histfile = os.path.join(os.environ["HOME"], ".pysty_history")
        try:
            readline.read_history_file(histfile)
        except IOError:
            pass
        atexit.register(readline.write_history_file, histfile)

    def _auto_complete(self, text, state):
        methods = filter(lambda a: not a.startswith('_'), dir(self))
        c = 0
        for method in methods:
            if method.startswith(text):
                if state != c:
                    c += 1
                    continue
                return method

    def loop(self):
        while 1:
            if not self._cfg.base_url:
                prompt = "[no server configured]";
            else:
                prompt = self._cfg.base_url

            self._cli_execute(raw_input('%s> ' % prompt))


class Config:

    def __init__(self):
        self._opt = configopt.ConfigOpt()
        self.setup()

    def setup(self):
        self._opt.add_group('general', 'General Options')
        self._opt.add_option('-b', '--base-url', group='general',
                option='base_url', default=None,
                help='Base URL for all requests')
        self._opt.add_option('--headers', group='general',
                option='headers', default='off',
                help='Show headers. Can be on or off. e.g. --headers=on')

    def parse(self):
        self._opt()

    def save(self):
        self._opt.save()

    def set(self, key, val):
        self._opt['general'][key] = val

    def __getattr__(self, key):
        return self._opt['general'].options[key].config_value

