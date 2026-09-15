"""Compatibility entry point for field-level sample evaluation."""
import argparse
import runpy
import sys
from pathlib import Path


def main(argv=None):
    code_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description='Evaluate a prediction CSV against public samples')
    parser.add_argument('predictions', type=Path)
    parser.add_argument('--dataset', type=Path, default=code_dir.parent / 'dataset')
    args = parser.parse_args(argv)
    sys.path.insert(0, str(code_dir))
    sys.argv = [str(code_dir / 'main.py'), '--dataset', str(args.dataset),
                'evaluate', str(args.predictions)]
    runpy.run_path(str(code_dir / 'main.py'), run_name='__main__')


if __name__ == '__main__':
    main()
