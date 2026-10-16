"""Export editable Excalidraw report diagrams as portable SVG previews.

The .excalidraw files remain the source of truth. This supports the simple
rectangles, lines, straight arrows and text used in the report diagrams.
"""

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / 'diagrams'


def export(name):
    source = ROOT / f'system-{name}.excalidraw'
    data = json.loads(source.read_text())
    extent_x = max(element['x'] + element['width'] for element in data['elements']) + 60
    extent_y = max(element['y'] + element['height'] for element in data['elements']) + 45
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {extent_x} {extent_y}" '
        'role="img" aria-label="Book Ledger report diagram">',
        '<defs><marker id="arrow" markerWidth="9" markerHeight="9" '
        'refX="7" refY="4.5" orient="auto-start-reverse" markerUnits="strokeWidth">'
        '<path d="M1,1 L8,4.5 L1,8" fill="none" stroke="#334155" '
        'stroke-width="1.7"/></marker></defs>',
        f'<rect width="{extent_x}" height="{extent_y}" fill="#ffffff"/>',
    ]
    for element in data['elements']:
        kind = element['type']
        x, y = element['x'], element['y']
        stroke = element.get('strokeColor', '#334155')
        if kind == 'rectangle':
            dash = ' stroke-dasharray="8 6"' if element['strokeStyle'] == 'dashed' else ''
            parts.append(
                f'<rect x="{x}" y="{y}" width="{element["width"]}" '
                f'height="{element["height"]}" rx="10" '
                f'fill="{element["backgroundColor"]}" stroke="{stroke}" '
                f'stroke-width="{element["strokeWidth"]}"{dash}/>'
            )
        elif kind in {'arrow', 'line'}:
            points = element['points']
            x1, y1 = x + points[0][0], y + points[0][1]
            x2, y2 = x + points[-1][0], y + points[-1][1]
            start = ' marker-start="url(#arrow)"' if element.get('startArrowhead') else ''
            end = ' marker-end="url(#arrow)"' if element.get('endArrowhead') else ''
            dash = ' stroke-dasharray="7 6"' if element['strokeStyle'] == 'dashed' else ''
            parts.append(
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                f'stroke="{stroke}" stroke-width="{element["strokeWidth"]}"'
                f'{dash}{start}{end}/>'
            )
        elif kind == 'text':
            size = element['fontSize']
            line_height = size * element.get('lineHeight', 1.25)
            family = 'Arial, Helvetica, sans-serif'
            lines = element['text'].split('\n')
            for line_number, line in enumerate(lines):
                parts.append(
                    f'<text x="{x}" y="{y + size + line_number * line_height}" '
                    f'fill="{stroke}" font-size="{size}" '
                    f'font-family="{family}">{html.escape(line)}</text>'
                )
    parts.append('</svg>')
    (ROOT / f'system-{name}.svg').write_text('\n'.join(parts) + '\n')


for diagram in ('baseline', 'secured', 'sequence'):
    export(diagram)
