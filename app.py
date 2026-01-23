
import json
import re
import hashlib
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from st_cytoscape import cytoscape

st.set_page_config(page_title='Curricular Flows Demo', layout='wide')

DATA_DIR = Path(__file__).parent / 'data'
SCHOOL_FILES = {
    'Rural High': DATA_DIR / 'rural_high.json',
    'Magnet High': DATA_DIR / 'magnet_high.json',
}

TRACK_COLORS = {
    'Special education': '#7B61FF',
    'Lower-basic': '#FF8C42',
    'Upper-basic': '#F9C74F',
    'Regular': '#43AA8B',
    'Accelerated': '#277DA1',
    'Honors': '#577590',
    'Pre-IB': '#4D908E',
    'IB-general': '#90BE6D',
    'IB-standard': '#F9844A',
    'IB-honors': '#F94144',
}

DIM_COLOR = '#D0D4DC'
EDGE_COLOR = '#8D99AE'
EDGE_HIGHLIGHT = '#111827'
NODE_BORDER = '#111827'


@st.cache_data
def load_school_graph(school_name: str) -> dict:
    return json.loads(SCHOOL_FILES[school_name].read_text(encoding='utf-8'))


def placeholder_demographics() -> pd.DataFrame:
    rows = [
        {'Dimension': 'Gender', 'Group': 'Female', 'Share': 0.52},
        {'Dimension': 'Gender', 'Group': 'Male', 'Share': 0.48},
        {'Dimension': 'Race', 'Group': 'Black', 'Share': 0.28},
        {'Dimension': 'Race', 'Group': 'Latine', 'Share': 0.18},
        {'Dimension': 'Race', 'Group': 'White', 'Share': 0.44},
        {'Dimension': 'Race', 'Group': 'Asian', 'Share': 0.10},
    ]
    return pd.DataFrame(rows)


def node_tracks(course: str, tracks: dict) -> list:
    return [t for t, courses in tracks.items() if course in set(courses)]


def primary_track(course: str, tracks: dict):
    for t, courses in tracks.items():
        if course in set(courses):
            return t
    return None


def edge_tracks(src: str, dst: str, tracks: dict) -> list:
    src_t = set(node_tracks(src, tracks))
    dst_t = set(node_tracks(dst, tracks))
    inter = sorted(src_t.intersection(dst_t))
    if inter:
        return inter
    return sorted(src_t.union(dst_t))


def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return s or 'node'


def make_unique_ids(courses: list[str]) -> tuple[dict, dict]:
    course_to_uid = {}
    used = set()
    for c in courses:
        base = _slugify(c)
        uid = base
        if uid in used:
            h = hashlib.md5(c.encode('utf-8')).hexdigest()[:8]
            uid = f"{base}_{h}"
        k = 2
        while uid in used:
            uid = f"{base}_{k}"
            k += 1
        used.add(uid)
        course_to_uid[c] = uid
    uid_to_course = {v: k for k, v in course_to_uid.items()}
    return course_to_uid, uid_to_course


def get_self_loop_p(graph: dict, course: str) -> float | None:
    for s, t, p in graph['edges']:
        if s == course and t == course:
            return float(p)
    return None


def course_panel(graph: dict, course: str):
    tracks = graph['tracks']
    st.subheader(course)
    tlist = node_tracks(course, tracks)
    st.caption('Track membership: ' + (', '.join(tlist) if tlist else '(none)'))

    loop_p = get_self_loop_p(graph, course)
    if loop_p is not None and loop_p > 0:
        st.metric('Retake / repeat (self-loop)', f"{loop_p:.2f}")

    incoming = [(s, p) for (s, t, p) in graph['edges'] if t == course and s != course]
    outgoing = [(t, p) for (s, t, p) in graph['edges'] if s == course and t != course]

    def fmt(items):
        return sorted(items, key=lambda x: -x[1])

    with st.expander('Outgoing transitions (top 5, excluding retake)', expanded=True):
        for dst, p in fmt(outgoing)[:5]:
            st.write(f'- **{dst}**: {p:.2f}')

    with st.expander('Incoming transitions (top 5)', expanded=False):
        for src, p in fmt(incoming)[:5]:
            st.write(f'- **{src}**: {p:.2f}')

    st.markdown('---')
    st.caption('PLACEHOLDER: Demographics chart (fake demo data — same for all courses)')

    demo_df = placeholder_demographics()
    chart = (
        alt.Chart(demo_df)
        .mark_bar()
        .encode(
            x=alt.X('Share:Q', axis=alt.Axis(format='%')),
            y=alt.Y('Group:N', sort='-x'),
            color=alt.Color('Dimension:N'),
            tooltip=['Dimension', 'Group', alt.Tooltip('Share:Q', format='.1%')],
        )
        .properties(height=240)
    )

    # Avoid Streamlit's use_container_width deprecation.
    st.altair_chart(chart, width='stretch')


