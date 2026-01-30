
import json
import re
import hashlib
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from st_cytoscape import cytoscape

st.set_page_config(page_title='Course Pathways', layout='wide')

st.markdown(
    """
<style>
  .stApp { font-size: 18px; }
  .stMarkdown, .stText, .stCaption, .stAlert { line-height: 1.5; }
  h1 { font-size: 2.0rem; letter-spacing: 0.2px; }
  h2 { font-size: 1.55rem; }
  h3 { font-size: 1.25rem; }
  [data-testid="stSidebar"] { font-size: 1.0rem; }
  [data-testid="stSidebar"] .stMarkdown p { font-size: 1.0rem; }
  .stButton > button { font-size: 1.0rem; padding: 0.55rem 0.9rem; border-radius: 10px; }
  .stSelectbox, .stTextInput, .stRadio, .stMultiSelect { font-size: 1.0rem; }
  .stCaption { font-size: 0.98rem; color: #374151; }
  [data-testid="stWidgetLabel"] p { font-size: 1.0rem; }
  .block-container { padding-top: 1.25rem; padding-bottom: 2.25rem; }
</style>
""",
    unsafe_allow_html=True,
)

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
TERMINALS = {'Graduate', 'Leave School'}


@st.cache_data
def load_school_graph(school_name: str) -> dict:
    return json.loads(SCHOOL_FILES[school_name].read_text(encoding='utf-8'))


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
    return inter if inter else sorted(src_t.union(dst_t))


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


def friendly_percent(x: float) -> str:
    return f"{x * 100:.0f}%"


def course_panel(graph: dict, course: str):
    tracks = graph['tracks']

    st.subheader(course)

    tlist = node_tracks(course, tracks)
    st.write('**Path group:** ' + (', '.join(tlist) if tlist else 'Not listed'))

    loop_p = get_self_loop_p(graph, course)
    if loop_p is not None and loop_p > 0:
        st.write(f"**Repeat this class next year:** {friendly_percent(loop_p)}")

    incoming = [(s, p) for (s, t, p) in graph['edges'] if t == course and s != course]
    outgoing = [(t, p) for (s, t, p) in graph['edges'] if s == course and t != course]

    def fmt(items):
        return sorted(items, key=lambda x: -x[1])

    st.markdown('---')
    st.write('### What students do next')
    if outgoing:
        for dst, p in fmt(outgoing)[:6]:
            st.write(f"- **{dst}**: {friendly_percent(float(p))}")
    else:
        st.write('No next-step arrows from this class.')

    st.markdown('---')
    st.write('### Where students come from')
    if incoming:
        for src, p in fmt(incoming)[:6]:
            st.write(f"- **{src}**: {friendly_percent(float(p))}")
    else:
        st.write('No arrows pointing into this class.')

    st.markdown('---')
    st.write('### Example charts (demo)')
    st.write('Pick a tab to see a placeholder chart. These are not real numbers yet.')

    tab_gender, tab_race, tab_both = st.tabs(['Gender', 'Race', 'Gender × Race'], width='stretch')

    with tab_gender:
        st.write('**Gender (placeholder)**')
        gender_df = pd.DataFrame([
            {'Group': 'Girls', 'Share': 0.52},
            {'Group': 'Boys', 'Share': 0.48},
        ])
        gender_chart = (
            alt.Chart(gender_df)
            .mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6)
            .encode(
                x=alt.X('Share:Q', axis=alt.Axis(format='%'), title='Share of students'),
                y=alt.Y('Group:N', sort='-x', title=''),
                tooltip=[alt.Tooltip('Share:Q', format='.0%')],
            )
            .properties(height=220)
        )
        st.altair_chart(gender_chart, width='stretch')

    with tab_race:
        st.write('**Race (placeholder)**')
        race_df = pd.DataFrame([
            {'Group': 'Black', 'Share': 0.28},
            {'Group': 'Latine', 'Share': 0.18},
            {'Group': 'White', 'Share': 0.44},
            {'Group': 'Asian', 'Share': 0.10},
        ])
        race_chart = (
            alt.Chart(race_df)
            .mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6)
            .encode(
                x=alt.X('Share:Q', axis=alt.Axis(format='%'), title='Share of students'),
                y=alt.Y('Group:N', sort='-x', title=''),
                tooltip=[alt.Tooltip('Share:Q', format='.0%')],
            )
            .properties(height=240)
        )
        st.altair_chart(race_chart, width='stretch')

    with tab_both:
        st.write('**Gender × Race (placeholder)**')
        st.write('This is an “intersection”: we look at two things at the same time.')

        both_df = pd.DataFrame([
            {'Gender': 'Girls', 'Race': 'Black', 'Share': 0.15},
            {'Gender': 'Girls', 'Race': 'Latine', 'Share': 0.10},
            {'Gender': 'Girls', 'Race': 'White', 'Share': 0.22},
            {'Gender': 'Girls', 'Race': 'Asian', 'Share': 0.05},
            {'Gender': 'Boys', 'Race': 'Black', 'Share': 0.13},
            {'Gender': 'Boys', 'Race': 'Latine', 'Share': 0.08},
            {'Gender': 'Boys', 'Race': 'White', 'Share': 0.22},
            {'Gender': 'Boys', 'Race': 'Asian', 'Share': 0.05},
        ])

        heat = (
            alt.Chart(both_df)
            .mark_rect(cornerRadius=6)
            .encode(
                x=alt.X('Race:N', title='Race'),
                y=alt.Y('Gender:N', title='Gender'),
                color=alt.Color('Share:Q', title='Share', scale=alt.Scale(scheme='blues')),
                tooltip=['Gender', 'Race', alt.Tooltip('Share:Q', format='.0%')],
            )
            .properties(height=180)
        )
        st.altair_chart(heat, width='stretch')


