"""Receipt-time decisions over the original forecast window, with explicit age."""
import math
import numpy as np

HORIZONS=(1,2,5,10,15,30)
ACTIONS=(('Monitor',0,0.,0.),('Restrict',2,.45,.1),('Block',5,.8,.5),('Isolate',1,.95,2.))


def onset_losses(risk,age_seconds=0.):
    risk=np.asarray(risk,dtype=float)
    if risk.shape!=(6,) or not np.isfinite(risk).all() or (risk<0).any() or (risk>1).any() or (np.diff(risk)<0).any():
        raise ValueError('A coherent six-horizon forecast is required')
    if not math.isfinite(age_seconds) or age_seconds<0:raise ValueError('Forecast age must be finite and nonnegative')
    # Linear interpolation is an explicit decision-model assumption, not an
    # additional calibrated forecast horizon. The original window end is fixed.
    clock=np.array((0,*HORIZONS));cdf=np.r_[0.,risk];age=age_seconds/60
    return np.array([disruption+20*(risk[-1]-.8*effect*max(0.,risk[-1]-np.interp(age+delay,clock,cdf)))
                     for _,delay,effect,disruption in ACTIONS])
