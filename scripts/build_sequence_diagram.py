"""Build the editable Excalidraw sequence diagram used in REPORT_DRAFT.md."""

import json
from pathlib import Path


OUT = Path(__file__).resolve().parents[1] / 'diagrams' / 'system-sequence.excalidraw'
ELEMENTS = []
NEXT_ID = 1
COLORS = {
    'ink': '#243449',
    'muted': '#64748b',
    'green': '#166534',
    'blue': '#1d4ed8',
    'amber': '#92400e',
    'red': '#b42318',
}
LIFELINES = {'Reader': 150, 'React': 480, 'Flask': 990, 'SQLite': 1430}


def base(kind, x, y, width, height, stroke='#334155', fill='transparent', style='solid'):
    global NEXT_ID
    number = NEXT_ID
    NEXT_ID += 1
    return {
        'id': f'seq-{number}', 'type': kind, 'x': x, 'y': y,
        'width': width, 'height': height, 'angle': 0,
        'strokeColor': stroke, 'backgroundColor': fill,
        'fillStyle': 'solid', 'strokeWidth': 2,
        'strokeStyle': style, 'roughness': 0, 'opacity': 100,
        'groupIds': [], 'frameId': None,
        'roundness': {'type': 3} if kind == 'rectangle' else None,
        'seed': 1000 + number, 'version': 1, 'versionNonce': 2000 + number,
        'isDeleted': False, 'boundElements': None,
        'updated': 1792108800000, 'link': None, 'locked': False,
    }


def rect(x, y, width, height, fill, stroke='#cbd5e1'):
    ELEMENTS.append(base('rectangle', x, y, width, height, stroke, fill))


def text(x, y, value, size=18, color=COLORS['ink']):
    lines = value.split('\n')
    longest = max(len(line) for line in lines)
    element = base('text', x, y, max(20, longest * size * 0.57),
                   len(lines) * size * 1.25, color)
    element.update({
        'text': value, 'originalText': value, 'fontSize': size,
        'fontFamily': 2, 'textAlign': 'left', 'verticalAlign': 'top',
        'containerId': None, 'autoResize': True, 'lineHeight': 1.25,
    })
    ELEMENTS.append(element)


def line(x1, y1, x2, y2, color='#cbd5e1', dashed=True):
    element = base('line', x1, y1, abs(x2 - x1), abs(y2 - y1), color,
                   style='dashed' if dashed else 'solid')
    element.update({'points': [[0, 0], [x2 - x1, y2 - y1]],
                    'lastCommittedPoint': None, 'startBinding': None,
                    'endBinding': None})
    ELEMENTS.append(element)


def message(left, right, y, label, color=COLORS['ink']):
    x1, x2 = LIFELINES[left], LIFELINES[right]
    low, high = sorted((x1, x2))
    element = base('arrow', low + 12, y, high - low - 24, 0, color)
    element.update({
        'points': [[0, 0], [high - low - 24, 0]],
        'lastCommittedPoint': None, 'startBinding': None, 'endBinding': None,
        'startArrowhead': 'arrow' if x1 > x2 else None,
        'endArrowhead': 'arrow' if x1 < x2 else None,
        'elbowed': False,
    })
    ELEMENTS.append(element)
    text(low + 24, y - 25, label, 16, color)


def band(y, height, title, fill):
    rect(60, y, 1515, height, fill, '#e2e8f0')
    text(82, y + 12, title, 20, COLORS['green'])


# Phase bands go behind lifelines and messages.
band(205, 685, '01  OPEN, SIGN IN AND ESTABLISH A SESSION', '#f0fdf4')
band(910, 590, '02  LOAD AND SEARCH A PERSONAL LIBRARY', '#eff6ff')
band(1520, 390, '03  CHANGE A BOOK WITH SERVER CHECKS', '#f8fafc')
band(1930, 340, '04  REJECT UNAUTHORIZED REQUESTS', '#fff7ed')
band(2290, 345, '05  SIGN OUT', '#f0fdf4')

for label, x in LIFELINES.items():
    line(x, 185, x, 2650, '#94a3b8')

text(60, 38, 'BOOK LEDGER  /  SECURED USER-INTERACTION SEQUENCE', 26, COLORS['green'])
text(60, 83, 'HTTPS browser flow; server decisions are based on the session, not the URL.', 20)
text(60, 125, 'Solid arrows are requests or responses. Dashed vertical lines are participants.', 16, COLORS['muted'])

