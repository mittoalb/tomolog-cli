import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objects as go
import numpy as np
import os
import subprocess
import threading
import glob
import socket
import ipaddress
import re
from datetime import datetime

# Optional imports with fallbacks
try:
    import h5py
    HAS_H5PY = True
except ImportError:
    HAS_H5PY = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import tifffile
    HAS_TIFFFILE = True
except ImportError:
    HAS_TIFFFILE = False

try:
    from skimage.transform import resize
    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False

app = dash.Dash(__name__)

def check_ip_type():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        ip_obj = ipaddress.ip_address(local_ip)
        is_private = ip_obj.is_private
        
        return 'private' if is_private else 'public'
    except:
        return 'private'

# Global state
app_state = {
    'logs': [],
    'status': 'Ready',
    'process_running': False,
    'current_process': None,
    'preview_data': None,
    'preview_data_original': None,
    'preview_file': None,
    'file_info': {},
    'ip_type': check_ip_type(),
    'roi_coords': None
}

def add_log(message):
    timestamp = datetime.now().strftime('%H:%M:%S')
    app_state['logs'].append(f"{timestamp} - {message}")
    if len(app_state['logs']) > 50:
        app_state['logs'] = app_state['logs'][-50:]

def get_slides_path(url):
    """Return the full slides URL/path as provided"""
    if not url:
        return None
    
    # Just return the full URL as provided
    add_log(f"Using slides path: {url}")
    return url

def get_slice_count(file_path):
    """Get the number of available slices from the reconstruction directory"""
    if not file_path:
        return 100
    
    try:
        # For preview, use the first file from template
        if '{}' in file_path:
            preview_file = file_path.format(657)  # Use default number
        else:
            preview_file = file_path
        
        # Try reconstruction directory first
        if preview_file.endswith('.h5') and 'rec' not in preview_file:
            path_parts = preview_file.split('/')
            base_dir = '/'.join(path_parts[:-2])
            experiment_dir = path_parts[-2]
            filename = path_parts[-1]
            base_name = os.path.splitext(filename)[0]
            rec_name = f"{base_name}_rec"
            rec_dir = f"{experiment_dir}_rec"
            rec_path = os.path.join(base_dir, rec_dir, rec_name)
            
            if os.path.exists(rec_path):
                preview_file = rec_path
        
        # Count TIFF files in directory
        if os.path.isdir(preview_file):
            tiff_files = []
            for pattern in ['*.tif', '*.tiff', '*.TIF', '*.TIFF']:
                tiff_files.extend(glob.glob(os.path.join(preview_file, pattern)))
            
            if tiff_files:
                add_log(f"Found {len(tiff_files)} TIFF files for slice range")
                return len(tiff_files)
        
        # Check H5 file dimensions
        elif preview_file.endswith('.h5') and HAS_H5PY:
            with h5py.File(preview_file, 'r') as f:
                possible_paths = ['exchange/data', 'data', 'tomo', 'reconstruction']
                
                for path in possible_paths:
                    if path in f:
                        data_array = f[path]
                        if len(data_array.shape) == 3:
                            add_log(f"Found {data_array.shape[0]} slices in H5 file")
                            return data_array.shape[0]
                        break
                
                # Search for any 3D dataset
                for key in f.keys():
                    if isinstance(f[key], h5py.Dataset) and len(f[key].shape) == 3:
                        add_log(f"Found {f[key].shape[0]} slices in H5 dataset: {key}")
                        return f[key].shape[0]
        
        add_log("Could not determine slice count, using default 100")
        return 100
        
    except Exception as e:
        add_log(f"Error getting slice count: {str(e)}")
        return 100

