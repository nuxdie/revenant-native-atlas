"""Prepare verified map files and a byte-exact tile pack for public hosting."""
import hashlib
import json
from pathlib import Path

from atlas import dump


def digest(path):
    with path.open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def prepare(root=Path('native-output'),out=Path('runtime/publication')):
    out.mkdir(parents=True,exist_ok=True);uploads=[];levels=[]
    def upload(key,path,sha=None):
        uploads.append(dict(key=key,path=str(path.resolve()),size=path.stat().st_size,sha256=sha or digest(path)))
    for manifest in sorted(root.glob('level-*/manifest.json'),key=lambda p:int(p.parent.name.split('-')[1])):
        directory=manifest.parent;vp=directory/'validation.json'
        if not vp.exists():continue
        m=json.loads(manifest.read_text());v=json.loads(vp.read_text());png=directory/'full-resolution.png'
        if v.get('acceptance')=='review_required'or v.get('full_png_crc')!='verified'or not png.exists()or'full_png_sha256'not in v:continue
        level=m['level'];sha=v['full_png_sha256'];revision=f'r-{level}-{sha[:20]}'
        tif=directory/'full-resolution.tif';tv=directory/'tiff-validation.json';tiff=None
        if tif.exists()and tv.exists():
            tiff=json.loads(tv.read_text())
            if tiff['source_png_sha256']!=sha or tiff['bytes']!=tif.stat().st_size:tiff=None
        target=out/f'level-{level}';target.mkdir(exist_ok=True);index_path=target/'tiles.json';pack=target/'tiles.pack'
        old=json.loads(index_path.read_text())if index_path.exists()else{}
        if old.get('source_png_sha256')!=sha or not pack.exists():
            index={};offset=0
            with pack.with_suffix('.pack.tmp').open('wb')as stream:
                for tx,ty in sorted(map(tuple,m['tiles'])):
                    path=directory/'tiles'/f'{tx}_{ty}.png';data=path.read_bytes();stream.write(data)
                    index[f'{tx}_{ty}']=dict(offset=offset,length=len(data),sha256=hashlib.sha256(data).hexdigest());offset+=len(data)
            pack.with_suffix('.pack.tmp').replace(pack)
            dump(index_path,dict(pack='tiles.pack',source_png_sha256=sha,tiles=index))
        public_validation=dict(level=level,names=m['names'],size=[m['width'],m['height']],bounds=m['bounds'],
            renderer='Original Revenant executable, Wine/D7VK; black-shadow RGB565 to ARGB1555 format correction',
            geyser_base_blending=v.get('geyser_blending_validation',{}),
            game_time='08:07',base_module_editor_state=True,gameplay_ai_paused=True,
            source_captures=v['captures'],capture_hashes=v['capture_hashes'],owned_pixels_verified=v['export_pixels_exactly_equal_to_raw_captures'],
            nonblack_pixels_have_native_source=v.get('all_nonblack_export_pixels_have_native_source'),
            missing_captures=len(v['missing_captures']),nonblack_unplanned_boundaries=v['nonblack_unplanned_boundaries'],
            stitching=v.get('actual_stitched_edges'),full_png_crc=v['full_png_crc'],full_png_samples_equal_tiles=v['full_png_samples_equal_tiles'],
            full_png_sha256=sha,full_png_bytes=png.stat().st_size,
            limitation='Successive animation frames; local native-pixel/source validation does not promise identity to every gameplay state or GPU.')
        validation_path=target/'validation.json';dump(validation_path,public_validation)
        prefix=f'releases/{revision}/level-{level}/'
        for name,path,known in [('tiles.pack',pack,None),('tiles.json',index_path,None),('overview.jpg',directory/'overview.jpg',None),
                                ('full-resolution.png',png,sha),('validation.json',validation_path,None)]:upload(prefix+name,path,known)
        if tiff:upload(prefix+'full-resolution.tif',tif,tiff['sha256'])
        levels.append(dict(level=level,names=m['names'],width=m['width'],height=m['height'],bounds=m['bounds'],tile_size=m['tile_size'],
            tiles=m['tiles'],statistics=m['statistics'],provider='original_game',revision=revision,content_revision=sha[:16],
            png_bytes=png.stat().st_size,sha256=sha,tiff_bytes=tiff['bytes']if tiff else None,tiff_sha256=tiff['sha256']if tiff else None,
            static_boundary_pixels_requiring_review=v['actual_stitched_edges']['unmeasured_edges_requiring_review'],
            animated_boundary_pixels=v['actual_stitched_edges']['measured_animation_edges']))
    catalog=out/'catalog.json';dump(catalog,dict(revision='native-atlas',expected_levels=33,levels=levels))
    upload('catalog.json',catalog)
    result=dict(levels=len(levels),expected_levels=33,uploads=uploads);dump(out/'upload-manifest.json',result)
    print(f'{len(levels)}/33 verified maps prepared; {len(uploads)} objects; {sum(u["size"]for u in uploads):,} bytes',flush=True)
    return result


if __name__=='__main__':prepare()
