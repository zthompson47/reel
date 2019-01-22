"""Command line interface for tapedeck."""
import trio
import trio_click as click

import reel


@click.command()
@click.option('-v', '--version', is_flag=True,
              help='Print the version number and exit.')
async def main(**kwargs: str) -> None:
    """Run reel from the command line."""
    await trio.sleep(0.1)
    if kwargs['version']:
        click.echo(reel.__version__)

if __name__ == '__main__':
    trio.run(main())