def build_cytoscape_elements(graph: dict, selected_node: str | None, selected_edge: str | None,
                             course_to_uid: dict, uid_to_course: dict):
    tracks = graph['tracks']
    positions = graph.get('positions', {})

    focus_tracks = set()
    focus_neighbors = set()
    focus_edges = set()

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
            'data': {
                'id': uid,
                'label': course,
                'bg': fill,
                'opacity': opacity,
                'border': NODE_BORDER,
                'borderWidth': border_width,
            },
            'classes': ' '.join(classes),
        }
        if course in positions:
            x, y = positions[course]
            node_el['position'] = {'x': x, 'y': y}
        elements.append(node_el)

    for (s, t, p) in graph['edges']:
        src_uid = course_to_uid[s]
        dst_uid = course_to_uid[t]
        uid_eid = f'{src_uid}→{dst_uid}'
        course_eid = f'{s}→{t}'

        is_self = (s == t)

        show_label = is_self
        if (not is_self) and selected_node and (s == selected_node or t == selected_node):
            show_label = True
        if (not is_self) and selected_edge and course_eid == selected_edge:
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

        label_txt = friendly_percent(float(p)) if show_label else ''

        elements.append({
            'data': {
                'id': uid_eid,
                'source': src_uid,
                'target': dst_uid,
                'label': label_txt,
                'color': ecolor,
                'opacity': opacity,
            },
            'classes': ' '.join(classes),
        })

    return elements


with st.sidebar:
    st.title('Course Pathways')
    st.write('This map shows how students move from one math class to the next.')
    st.write('Tap a circle to see details on the right.')

    school = st.selectbox('Choose a school', list(SCHOOL_FILES.keys()), index=0)

    st.markdown('---')
    st.subheader('Filters')
    st.write('These filters are not ready yet.')
    st.selectbox('Subject', ['Math'], disabled=True)
    st.selectbox('Race', ['All'], disabled=True)
    st.selectbox('Gender', ['All'], disabled=True)

    gtmp = load_school_graph(school)
    st.markdown('---')
    st.subheader('Color key')
    st.write('Colors show different course paths.')
    for t in gtmp['tracks'].keys():
        st.markdown(
            "- <span style='display:inline-block;width:12px;height:12px;background:{};border:1px solid #111827;margin-right:10px;'></span> {}".format(
                TRACK_COLORS.get(t, '#2B2D42'), t
            ),
            unsafe_allow_html=True,
        )


left, right = st.columns([0.68, 0.32], gap='large')

graph = load_school_graph(school)

if 'selected_node' not in st.session_state:
    st.session_state.selected_node = None
if 'selected_edge' not in st.session_state:
    st.session_state.selected_edge = None

course_to_uid, uid_to_course = make_unique_ids(graph['nodes'])
edge_uid_to_course = {f"{course_to_uid[s]}→{course_to_uid[t]}": f"{s}→{t}" for (s, t, p) in graph['edges']}

stylesheet = [
    {
        'selector': 'node',
        'style': {
            'label': 'data(label)',
            'background-color': 'data(bg)',
            'opacity': 'data(opacity)',
            'border-color': 'data(border)',
            'border-width': 'data(borderWidth)',
            'color': '#FFFFFF',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': 18,
            'width': 64,
            'height': 64,
            'z-index': 1,
        },
    },
    {
        'selector': 'edge',
        'style': {
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': 'data(color)',
            'line-color': 'data(color)',
            'opacity': 'data(opacity)',
            'width': 3,
            'label': 'data(label)',
            'font-size': 16,
            'color': '#111827',
            'text-background-color': '#FFFFFF',
            'text-background-opacity': 0.85,
            'text-background-padding': 3,
            'z-index': 0,
        },
    },
    {
        'selector': 'edge.selfloop',
        'style': {
            'curve-style': 'bezier',
            'loop-direction': '-45deg',
            'loop-sweep': '120deg',
            'source-endpoint': 'outside-to-line',
            'target-endpoint': 'outside-to-line',
            'control-point-step-size': 140,
            'width': 4,
            'z-index-compare': 'manual',
            'z-compound-depth': 'top',
            'z-index': 9999,
        },
    },
    {'selector': '.dim', 'style': {'opacity': 0.18}},
    {'selector': 'edge.dim', 'style': {'opacity': 0.10}},
    {'selector': '.selected', 'style': {'border-width': 6}},
]

with left:
    st.header('Math class map')
    st.write('Circles are classes. Arrows show where students go next.')
    st.write('A looped arrow means some students repeat the same class.')
    st.write('"Graduate" and "Leave School" are endings, so they have no arrows going out.')

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
        layout={'name': 'preset', 'animationDuration': 0},
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

    if st.button('Clear selection'):
        st.session_state.selected_node = None
        st.session_state.selected_edge = None
        st.rerun()


with right:
    st.header('Details')

    if st.session_state.selected_node:
        course_panel(graph, st.session_state.selected_node)

    elif st.session_state.selected_edge:
        st.subheader('Arrow details')
        try:
            s, t = st.session_state.selected_edge.split('→')
            st.write(f'**From:** {s}')
            st.write(f'**To:** {t}')
        except Exception:
            st.write(st.session_state.selected_edge)
            s = t = None

        p = None
        for (ss, tt, pp) in graph['edges']:
            if f'{ss}→{tt}' == st.session_state.selected_edge:
                p = float(pp)
                break

        if p is not None:
            st.write(f'**Chance:** {friendly_percent(p)}')

        if s and t and s != t:
            et = edge_tracks(s, t, graph['tracks'])
            if et:
                st.write('**Path colors involved:** ' + ', '.join(et))

    else:
        st.write('Click a circle or an arrow to see more information here.')
