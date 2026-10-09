#!/usr/bin/env python3
"""Offline unit tests for tools/footage.py (rights classification, file choice, provenance, credits). Run by tests/shorts.js."""
import os, sys, json, tempfile, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('footage', os.path.join(HERE, '..', 'tools', 'footage.py'))
F = importlib.util.module_from_spec(spec); spec.loader.exec_module(F)

def eq(a, b, msg=''): assert a == b, f'{msg}: expected {b!r}, got {a!r}'

# ---- rights: licence URLs -------------------------------------------------------------------------------------------
eq(F.classify_license_url('http://creativecommons.org/publicdomain/zero/1.0/'), F.PD, 'cc0')
eq(F.classify_license_url('https://creativecommons.org/publicdomain/mark/1.0/'), F.PD, 'pdm')
eq(F.classify_license_url('http://creativecommons.org/licenses/publicdomain/'), F.PD, 'legacy pd')
eq(F.classify_license_url('http://creativecommons.org/licenses/by/3.0/'), F.BY, 'by')
for bad in ('by-nc/2.5', 'by-nd/1.0', 'by-sa/4.0', 'by-nc-sa/2.5', 'by-nc-nd/4.0'):
    eq(F.classify_license_url('http://creativecommons.org/licenses/' + bad + '/'), F.RESTRICTED, bad)
eq(F.classify_license_url(None), F.UNKNOWN, 'none'); eq(F.classify_license_url(''), F.UNKNOWN, 'empty')

# ---- rights: archive.org items --------------------------------------------------------------------------------------
cls, why = F.classify_ia({'identifier': 'gov.doe.0800001', 'licenseurl': 'http://creativecommons.org/publicdomain/zero/1.0/', 'collection': ['FedFlix', 'usgovfilms'], 'title': 'Nuclear Test Film - Trinity Shot'})
eq(cls, F.PD, 'doe cc0')
cls, why = F.classify_ia({'identifier': 'gov.archives.arc.2765', 'collection': ['FedFlix', 'usgovfilms'], 'title': 'ARMY AIR FORCES--PACIFIC'})
eq(cls, F.PD, 'us gov film without licenseurl'); assert 'government' in why.lower(), why
cls, why = F.classify_ia({'identifier': 'random-upload', 'title': 'Some film', 'collection': ['opensource_movies']})
eq(cls, F.UNKNOWN, 'no licence info')
cls, why = F.classify_ia({'identifier': 'x', 'licenseurl': 'http://creativecommons.org/licenses/by-nc-nd/4.0/', 'title': 'x'})
eq(cls, F.RESTRICTED, 'nc-nd')
# a derivative (colourised / restored / upscaled) of public-domain footage carries its own claims -> must be flagged for a human
cls, why = F.classify_ia({'identifier': 'c', 'licenseurl': 'https://creativecommons.org/publicdomain/mark/1.0/', 'title': 'The First Atomic Explosion: Trinity Test in HD Color', 'description': 'Incredible colorized footage'})
eq(cls, F.CHECK, 'colourised derivative'); assert 'derivative' in why.lower(), why
assert F.is_derivative('Restored 4K upscale'); assert F.is_derivative('AI enhanced'); assert not F.is_derivative('Nuclear Test Film - Trinity Shot')
assert not F.is_derivative('Main Street, 1925'), 'a street named "Main" must not trip the AI detector'

# ---- rights: Wikimedia Commons --------------------------------------------------------------------------------------
em = lambda short, copyrighted='False': {'LicenseShortName': {'value': short}, 'UsageTerms': {'value': short}, 'Copyrighted': {'value': copyrighted}}
eq(F.classify_commons(em('Public domain'))[0], F.PD, 'commons pd')
eq(F.classify_commons(em('CC0'))[0], F.PD, 'commons cc0')
eq(F.classify_commons(em('CC BY 4.0', 'True'))[0], F.BY, 'commons by')
eq(F.classify_commons(em('CC BY-SA 4.0', 'True'))[0], F.RESTRICTED, 'commons by-sa')
eq(F.classify_commons(em('GFDL', 'True'))[0], F.RESTRICTED, 'commons gfdl')
eq(F.classify_commons({})[0], F.UNKNOWN, 'commons unknown')

# ---- choosing a file in an archive.org item -------------------------------------------------------------------------
files = [{'name': 'a.gif', 'format': 'Animated GIF', 'size': '300000'},
         {'name': 'a.mpeg', 'format': 'MPEG2', 'size': str(862 * 10**6), 'width': '640', 'height': '480'},
         {'name': 'a.ogv', 'format': 'Ogg Video', 'size': str(60 * 10**6), 'width': '400', 'height': '304'},
         {'name': 'a_512kb.mp4', 'format': '512Kb MPEG4', 'size': str(51 * 10**6), 'width': '320', 'height': '240'},
         {'name': 'a_meta.xml', 'format': 'Metadata', 'size': '10'}]
eq(F.pick_ia_file(files, max_mb=100)['name'], 'a.ogv', 'largest picture that fits the cap')
eq(F.pick_ia_file(files, max_mb=2000)['name'], 'a.mpeg', 'best picture when the cap allows')
eq(F.pick_ia_file(files, max_mb=100, prefer='a_512kb.mp4')['name'], 'a_512kb.mp4', 'explicit file wins')
assert F.pick_ia_file([{'name': 'x.txt', 'format': 'Text'}], 100) is None, 'no video -> None'

# ---- provenance + credits -------------------------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, 'provenance.json')
    F.record(p, {'key': 'ia:gov.doe.0800001', 'title': 'Nuclear Test Film - Trinity Shot', 'creator': 'Department of Energy', 'year': '1945', 'rights_class': F.PD, 'license': 'CC0 1.0', 'landing': 'https://archive.org/details/gov.doe.0800001', 'file': 'raw/a.mpeg', 'sha256': 'ab' * 32})
    F.record(p, {'key': 'commons:File:X.jpg', 'title': 'X', 'creator': 'Jane Doe', 'rights_class': F.BY, 'license': 'CC BY 4.0', 'landing': 'https://commons.wikimedia.org/wiki/File:X.jpg', 'file': 'raw/x.jpg'})
    F.record(p, {'key': 'ia:gov.doe.0800001', 'title': 'Nuclear Test Film - Trinity Shot', 'file': 'raw/b.mpeg'})          # same key -> updated, not duplicated
    data = json.load(open(p)); eq(len(data), 2, 'dedupe by key'); eq([e for e in data if e['key'].startswith('ia:')][0]['file'], 'raw/b.mpeg', 'update merges')
    assert [e for e in data if e['key'].startswith('ia:')][0]['creator'] == 'Department of Energy', 'update keeps earlier fields'
    md = F.credits_markdown(data)
    assert 'Nuclear Test Film - Trinity Shot' in md and 'archive.org/details/gov.doe.0800001' in md, md
    assert 'Jane Doe' in md and 'CC BY 4.0' in md, 'attribution licences must name the author and licence'
    blocked = F.problems(data + [{'key': 'ia:bad', 'title': 'Bad', 'rights_class': F.RESTRICTED, 'license': 'by-nc-nd'}, {'key': 'ia:huh', 'title': 'Huh', 'rights_class': F.UNKNOWN}])
    eq(sorted(b[0] for b in blocked), ['ia:bad', 'ia:huh'], 'restricted and unknown items are reported before publishing')
print('ok')
