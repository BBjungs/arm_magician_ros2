"""Match registered stream metadata by integer ROS header time."""

def header_ns(header):
    return header.stamp.sec * 1_000_000_000 + header.stamp.nanosec


def calibration_signature(message):
    return (message.header.frame_id, message.width, message.height, tuple(message.k),
            tuple(message.d), tuple(message.r), tuple(message.p), message.distortion_model)


# One observed ~100 ms arrival gap plus one 25 ms evaluation period.
INFO_DELIVERY_WAIT = .125


def select_frame(rgb, depth, info, now, freshness, skew, invalid_info=False, *,
                 retain_fresh_triplet=False, trace=None):
    """Queues carry (header nanoseconds, local capture seconds, ...) tuples."""
    limit = round(skew * 1e9)
    fresh_rgb = sorted((r for r in rgb if 0 <= now-r[1] <= freshness),
                       key=lambda r: r[0], reverse=True)
    if not fresh_rgb:
        return None, None, None, 'stale_rgb' if rgb else 'missing_rgb'
    fallback = None
    for r in fresh_rgb:
        matches = []
        reason = ''
        for kind, samples in (('depth', depth), ('info', info)):
            near = min((s for s in samples if 0 <= now-s[1] <= freshness),
                       key=lambda s: abs(s[0]-r[0]), default=None)
            matches.append(near)
            if not reason:
                if near is None:
                    reason = ('invalid_calibration' if kind == 'info' and invalid_info else
                              f'stale_{kind}' if samples else f'missing_{kind}')
                elif abs(near[0]-r[0]) > limit:
                    reason = f'{kind}_skew'
        result = (r, *matches, reason)
        if trace is not None:
            trace(r, *matches, reason)
        if not reason:
            return result
        # Allow newly arrived unmatched frames time for their partners. Older
        # previews may be emitted without consuming newer pending RGB frames.
        waiting_info = reason in ('missing_info', 'stale_info', 'info_skew')
        if retain_fresh_triplet and reason != 'invalid_calibration':
            continue
        delivery_wait = INFO_DELIVERY_WAIT if waiting_info else skew
        if now-r[2] >= delivery_wait:
            fallback = result
    return fallback or (None, None, None, 'waiting')


def append_sample(kind, queue, value, pending_rgb, limit_ns):
    """Return the locally evicted header, or None. Preserve pending calibration matches."""
    # Repeated calibration metadata for one capture needs only one history slot.
    if kind == 'info' and any(sample[0] == value[0] for sample in queue):
        return None
    dropped = None
    if len(queue) == queue.maxlen:
        if kind == 'info':
            samples = [*queue, value]
            protected = set()
            for rgb in pending_rgb:
                best = min(range(len(samples)), key=lambda n: abs(samples[n][0]-rgb[0]))
                if abs(samples[best][0]-rgb[0]) <= limit_ns:
                    protected.add(best)
            # The calibration history has more slots than the pending RGB queue.
            # Arrival order can differ from header order. Keep recent unclaimed
            # calibration for RGB frames whose callback has not run yet.
            index = min((n for n in range(len(samples)) if n not in protected),
                        key=lambda n: samples[n][0])
            dropped = samples.pop(index)[0]
            queue.clear()
            queue.extend(samples)
            return dropped
        dropped = queue[0][0]
    queue.append(value)
    return dropped
