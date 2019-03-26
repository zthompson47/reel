"""Spool class."""
import logging
import os
import shlex
import subprocess

import trio

from ._transport import Transport

LOG = logging.getLogger(__name__)


class Spool(trio.abc.AsyncResource):
    """A shell command."""

    def __init__(self, command, xenv=None, xflags=None):
        """Queue a subprocess."""
        if isinstance(command, list):
            self._command = command
        else:
            self._command = shlex.split(command)
        self._env = os.environ.copy()
        self._limit = None
        self._proc = None
        self._status = None
        self._stderr = None
        self._stdout = None
        if xflags:
            for flag in xflags:
                # Accept objects like Path that look like a str
                self._command.append(str(flag))
        if xenv:
            for key, val in xenv.items():
                self._env[key] = val
        # super().__init__()
        LOG.debug(self.__repr__())

    def __str__(self):
        """Print the command."""
        return ' '.join(self._command)

    def __repr__(self):
        """Represent the command."""
        return f"Spool('{str(self)}')"

    def __or__(self, next_one):
        """Create a server with the first two spools."""
        return Transport(self, next_one)

    def __rshift__(self, next_one):
        """Create a transport with the first two spools."""
        return Transport(self, next_one)

    async def __aenter__(self):
        """Start an async context."""
        return Transport(self)

    async def aclose(self):
        """Clean up."""
        if self.proc:
            await self.proc.aclose()

    @property
    def pid(self):
        """Return the process pid."""
        if self._proc:
            return self._proc.pid
        return None

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
        """Return whatever the process sent to stdout."""
        # if self._stdout:
        #    return self._stdout.decode('utf-8')
        # return None
        return self._stdout

    def limit(self, byte_limit=65536):
        """Configure this `spool` to limit output to `byte_limit` bytes."""
        self._limit = byte_limit
        return self

    async def run(self, message=b''):
        """Send stdin to process and return stdout."""
        async with trio.open_nursery() as nursery:
            self._proc = trio.Process(
                self._command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._env
            )
            nursery.start_soon(self._handle_stdin, message)
            nursery.start_soon(self._handle_stdout, self._limit)
            nursery.start_soon(self._handle_stderr)
        await self._proc.wait()
        if self._stdout:
            return self._stdout.decode('utf-8', errors='ignore').strip()
        return None

    async def _handle_stderr(self):
        """Read stderr."""
        while True:
            try:
                chunk = await self._proc.stderr.receive_some(16384)
            except trio.ClosedResourceError:
                LOG.debug('Stderr closed', exc_info=True)
                break
            else:
                if not chunk:
                    break
                if not self._stderr:
                    self._stderr = b''
                self._stderr += chunk

    async def _handle_stdout(self, limit=None):
        """Read stdout."""
        max_rcv = limit or 16834

        while True:
            try:
                chunk = await self._proc.stdout.receive_some(max_rcv)
                LOG.debug(chunk)
            except trio.ClosedResourceError:
                LOG.debug('Stdout closed', exc_info=True)
                break
            else:
                if not chunk:
                    break
                if not self._stdout:
                    self._stdout = b''
                self._stdout += chunk
                max_rcv -= len(chunk)
                if max_rcv == 0:
                    await self._proc.stderr.aclose()
                    await self._proc.stdout.aclose()
                    break

    async def _handle_stdin(self, message):
        """Receive stdin."""
        if isinstance(message, str):
            _msg = message.encode('utf-8')
        elif message is None:
            _msg = b''
        else:
            _msg = message
        async with self.proc.stdin as stdin:
            await stdin.send_all(_msg)

    def handle_stderr(self, nursery):
        """Read stderr, called as a task in a nursery."""
        nursery.start_soon(self._handle_stderr)

    def handle_stdout(self, nursery):
        """Read stdout, called as a task in a nursery."""
        nursery.start_soon(self._handle_stdout)

    def handle_stdin(self, nursery, message):
        """Feed stdin, called as a task in a nursery."""
        nursery.start_soon(self._handle_stdin, message)

    def start(self, nursery, stdin=None):
        """Initialize the subprocess and run the command."""
        LOG.debug('-- << SPOOL start about to run proc %s', self)
        self._proc = trio.Process(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._env
        )
        LOG.debug('-- >> SPOOL start ljjjj to run proc %s', self._proc)
        if stdin:
            self.handle_stdin(nursery, stdin)
        self.handle_stderr(nursery)

    async def stop(self):
        """Stop it."""
        await self.aclose()

    async def receive_from_channel(self, channel):
        """Send output of channel to stdin."""
        try:
            async with self._proc.stdin:
                async for chunk in channel:
                    await self._proc.stdin.send_all(chunk)
        except trio.ClosedResourceError as error:
            LOG.debug(error)
        except AttributeError:
            LOG.debug('<><><><><><><><><><><: %s %s', self, self._proc)

    async def send_to_channel(self, channel):
        """Stream stdout to `channel` and close both sides."""
        async with channel:
            async with self.proc:
                await self.send_no_close(channel)

    async def send_all(self, chunk):
        """Send a chunk of data to stdin."""
        await self._proc.stdin.send_all(chunk)

    async def receive_some(self, max_bytes):
        """Return a chunk of data from the output of this stream."""
        try:
            return await self._proc.stdout.receive_some(max_bytes)
        except trio.ClosedResourceError as error:
            LOG.debug(error)

    async def send_no_close(self, channel):
        """Stream stdout to `channel` without closing either side."""
        buffsize = 16384
        bytes_received = 0

        # Don't receive more than the bytes limit.
        if self._limit and self._limit < 16384:
            buffsize = self._limit

        # <=~ Receive data.
        chunk = await self.receive_some(buffsize)
        while chunk:

            # ~=> Send data.
            await channel.send(chunk)

            # Check for byte limit.
            bytes_received += len(chunk)
            if self._limit and bytes_received > self._limit:
                break

            # Cap buffer at limit.
            buffsize = 16384
            if self._limit and self._limit < 16384:
                buffsize = self._limit

            # <=~ Receive data.
            chunk = await self.receive_some(buffsize)
