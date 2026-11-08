"""Pixel comparison for identical Nick fixtures. The replay disclosure is excluded.

Current application data/copy differ intentionally; this isolates preservation of
the visual implementation and self-hosted font metrics without fictional claims.
"""
from pathlib import Path
import json
import numpy as np
from PIL import Image

root=Path('docs/screenshots/comparison')
report=[]
for baseline in sorted(root.glob('*-baseline.png')):
    replay=baseline.with_name(baseline.name.replace('-baseline.png','-replay.png'))
    a=np.asarray(Image.open(baseline).convert('RGB'))
    b=np.asarray(Image.open(replay).convert('RGB'))
    # Fixed fictional-replay disclosure at the bottom is the sole intentional
    # addition in this route. Nothing in the current application is hidden.
    a,b=a[:-30],b[:-30]
    delta=np.abs(a.astype(int)-b.astype(int))
    fraction=float(np.mean(np.max(delta,axis=2)>16))
    report.append({'baseline':baseline.name,'replay':replay.name,'excluded_bottom_pixels':30,
        'fraction_pixels_delta_gt_16':round(fraction,6),'mean_channel_delta':round(float(delta.mean()),6),
        'passed':fraction < .005})
result={'method':'Identical fixture data, theme, viewport and 1.8-second animation settling; bottom 30px replay disclosure excluded.',
    'comparisons':report,'passed':bool(report) and all(x['passed'] for x in report)}
(root/'results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['passed'] else 1)
