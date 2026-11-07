#!/usr/bin/env python3
"""Compare equally registered native game and atlas crops without resampling."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def compare(reference, candidate, destination, tolerance=0, mask=None):
    reference, candidate, destination = map(Path, (reference, candidate, destination))
    a = np.asarray(Image.open(reference).convert('RGB'))
    b = np.asarray(Image.open(candidate).convert('RGB'))
    if a.shape != b.shape:
        raise ValueError(f'Native crop dimensions differ: {a.shape} versus {b.shape}')
    valid = np.ones(a.shape[:2], dtype=bool)
    if mask:
        m = np.asarray(Image.open(mask).convert('L'))
        if m.shape != valid.shape:
            raise ValueError('Mask dimensions differ from native crops')
        valid = m > 0
    if not valid.any():
        raise ValueError('No pixels selected')
    delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
    peak = delta.max(axis=2)
    mismatch = (peak > tolerance) & valid
    ys, xs = np.where(mismatch)
    destination.mkdir(parents=True, exist_ok=True)
    # Bright red marks mismatches; excluded pixels are blue. No smoothing.
    heat = np.zeros_like(a)
    heat[..., 0] = np.where(mismatch, np.maximum(32, peak), 0)
    heat[~valid] = (0, 0, 128)
    Image.fromarray(heat).save(destination / 'difference.png')
    Image.fromarray(np.concatenate((a, b, heat), axis=1)).save(destination / 'comparison.png')
    report = {
        'reference': str(reference.resolve()),
        'candidate': str(candidate.resolve()),
        'reference_sha256': hashlib.sha256(reference.read_bytes()).hexdigest(),
        'candidate_sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
        'size': [a.shape[1], a.shape[0]],
        'mask': str(Path(mask).resolve()) if mask else None,
        'tolerance_per_channel': tolerance,
        'compared_pixels': int(valid.sum()),
        'exact_pixel_fraction': float((peak[valid] == 0).mean()),
        'within_tolerance_fraction': float((peak[valid] <= tolerance).mean()),
        'mean_absolute_channel_error': float(delta[valid].mean()),
        'maximum_channel_error': int(peak[valid].max()),
        'mismatch_bounds': [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if len(xs) else None,
        'resampled': False,
    }
    (destination / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('reference', type=Path)
    p.add_argument('candidate', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--tolerance', type=int, choices=range(256), default=0)
    p.add_argument('--mask', type=Path, help='Explicit white pixels to include; recorded in report')
    a = p.parse_args()
    print(json.dumps(compare(a.reference, a.candidate, a.out, a.tolerance, a.mask), indent=2))


if __name__ == '__main__':
    main()
