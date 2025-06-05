import pandas as pd
import numpy as np
import networkx as nx
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State
import dash.exceptions
from datetime import datetime


# DATA LOADING
thesaurus = pd.read_csv('parser/org_data/processed/14346/thesaurus_authors.txt', sep='\t').set_index('Label')
replace_dict = (
    pd.read_csv('parser/org_data/processed/14346/thesaurus_authors.txt', sep='\t')
    .set_index('Label')
    .to_dict()['Replace by']
)
publication = pd.read_csv('parser/org_data/processed/14346/publications.csv')
nodes = pd.read_csv('parser/org_data/processed/14346/Innopolis University map.txt', sep='\t')
edges = pd.read_csv('parser/org_data/processed/14346/Innopolis University network.txt', sep='\t', names=['first_author','second_author','weight'], header=None)


# DATA PROCESSING FUNCTIONS
def standardize_author_names(names, replace_dict):
    arr_authors = [name.strip() for name in names.split(';')]
    res = []
    for name in arr_authors:
        res.append(replace_dict.get(name, name).lower())
    return res

def build_description(row, max_display=3):
    first = nodes.loc[nodes['id'] == row['first_author'], 'label'].iloc[0]
    second = nodes.loc[nodes['id'] == row['second_author'], 'label'].iloc[0]

    first_inform = authors_with_inform[authors_with_inform['Authors'] == first].iloc[0]
    second_inform = authors_with_inform[authors_with_inform['Authors'] == second].iloc[0]

    first_works = set(zip(first_inform['Title'], first_inform['Year'],
                          first_inform['Source title'], first_inform['Cited by']))
    second_works = set(zip(second_inform['Title'], second_inform['Year'],
                           second_inform['Source title'], second_inform['Cited by']))
    
    common = sorted(first_works & second_works, key=lambda x: x[-1], reverse=True)

    res = []
    for number, inform in enumerate(common[:max_display], 1):
        res.append(f"{number}. {inform[0]}, {inform[1]}")
    total = len(common)
    if total > max_display:
        res.append(f"\nи ещё {total - max_display} совместных работ.")
    return '<br>'.join(res)

def id_to_name(ID):
    return nodes.loc[nodes['id'] == ID, 'label'].iloc[0]

def wrap_text(txt, width=50):
    sentences = txt.split('<br>')
    res = []
    for sentence in sentences:
        words = sentence.split(' ')
        lines, cur = [], ''
        for w in words:
            if len(cur) + len(w) + 1 > width:
                lines.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
        lines.append(cur)
        res.append('<br>'.join(lines))
    return '<br>'.join(res)


# DATA PREPARING
authors_with_inform = (
    publication.assign(
        Authors = lambda df: df['Authors'].apply(
            standardize_author_names,
            replace_dict=replace_dict
        )
    )
    .explode('Authors')
    .groupby('Authors', as_index=False)
    .agg({
        'Title': list,
        'Year': list,
        'Source title': list,
        'Cited by': list,
        'Link': list
    })
)

# Build edge descriptions
edges['hover_text'] = edges.apply(build_description, axis=1)
# Convert IDs to names
edges['first_author'] = edges['first_author'].apply(id_to_name)
edges['second_author'] = edges['second_author'].apply(id_to_name)

# Impossible years
YEAR_NOW = datetime.now().year
nodes['score<Avg. pub. year>'] = nodes['score<Avg. pub. year>'].apply(
    lambda x: x if x <= YEAR_NOW else YEAR_NOW
)
# Clusters to colors
COLORS = px.colors.qualitative.Plotly
clusters = nodes['cluster'].unique()
cluster_colors_map = {}
for cl in clusters:
    cluster_colors_map[cl] = COLORS[(cl-1) % len(COLORS)]
nodes['node_color'] = nodes['cluster'].map(cluster_colors_map)

# Create dictionaries for node properties
label_with_coordinates = nodes.set_index('label')[['x', 'y']].to_dict('index')
label_with_color = nodes.set_index('label')['node_color'].to_dict()

# Initializing x range
X_MIN, X_MAX = nodes['x'].min(), nodes['x'].max()
initial_x_range = np.abs(X_MAX - X_MIN)
last_x_range = initial_x_range

# Option dictionaries
size_options = []
options = ['weight<Links>', 'weight<Total link strength>', 'weight<Documents>', 'weight<Citations>', 'weight<Norm. citations>']
options_label = {'weight<Links>': 'Количество связей',
                'weight<Total link strength>': 'Индекс связанности',
                'weight<Documents>': 'Число публикаций',
                'weight<Citations>': 'Число цитирований',
                'weight<Norm. citations>': 'Норм. цитирования'}
