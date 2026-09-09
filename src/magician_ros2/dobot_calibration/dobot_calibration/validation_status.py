"""Full live acceptance is distinct from a mathematical hand-eye PASS."""

REQUIRED_LIVE_CHECKS = (
    'hardware', 'table_stability', 'observability', 'independent_verification',
    'repeatability', 'reload_verification', 'real_object_validation',
)


def live_acceptance_error(report):
    if report.get('validation_source') != 'live':
        return 'LIVE_VALIDATION_NOT_COMPLETED: mathematical verification alone does not authorize picking'
    checks = report.get('live_checks', {})
    missing = [name for name in REQUIRED_LIVE_CHECKS
               if not isinstance(checks.get(name), dict) or checks[name].get('result') != 'PASS']
    if not isinstance(checks.get('health_check'), dict) or checks['health_check'].get('status') != 'READY':
        missing.append('health_check')
    if missing:
        return 'LIVE_VALIDATION_INCOMPLETE: ' + ', '.join(missing)
    return ''
