
import re
import time
from pathlib import Path
import os
from typing import Dict, Tuple
from importlib import import_module
from importlib import import_module
from pathlib import Path
import time

import numpy as np
from flask import Flask, jsonify, request, send_from_directory, send_file
from clawpack.clawutil import runclaw
from clawpack.geoclaw import dtopotools, topotools
from clawpack.visclaw import plotclaw

NUM_FRAMES = 6

BASE_DIR = Path(__file__).resolve().parent
RUNS_DIR = BASE_DIR / "web_runs"
RUNS_DIR.mkdir(exist_ok=True)

TSUNAMI_REGISTRY: Dict[str, dict] = {
    # 2010 chile 
    "chile2010": {
        "name": "Chile 2010 earthquake",
        "kind": "earthquake_okada",
        "tfinal_hours": 2,
        "map_key": "etopo1",
        "coarsen": 2,
        "dtopo_nx": 200,
        "dtopo_ny": 200,
        "times": [1.0],
        "subfault": {
            "strike_deg": 16.0,
            "dip_deg": 14.0,
            "rake_deg": 90.0,
            "slip_m": 15.0,
            "length_m": 450e3,
            "width_m": 100e3,
            "depth_m": 35e3,
            "coordinate_specification": "top center",
        },
    },

    # 2004 indian ocean earthquake
    "sumatra2004": {
        "name": "2004 Sumatra–Andaman earthquake",
        "kind": "earthquake_okada",
        "tfinal_hours": 2,
        "map_key": "etopo1",
        "coarsen": 2,
        "dtopo_nx": 200,
        "dtopo_ny": 200,
        "times": [1.0],
        "subfault": {
            "strike_deg": 329,
            "dip_deg": 8,
            "rake_deg": 110,
            "slip_m": 20,
            "length_m": 1500000,
            "width_m": 150000,
            "depth_m": 30000,
            "coordinate_specification": "top center",
        },
    },

    # 2011 Japan earthquake
    "tohoku2011": {
        "name": "2011 Tohoku earthquake",
        "kind": "earthquake_okada",
        "tfinal_hours": 2,
        "map_key": "etopo1",
        "coarsen": 2,
        "dtopo_nx": 200,
        "dtopo_ny": 200,
        "times": [1.0],
        "subfault": {
            "strike_deg": 193,
            "dip_deg": 9,
            "rake_deg": 78,
            "slip_m": 55,
            "length_m": 400000,
            "width_m": 150000, 
            "depth_m": 29000,
            "coordinate_specification": "top center",
        },
    },

    # Large megastunami
    "ultra_megaquake": {
        "name": "Hypothetical Tsunami (really bad)",
        "kind": "earthquake_okada",
        "tfinal_hours": 2,
        "map_key": "etopo1",
        "coarsen": 2,
        "dtopo_nx": 200,
        "dtopo_ny": 200,
        "times": [1.0],
        "subfault": {
            "strike_deg": 10.0,
            "dip_deg": 8.0,
            "rake_deg": 90.0,
            "slip_m": 120,
            "length_m": 2000000,   # 2000 km
            "width_m": 200000,     # 200 km
            "depth_m": 35000,      # 35 km depth
            "coordinate_specification": "top center",
        },
    },
}


# helpers with plot using setplot.py
def list_plot_frames(plotdir: Path):
    """Return sorted list of frame numbers by scanning for PNG files."""
    frames = []
    if not plotdir.exists():
        return frames
    
    for f in plotdir.iterdir():
        m = re.match(r"frame(\d{4})fig0\.png$", f.name)
        if m:
            frames.append(int(m.group(1)))
    return sorted(frames)


def read_frame_time(outdir: Path, frameno: int) -> float:
    """
    Read the time from fort.tXXXX without loading the full fort.q grid.
    """
    tfile = outdir / f"fort.t{frameno:04d}"
    if not tfile.exists():
        return None
    
    try:
        with tfile.open() as f:
            line = f.readline().strip()
        return float(line.split()[0])
    except Exception:
        return None