for col in nodes.columns:
    if col in options:
        size_options.append({'label': options_label[col], 'value': col})

color_options = []
options = ['score<Avg. pub. year>', 'score<Avg. citations>', 'score<Avg. norm. citations>']
options_label = {'score<Avg. pub. year>': 'Ср. год публикаций',
                'score<Avg. citations>': 'Ср. число цитирований',
                'score<Avg. norm. citations>': 'Ср. норм. цитирования'}
for col in nodes.columns:
    if col in options:
        color_options.append({'label': options_label[col], 'value': col})


# GRAPH TRACING FUNCTIONS
def build_traces():
    segment_by_color = {}
    mid_x, mid_y, edge_weight, edge_hover = [], [], [], []
    for index, edge in edges.iterrows():
        x1, y1 = label_with_coordinates[edge['first_author']]['x'], label_with_coordinates[edge['first_author']]['y']
        x2, y2 = label_with_coordinates[edge['second_author']]['x'], label_with_coordinates[edge['second_author']]['y']

        c1 = label_with_color[edge['first_author']]
        c2 = label_with_color[edge['second_author']]

        xm, ym = (x1 + x2)/2, (y1 + y2)/2
        mid_x.append(xm)
        mid_y.append(ym)
        edge_weight.append(edge['weight'])
        edge_hover.append(wrap_text(edge['hover_text']))
        
        for color, (xA, yA, xB, yB) in [(c1, (x1, y1, xm, ym)), (c2, (xm, ym, x2, y2))]:
            seg = segment_by_color.setdefault(color, {'x': [], 'y': []})
            seg['x'].extend([xA, xB, None])
            seg['y'].extend([yA, yB, None])

    edge_traces = []
    for color, seg in segment_by_color.items():
        edge_traces.append(go.Scattergl(
            x = seg['x'],
            y = seg['y'],
            mode = 'lines',
            hoverinfo='none',
            line = dict(color=color),
            opacity = 0.25,
            name = 'Edges'
        ))

    weight_trace = go.Scattergl(
        x = mid_x,
        y = mid_y,
        mode = 'markers+text',
        marker = dict(size=9, color='#ffffff'),
        text = edge_weight,
        textposition = 'middle center',
        hoverinfo = 'none',
        textfont = dict(size=8, color='rgba(0,0,0,1)'),
        name = 'EdgeWeights'
    )
    weight_trace_hover = go.Scattergl(
        x = mid_x,
        y = mid_y,
        mode = 'markers',
        marker = dict(size=9, color='#fff'),
        opacity = 0,
        hoverinfo = 'text',
        hoverlabel=dict(font_color='#000'),
        hovertext = edge_hover,
        name = 'EdgeWeightsHover'
    )

    raw_sizes = nodes['weight<Links>']
    sizes = 12 + 30 * (raw_sizes - raw_sizes.min()) / (raw_sizes.max() - raw_sizes.min())
    font_size = 8 + 10 * (raw_sizes - raw_sizes.min()) / (raw_sizes.max() - raw_sizes.min())
    font_size = font_size.clip(lower=8, upper=16)
    text_colors = ['rgba(0,0,0,0)' for _ in sizes]
    
    node_trace = go.Scattergl(
        x = nodes['x'],
        y = nodes['y'],
        mode = 'markers+text',
        hoverinfo = 'text',
        text = nodes['label'],
        hovertext = nodes['label'],
        marker = dict(size=sizes.tolist(), color=nodes['node_color']),
        textposition = 'middle center',
        hoverlabel = dict(font_color='#fff'),
        textfont = dict(size=font_size.tolist(), color=text_colors),
        name = 'Nodes'
    )
    node_trace_hover = go.Scattergl(
        x = nodes['x'],
        y = nodes['y'],
        mode = 'markers',
        hoverinfo = 'text',
        hovertext = nodes['label'],
        marker = dict(size=12, color=nodes['node_color']),
        opacity = 0,
        hoverlabel = dict(font_color='#fff'),
        name = 'NodesHover'
    )
    
    edge_traces = [weight_trace_hover] + edge_traces + [weight_trace]
    return node_trace_hover, edge_traces, node_trace

