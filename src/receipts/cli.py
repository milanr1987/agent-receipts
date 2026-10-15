import argparse
from . import __version__


def main(argv=None):
    parser = argparse.ArgumentParser(prog='receipts', description='Lokalni audit dokaza: audit, check-diff, eval, hook.')
    parser.add_argument('--version', action='version', version=__version__)
    parser.parse_args(argv)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
