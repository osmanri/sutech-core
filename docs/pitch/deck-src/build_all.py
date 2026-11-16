import os, process2 as P
M = '../native/m/'
have = lambda n: os.path.exists(f'{n}.jpg') and open(f'{n}.jpg', 'rb').read(2) == b'\xff\xd8'
src = lambda want, *fallback: next(n for n in (want, *fallback) if have(n))
plan = {   # slide photo -> (candidates, flip, overlay left, overlay right, colour kept, overlay top, overlay bottom)
    'aral':    (('aral', 'dry'),            False, 60, 60, 0.8, 30, 200),
    'canal':   (('canal',),                 False, 185, 60, 0.7, 0, 0),
    'green':   (('green', 'canal'),         False, 190, 90, 0.7, 0, 0),
    'fields':  (('fields',),                False, 185, 140, 0.7, 0, 0),
    'steppe':  (('steppe', 'fields'),       False, 150, 150, 0.7, 120, 175),
    'fields2': (('fields2', 'fields'),      False, 185, 60, 0.7, 0, 0),
    'dry':     (('dry',),                   False, 185, 90, 0.6, 0, 0),
}
for name, (cands, flip, l, r, keep, tp, bt) in plan.items():
    s = src(*cands)
    P.full(f'{s}.jpg', f'{M}full-{name}.jpg', blur=1.2, left=l, right=r, keep=keep, flip=flip, top=tp, bottom=bt)
    print(f'{name:8s} <- {s}')
P.split(f"{src('dry')}.jpg", f"{src('green', 'canal')}.jpg", f'{M}full-split.jpg')
print('split    <-', src('dry'), '|', src('green', 'canal'))