def build_cytoscape_elements(graph: dict, selected_node: str | None, selected_edge: str | None,
                             course_to_uid: dict, uid_to_course: dict):
    tracks = graph['tracks']
    positions = graph.get('positions', {})

    focus_tracks = set()
    focus_neighbors = set()
    focus_edges = set()  # course edge ids "Course A→Course B"

    if selected_node:
        focus_tracks.update(node_tracks(selected_node, tracks))
        for (s, t, p) in graph['edges']:
            if s == selected_node or t == selected_node:
                focus_neighbors.update([s, t])
                focus_edges.add(f'{s}→{t}')

    if selected_edge:
        try:
            s, t = selected_edge.split('→')
            focus_tracks.update(edge_tracks(s, t, tracks))
            focus_neighbors.update([s, t])
            focus_edges.add(selected_edge)
        except Exception:
            pass

    focus_mode = bool(selected_node or selected_edge)

    elements = []

    # Nodes
    for course in graph['nodes']:
        t_primary = primary_track(course, tracks)
        fill = TRACK_COLORS.get(t_primary, '#2B2D42')
        opacity = 1.0
        border_width = 2
        classes = []

        if focus_mode:
            course_track_list = node_tracks(course, tracks)
            in_focus_track = any(t in focus_tracks for t in course_track_list)
            is_neighbor = course in focus_neighbors
            if (not in_focus_track) and (not is_neighbor):
                fill = DIM_COLOR
                opacity = 0.18
                classes.append('dim')

        if selected_node == course:
            border_width = 6
            classes.append('selected')

        uid = course_to_uid[course]

        node_el = {
            "data": {
                "id": uid,
                "label": course,
                "bg": fill,
                "opacity": opacity,
                "border": NODE_BORDER,
                "borderWidth": border_width,
            },
            "classes": ' '.join(classes),
        }
        if course in positions:
            x, y = positions[course]
            node_el["position"] = {"x": x, "y": y}
        elements.append(node_el)

    # Edges
    for (s, t, p) in graph['edges']:
        course_eid = f'{s}→{t}'
        src_uid = course_to_uid[s]
        dst_uid = course_to_uid[t]
        uid_eid = f'{src_uid}→{dst_uid}'

        is_self = (s == t)

        show_label = False
        if is_self:
            show_label = True  # always show retake/loop proportion
        elif selected_node and (s == selected_node or t == selected_node):
            show_label = True
        elif selected_edge and course_eid == selected_edge:
            show_label = True

        opacity = 0.85
        ecolor = EDGE_COLOR
        classes = []

        if is_self:
            classes.append('selfloop')

        if focus_mode and not is_self:
            etracks = edge_tracks(s, t, tracks)
            in_focus = bool(set(etracks).intersection(focus_tracks)) or (course_eid in focus_edges)
            if in_focus:
                ecolor = EDGE_HIGHLIGHT
                opacity = 1.0
                classes.append('focus')
            else:
                ecolor = DIM_COLOR
                opacity = 0.10
                classes.append('dim')

        if selected_edge and course_eid == selected_edge:
            classes.append('selected')

        elements.append({
            "data": {
                "id": uid_eid,
                "source": src_uid,
                "target": dst_uid,
                "label": (f'{float(p):.2f}' if show_label else ''),
                "color": ecolor,
                "opacity": opacity,
            },
            "classes": ' '.join(classes),
        })

    return elements


# Sidebar
with st.sidebar:
    st.title('Curricular Flows')
    st.caption('Interactive demo inspired by McFarland (2006) Figures 1–2.')

    school = st.selectbox('School', list(SCHOOL_FILES.keys()), index=0)

    st.markdown('### Filters (coming soon)')
    st.selectbox('Subject', ['Math'], disabled=True)
    st.selectbox('Race', ['All'], disabled=True)
    st.selectbox('Gender', ['All'], disabled=True)
    st.info('Subject and Race/Gender filtering is disabled in this demo. It will be enabled in the full product.')

    graph = load_school_graph(school)

    st.markdown('### Tracks (legend)')
    for t in graph['tracks'].keys():
        st.markdown(
            "- <span style='display:inline-block;width:10px;height:10px;background:{};border:1px solid #111827;margin-right:8px;'></span> {}".format(
                TRACK_COLORS.get(t, '#2B2D42'), t
            ),
            unsafe_allow_html=True,
        )