def load_image_for_preview(file_path, slice_num):
    """Load image data for preview only - no processing"""
    if not file_path:
        return None
    
    try:
        # Try reconstruction directory first
        if file_path.endswith('.h5') and 'rec' not in file_path:
            path_parts = file_path.split('/')
            base_dir = '/'.join(path_parts[:-2])
            experiment_dir = path_parts[-2]
            filename = path_parts[-1]
            base_name = os.path.splitext(filename)[0]
            rec_name = f"{base_name}_rec"
            rec_dir = f"{experiment_dir}_rec"
            rec_path = os.path.join(base_dir, rec_dir, rec_name)
            
            if os.path.exists(rec_path):
                add_log(f"Using reconstruction directory: {rec_path}")
                file_path = rec_path
        
        # Load from TIFF directory
        if os.path.isdir(file_path):
            tiff_files = []
            for pattern in ['*.tif', '*.tiff', '*.TIF', '*.TIFF']:
                tiff_files.extend(glob.glob(os.path.join(file_path, pattern)))
            
            if not tiff_files:
                add_log("No TIFF files found")
                return None
            
            tiff_files.sort()
            slice_idx = min(slice_num, len(tiff_files) - 1)
            selected_file = tiff_files[slice_idx]
            
            if HAS_TIFFFILE:
                data = tifffile.imread(selected_file)
            elif HAS_PIL:
                data = np.array(Image.open(selected_file))
            else:
                add_log("No TIFF library available")
                return None
        
        # Load from H5 file
        elif file_path.endswith('.h5') and HAS_H5PY:
            with h5py.File(file_path, 'r') as f:
                possible_paths = ['exchange/data', 'data', 'tomo', 'reconstruction']
                data_array = None
                
                for path in possible_paths:
                    if path in f:
                        data_array = f[path]
                        break
                
                if data_array is None:
                    for key in f.keys():
                        if isinstance(f[key], h5py.Dataset) and len(f[key].shape) >= 2:
                            data_array = f[key]
                            break
                
                if data_array is None:
                    add_log("No data found in H5 file")
                    return None
                
                if len(data_array.shape) == 3:
                    slice_idx = min(slice_num, data_array.shape[0] - 1)
                    data = data_array[slice_idx, :, :]
                else:
                    data = data_array[:, :]
        else:
            add_log("Unsupported file type")
            return None
        
        # Basic normalization for display
        data = np.array(data, dtype=np.float32)
        if data.max() > data.min():
            data = (data - data.min()) / (data.max() - data.min())
        
        # Resize if too large
        if data.shape[0] > 512 or data.shape[1] > 512:
            if HAS_SKIMAGE:
                data = resize(data, (min(512, data.shape[0]), min(512, data.shape[1])))
        
        add_log(f"Loaded image: {data.shape}")
        return data
        
    except Exception as e:
        add_log(f"Error loading image: {str(e)}")
        return None

def generate_file_list(file_template, start, count):
    """Generate list of files based on template and range"""
    if not file_template or '{}' not in file_template:
        return [file_template] if file_template else []
    
    file_list = []
    for i in range(count):
        file_number = start + i  # Sequential numbering
        file_path = file_template.format(file_number)
        file_list.append(file_path)
    
    return file_list