for label, x, width in [('Reader', 150, 180), ('React UI', 480, 180),
                        ('Flask API', 990, 190), ('SQLite', 1430, 180)]:
    rect(x - width / 2, 150, width, 54, '#ffffff', '#94a3b8')
    text(x - width / 2 + 18, 160, label, 23)

# 01: initial anonymous session check followed by a successful login.
message('Reader', 'React', 275, 'Open application')
message('React', 'Flask', 335, 'GET /api/session; cookie if present')
message('Flask', 'SQLite', 395, 'Look up token digest and expiry')
message('SQLite', 'Flask', 455, 'No active session', COLORS['muted'])
message('Flask', 'React', 515, '401; display sign-in', COLORS['muted'])
message('Reader', 'React', 575, 'Submit username and password')
message('React', 'Flask', 635, 'POST /api/login; rate limit applies')
message('Flask', 'SQLite', 695, 'Read user hash; verify password')
message('Flask', 'SQLite', 755, 'Store new token digest, expiry and CSRF')
message('Flask', 'React', 815, '200; session cookie + CSRF token', COLORS['green'])
text(83, 854, 'Alternate login result: generic 401 for bad credentials; 429 after five requests/minute/IP.',
     16, COLORS['amber'])

# 02: dashboard, refresh and search. The saved cookie accompanies API calls.
message('React', 'Flask', 980, 'GET /api/users/1 and /books; cookie')
message('Flask', 'SQLite', 1040, 'Validate session; owner-bound SELECT')
message('SQLite', 'Flask', 1100, "Doon's profile and book rows", COLORS['muted'])
message('Flask', 'React', 1160, '200; render notes as text', COLORS['green'])
message('Reader', 'React', 1220, 'Search a book title')
message('React', 'Flask', 1280, 'GET /books?q=...')
message('Flask', 'SQLite', 1340, 'Bind owner ID and title term')
message('SQLite', 'Flask', 1400, 'Matching own books', COLORS['muted'])
message('Flask', 'React', 1460, '200; filtered library', COLORS['green'])

# 03: the three write methods share the same validation and ownership boundary.
message('Reader', 'React', 1590, 'Add, edit or remove a book')
message('React', 'Flask', 1650, 'POST / PUT / DELETE; cookie + CSRF')
message('Flask', 'SQLite', 1710, 'Validate session and book owner')
message('Flask', 'SQLite', 1770, 'Allowlisted, owner-bound write')
message('SQLite', 'Flask', 1830, 'Own row changed', COLORS['muted'])
message('Flask', 'React', 1890, '201 / 200 / 204; refresh list', COLORS['green'])

# 04: these are alternative attack paths, not normal steps after a successful edit.
message('Reader', 'React', 1995, "Change URL to another user's ID")
message('React', 'Flask', 2055, 'GET /api/users/3/books; Doon cookie')
message('Flask', 'React', 2115, '404; no private rows returned', COLORS['red'])
message('React', 'Flask', 2175, 'GET /api/admin/books; Doon cookie')
message('Flask', 'React', 2235, '403; administrator role required', COLORS['red'])
text(83, 2250, 'Another rejected branch: a protected write without the CSRF header returns 403 before mutation.',
     16, COLORS['amber'])

# 05: server-side deletion invalidates the browser-held token.
message('Reader', 'React', 2360, 'Choose Sign out')
message('React', 'Flask', 2420, 'POST /api/logout; cookie + CSRF')
message('Flask', 'SQLite', 2480, 'Delete session digest')
message('SQLite', 'Flask', 2540, 'Session removed', COLORS['muted'])
message('Flask', 'React', 2600, '200; clear cookie', COLORS['green'])
text(60, 2665, 'After logout or one-hour expiry, a protected API call receives 401 and the UI returns to sign-in.',
     18, COLORS['muted'])

OUT.write_text(json.dumps({
    'type': 'excalidraw', 'version': 2, 'source': 'https://excalidraw.com',
    'elements': ELEMENTS,
    'appState': {'viewBackgroundColor': '#ffffff', 'gridSize': None},
    'files': {},
}, indent=2, ensure_ascii=False) + '\n')
print(OUT)
