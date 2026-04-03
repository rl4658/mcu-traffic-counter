# MCU Traffic Counter

A real-time vehicle detection and counting system built with Python and OpenCV. Features a dark-themed GUI with two modes: a scripted intersection simulation and live camera detection (designed for a Raspberry Pi camera pointed at an iPad).

## Requirements

- Python 3.8+
- `pip install opencv-python numpy Pillow`
- A webcam or Raspberry Pi camera (for Camera mode only)

## Running

```bash
python main.py
```

A launcher window opens. Choose a mode:

| Mode | Description |
|------|-------------|
| **Simulation** | Animated 4-way intersection with scripted cars — no hardware needed |
| **Camera (iPad)** | Live camera feed with road-line detection overlay and vehicle counting |

## How It Works

### Simulation Mode
- Renders a top-down 4-way intersection using `intersection_generator.py`
- Cars follow scripted paths (straight, left turn, right turn) across all 8 routes
- Motion detection picks up moving cars via background subtraction

### Camera Mode
- Designed for a camera pointed at an iPad playing the intersection simulation
- **Hough Line Transform** detects road/lane lines and overlays them in real time
- Motion detection tracks vehicles as they move through the frame

### Counting Logic (both modes)
- A **4-gate intersection box** sits in the center of the frame
- Vehicles are counted when their centroid crosses a gate from outside to inside:
  - **N** (red line) — vehicle enters from the top
  - **S** (yellow line) — vehicle enters from the bottom
  - **W** (magenta line) — vehicle enters from the left
  - **E** (cyan line) — vehicle enters from the right
- Each vehicle gets a unique ID and is counted only once

### Severity
Updates live based on total count:
- 🟢 **Low** — fewer than 5
- 🟡 **Medium** — 5–14
- 🔴 **High** — 15+

## Project Structure

```
mcu-traffic-counter/
├── main.py                    # GUI app — launcher, camera loop, detection, counting
└── intersection_generator.py  # Generates the synthetic intersection animation frames
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `opencv-python` | Video capture, image processing, Hough lines, contour detection |
| `numpy` | Frame and mask operations |
| `Pillow` | Embedding OpenCV frames into the tkinter GUI |
