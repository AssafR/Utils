from pathlib import Path

import click

@click.command()
@click.option('--dirname', required=True, type=str)
def read_mp3(**kwargs):
    dirname = kwargs['dirname']
    dirpath = Path(dirname)

if __name__ == "__main__":
    read_mp3()