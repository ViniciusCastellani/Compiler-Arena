"""ZIP reproduzível sem ambientes, caches, .git ou o próprio ZIP."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo
ROOT=Path(__file__).resolve().parent.parent
EXCLUDE={'.git','.venv','venv','__pycache__','.pytest_cache','.mypy_cache','.agents','.codex','.aws'}


def main():
    target=ROOT/'entrega_compiler_arena.zip'
    files=[]
    for path in ROOT.rglob('*'):
        rel=path.relative_to(ROOT)
        if path.is_file() and not (set(rel.parts)&EXCLUDE) and path.suffix not in ('.zip','.pyc'):
            files.append((rel,path))
    with ZipFile(target,'w',ZIP_DEFLATED,compresslevel=9) as z:
        for rel,path in sorted(files):
            info=ZipInfo('compiler_arena_entrega/'+rel.as_posix(),date_time=(2026,10,19,12,0,0))
            info.compress_type=ZIP_DEFLATED; info.external_attr=0o644<<16
            z.writestr(info,path.read_bytes())
    print(f'{target.name}: {len(files)} arquivos, {target.stat().st_size} bytes')


if __name__=='__main__': main()
