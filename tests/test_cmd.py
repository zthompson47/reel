# pylint: disable=W0611, W0621
"""Test the pre-configured commands."""
import os

from trio import Path

from reel import cmd
from reel.cmd import (
    ffmpeg, sox, tapedeck
)
from reel.io import NullDestStream, StreamIO

from tests.fixtures import (
    audio_dir, env_audio_dest, music_dir,
    RADIO, SONG
)

BYTE_LIMIT = 1000000


async def test_audio_dir(audio_dir):
    """Get test audio files."""
    assert audio_dir.exists()
    # assert (audio_dir / 'output.wav').exists()


async def test_import():
    """Make sure the module is imported."""
    assert cmd
    assert cmd.SRC_SILENCE


async def test_play_music(capsys, env_audio_dest):
    """Play a few seconds of music."""
    async with env_audio_dest as out:
        async with await ffmpeg.stream(SONG) as src:
            count = 0
            chunk = await src.receive_some(4096)
            while chunk:
                await out.send_all(chunk)
                if count > 200:
                    break
                chunk = await src.receive_some(4096)
                count += 1
                assert chunk
        async with await ffmpeg.stream(RADIO) as src:
            count = 0
            chunk = await src.receive_some(4096)
            while chunk:
                await out.send_all(chunk)
                if count > 200:
                    break
                chunk = await src.receive_some(4096)
                count += 1
                assert chunk

    # put these somewhere better - "check output doesn't bork ipython"
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == ''


async def test_play_music_better_way(env_audio_dest):
    """Play a few seconds of music with less code."""
    async with env_audio_dest as out:
        async with await ffmpeg.stream(SONG) as src:
            await StreamIO(src, out).flow(byte_limit=1000000)
        async with await ffmpeg.stream(RADIO) as src:
            await StreamIO(src, out).flow(byte_limit=1000000)


async def test_tapedeck(music_dir):
    """Run tapedeck.cli through reel.cmd."""
    results = await tapedeck.search(music_dir)
    assert len(results) == 3