def update_edge_traces(edges, show_weights):
    segment_by_color = {}
    mid_x, mid_y, edge_weight, edge_hover = [], [], [], []
    for index, edge in edges.iterrows():
        x1, y1 = label_with_coordinates[edge['first_author']]['x'], label_with_coordinates[edge['first_author']]['y']
        x2, y2 = label_with_coordinates[edge['second_author']]['x'], label_with_coordinates[edge['second_author']]['y']

        c1 = label_with_color[edge['first_author']]
        c2 = label_with_color[edge['second_author']]

        xm, ym = (x1 + x2)/2, (y1 + y2)/2
        mid_x.append(xm)
        mid_y.append(ym)
        edge_weight.append(edge['weight'])
        edge_hover.append(wrap_text(edge['hover_text']))
        
        for color, (xA, yA, xB, yB) in [(c1, (x1, y1, xm, ym)), (c2, (xm, ym, x2, y2))]:
            seg = segment_by_color.setdefault(color, {'x': [], 'y': []})
            seg['x'].extend([xA, xB, None])
            seg['y'].extend([yA, yB, None])

    new_edge_traces = []
    for color, seg in segment_by_color.items():
        new_edge_traces.append(go.Scattergl(
            x = seg['x'],
            y = seg['y'],
            mode = 'lines',
            hoverinfo='none',
            line = dict(color=color),
            opacity = 0.25,
            name = 'Edges'
        ))
    weight_trace = go.Scattergl(
        x = mid_x,
        y = mid_y,
        mode = 'markers+text',
        marker = dict(size=9, color='#ffffff'),
        text = edge_weight,
        textposition = 'middle center',
        hoverinfo = 'none',
        textfont = dict(
            size = [8] * len(mid_x),
            color = 'rgba(0,0,0,1)' if 'show' in show_weights else 'rgba(0,0,0,0)'
        ),
        name = 'EdgeWeights'
    )
    weight_trace_hover = go.Scattergl(
        x = mid_x,
        y = mid_y,
        mode = 'markers',
        marker = dict(size=9, color='#fff'),
        opacity = 0,
        hoverinfo = 'text',
        hoverlabel=dict(font_color='#000'),
        hovertext = edge_hover,
        name = 'EdgeWeightsHover'
    )

    return [weight_trace_hover] + new_edge_traces + [weight_trace]


# DASH
app = Dash(__name__, suppress_callback_exceptions=True)
# Layout
app.layout = html.Div([
    dcc.Location(id='url'),
    html.Div([
        html.Div([
            html.Label('Размер вершин:'),
            dcc.Dropdown(
                id = 'size-dropdown',
                options = size_options,
                value = size_options[0]['value']
            )
        ], id='content__size'),
        html.Div([
            html.Label('Минимальный вес ребра:'),
            dcc.Input(
                id = 'edge-threshold',
                type = 'number',
                min = int(edges['weight'].min()),
                max = int(edges['weight'].max()),
                step = 1,
                value = int(edges['weight'].min()),
            )
        ], id='content__filter_edge'),
        html.Div([
            html.Label('Поиск автора:'),
            html.Div([
                dcc.Input(
                    id = 'person-search',
                    type = 'text',
                    placeholder = 'иванов и.и.',
                    debounce = True
                )
            ], id='content__input-search'),
            html.Div([
                html.Button('', id = 'search-button', n_clicks = 0)
            ], id='content__search-button')
        ], id='content__search'),
        html.Div([
            html.Button("Сбросить поиск", id = "reset-button", n_clicks = 0)
        ], id='content__reset'),
        html.Div([
            dcc.Checklist(
                id = 'show-weights',
                options = [{'label': 'Показывать веса рёбер', 'value': 'show'}],
                value = ['show'],
                labelStyle = {'display': 'flex'}
            ),
        ], id='content__checkbox'),
        html.Div([
            html.Button("Анализ по метрике", id="color-button", n_clicks=0),
            html.Div([
                dcc.Dropdown(
                    id = 'color-by-dropdown',
                    options = color_options,
                    placeholder = "Выберите показатель",
                ),
            ], id='color-by-container', style={'display': 'none'}),
            html.Div([
                dcc.Store(id='node-color-limits', data={'vmin': None, 'vmax': None}),
                html.Label('Порог минимума:'),
                dcc.Input(id='node-color-min', type='number'),
                html.Label('Порог максимума:'),
                dcc.Input(id='node-color-max', type='number'),
            ], id='color-thresholds-container', style={'display': 'none'}),
        ], id='content__scale')
    ], id='content__sidebar'),
    html.Div([
        dcc.Graph(
            id = 'network-graph',
            config = {
                'scrollZoom': True,
                'displaylogo': False,
                'modeBarButtonsToRemove': [
                    'select2d',
                    'lasso2d',
                    'autoScale2d',
                    'resetScale2d'
                ],
                'modeBarButtonsToAdd': [
                    'drawline',
                    'drawopenpath',
                    'drawcircle',
                    'drawrect',
                    'eraseshape'
                ],
            },
        )
    ], id='content__graph')
], id='content')


