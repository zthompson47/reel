"""Spool class."""
from datetime import datetime
import logging
import os
import shlex
import subprocess

import trio

from . _transport import Transport

LOG = logging.getLogger(__name__)


class Spool(trio.abc.AsyncResource):
    """A command to run as an async subprocess in a ``Transport``."""

    def __init__(self, command, xenv=None, xflags=None):
        """Start a subprocess with a modified argument list and environment."""
        self._command = shlex.split(command)
        self._env = dict(os.environ)
        self._limit = None
        self._status = None
        self._stderr = None
        self._timeout = None
        if xflags:
            for flag in xflags:
                # Accept objects like Path that look like a str
                self._command.append(str(flag))
        if xenv:
            for key, val in xenv.items():
                self._env[key] = val
        LOG.debug(' '.join(self._command))

        self._proc = None

    def __repr__(self):
        """Represent prettily."""
        return f"Spool('{' '.join(self._command)}')"

    def __or__(self, the_other_one):
        """Create a `Transport` out of the first two spools in the chain."""
        return Transport(self, the_other_one)

    async def __aenter__(self):
        """Run through a tranport in an async managed context."""
        return Transport(self)

    async def aclose(self):
        """Wait for the process to end and close it."""
        await self._proc.wait()
        await self._proc.aclose()

    @property
    def proc(self):
        """Return the process."""
        return self._proc

    @property
    def returncode(self):
        """Return the exit code of the process."""
        return self._proc.returncode

    @property
    def stderr(self):
        """Return whatever the process sent to stderr."""
        if self._stderr:
            return self._stderr.decode('utf-8')
        return None

    @property
    def stdout(self):
        """Return stdout of the subprocess."""
        return self._proc.stdout

    def limit(self, byte_limit=65536):
        """Configure this `spool` to limit output to `byte_limit` bytes."""
        self._limit = byte_limit
        return self

    def timeout(self, seconds=0.47):
        """Configure this `spool` to stop after `seconds` seconds."""
        self._timeout = seconds
        return self

    async def run(self, message=None, text=True):
        """Send stdin to process and return stdout."""
        return await Transport(self).read(message, text=text)

    # ~= Transport hooks =~

    async def _handle_stderr(self):
        """Read stderr in a function so that the nursery has a function."""
        LOG.debug('()()()()()()()()()(~> IN _HANDLE_STDERR')
        while True:
            chunk = await self._proc.stderr.receive_some(16384)
            if not chunk:
                break
            if not self._stderr:
                self._stderr = b''
            self._stderr += chunk

    def handle_stderr(self, nursery):
        """Read stderr, called as a task by a Transport in a nursery."""
        LOG.debug('()()()()()()()()()(~> IN HANDLE_STDERR')
        nursery.start_soon(self._handle_stderr)

    def start_process(self, nursery):
        """Initialize the subprocess and run the command."""
        self._proc = trio.Process(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._env
        )
        LOG.debug('()()()()()()()()()(~> IN HANDLE_STDERR')
        self.handle_stderr(nursery)

    async def receive(self, channel):
        """Send the output of the receive `channel` to this spool's stdin."""
        async for chunk in channel:
            await self._proc.stdin.send_all(chunk)
        await self._proc.stdin.aclose()  # ??? unless last in chain

    async def send(self, channel):
        """Stream stdout to `channel` and close both sides."""
        LOG.debug('seinding to channel!!!')
        async with channel:
            await self.send_no_close(channel)
        await self._proc.stdout.aclose()

    async def send_no_close(self, channel):
        """Stream stdout to `channel` without closing either side."""
        buffsize = 16384
        if self._limit and self._limit < 16384:
            buffsize = self._limit
        LOG.debug('-----!!!!!!!>>>>>>>>>> %s %s', self._limit, buffsize)
        bytes_received = 0
        chunk = await self._proc.stdout.receive_some(buffsize)
        _start_time = datetime.now().microsecond
        while chunk:

            # Send data.
            await channel.send(chunk)
            bytes_received += len(chunk)

            # Check for byte limit.
            if self._limit and bytes_received > self._limit:
                break

            # Check for timeout.
            if self._timeout:
                now = datetime.now().microsecond
                if (now - _start_time) >= self._timeout * 1000:
                    break

            # Read from stdout.
            buffsize = 16384
            if self._limit and self._limit < 16384:
                buffsize = self._limit
            chunk = await self._proc.stdout.receive_some(buffsize)
