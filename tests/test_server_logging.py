"""Sanitize event-loop failures; only a native Proactor close race is quiet."""
import asyncio.proactor_events
import io
import logging
import sys
import types
import unittest
from unittest.mock import Mock

from media_clarity.__main__ import SafeServerLog


class ServerLoggingTests(unittest.TestCase):
    def emitted(self, info, name='asyncio'):
        stream=io.StringIO();handler=logging.StreamHandler(stream)
        handler.addFilter(SafeServerLog())
        record=logging.LogRecord(name,logging.ERROR,'private/path.py',7,
            'private-url %s',('private-query',),info,sinfo='private-stack')
        handler.handle(record)
        return stream.getvalue()

    def test_unexpected_loop_and_protocol_errors_are_visible_but_sanitized(self):
        for error in (RuntimeError('private-runtime'),ConnectionResetError('private-reset')):
            try:raise error
            except Exception:info=sys.exc_info()
            self.assertEqual(self.emitted(info),'Local server operation failed; check the in-app diagnostic.\n')
        self.assertEqual(self.emitted(None),'Local server operation failed; check the in-app diagnostic.\n')

    def test_native_proactor_close_reset_is_quiet_without_hiding_callback_errors(self):
        # Exercise the real stdlib close callback. Linux's mock contributes Python
        # frames; native Windows socket.shutdown contributes no such frames.
        transport=types.SimpleNamespace(_called_connection_lost=False,_protocol=Mock(),
            _sock=Mock(),_server=None)
        transport._sock.shutdown.side_effect=ConnectionResetError('private-socket')
        try:asyncio.proactor_events._ProactorBasePipeTransport._call_connection_lost(transport,None)
        except ConnectionResetError:info=sys.exc_info()
        trace=info[2]
        while trace.tb_frame.f_code.co_name!='_call_connection_lost':trace=trace.tb_next
        native=types.TracebackType(None,trace.tb_frame,trace.tb_lasti,trace.tb_lineno)
        self.assertEqual(self.emitted((info[0],info[1],native)),'')
        self.assertIn('Local server operation failed',self.emitted((info[0],info[1],native),'uvicorn.error'))
        # A Python callback's own reset has a deeper origin and must be reported.
        self.assertIn('Local server operation failed',self.emitted(info))
        self.assertIn('Local server operation failed',self.emitted((RuntimeError,RuntimeError('private'),native)))