def run_tomolog_cli(params):
    """Run tomolog on multiple files with same parameters"""
    try:
        app_state['process_running'] = True
        app_state['status'] = 'Running tomolog...'
        
        # Generate file list
        file_list = generate_file_list(
            params.get('file_template'),
            params.get('file_start', 1),
            params.get('file_count', 1)
        )
        
        if not file_list:
            add_log("No files to process")
            return
        
        add_log(f"Processing {len(file_list)} files")
        
        # Get common parameters
        slides_path = get_slides_path(params.get('slides_url'))
        
        # Process each file
        for i, file_path in enumerate(file_list):
            if not app_state['process_running']:  # Check if stopped
                add_log("Process stopped by user")
                break
                
            add_log(f"Processing file {i+1}/{len(file_list)}: {os.path.basename(file_path)}")
            
            # Build command for this file
            cmd = ["tomolog", "run"]
            cmd.extend(["--file", file_path])
            
            if slides_path:
                cmd.extend(["--presentation-url", slides_path])
            
            if params.get('min_intensity') is not None:
                cmd.extend(["--min-intensity", str(params['min_intensity'])])
            
            if params.get('max_intensity') is not None:
                cmd.extend(["--max-intensity", str(params['max_intensity'])])
            
            if params.get('slice_number') is not None:
                cmd.extend(["--slice", str(params['slice_number'])])
            
            if params.get('roi_coords'):
                roi = params['roi_coords']
                cmd.extend(["--roi", f"{roi['x0']},{roi['y0']},{roi['x1']},{roi['y1']}"])
            
            if params.get('visibility') == 'public':
                cmd.extend(["--public", "True"])
                
            cmd.extend(["--cloud-service", "aps"])
            cmd_str = " ".join(cmd)
            add_log(f"Command: {cmd_str}")
            
            # Execute command
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                universal_newlines=True,
                bufsize=1
            )
            
            app_state['current_process'] = process
            
            
            ANSI_ESCAPE = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
            # Read output line by line
            for line in iter(process.stdout.readline, ''):
                if line:
                    add_log(ANSI_ESCAPE.sub('', line.rstrip()))
            
            # Wait for process to complete
            process.wait()
            return_code = process.returncode
            
            if return_code == 0:
                add_log(f"File {i+1} completed successfully")
            else:
                add_log(f"File {i+1} failed with code {return_code}")
                if params.get('stop_on_error', False):
                    add_log("Stopping due to error")
                    break
        
        # Final status
        if app_state['process_running']:
            add_log("All files processed successfully")
            app_state['status'] = "All files completed successfully"
        else:
            app_state['status'] = "Process stopped"
            
    except FileNotFoundError:
        add_log("tomolog command not found")
        app_state['status'] = "tomolog not installed"
    except Exception as e:
        add_log(f"Error: {str(e)}")
        app_state['status'] = f"Error: {str(e)}"
    finally:
        app_state['process_running'] = False
        app_state['current_process'] = None

