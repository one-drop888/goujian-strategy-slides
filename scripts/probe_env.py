#!/usr/bin/env python3
"""Static interpreter probes used by Doctor and Bootstrap.

Modes:
  python-version   print MAJOR.MINOR.PATCH of the running interpreter
  pillow-version   print the installed Pillow distribution version
  venv-prefix      print JSON with sys.prefix and sys.base_prefix
"""
import importlib.metadata, json, sys

MODES=('python-version','pillow-version','venv-prefix')

def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv)
    if len(args)!=1 or args[0] not in MODES:
        print('usage: probe_env.py {python-version|pillow-version|venv-prefix}',file=sys.stderr)
        return 2
    mode=args[0]
    if mode=='python-version':
        print('.'.join(str(part) for part in sys.version_info[:3]))
        return 0
    if mode=='pillow-version':
        try:
            print(importlib.metadata.version('Pillow'))
            return 0
        except importlib.metadata.PackageNotFoundError:
            print('Pillow is not installed',file=sys.stderr)
            return 1
        except Exception as error:
            print(str(error),file=sys.stderr)
            return 1
    print(json.dumps({'prefix':sys.prefix,'base':sys.base_prefix}))
    return 0

if __name__=='__main__':raise SystemExit(main())