# topo creation
def fetch_topo_for_extent(
    extent: Tuple[float, float, float, float],
    topo_dir: Path,
    dataset_key: str = "etopo1",
    coarsen: int = 1,
) -> str:
    topo_dir.mkdir(parents=True, exist_ok=True)
    xlower, xupper, ylower, yupper = extent

    # Make filename stable & cacheable:
    tag = f"{xlower:.3f}_{xupper:.3f}_{ylower:.3f}_{yupper:.3f}_{dataset_key}_c{coarsen}"
    tag = tag.replace("-", "m").replace(".", "p")
    fname = topo_dir / f"topo_{tag}.tt3"
    if fname.exists():
        return str(fname)

    topo = topotools.read_netcdf(
        dataset_key,
        extent=[xlower, xupper, ylower, yupper],
        coarsen=coarsen,
        verbose=True,
    )
    topo.write(str(fname), topo_type=3, Z_format="%.1f")
    return str(fname)

# make disruption topography
# Create dtopo tt3 from a single Okada subfault centered at the clicked lon/lat.
# Grid for dtopo matches the GUI extent (and dtopo_nx/ny from the tsunami template).
def make_dtopo_single_fault(
    extent: Tuple[float, float, float, float],
    fault_lonlat: Tuple[float, float],
    tsunami_cfg: dict,
    out_dir: Path,
) -> str:
    xlower, xupper, ylower, yupper = extent
    lon, lat = fault_lonlat

    nx = int(tsunami_cfg.get("dtopo_nx", 240))
    ny = int(tsunami_cfg.get("dtopo_ny", 240))
    x = np.linspace(xlower, xupper, nx)
    y = np.linspace(ylower, yupper, ny)

    subcfg = tsunami_cfg["subfault"]
    sub = dtopotools.SubFault()
    sub.strike = float(subcfg.get("strike_deg", 0.0))
    sub.dip = float(subcfg.get("dip_deg", 10.0))
    sub.rake = float(subcfg.get("rake_deg", 90.0))
    sub.slip = float(subcfg.get("slip_m", 1.0))
    sub.length = float(subcfg.get("length_m", 100e3))
    sub.width = float(subcfg.get("width_m", 50e3))
    sub.depth = float(subcfg.get("depth_m", 10e3))
    sub.longitude = float(lon)
    sub.latitude = float(lat)
    sub.coordinate_specification = subcfg.get("coordinate_specification", "top center")

    fault = dtopotools.Fault()
    fault.subfaults = [sub]

    try:
        print(f"[dtopo] Mw ~ {fault.Mw():.3f}")
    except Exception:
        pass

    times = tsunami_cfg.get("times", [0.0, 1.0])
    fault.create_dtopography(x, y, times=times)

    dtopo_path = out_dir / "dtopo_user_fault.tt3"
    fault.dtopo.write(str(dtopo_path), dtopo_type=3)
    return str(dtopo_path)

# run geoclaw
def run_geoclaw(lon_fault: float,
                        lat_fault: float,
                        extent,
                        template: str):

    x0, x1, y0, y1 = map(float, extent)


    extent_tuple = (x0, x1, y0, y1)

    # gather the config for the tsunami
    if template not in TSUNAMI_REGISTRY:
        raise KeyError(f"Unknown tsunami template: {template!r}")
    tsunami_cfg = TSUNAMI_REGISTRY[template]

    # generate directories to store the output
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    run_id = f"{timestamp}_{template}_run"
    run_dir = RUNS_DIR / run_id
    outdir = run_dir / "_output"
    plotdir = run_dir / "_plots"
    topo_dir = run_dir / "topo"

    run_dir.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(parents=True, exist_ok=True)
    topo_dir.mkdir(parents=True, exist_ok=True)
    plotdir.mkdir(parents=True, exist_ok=True)


    # build default rundata
    base_setrun = import_module("setrun").setrun
    rundata = base_setrun("geoclaw")

    # 4. Override domain & basic settings
    clawdata = rundata.clawdata

    # Domain bounds (lon,lat)
    clawdata.lower[0] = x0
    clawdata.upper[0] = x1
    clawdata.lower[1] = y0
    clawdata.upper[1] = y1

    # number of frames to generate
    clawdata.num_output_times = NUM_FRAMES
    #resolution
    nx = int(tsunami_cfg.get("dtopo_nx", 240))
    ny = int(tsunami_cfg.get("dtopo_ny", 240))
    clawdata.num_cells[0] = nx
    clawdata.num_cells[1] = ny

    # Final simulation time (seconds)
    clawdata.tfinal = float(tsunami_cfg["tfinal_hours"]) * 3600.0
 
    # Topography
    topo_file = fetch_topo_for_extent(extent_tuple, topo_dir=topo_dir, dataset_key=tsunami_cfg["map_key"], coarsen=1)
    rundata.topo_data.topofiles = [[3, topo_file]]

    # Dtopo (earthquake deformation from clicked point)
    dtopo_file = make_dtopo_single_fault(
        extent_tuple,
        (lon_fault, lat_fault),
        tsunami_cfg,
        out_dir=run_dir,
    )
    rundata.dtopo_data.dtopofiles = [[3, dtopo_file]]

    ## run the simulation exe
    xgeoclaw_path = BASE_DIR / "xgeoclaw"
    if not xgeoclaw_path.exists():
        raise FileNotFoundError(
            f"xgeoclaw not found at {xgeoclaw_path}. "
            "Make sure you ran `make .exe` or `make xgeoclaw` in the Tsunami dir."
        )

    cwd = os.getcwd()
    try:

        os.chdir(run_dir)

        # write all output files into run_dir
        rundata.write()

        # run xgeoclaw using run files
        runclaw.runclaw(
            xclawcmd=str(xgeoclaw_path),
            outdir=str(outdir),
            overwrite=True,
        )
        
        # generate plots
        print(f"Generating plots in {plotdir}")
        plotclaw.plotclaw(
            outdir=str(outdir),
            plotdir=str(plotdir),
            setplot=str(BASE_DIR / "setplot.py")
        )
        print(f"Plots generated successfully")
        
    finally:
        os.chdir(cwd)

    return run_id, outdir

