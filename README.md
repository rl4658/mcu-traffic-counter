# MCU Traffic Counter

A real-time vehicle detection and counting system built with Python and OpenCV. Features a dark-themed GUI with two modes: a highly structured 4-Way Stop Intersection simulation and live camera detection.

## Requirements

- Python 3.8+
- `pip install opencv-python numpy Pillow flask requests`
- A webcam or Raspberry Pi camera (for Camera mode only)

## Running

This application utilizes a decoupled client-server architecture to provide both the main GUI simulation and a live web dashboard.

**1. Generate Target Videos (Optional)**
If you want to tweak or recreate the scripted video simulation loops, you can use the macro script to inject changes recursively and bake out the `.mp4` artifacts across all severity scenarios:
```bash
python make_scripts.py
python intersection_generator_low.py
python intersection_generator_medium.py
python intersection_generator_high.py
```

**2. Start the Backend Web Server**
```bash
python server.py
```
> The dashboard will be available at `http://127.0.0.1:5000`

**3. Start the Client GUI**
In a new terminal window, run:
```bash
python main.py
```

A launcher window opens. Choose a mode:

| Mode | Description |
|------|-------------|
| **Simulation** | Animated, strictly logical 4-way stop intersection — no hardware needed |
| **Camera (iPad)** | Live camera feed with road-line detection overlay and vehicle counting |

## How It Works

### Simulation Environment Generators
- Renders a visually robust 4-way intersection (dark asphalt, white stop lines, yellow center dividers, and grass bounds) using instances of `intersection_generator.py`.
- Includes sophisticated `cv2` graphical flourishes like pseudo-3D drop shadows beneath the vehicles.
- Simulation generator loops are specifically timed (`DURATION_SEC`) to dump massive load test counts while dynamically halting spawning near the end of the video timeline to allow all stopped queues to fully resolve prior to looping.

### Flow Logic (4-Way Stop & Go)
- Operates on strict **4-Way Stop Sign Queueing**, utilizing an intelligent FIFO-based geometric arbitration.
- A **precomputed conflict matrix** evaluates intersecting Bezier curve paths to flawlessly direct the intersection. If routes clash, cars gracefully stop and queue up perfectly behind one another via active `dist` radar until their geometric path clears!
- Motion detection picks up moving cars via background subtraction against the simulated environment.

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

### Severity Level Tracker
Updates dynamically based entirely on **waiting vehicles** in the queues rather than actively moving cars:
- 🟢 **Low** — less than 2 cars waiting
- 🟡 **Medium** — 2–3 cars waiting
- 🔴 **High** — 4+ fully gridlocking the intersection

### Web Dashboard & IoT Reporting
- A background thread polls the local `server.py` via HTTP `POST` every 60 seconds with payload data.
- The server records the traffic stat history without blocking the `main.py` client visual loops.
- Displays congestion data securely as responsive human-readable text logic strings ("Medium", "High") across custom Glassmorphism UI badges.
- View the styled visual dashboard by navigating your local browser to the host machine's port `5000`.

## Project Structure

```
mcu-traffic-counter/
├── main.py                          # GUI app — launcher, video detection, counting, HTTP agent
├── server.py                        # API Aggregator & dynamic HTML web dashboard server  
├── intersection_generator.py        # Base simulation rendering logic
├── make_scripts.py                  # Build macro injecting variables to spit out the tier-scripts below
├── intersection_generator_low.py    # Sparse traffic simulation generator
├── intersection_generator_medium.py # Typical traffic simulation generator
└── intersection_generator_high.py   # Heavy gridlock congestion generator + timed queue flushing
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `opencv-python` | Video capture, image processing, Hough lines, contour detection, drawing |
| `numpy` | Frame background subtraction and mathematical matrix masking |
| `Pillow` | Embedding OpenCV frames natively into the tkinter GUI |
| `flask` | Aggregation API server and serving the live web dashboard template |
| `requests` | Non-blocking synchronous HTTP reporting agent inside client threads |
