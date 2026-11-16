"""Add real PowerPoint motion to a pptxgenjs deck.

Reads object names written by deck6.js:
  "!!name"         left as is: PowerPoint's Morph transition matches these across slides
  "aN|kind|name"   entrance animation in stagger group N (kind: rise, zoom, wipe, wipeup, fade)

Writes, per slide: a Morph transition (fade fallback for PowerPoint older than 2019) and one
<p:timing> tree where every animated object starts by itself after the transition, group by group.
Usage: python animate.py in.pptx out.pptx
"""
import re
import sys
import zipfile

STEP_MS = 140      # delay between stagger groups
MORPH_MS = 1100

NAME = re.compile(r'<p:cNvPr id="(\d+)" name="a(\d+)\|(\w+)\|([^"]*)"')


def transition(first: bool) -> str:
    if first:
        return '<p:transition spd="slow"><p:fade/></p:transition>'
    return (
        '<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
        '<mc:Choice xmlns:p159="http://schemas.microsoft.com/office/powerpoint/2015/09/main" Requires="p159">'
        f'<p:transition xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" spd="slow" p14:dur="{MORPH_MS}">'
        '<p159:morph option="byObject"/></p:transition></mc:Choice>'
        '<mc:Fallback><p:transition spd="slow"><p:fade/></p:transition></mc:Fallback>'
        '</mc:AlternateContent>'
    )


class Ids:
    def __init__(self, start: int) -> None:
        self.n = start

    def next(self) -> int:
        self.n += 1
        return self.n


def tgt(spid: str) -> str:
    return f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>'


def show(spid: str, ids: Ids) -> str:
    return (f'<p:set><p:cBhvr><p:cTn id="{ids.next()}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
            f'{tgt(spid)}<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>'
            '<p:to><p:strVal val="visible"/></p:to></p:set>')


def fade(spid: str, ids: Ids, dur: int, flt: str = 'fade') -> str:
    return (f'<p:animEffect transition="in" filter="{flt}"><p:cBhvr><p:cTn id="{ids.next()}" dur="{dur}"/>{tgt(spid)}</p:cBhvr></p:animEffect>')


def anim(spid: str, ids: Ids, attr: str, start: str, dur: int, start_is_num: bool = False) -> str:
    v0 = f'<p:fltVal val="{start}"/>' if start_is_num else f'<p:strVal val="{start}"/>'
    return (f'<p:anim calcmode="lin" valueType="num"><p:cBhvr><p:cTn id="{ids.next()}" dur="{dur}" decel="100000" fill="hold"/>{tgt(spid)}'
            f'<p:attrNameLst><p:attrName>{attr}</p:attrName></p:attrNameLst></p:cBhvr><p:tavLst>'
            f'<p:tav tm="0"><p:val>{v0}</p:val></p:tav><p:tav tm="100000"><p:val><p:strVal val="#{attr}"/></p:val></p:tav></p:tavLst></p:anim>')


def effect(spid: str, kind: str, delay: int, first: bool, ids: Ids) -> str:
    node = 'afterEffect' if first else 'withEffect'
    if kind == 'zoom':
        preset, sub = 53, 16
        body = show(spid, ids) + anim(spid, ids, 'ppt_w', '0', 550, True) + anim(spid, ids, 'ppt_h', '0', 550, True) + fade(spid, ids, 550)
    elif kind == 'wipe':
        preset, sub = 22, 8
        body = show(spid, ids) + fade(spid, ids, 700, 'wipe(left)')
    elif kind == 'wipeup':
        preset, sub = 22, 4
        body = show(spid, ids) + fade(spid, ids, 900, 'wipe(down)')
    elif kind == 'fade':
        preset, sub = 10, 0
        body = show(spid, ids) + fade(spid, ids, 600)
    else:  # rise: fade in while floating up
        preset, sub = 42, 0
        body = (show(spid, ids) + fade(spid, ids, 650) + anim(spid, ids, 'ppt_x', '#ppt_x', 650)
                + anim(spid, ids, 'ppt_y', '#ppt_y+.07', 650))
    head = ids.next()
    return (f'<p:par><p:cTn id="{head}" presetID="{preset}" presetClass="entr" presetSubtype="{sub}" fill="hold" nodeType="{node}">'
            f'<p:stCondLst><p:cond delay="{delay}"/></p:stCondLst><p:childTnLst>{body}</p:childTnLst></p:cTn></p:par>')


def timing(objs: list[tuple[str, int, str]]) -> str:
    if not objs:
        return ''
    ids = Ids(4)
    g0 = min(g for _, g, _ in objs)
    parts = []
    for i, (spid, g, kind) in enumerate(sorted(objs, key=lambda o: o[1])):
        parts.append(effect(spid, kind, (g - g0) * STEP_MS, i == 0, ids))
    return (
        '<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
        '<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
        '<p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/>'
        '<p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond></p:stCondLst><p:childTnLst>'
        '<p:par><p:cTn id="4" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
        + ''.join(parts) +
        '</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn>'
        '<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
        '<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>'
        '</p:seq></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>'
    )


def dedupe_ids(xml: str) -> str:
    """pptxgenjs can give a table and a text box the same shape id; PowerPoint then offers to repair the file."""
    pat = re.compile(r'<p:cNvPr id="(\d+)"')
    seen, used = set(), {int(i) for i in pat.findall(xml)}
    nxt = max(used) + 1

    def fix(m):
        nonlocal nxt
        i = int(m.group(1))
        if i not in seen:
            seen.add(i)
            return m.group(0)
        new, nxt = nxt, nxt + 1
        seen.add(new)
        return f'<p:cNvPr id="{new}"'
    return pat.sub(fix, xml)


def process(xml: str, first: bool) -> tuple[str, int]:
    xml = dedupe_ids(xml)
    objs = [(m.group(1), int(m.group(2)), m.group(3)) for m in NAME.finditer(xml)]
    xml = NAME.sub(lambda m: f'<p:cNvPr id="{m.group(1)}" name="{m.group(4)}"', xml)
    tail = '</p:clrMapOvr>'
    assert xml.count(tail) == 1, 'unexpected slide layout'
    return xml.replace(tail, tail + transition(first) + timing(objs)), len(objs)


def main(src: str, dst: str) -> None:
    zin = zipfile.ZipFile(src)
    slides = sorted((n for n in zin.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)), key=lambda n: int(re.findall(r'\d+', n)[0]))
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.is_dir():
                continue
            data = zin.read(item.filename)
            if item.filename in slides:
                xml, n = process(data.decode('utf-8'), item.filename == slides[0])
                print(f'{item.filename}: {n} animated objects')
                data = xml.encode('utf-8')
            zout.writestr(item, data)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