# generate website usign flask
app = Flask(__name__, static_folder=str(BASE_DIR))


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

# for template selection
# returns available tsunami templates
@app.route("/api/templates", methods=["GET"])
def api_templates():
    templates = []
    for key, config in TSUNAMI_REGISTRY.items():
        templates.append({
            "id": key,
            "name": config.get("name", key)
        })
    return jsonify({"templates": templates})

# to show a previosuly run simulation
# lists available runs
@app.route("/api/runs", methods=["GET"])
def api_list_runs():
    runs = []
    if not RUNS_DIR.exists():
        return jsonify({"runs": runs})

    # show directories with most recent above
    for sub in sorted(RUNS_DIR.iterdir(), reverse=True):
        if not sub.is_dir():
            continue
        
        plotdir = sub / "_plots"
        if not plotdir.exists():
            continue

        frames = list_plot_frames(plotdir)
        if not frames:
            continue

        runs.append(
            {
                "run_id": sub.name,
                "n_frames": len(frames),
                "meta": {},
            }
        )

    return jsonify({"runs": runs})

# simulates a tsunami for given fault location and extent
@app.route("/api/simulate", methods=["POST"])
def simulate():
    data = request.get_json(force=True)
    lon = float(data["lon"])
    lat = float(data["lat"])
    extent = data["extent"]
    template = data["template"]
    x0 = float(extent["west"])
    x1 = float(extent["east"])
    y0 = float(extent["south"])
    y1 = float(extent["north"])

    # Run simulation and generate plots
    run_id, outdir = run_geoclaw(
        lon_fault=lon,
        lat_fault=lat,
        extent=[x0, x1, y0, y1],
        template=template,
    )

    # Get frames from plot files
    run_dir = RUNS_DIR / run_id
    plotdir = run_dir / "_plots"
    frames = list_plot_frames(plotdir)
    
    times = []
    for n in frames:
        t = read_frame_time(outdir, n)
        times.append({"frame": n, "t": t})

    return jsonify(
        {
            "run_id": run_id,
            "frames": times,
        }
    )


# serve png plot files from plots directory
@app.route("/run/<run_id>/plots/<path:filename>")
def serve_plot(run_id, filename):
    run_dir = RUNS_DIR / run_id
    plot_file = run_dir / "_plots" / filename
    
    if not plot_file.exists():
        return jsonify({"error": f"Plot file not found: {filename}"}), 404
    
    return send_file(plot_file, mimetype='image/png')


@app.route("/api/run/<run_id>/summary", methods=["GET"])
def api_run_summary(run_id):
    run_dir = RUNS_DIR / run_id
    plotdir = run_dir / "_plots"
    outdir = run_dir / "_output"

    if not plotdir.exists():
        return jsonify({"error": f"Plots dir not found: {plotdir}"}), 404


    frames = list_plot_frames(plotdir)
    frame_meta = []
    for fno in frames:
        t = read_frame_time(outdir, fno) if outdir.exists() else None
        frame_meta.append({"frame": fno, "t": t})

    return jsonify(
        {
            "run_id": run_id,
            "frames": frame_meta,
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)