# CALLBACKES
@app.callback(
    Output('network-graph', 'figure'),
    Input('url', 'pathname')
)
def build_graph(pathname):
    node_trace_hover, edge_traces, node_trace = build_traces()

    fig = go.Figure(data = [node_trace_hover] + edge_traces + [node_trace])
    fig.update_layout(
        dragmode = 'pan',
        newshape=dict(
            line_color='#ffa294',
            opacity=0.8
        ),
        plot_bgcolor='#f7f9ff',
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            ticks=''
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            ticks='',
            scaleanchor="x",
            scaleratio=1
        ),
        showlegend = False,
        margin = dict(l=0, r=0, t=0, b=0),
        hoverlabel = dict(
            bordercolor = 'gray',
            font_size = 13,
            font_family = 'Arial',
            align = 'left'
        )
    )
    
    return fig

@app.callback(
    Output('network-graph', 'figure', allow_duplicate=True),
    Input('size-dropdown', 'value'),
    State('network-graph', 'figure'),
    prevent_initial_call=True
)
def update_size(size_attr, current_fig):
    raw_sizes = nodes[size_attr]
    sizes = 12 + 30 * (raw_sizes - raw_sizes.min()) / (raw_sizes.max() - raw_sizes.min())
    font_size = 8 + 10 * (raw_sizes - raw_sizes.min()) / (raw_sizes.max() - raw_sizes.min())
    font_size = font_size.clip(lower=8, upper=16)

    node_trace = current_fig['data'][-1]
    node_trace['marker']['size'] = sizes.tolist()
    node_trace['textfont']['size'] = font_size.tolist()
    current_fig['data'][-1] = node_trace
    
    return current_fig

@app.callback(
    Output('network-graph', 'figure', allow_duplicate=True),
    Input('edge-threshold', 'value'),
    State('show-weights', 'value'),
    State('network-graph', 'figure'),
    prevent_initial_call=True
)
def update_threshold(threshold, show_weights, current_fig):
    filtered_edges = edges[edges['weight'] >= threshold]
    edge_traces = update_edge_traces(filtered_edges, show_weights)

    node_trace_hover = current_fig['data'][0]
    node_trace = current_fig['data'][-1]
    current_fig['data'] = [node_trace_hover] + edge_traces + [node_trace]

    return current_fig

@app.callback(
    Output('network-graph', 'figure', allow_duplicate=True),
    Input('search-button', 'n_clicks'),
    Input('person-search', 'n_submit'),
    State('network-graph', 'figure'),
    State('person-search', 'value'),
    prevent_initial_call=True
)
def update_search(n_clicks, n_submit, current_fig, person):
    if not person:
        raise dash.exceptions.PreventUpdate
    
    person = person.lower()
    colors = []
    for name in nodes['label']:
        if person in name:
            colors.append('red')
        else:
            colors.append('#b0daff')
            
    current_fig['data'][0]['marker']['color'] = colors
    current_fig['data'][-1]['marker']['color'] = colors
    
    return current_fig

@app.callback(
    Output('network-graph', 'figure', allow_duplicate=True),
    Output('person-search', 'value'),
    Input('reset-button', 'n_clicks'),
    State('network-graph', 'figure'),
    State('person-search', 'value'),
    prevent_initial_call=True
)
def update_reset(n_clicks, current_fig, person):
    if not person:
        raise dash.exceptions.PreventUpdate

    current_fig['data'][0]['marker']['color'] = nodes['node_color']
    current_fig['data'][-1]['marker']['color'] = nodes['node_color']
    
    return current_fig, ''

@app.callback(
    Output('network-graph', 'figure', allow_duplicate=True),
    Input('show-weights', 'value'),
    State('network-graph', 'figure'),
    prevent_initial_call=True
)
def update_weights(show_weights, current_fig):
    if 'show' in show_weights:
        current_fig['data'][-2]['textfont']['color'] = 'rgba(0,0,0,1)'
    else:
        current_fig['data'][-2]['textfont']['color'] = 'rgba(0,0,0,0)'

    return current_fig

