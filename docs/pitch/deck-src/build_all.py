import os, process2 as P
M = '../native/m/'
have = lambda n: os.path.exists(f'{n}.jpg') and open(f'{n}.jpg', 'rb').read(2) == b'\xff\xd8'
src = lambda want, *fallback: next(n for n in (want, *fallback) if have(n))
plan = {   # slide photo -> (source, fallbacks, flip, left, right)
    'aral':    (('aral', 'dry'),            False, 215, 120),
    'canal':   (('canal',),                 False, 215, 95),
    'green':   (('green', 'canal'),         True,  215, 150),
    'fields':  (('fields',),                False, 215, 140),
    'steppe':  (('steppe', 'fields'),       True,  205, 165),
    'fields2': (('fields2', 'fields'),      False, 215, 100),
    'dry':     (('dry',),                   False, 215, 140),
}
for name, (cands, flip, l, r) in plan.items():
    s = src(*cands)
    P.full(f'{s}.jpg', f'{M}full-{name}.jpg', blur=1.6, left=l, right=r, flip=flip)
    print(f'{name:8s} <- {s}')
P.split(f"{src('dry')}.jpg", f"{src('green', 'canal')}.jpg", f'{M}full-split.jpg')
print('split    <-', src('dry'), '|', src('green', 'canal'))
