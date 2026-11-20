#!/usr/bin/env python3
"""GitHub-hosted import: verify existing release ZIPs, publish unchanged individual files."""
import hashlib, json, os, subprocess, tempfile, zipfile
from pathlib import Path, PurePosixPath
ROOT=Path.cwd()
config=json.loads((ROOT/'import-release.json').read_text())
BASE='https://github.com/sensoryapphouse/Symbol-Library/releases/download/library-2026-11-20/'
TAG='library-2026-11-20'

def git(*args):
    return subprocess.check_output(['git',*args],text=True).strip()

git('config','user.name','Sensory Library Publisher')
git('config','user.email','actions@users.noreply.github.com')
git('config','pack.threads','2')
git('config','pack.window','0')
git('config','pack.compression','1')
git('config','gc.auto','0')
if git('ls-remote','--tags','origin','refs/tags/'+TAG):
    raise SystemExit('Release tag already exists; refusing to replace verified publication')
hashes={};counts={};totalbytes=0
for asset in config['assets']:
    with tempfile.TemporaryDirectory() as temp:
        archive=Path(temp)/asset['name']
        subprocess.run(['curl','-fL','--retry','5','--retry-all-errors','--connect-timeout','30','--max-time','900',BASE+asset['name'],'-o',str(archive)],check=True)
        with archive.open('rb') as f:
            h=hashlib.file_digest(f,'sha256').hexdigest()
        assert h==asset['sha256'],'Release archive checksum mismatch: '+asset['name']
        with zipfile.ZipFile(archive) as z:
            assert len(z.infolist())==asset['files']
            for item in z.infolist():
                parts=PurePosixPath(item.filename).parts
                assert len(parts)>=3 and parts[0]=='Library' and '..' not in parts
                style=parts[1];assert style in config['groups']
                dest=PurePosixPath('library',config['groups'][style],*parts[2:])
                assert dest.suffix.lower() in ('.webp','.svg') and str(dest) not in hashes
                data=z.read(item)  # includes CRC verification
                target=ROOT/str(dest);target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(data)
                hashes[str(dest)]=hashlib.sha256(data).hexdigest()
                counts[style]=counts.get(style,0)+1;totalbytes+=len(data)
        git('add','--','library')
        if git('diff','--cached','--name-only'):
            git('commit','-m','Import verified '+asset['name']+' from Symbol-Library release')
            git('push','origin','HEAD:main')
        print(json.dumps({'archive':asset['name'],'verified_files_so_far':len(hashes)}),flush=True)
assert counts==config['counts'],(counts,config['counts'])
actual={p.as_posix() for p in Path('library').rglob('*') if p.suffix.lower() in ('.webp','.svg')}
assert actual==set(hashes),'Unexpected or missing image paths'
for file,expected in hashes.items():
    assert hashlib.sha256(Path(file).read_bytes()).hexdigest()==expected
audit={'complete':True,'counts':counts,'images':len(hashes),'image_bytes':totalbytes,
       'source_release':BASE,'all_archive_sha256_verified':True,'all_image_crcs_verified':True,
       'source_images_unchanged':True}
Path('publication.json').write_text(json.dumps(audit,indent=2)+'\n')
Path('library/SHA256.jsonl').write_text(''.join(json.dumps({'path':p,'sha256':h})+'\n' for p,h in sorted(hashes.items())))
Path('README.md').write_text('# Sensory Symbols\n\nIndividual, unchanged images from the verified [Symbol-Library release](https://github.com/sensoryapphouse/Symbol-Library/releases/tag/library-2026-11-20).\n\nCopyright and licence metadata embedded in each file are preserved. Third-party exceptions retain their own terms. See publication.json and library/SHA256.jsonl for verification.\n')
git('add','publication.json','library/SHA256.jsonl','README.md')
git('commit','-m','Verify complete symbol collection and preserve source licences')
git('tag',TAG)
git('push','--atomic','origin','HEAD:main','refs/tags/'+TAG)
print(json.dumps(audit),flush=True)
