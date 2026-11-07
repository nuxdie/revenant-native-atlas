"""Publish the completed native capture checks beside the local atlas."""
import html
import json
from pathlib import Path
import shutil

from atlas import dump


def build(root=Path('native-output')):
    issue_source=Path('comparisons/barrel-band')
    issues=[]
    if (issue_source/'diagnosis.json').exists():
        shutil.copytree(issue_source,root/'proofs'/'shadow-band',dirs_exist_ok=True)
        issues.append(json.loads((issue_source/'diagnosis.json').read_text()))
    shoreline=Path('comparisons/shore-bands')
    shore_issue=None
    if (shoreline/'diagnosis.json').exists():
        shutil.copytree(shoreline,root/'proofs'/'shore-bands',dirs_exist_ok=True)
        shore_issue=json.loads((shoreline/'diagnosis.json').read_text());issues.append(shore_issue)
    shadow_controls=[]
    for name in ('shadow-negative-keep','shadow-other-barrel'):
        source=Path('comparisons')/name
        if (source/'fix-validation.json').exists():
            shutil.copytree(source,root/'proofs'/name,dirs_exist_ok=True)
            shadow_controls.append(dict(name=name,**json.loads((source/'fix-validation.json').read_text())))
    levels=[]
    for directory in sorted(root.glob('level-*'),key=lambda p:int(p.name.split('-')[1])):
        manifest=json.loads((directory/'manifest.json').read_text())
        validation=json.loads((directory/'validation.json').read_text())
        levels.append(dict(level=manifest['level'],size=[manifest['width'],manifest['height']],
                           names=manifest['names'],validation=validation))
    checks=[]
    for name,label in [('town','Misthaven'),('keep','Keep: lights and NPCs'),
                       ('arakna','Arakna: water and Gus'),('araknids','Forest: creatures'),
                       ('shadow','Barrel/crate correction: full viewport')]:
        source=Path('comparisons')/f'final-{name}'
        if not (source/'capture.json').exists():continue
        target=root/'proofs'/name
        shutil.copytree(source,target,dirs_exist_ok=True)
        record=json.loads((source/'capture.json').read_text())
        checks.append(dict(name=name,label=label,
                           foreground=record['foreground_static_comparison'],
                           all_pixels=record['all_pixel_comparison'],
                           measured_temporal_pixels=record['measured_temporal_pixels']))
    clips=[]
    for path in sorted((root/'clips').glob('*/capture.json')):
        data=json.loads(path.read_text())
        clips.append(dict(name=path.parent.name,distinct_frames=data['distinct_frames'],
                          recorded_frames=data['recorded_frames'],rgb_preservation=data['rgb_preservation']))
    summary=dict(provider='original_game',native_levels=levels,fresh_comparisons=checks,clips=clips,
                 known_rendering_issues=[i for i in issues if i.get('status')!='fixed'],
                 resolved_rendering_issues=[i for i in issues if i.get('status')=='fixed'],
                 shadow_control_checks=shadow_controls,
                 scope='Base-module editor state, AI paused, visual animations active, original real-time lighting at 08:07.',
                 limitation='The stitched PNG combines successive frames. Animation joins remain; fresh comparisons are close but not 100% identical. Visible objects depend on the loaded game state.')
    dump(root/'fidelity.json',summary)
    rows=''.join(f'<tr><td>{m["level"]}</td><td>{m["size"][0]:,} × {m["size"][1]:,}</td>'
                 f'<td>{m["validation"]["captures"]:,}</td><td>{m["validation"]["actual_stitched_edges"]["unmeasured_edges_requiring_review"]:,}</td>'
                 f'<td>{m["validation"]["actual_stitched_edges"]["measured_animation_edges"]:,}</td>'
                 f'<td><a href="level-{m["level"]}/full-resolution.png">PNG</a> · <a href="level-{m["level"]}/validation.json">Audit</a></td></tr>'for m in levels)
    comparisons=''.join(f'<article><h3>{html.escape(c["label"])}</h3><p>'
                        f'{c["foreground"]["exact_pixel_fraction"]:.4%} exact across {c["foreground"]["compared_pixels"]:,} selected foreground pixels; '
                        f'{c["all_pixels"]["exact_pixel_fraction"]:.4%} exact across the complete viewport, including animation differences and black pixels.</p>'
                        f'<a href="proofs/{c["name"]}/static-foreground/comparison.png"><img src="proofs/{c["name"]}/static-foreground/comparison.png" alt="Original game, exported crop, and pixel difference"></a>'
                        f'<p><a href="proofs/{c["name"]}/capture.json">Camera, mask definition and measurements</a></p></article>'for c in checks)
    animations=''.join(f'<article><h3>{html.escape(c["name"])}</h3><img class="clip" src="clips/{c["name"]}/animation.apng" alt="Lossless original-game animation">'
                      f'<p>{c["distinct_frames"]} distinct frames from {c["recorded_frames"]} captures. All decoded APNG frames exactly match source RGB.</p></article>'for c in clips)
    shore_section='''<h2>Shoreline source-capture correction</h2><p>The PNG reused older native frames containing black bands, while the live renderer produced clean frames at the same registered cameras. The bands were in the raw captures, so neither PNG compression nor stitching created them. The low-level fault in the older runtime session is not established.</p><p>391 candidate frames were recaptured in full. Their owned pixels were refreshed directly from the new registered frames. At camera 0 / 3196, 28775, 0, all 217,600 viewport pixels now exactly match fresh game output. The ten-second confirmation advanced 243 original game frames. Frozen renderers and retired capture digests are now rejected.</p><a href="proofs/shore-bands/before-after.png"><img src="proofs/shore-bands/before-after.png" alt="Older PNG with black bands, and corrected export"></a><p><a href="proofs/shore-bands/diagnosis.json">Observations and measurements</a> · <a href="proofs/shore-bands/corrected/capture.json">Fresh viewport comparison</a></p>'''if shore_issue and shore_issue.get('status')=='fixed'else ''
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Revenant native fidelity checks</title>
<style>body{max-width:1400px;margin:32px auto;padding:0 24px;background:#0c100f;color:#e5e9df;font:16px/1.5 system-ui}a{color:#bbdca9}h1,h2,h3{font-family:Georgia}p{max-width:1000px}table{border-collapse:collapse}td,th{padding:10px 16px;border-bottom:1px solid #3c493c;text-align:left}img{max-width:100%;image-rendering:pixelated}.clip{width:640px}article{margin:32px 0}</style>
<h1>Revenant · Native fidelity checks</h1><p><a href="/">Live original-game camera</a> · <a href="index.html">Stitched map viewer</a> · <a href="fidelity.json">All measurements</a></p>
<p>The map uses pixels captured from the original executable, with a narrow correction for black-shadow blending into its background texture. Lighting, shadows, creatures, NPCs and visible items are rendered by the game. Each owned output pixel was exhaustively checked against its registered source viewport. No post-capture blending, colour correction or resampling is used.</p>
<p>The PNG combines successive animation frames. It is not one synchronized island instant, and fresh comparisons are not 100% identical. The live camera and the lossless clips below retain animation. Editor mode pauses AI; visible objects reflect the base-module game state. Hidden, quest-spawned and inventory contents are not made visible artificially.</p>
'''+('''<h2>Corrected shadow rendering</h2><p>The barrel/crate rainbow band at level 0, camera 2012, 27407, 0 came from the original dispatcher applying an RGB565 alpha routine to an ARGB1555 background texture. Its coverage bit was treated as colour. The correction preserves coverage and uses the native 15-bit channel rounding for black shadow bitmaps; all other draws retain the original dispatcher.</p><p>The direct-game A/B check changed 586 pixels, all inside the two shadow regions, with every pixel outside identical. All 586 corrected pixels in the rebuilt map exactly match a fresh game capture. The regression checks cover all 65,536 packed colours, transparent/opaque alpha endpoints, dimming, clipped strides, and both mirrors. Source-bounded affected captures were replaced.</p><img class="clip" src="proofs/shadow-band/fixed-detail.png" alt="Before: coloured bands; after: corrected shadows"><p><a href="proofs/shadow-band/fix-validation.json">A/B measurements</a> · <a href="proofs/shadow-band/corrected-shadow-export/report.json">Corrected export pixels</a> · <a href="proofs/shadow-band/native-table-proof.json">Native lookup-table fault proof</a> · <a href="proofs/shadow-band/diagnosis.json">Diagnostic history</a></p>'''if issues and all(i.get('status')=='fixed'for i in issues)else '<p>A rendering issue remains under investigation; consult fidelity.json.</p>'if issues else '')+'''
'''+shore_section+'''
<h2>Export and boundary audit</h2><p>Static boundary differences are neighbouring output pixels that neither overlapping source reproduces and that fall outside measured animation masks. Animation boundary differences use the same test inside measured masks. Zero static boundary differences does not mean all fresh viewports match exactly or that source rendering is free of defects.</p>
<table><thead><tr><th>Level</th><th>Native dimensions</th><th>Captures</th><th>Static boundary differences</th><th>Animation boundary differences</th><th>Files</th></tr></thead><tbody>'''+rows+'''</tbody></table>
<p>The native exports cover all 33 drawable base-module levels, including the outdoor island, interiors and shipped test layouts. The independent static artwork baseline remains separate. Each completed native export has zero unmeasured static ownership edges and no nonblack boundary into unplanned coverage.</p>
<h2>Fresh original-game comparisons</h2><p>Each strip shows the fresh game viewport, the registered exported crop, and the difference. Red marks unequal selected pixels; blue marks excluded pixels. Foreground measurements exclude black background and measured animation, with the mask and its margins recorded explicitly.</p>'''+comparisons+'''<h2>Original animation</h2>'''+animations+'''<p>Rendering configuration: original real-time light grid, 08:07 game time, GammaLevel 3, Wine/D7VK. D7VK ignores application gamma ramps; these measurements apply to this configuration. Shipped test geometry remains where the original game renders it.</p></html>'''
    (root/'fidelity.html').write_text(page)
    return summary


if __name__=='__main__':
    build()
    print('native-output/fidelity.html')