# Layout
app.layout = html.Div([
    # Add interval for real-time updates
    dcc.Interval(
        id='interval-component',
        interval=1000,  # Update every second
        n_intervals=0
    ),
    
    # Header
    html.Div([
        html.H2("Tomolog Interface", style={'margin': 0, 'color': 'white'}),
        html.Span("Parameter Setup for tomolog", style={'color': '#aaa', 'fontSize': '14px'})
    ], style={
        'background': '#333',
        'padding': '15px 20px', 
        'marginBottom': '10px'
    }),
    
    # Main layout
    html.Div([
        # Left column - Controls
        html.Div([
            # File input
            html.Div([
                html.H4("Data File(s)", style={'color': '#e0e0e0', 'marginBottom': '8px'}),
                
                dcc.Input(id="file-path", placeholder="H5 file path template (use {} for number)", 
                         value="/data/32ID/2025-07/2025-07/Mittone/Allen_Particle_capillary_{}.h5",
                         style={'width': '100%', 'marginBottom': '8px', 'padding': '6px', 
                               'backgroundColor': '#444', 'color': 'white', 'border': '1px solid #666'}),
                
                html.Div([
                    html.Label("File Range:", style={'color': '#e0e0e0', 'fontSize': '12px', 'display': 'block', 'marginBottom': '4px'}),
                    html.Div([
                        dcc.Input(id="file-start", type="number", value=657, placeholder="Start",
                                 style={'width': '48%', 'marginRight': '4%', 'padding': '4px',
                                       'backgroundColor': '#444', 'color': 'white', 'border': '1px solid #666'}),
                        dcc.Input(id="file-count", type="number", value=1, placeholder="Count",
                                 style={'width': '48%', 'padding': '4px',
                                       'backgroundColor': '#444', 'color': 'white', 'border': '1px solid #666'})
                    ], style={'display': 'flex', 'marginBottom': '4px'}),
                    html.Div([
                        html.Span("Start: ", style={'color': '#aaa', 'fontSize': '11px'}),
                        html.Span(id="file-start-display", style={'color': '#e0e0e0', 'fontSize': '11px'}),
                        html.Span(" | End: ", style={'color': '#aaa', 'fontSize': '11px'}),
                        html.Span(id="file-end-display", style={'color': '#e0e0e0', 'fontSize': '11px'}),
                        html.Span(" | Total: ", style={'color': '#aaa', 'fontSize': '11px'}),
                        html.Span(id="file-total-display", style={'color': '#4fc3f7', 'fontSize': '11px'})
                    ])
                ])
            ], style={'backgroundColor': '#333', 'padding': '10px', 'borderRadius': '5px', 'marginBottom': '10px'}),
            
            # Parameters
            html.Div([
                html.H4("Parameters", style={'color': '#e0e0e0', 'marginBottom': '8px'}),
                
                html.Label("Slice Number:", style={'color': '#e0e0e0', 'fontSize': '12px'}),
                dcc.Slider(id="slice-slider", min=0, max=100, value=50, step=1,
                          marks={},  # Dynamic marks will be set by callback
                          tooltip={"placement": "bottom", "always_visible": True}),
                html.Div(id="slice-info", style={'color': '#aaa', 'fontSize': '11px', 'marginTop': '4px'}),
                
                html.Label("Min Intensity:", style={'color': '#e0e0e0', 'fontSize': '12px', 'marginTop': '8px', 'display': 'block'}),
                dcc.Slider(id="min-intensity", min=0, max=1, value=0, step=0.01,
                          marks={0: {'label': '0', 'style': {'color': '#aaa', 'fontSize': '9px'}},
                                1: {'label': '1', 'style': {'color': '#aaa', 'fontSize': '9px'}}},
                          tooltip={"placement": "bottom", "always_visible": True}),
                
                html.Label("Max Intensity:", style={'color': '#e0e0e0', 'fontSize': '12px', 'marginTop': '6px', 'display': 'block'}),
                dcc.Slider(id="max-intensity", min=0, max=1, value=1, step=0.01,
                          marks={0: {'label': '0', 'style': {'color': '#aaa', 'fontSize': '9px'}},
                                1: {'label': '1', 'style': {'color': '#aaa', 'fontSize': '9px'}}},
                          tooltip={"placement": "bottom", "always_visible": True}),
                
                html.Div(id="roi-info", style={'marginTop': '10px', 'color': '#aaa', 'fontSize': '12px'})
            ], style={'backgroundColor': '#333', 'padding': '10px', 'borderRadius': '5px', 'marginBottom': '10px'}),
            
            # Google settings
            html.Div([
                html.H4("Google Settings", style={'color': '#e0e0e0', 'marginBottom': '8px'}),
                
                dcc.Input(id="slides-url", placeholder="Google Slides URL",
                         value="https://docs.google.com/presentation/d/13-4469-a4b0-91f35a517985/edit",
                         style={'width': '100%', 'marginBottom': '6px', 'padding': '6px',
                               'backgroundColor': '#444', 'color': 'white', 'border': '1px solid #666'}),
                
                html.Div([
                    html.Label(f"Visibility (auto-detected: {app_state['ip_type']}):", 
                              style={'color': '#e0e0e0', 'fontSize': '12px', 'display': 'block', 'marginBottom': '4px'}),
                    dcc.RadioItems(id="visibility",
                                 options=[
                                     {'label': ' Public', 'value': 'public'},
                                     {'label': ' Private', 'value': 'private'}
                                 ],
                                 value=app_state['ip_type'],
                                 style={'color': '#e0e0e0', 'fontSize': '12px'},
                                 labelStyle={'marginRight': '10px', 'display': 'inline-block'})
                ])
            ], style={'backgroundColor': '#333', 'padding': '10px', 'borderRadius': '5px', 'marginBottom': '10px'}),
            
            # Buttons
            html.Div([
                html.Button("Load Preview", id="preview-btn", n_clicks=0,
                           style={'width': '48%', 'padding': '8px', 'margin': '1%', 'backgroundColor': '#007bff', 
                                 'color': 'white', 'border': 'none', 'borderRadius': '4px', 'fontWeight': 'bold'}),
                html.Button("Run tomolog", id="run-btn", n_clicks=0,
                           style={'width': '48%', 'padding': '8px', 'margin': '1%', 'backgroundColor': '#28a745', 
                                 'color': 'white', 'border': 'none', 'borderRadius': '4px', 'fontWeight': 'bold'}),
                html.Button("Stop", id="stop-btn", n_clicks=0,
                           style={'width': '98%', 'padding': '8px', 'margin': '1%', 'backgroundColor': '#dc3545', 
                                 'color': 'white', 'border': 'none', 'borderRadius': '4px', 'fontWeight': 'bold'})
            ], style={'textAlign': 'center'})
            
        ], style={'width': '25%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '10px'}),
        
        # Middle column - Preview
        html.Div([
            html.Div(id="status", style={
                'padding': '8px', 'backgroundColor': '#444', 'color': '#e0e0e0', 
                'borderRadius': '4px', 'marginBottom': '10px', 'fontSize': '14px'
            }),
            
            html.Div([
                html.H4("Image Preview (Draw ROI)", style={'color': '#e0e0e0', 'marginBottom': '8px'}),
                html.Div(id="preview-container", style={'height': '400px'})
            ])
            
        ], style={'width': '40%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '10px'}),
        
        # Right column - Console
        html.Div([
            html.H4("Console Output", style={'color': '#e0e0e0', 'marginBottom': '10px'}),
            
            html.Pre(id="logs", style={
                'backgroundColor': '#2d2d2d', 'color': '#e0e0e0', 'padding': '12px',
                'borderRadius': '4px', 'fontSize': '12px', 'height': '420px',
                'overflow': 'auto', 'fontFamily': 'monospace', 'margin': 0,
                'border': '1px solid #444'
            })
            
        ], style={'width': '30%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '10px'})
        
    ], style={'height': '80vh'})
    
], style={
    'backgroundColor': '#1a1a1a', 'color': '#e0e0e0', 'minHeight': '100vh',
    'fontFamily': 'system-ui, -apple-system, sans-serif', 'margin': 0, 'padding': 0
})

# Slice range callback
@app.callback(
    [Output('slice-slider', 'max'),
     Output('slice-slider', 'value'),
     Output('slice-slider', 'marks'),
     Output('slice-info', 'children')],
    [Input('file-path', 'value')]
)
def update_slice_range(file_path):
    slice_count = get_slice_count(file_path)
    
    # Set reasonable marks
    if slice_count <= 10:
        marks = {i: {'label': str(i), 'style': {'color': '#aaa', 'fontSize': '10px'}} 
                for i in range(0, slice_count, 1)}
    elif slice_count <= 100:
        step = max(1, slice_count // 10)
        marks = {i: {'label': str(i), 'style': {'color': '#aaa', 'fontSize': '10px'}} 
                for i in range(0, slice_count, step)}
    else:
        step = max(1, slice_count // 10)
        marks = {i: {'label': str(i), 'style': {'color': '#aaa', 'fontSize': '10px'}} 
                for i in range(0, slice_count, step)}
    
    # Ensure we have marks at 0 and max
    marks[0] = {'label': '0', 'style': {'color': '#aaa', 'fontSize': '10px'}}
    marks[slice_count - 1] = {'label': str(slice_count - 1), 'style': {'color': '#aaa', 'fontSize': '10px'}}
    
    # Set initial value to middle
    initial_value = min(50, slice_count // 2)
    
    info_text = f"Available slices: 0 to {slice_count - 1} (total: {slice_count})"
    
    return slice_count - 1, initial_value, marks, info_text

# File count callback
@app.callback(
    [Output('file-start-display', 'children'),
     Output('file-end-display', 'children'),
     Output('file-total-display', 'children')],
    [Input('file-start', 'value'),
     Input('file-count', 'value')]
)
def update_file_range_display(start, count):
    if start is not None and count is not None and count > 0:
        end = start + count - 1
        return str(start), str(end), f"{count} files"
    return "—", "—", "0 files"

# Preview callback with real-time intensity updates
@app.callback(
    [Output('preview-container', 'children'),
     Output('roi-info', 'children')],
    [Input('preview-btn', 'n_clicks'),
     Input('slice-slider', 'value'),
     Input('min-intensity', 'value'),
     Input('max-intensity', 'value')],
    [State('file-path', 'value')]
)
def update_preview(preview_clicks, slice_val, min_intensity, max_intensity, file_path):
    ctx = dash.callback_context
    
    # Check if we have cached preview data and only min/max changed
    if (app_state.get('preview_data_original') is not None and 
        ctx.triggered and 
        any('intensity' in trigger['prop_id'] for trigger in ctx.triggered)):
        
        # Just update the intensity scaling on existing data
        data = app_state['preview_data_original']  # Use original data
        
        # Apply new intensity clipping
        if max_intensity > min_intensity:
            data_display = np.clip((data - min_intensity) / (max_intensity - min_intensity), 0, 1)
        else:
            data_display = data
        
        app_state['preview_data'] = data_display
        
        # Get current preview file name
        preview_file = app_state.get('preview_file', 'current file')
        
    else:
        # Load new preview (only when preview button clicked or slice changed)
        if not ctx.triggered or 'preview-btn' not in str(ctx.triggered):
            return html.Div([
                html.H4("Click 'Load Preview' to view image", style={'color': '#aaa', 'textAlign': 'center'}),
                html.P("Preview not loaded for performance", style={'color': '#666', 'fontSize': '12px', 'textAlign': 'center'})
            ], style={'padding': '20px'}), "No preview loaded"
        
        # For preview, use the first file from template
        if '{}' in file_path:
            preview_file = file_path.format(657)  # Use default number for preview
        else:
            preview_file = file_path
        
        data = load_image_for_preview(preview_file, slice_val)
        
        if data is None:
            return html.Div([
                html.H4("No Preview Available", style={'color': '#ff6b6b', 'textAlign': 'center'}),
                html.P("Check file path", style={'color': '#aaa', 'fontSize': '12px', 'textAlign': 'center'})
            ], style={'padding': '20px'}), "No ROI selected"
        
        # Store original data for intensity updates
        app_state['preview_data_original'] = data.copy()
        app_state['preview_file'] = preview_file
        
        # Apply intensity clipping for display
        if max_intensity > min_intensity:
            data_display = np.clip((data - min_intensity) / (max_intensity - min_intensity), 0, 1)
        else:
            data_display = data
        
        app_state['preview_data'] = data_display
    
    fig = go.Figure()
    
    # Add image
    fig.add_trace(go.Heatmap(
        z=data_display,
        colorscale='Greys',
        showscale=True,
        hovertemplate='x: %{x}<br>y: %{y}<br>value: %{z}<extra></extra>'
    ))
    
    fig.update_layout(
        title=f"Preview: {os.path.basename(preview_file)}<br>Slice {slice_val} | Min: {min_intensity:.2f} Max: {max_intensity:.2f}<br>Draw rectangle to select ROI",
        height=400,
        width=400,
        template="plotly_dark",
        paper_bgcolor='#1a1a1a',
        plot_bgcolor='#1a1a1a',
        font=dict(color='#e0e0e0'),
        margin=dict(l=40, r=60, t=100, b=40),
        title_x=0.5,
        dragmode='drawrect',
        newshape=dict(
            line=dict(color='red', width=2),
            fillcolor='rgba(255, 0, 0, 0.1)'
        ),
        xaxis=dict(
            scaleanchor="y",
            scaleratio=1,
            constrain='domain'
        ),
        yaxis=dict(
            constrain='domain'
        )
    )
    
    graph = dcc.Graph(
        id='preview-graph',
        figure=fig,
        config={
            'modeBarButtonsToAdd': ['drawrect', 'eraseshape'],
            'displayModeBar': True
        }
    )
    
    roi_text = "Draw rectangle on image to select ROI (applies to all files)"
    
    return graph, roi_text

@app.callback(
    Output('roi-info', 'children', allow_duplicate=True),
    [Input('preview-graph', 'relayoutData')],
    prevent_initial_call=True
)
def update_roi(relayout_data):
    if relayout_data and 'shapes' in relayout_data:
        shapes = relayout_data['shapes']
        if shapes:
            shape = shapes[-1]  # Get latest shape
            if 'x0' in shape and 'x1' in shape and 'y0' in shape and 'y1' in shape:
                x0, x1 = int(shape['x0']), int(shape['x1'])
                y0, y1 = int(shape['y0']), int(shape['y1'])
                
                # Store ROI coordinates
                app_state['roi_coords'] = {
                    'x0': min(x0, x1), 'y0': min(y0, y1),
                    'x1': max(x0, x1), 'y1': max(y0, y1)
                }
                
                return f"ROI: ({min(x0,x1)}, {min(y0,y1)}) to ({max(x0,x1)}, {max(y0,y1)})"
    
    return "No ROI selected"

# Real-time log updates
@app.callback(
    [Output('logs', 'children'),
     Output('status', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_logs_realtime(n_intervals):
    logs_text = '\n'.join(app_state['logs'][-30:]) if app_state['logs'] else 'Ready to run tomolog'
    return logs_text, app_state['status']

# Button handlers
@app.callback(
    Output('interval-component', 'disabled'),
    [Input('run-btn', 'n_clicks'),
     Input('stop-btn', 'n_clicks')],
    [State('file-path', 'value'),
     State('file-start', 'value'),
     State('file-count', 'value'),
     State('slides-url', 'value'),
     State('slice-slider', 'value'),
     State('min-intensity', 'value'),
     State('max-intensity', 'value'),
     State('visibility', 'value')]
)
def handle_buttons(run_clicks, stop_clicks, file_template, file_start, file_count, 
                  slides_url, slice_val, min_intensity, max_intensity, visibility):
    ctx = dash.callback_context
    
    if ctx.triggered:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if button_id == 'run-btn' and run_clicks > 0:
            if file_template:
                params = {
                    'file_template': file_template,
                    'file_start': file_start or 1,
                    'file_count': file_count or 1,
                    'slides_url': slides_url,
                    'slice_number': slice_val,
                    'min_intensity': min_intensity,
                    'max_intensity': max_intensity,
                    'visibility': visibility,
                    'roi_coords': app_state.get('roi_coords')
                }
                
                file_list = generate_file_list(file_template, file_start or 1, file_count or 1)
                add_log(f"Starting tomolog on {len(file_list)} files")
                thread = threading.Thread(target=run_tomolog_cli, args=(params,))
                thread.daemon = True
                thread.start()
            else:
                add_log("No file template specified")
        
        elif button_id == 'stop-btn' and stop_clicks > 0:
            if app_state['current_process']:
                app_state['current_process'].terminate()
                add_log("Process terminated")
            else:
                add_log("No process to stop")
            
            app_state['process_running'] = False
            app_state['current_process'] = None
    
    return False  # Keep interval enabled

if __name__ == "__main__":
    print("Starting Tomolog Interface...")
    print("Available at: http://localhost:8050")
    
    try:
        app.run(debug=False, host="0.0.0.0", port=9000)
    except Exception as e:
        print(f"Port 8050 failed: {e}")
        try:
            app.run(debug=False, host="127.0.0.1", port=9001)
        except Exception as e2:
            print(f"Port 8051 failed: {e2}")
            app.run(debug=False, host="127.0.0.1", port=9002)
