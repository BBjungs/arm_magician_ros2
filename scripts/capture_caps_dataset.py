#!/usr/bin/env python3
"""Capture unmodified JPEG snapshots for the cap training dataset."""

import argparse
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import cv2
import numpy as np


def image_fingerprint(image: np.ndarray) -> np.ndarray:
    """Return a 64-bit difference hash used only to reject near duplicates."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    return (small[:, 1:] > small[:, :-1]).reshape(-1)


def hamming_distance(first: np.ndarray, second: np.ndarray) -> int:
    return int(np.count_nonzero(first != second))


def fetch_jpeg(url: str, timeout: float) -> tuple[bytes, np.ndarray]:
    request = Request(url, headers={'Accept': 'image/jpeg'})
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_type()
        payload = response.read()
    image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('snapshot response is not a decodable image')
    if content_type not in {'image/jpeg', 'image/jpg', 'application/octet-stream'}:
        raise ValueError(f'unexpected Content-Type: {content_type}')
    return payload, image


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8080/api/snapshot')
    parser.add_argument('--output', default='datasets/caps/raw')
    parser.add_argument('--interval', type=float, default=1.0)
    parser.add_argument('--count', type=int, default=200)
    parser.add_argument('--prefix', default='caps')
    parser.add_argument('--timeout', type=float, default=3.0)
    parser.add_argument(
        '--max-attempts',
        type=int,
        default=0,
        help='Stop after this many requests; 0 means count * 20.',
    )
    parser.add_argument(
        '--duplicate-distance',
        type=int,
        default=2,
        help='Reject frames whose 64-bit difference hash is this close to a saved frame.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.interval < 0 or args.count < 1 or args.timeout <= 0:
        raise SystemExit('interval must be >= 0; count and timeout must be > 0')
    if not 0 <= args.duplicate_distance <= 64:
        raise SystemExit('duplicate-distance must be within 0..64')
    max_attempts = args.max_attempts or args.count * 20
    if max_attempts < args.count:
        raise SystemExit('max-attempts must be 0 or at least count')

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    fingerprints: list[np.ndarray] = []
    exact_hashes: set[str] = set()
    saved = 0
    attempts = 0
    duplicate_count = 0

    print(f'Capture source: {args.url}')
    print(f'Output: {output.resolve()}')
    try:
        while saved < args.count and attempts < max_attempts:
            attempts += 1
            started = time.monotonic()
            try:
                payload, image = fetch_jpeg(args.url, args.timeout)
            except (HTTPError, URLError, OSError, ValueError) as exc:
                print(f'[{attempts}] ERROR: {exc}')
            else:
                digest = hashlib.sha256(payload).hexdigest()
                fingerprint = image_fingerprint(image)
                near_duplicate = any(
                    hamming_distance(fingerprint, previous) <= args.duplicate_distance
                    for previous in fingerprints[-100:]
                )
                if digest in exact_hashes or near_duplicate:
                    duplicate_count += 1
                    print(f'[{attempts}] duplicate skipped ({duplicate_count} total)')
                else:
                    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
                    destination = output / f'{args.prefix}_{stamp}_{saved + 1:05d}.jpg'
                    destination.write_bytes(payload)
                    fingerprints.append(fingerprint)
                    exact_hashes.add(digest)
                    saved += 1
                    height, width = image.shape[:2]
                    print(f'[{attempts}] saved {saved}/{args.count}: {destination} ({width}x{height})')

            remaining = args.interval - (time.monotonic() - started)
            if saved < args.count and remaining > 0:
                time.sleep(remaining)
    except KeyboardInterrupt:
        print('\nCapture stopped by user.')

    print(
        f'Captured: {saved}; duplicates skipped: {duplicate_count}; '
        f'attempts: {attempts}/{max_attempts}'
    )
    return 0 if saved == args.count else 130


if __name__ == '__main__':
    raise SystemExit(main())
