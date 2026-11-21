"""Shared validation and bounded raster allocation (metres throughout)."""
import argparse
import math
from PIL import Image

MAX_PIXELS = 24_000_000

def number(value, name, minimum=0, positive=False):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f'{name} must be a finite number')
    if not math.isfinite(value) or value < minimum or (positive and value == 0):
        raise ValueError(f'{name} must be finite and {">" if positive else ">="} {minimum}')
    return float(value)

def boolean(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be a JSON boolean')
    return value

def parse_color(value):
    if value is None:
        return None
    try:
        if isinstance(value, (tuple, list)):
            parts = list(value)
        elif isinstance(value, str) and value.startswith('#'):
            h = value[1:]
            if len(h) == 3:
                h = ''.join(c * 2 for c in h)
            if len(h) != 6:
                raise ValueError()
            parts = [int(h[i:i+2], 16) for i in (0, 2, 4)]
        elif isinstance(value, str):
            parts = [int(p.strip()) for p in value.split(',')]
        else:
            raise ValueError()
        if len(parts) != 3 or any(type(p) is not int or not 0 <= p <= 255 for p in parts):
            raise ValueError()
        return tuple(parts)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError(f'Invalid RGB color: {value!r}') from None

def check_size(size):
    w, h = size
    if w < 1 or h < 1 or w * h > MAX_PIXELS:
        raise ValueError(f'Raster {w}x{h} exceeds {MAX_PIXELS:,} pixel budget; reduce --scale')
    return size

def image(size, color=(0, 0, 0, 0), mode='RGBA'):
    return Image.new(mode, check_size(size), color)

def scale_value(scale):
    return number(scale, 'scale', positive=True)