left, right = st.columns([0.68, 0.32], gap='large')

graph = load_school_graph(school)

# Selection state stores *course names*
if 'selected_node' not in st.session_state:
    st.session_state.selected_node = None
if 'selected_edge' not in st.session_state:
    st.session_state.selected_edge = None

course_to_uid, uid_to_course = make_unique_ids(graph['nodes'])
edge_uid_to_course = {f"{course_to_uid[s]}→{course_to_uid[t]}": f"{s}→{t}" for (s, t, p) in graph['edges']}

stylesheet = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "background-color": "data(bg)",
            "opacity": "data(opacity)",
            "border-color": "data(border)",
            "border-width": "data(borderWidth)",
            "color": "#FFFFFF",
            "text-valign": "center",
            "text-halign": "center",
            "font-size": 14,
            "width": 60,
            "height": 60,
        },
    },
    {
        "selector": "edge",
        "style": {
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "data(color)",
            "line-color": "data(color)",
            "opacity": "data(opacity)",
            "width": 3,
            "label": "data(label)",
            "font-size": 14,
            "color": "#111827",
            "text-background-color": "#FFFFFF",
            "text-background-opacity": 0.85,
            "text-background-padding": 2,
        },
    },
    # Self-loop styling so retake edges are visible
    {
        "selector": "edge.selfloop",
        "style": {
            "loop-direction": -45,
            "loop-sweep": 90,
            "target-arrow-shape": "triangle",
            "width": 4,
        },
    },
    {"selector": ".dim", "style": {"opacity": 0.18}},
    {"selector": "edge.dim", "style": {"opacity": 0.10}},
    {"selector": ".selected", "style": {"border-width": 6}},
]


with left:
    st.subheader(f'{school}: course flow map')
    st.caption(
        'Preset layout (fixed positions if provided). Drag nodes to adjust. '
        'Click a course to focus and reveal transition rates on incident edges. '
        'Self-loops show the retake/repeat share so each node’s outgoing probabilities sum to 1.'
    )

    elements = build_cytoscape_elements(
        graph,
        st.session_state.selected_node,
        st.session_state.selected_edge,
        course_to_uid,
        uid_to_course,
    )

    selected = cytoscape(
        elements,
        stylesheet,
        width='100%',
        height='740px',
        layout={"name": "preset", "animationDuration": 0},
        selection_type='single',
        user_zooming_enabled=True,
        user_panning_enabled=True,
        key='cy_graph',
    )

    clicked_nodes = selected.get('nodes', []) if isinstance(selected, dict) else []
    clicked_edges = selected.get('edges', []) if isinstance(selected, dict) else []

    if clicked_nodes:
        uid = clicked_nodes[0]
        st.session_state.selected_node = uid_to_course.get(uid)
        st.session_state.selected_edge = None
    elif clicked_edges:
        uid_eid = clicked_edges[0]
        st.session_state.selected_edge = edge_uid_to_course.get(uid_eid)
        st.session_state.selected_node = None

    if st.button('Clear selection / reset focus'):
        st.session_state.selected_node = None
        st.session_state.selected_edge = None
        st.rerun()

    st.markdown('---')
    st.caption('⚠️ Demo note: transition rates are illustrative and meant to be replaced with your actual data in production.')


with right:
    st.subheader('Selection (side panel)')

    if st.session_state.selected_node:
        course_panel(graph, st.session_state.selected_node)

    elif st.session_state.selected_edge:
        st.subheader('Selected transition')
        try:
            s, t = st.session_state.selected_edge.split('→')
            st.write('**{} → {}**'.format(s, t))
        except Exception:
            st.write(st.session_state.selected_edge)
            s = t = None

        p = None
        for (ss, tt, pp) in graph['edges']:
            if '{}→{}'.format(ss, tt) == st.session_state.selected_edge:
                p = float(pp)
                break

        if p is not None:
            st.write('Transition rate: **{:.2f}**'.format(p))

        if s and t and s != t:
            et = edge_tracks(s, t, graph['tracks'])
            if et:
                st.caption('Track highlight: ' + ', '.join(et))

        st.markdown('---')
        st.caption('Tip: click a course node to see the course details panel.')

    else:
        st.write('Click a course bubble to focus and see details here.')
