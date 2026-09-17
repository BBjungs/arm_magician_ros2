from dobot_calibration.baseline_admission import AuthoritativeBaselineAdmissionGate, REQUIRED
def ok(**overrides):
 d={k:True for k in REQUIRED}; d.update(overrides); return d
def test_window_and_reset_are_monotonic():
 g=AuthoritativeBaselineAdmissionGate(); g.update(ok(),100); assert not g.evaluate_for_baseline(109.9)['accepted']; assert g.evaluate_for_baseline(110)['accepted']; g.update(ok(DEPTH_STABLE=False),111); assert g.status(111)['stable_for_s']==0; g.update(ok(),112); assert not g.evaluate_for_baseline(121.9)['accepted']; assert g.evaluate_for_baseline(122)['accepted']
def test_each_required_gate_rejects():
 for key, enum in REQUIRED.items():
  g=AuthoritativeBaselineAdmissionGate(); g.update(ok(**{key:False}),1); assert g.evaluate_for_baseline(20)['exact_gate']==enum

def test_reset_reports_exact_gate_and_time():
 g=AuthoritativeBaselineAdmissionGate(); g.update(ok(), 1); g.update(ok(DEPTH_FRESH=False), 2)
 status=g.status(2)
 assert status['last_reset_gate']=='DEPTH_STALE'
 assert status['last_reset_time']==2
 assert status['reset_count']==1