@app.callback(
    Output('network-graph', 'figure', allow_duplicate=True),
    Input('network-graph', 'relayoutData'),
    State('network-graph', 'figure'),
    prevent_initial_call=True
)
def update_zoom(relayout_data, current_fig):
    if not relayout_data or not current_fig:
        raise dash.exceptions.PreventUpdate

    global last_x_range, initial_x_range
    if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
        cur_x0 = relayout_data['xaxis.range[0]']
        cur_x1 = relayout_data['xaxis.range[1]']
        new_range = cur_x1 - cur_x0
        if new_range > 0:
            last_x_range = new_range
        else:
            last_x_range = initial_x_range
    else:
        last_x_range = initial_x_range

    current_x_range = last_x_range or initial_x_range

    zoom_level = initial_x_range / current_x_range

    sizes = np.array(current_fig['data'][-1]['marker']['size'], dtype=float)
    text_colors = []
    for s in sizes:
        if zoom_level <= 2:
            size_factor = 0.1 + 0.9 * (s - sizes.min()) / (sizes.max() - sizes.min() + 1e-5)
        else:
            size_factor = 0.5 + 0.5 * (s - sizes.min()) / (sizes.max() - sizes.min() + 1e-5)
        zoom_factor = 1 / (1 + np.exp(-3 * (zoom_level - 0.8)))
        alpha = size_factor * zoom_factor
        if (zoom_level == 1.0) or (alpha < 0.25) and (zoom_level < 1.5):
            alpha = 0.0
        alpha = min(alpha, 1.0)
        text_colors.append(f'rgba(0,0,0,{alpha:.3f})')
    current_fig['data'][-1]['textfont']['color'] = text_colors
    
    return current_fig

@app.callback(
    Output('network-graph', 'figure', allow_duplicate=True), 
    Output('color-by-container', 'style'),
    Output('color-thresholds-container', 'style'),
    Output('color-by-dropdown', 'value'),
    Input('color-button', 'n_clicks'),
    State('network-graph', 'figure'),
    prevent_initial_call=True
)
def toggle_color_dropdown(n_clicks, current_fig):
    if n_clicks % 2 == 1:
        return current_fig, {'display': 'block'}, {'display': 'flex'}, ''
    trace = current_fig['data'][-1]['marker']
    trace['color'] = nodes['node_color']
    trace.pop('colorscale', None)
    trace.pop('colorbar', None)
    trace.pop('showscale', None)
    trace.pop('cmin', None)
    trace.pop('cmax', None)
    
    return current_fig, {'display': 'none'}, {'display': 'none'}, ''

@app.callback(
    Output('network-graph', 'figure', allow_duplicate=True),
    Output('node-color-min', 'value'),
    Output('node-color-max', 'value'),
    Output('node-color-limits', 'data'),
    Input('color-by-dropdown', 'value'),
    State('network-graph', 'figure'),
    prevent_initial_call=True
)
def update_node_colors(metric, current_fig):
    if not metric:
        raise dash.exceptions.PreventUpdate

    values = nodes[metric]
    colorbar_title = options_label[metric]

    vmin = float(np.floor(np.min(values)))
    vmax = float(np.ceil(np.max(values)))

    node_trace = current_fig['data'][-1]['marker']
    node_trace['color'] = values
    node_trace['colorscale'] = 'Viridis'
    node_trace['cmin'] = vmin
    node_trace['cmax'] = vmax
    node_trace['colorbar'] = {
        'title': colorbar_title,
        'titleside': 'top',
        'orientation': 'h',
        'x': 0.00,
        'xanchor': 'left',
        'y': 0.00,
        'yanchor': 'bottom',
        'len': 0.4,
        'thickness': 14,
        'xanchor': 'left',
        'tickfont': dict(size=12),
        'titlefont': dict(size=15),
        'bgcolor': '#fff'
    }
    node_trace['showscale'] = True

    return current_fig, vmin, vmax, {'vmin': vmin, 'vmax': vmax}

@app.callback(
    Output('network-graph', 'figure', allow_duplicate=True),
    Input('node-color-min', 'value'),
    Input('node-color-max', 'value'),
    State('color-by-dropdown', 'value'),
    State('node-color-limits', 'data'),
    State('network-graph', 'figure'),
    prevent_initial_call=True
)
def update_node_colors_thresholds(scale_min, scale_max, metric, limits, current_fig):
    if metric is None or limits is None:
        raise dash.exceptions.PreventUpdate
    if scale_min is None or scale_max is None:
        raise dash.exceptions.PreventUpdate

    vmin = limits['vmin']
    vmax = limits['vmax']

    scale_min = max(scale_min, vmin)
    scale_max = min(scale_max, vmax)

    values = nodes[metric]
    clipped = np.clip(values, scale_min, scale_max)

    trace = current_fig['data'][-1]['marker']
    trace['color'] = values
    trace['cmin'] = scale_min
    trace['cmax'] = scale_max

    return current_fig


# START
if __name__ == '__main__':
    app.run()
