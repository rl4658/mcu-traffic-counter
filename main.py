# pip install Pillow   (required once for embedding OpenCV frames in tkinter)
import cv2
import numpy as np
import time
import math
import platform
import tkinter as tk
from PIL import Image, ImageTk
import intersection_generator as inters5

# ── Theme ──────────────────────────────────────────────────────────────────────
BG       = "#0d0d1a"
BG2      = "#13132b"
BG3      = "#1c1c3a"
ACCENT   = "#4e9af1"
ACCENT2  = "#7b68ee"
TEXT     = "#e8e8f0"
TEXT_DIM = "#5a5a7a"
BORDER   = "#2a2a4a"
SEV_GREEN  = "#2ecc71"
SEV_YELLOW = "#f1c40f"
SEV_RED    = "#e74c3c"

# ── Constants ──────────────────────────────────────────────────────────────────
FRAME_W       = 640
FRAME_H       = 480
SIDEBAR_W     = 260
MAX_GONE      = 12
MATCH_DIST    = 60
LOW_THRESH    = 5
MED_THRESH    = 15
KERNEL        = np.ones((5, 5), np.uint8)

# Default fallback intersection box parameters
DEF_BOX_X1, DEF_BOX_Y1 = 255, 153
DEF_BOX_X2, DEF_BOX_Y2 = 385, 327
GATE_BAND   = 15


# ══════════════════════════════════════════════════════════════════════════════
class TrafficApp:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MCU Traffic Counter")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.minsize(640, 400)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # runtime state
        self.mode      = None
        self.cap       = None
        self.fgbg      = None
        self.running   = False
        self._after_id = None

        self._reset_state()
        self._show_launcher()
        self.root.mainloop()

    # ── State reset ────────────────────────────────────────────────────────────
    def _reset_state(self):
        self.objects    = {}
        self.next_id    = 0
        self.count      = 0
        self.count_n    = 0
        self.count_s    = 0
        self.count_w    = 0
        self.count_e    = 0
        self.congestion = 0
        self.frame_num  = 0
        self.inters_sim = None
        
        # Dynamic Box Bounds (capable of lerping towards Hough lines)
        self.box_x1 = DEF_BOX_X1
        self.box_y1 = DEF_BOX_Y1
        self.box_x2 = DEF_BOX_X2
        self.box_y2 = DEF_BOX_Y2

    # ── Launcher screen ────────────────────────────────────────────────────────
    def _show_launcher(self):
        self._cancel_loop()
        self._clear()

        W, H = 520, 400
        self._center(W, H)

        root = self.root

        # ── gradient-ish header bar ──
        header = tk.Frame(root, bg=BG2, height=110)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="MCU Traffic Counter",
                 bg=BG2, fg=ACCENT,
                 font=("Helvetica", 26, "bold")).pack(pady=(28, 4))
        tk.Label(header, text="Real-time vehicle detection & counting",
                 bg=BG2, fg=TEXT_DIM,
                 font=("Helvetica", 10)).pack()

        # ── divider ──
        tk.Frame(root, bg=BORDER, height=1).pack(fill="x")

        # ── body ──
        body = tk.Frame(root, bg=BG, pady=30)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Select input mode",
                 bg=BG, fg=TEXT_DIM,
                 font=("Helvetica", 11)).pack(pady=(0, 24))

        btn_row = tk.Frame(body, bg=BG)
        btn_row.pack()

        # Simulation button
        sim_card = self._card_button(
            btn_row,
            icon="▶",
            title="Simulation",
            subtitle="Intersection\nsimulation",
            command=lambda: self._start("sim"),
            accent=ACCENT
        )
        sim_card.grid(row=0, column=0, padx=14)

        # Camera button
        cam_card = self._card_button(
            btn_row,
            icon="◉",
            title="Camera (iPad)",
            subtitle="Live camera\nline + motion detection",
            command=lambda: self._start("cam"),
            accent=ACCENT2
        )
        cam_card.grid(row=0, column=1, padx=14)

        # ── footer ──
        tk.Frame(root, bg=BORDER, height=1).pack(fill="x")
        tk.Label(root, text="Press  Q  or click Stop to end a session",
                 bg=BG, fg=TEXT_DIM,
                 font=("Helvetica", 9)).pack(pady=10)

    def _card_button(self, parent, icon, title, subtitle, command, accent):
        """A rounded-look card that acts as a button."""
        card = tk.Frame(parent, bg=BG3, cursor="hand2",
                        padx=22, pady=18, relief="flat",
                        highlightbackground=BORDER, highlightthickness=1)

        tk.Label(card, text=icon, bg=BG3, fg=accent,
                 font=("Helvetica", 30)).pack()
        tk.Label(card, text=title, bg=BG3, fg=TEXT,
                 font=("Helvetica", 13, "bold")).pack(pady=(6, 2))
        tk.Label(card, text=subtitle, bg=BG3, fg=TEXT_DIM,
                 font=("Helvetica", 9), justify="center").pack()

        for widget in (card, *card.winfo_children()):
            widget.bind("<Button-1>", lambda _e: command())
            widget.bind("<Enter>", lambda _e, c=card: c.configure(
                highlightbackground=accent))
            widget.bind("<Leave>", lambda _e, c=card: c.configure(
                highlightbackground=BORDER))

        return card

    # ── Counter screen ─────────────────────────────────────────────────────────
    def _start(self, mode):
        self.mode = mode
        self._reset_state()

        # Increase history to 2000 so queued stop-sign cars don't vanish into the background.
        # Disable shadow detection for purely binary silhouettes. 
        self.fgbg = cv2.createBackgroundSubtractorMOG2(
            history=2000, varThreshold=16, detectShadows=False)

        if mode == "cam":
            if platform.system() == "Linux":
                # Optimal backend for Raspberry Pi Camera modules
                self.cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
            else:
                self.cap = cv2.VideoCapture(0)

            # Ensure resolution and framerate are explicitly locked for standard processing
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)

            if not self.cap.isOpened():
                self._show_error("Camera not found.\nCheck that a webcam is connected.")
                return
        else:
            self.inters_sim = inters5.IntersectionSimulator()
            # Precompute empty road for sim-mode detection (frame diff vs MOG2)
            # Include stop signs in background so absdiff doesn't flag them as foreground
            bg = inters5.draw_scene()
            inters5.draw_stop_signs(bg)
            self._sim_bg = cv2.resize(bg, (FRAME_W, FRAME_H))

        self._build_counter_ui()
        self.running = True
        self._loop()

    def _build_counter_ui(self):
        self._clear()
        W = FRAME_W + SIDEBAR_W
        self._center(W, FRAME_H)

        root = self.root

        # ── top bar ──
        topbar = tk.Frame(root, bg=BG2, height=38)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        mode_label = "  ▶  SIMULATION MODE" if self.mode == "sim" else "  ◉  CAMERA MODE"
        tk.Label(topbar, text=mode_label, bg=BG2, fg=ACCENT,
                 font=("Helvetica", 10, "bold")).pack(side="left", padx=12)

        stop_btn = tk.Button(topbar, text="■  Stop",
                             bg=SEV_RED, fg="white",
                             font=("Helvetica", 9, "bold"),
                             relief="flat", padx=10, cursor="hand2",
                             command=self._stop)
        stop_btn.pack(side="right", padx=10, pady=6)

        tk.Frame(root, bg=BORDER, height=1).pack(fill="x")

        # ── main area ──
        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True)

        # video pane — fixed resolution, no auto-resize
        video_frame = tk.Frame(body, bg="black",
                               highlightbackground=BORDER, highlightthickness=1)
        video_frame.pack(side="left")

        self.video_lbl = tk.Label(video_frame, bg="black")
        self.video_lbl.pack()

        # sidebar
        side = tk.Frame(body, bg=BG2, width=SIDEBAR_W)
        side.pack(side="right", fill="y")
        side.pack_propagate(False)

        self._build_sidebar(side)

    def _build_sidebar(self, side):
        pad = {"padx": 20}

        tk.Label(side, text="TRAFFIC STATS",
                 bg=BG2, fg=ACCENT,
                 font=("Helvetica", 11, "bold")).pack(pady=(22, 4), **pad, anchor="w")
        tk.Frame(side, bg=ACCENT, height=2).pack(fill="x", padx=20, pady=(0, 16))

        # total count
        self.lbl_total = tk.Label(side, text="0",
                                   bg=BG2, fg=TEXT,
                                   font=("Helvetica", 48, "bold"))
        self.lbl_total.pack(**pad, anchor="w")
        tk.Label(side, text="vehicles counted",
                 bg=BG2, fg=TEXT_DIM,
                 font=("Helvetica", 9)).pack(**pad, anchor="w")

        tk.Frame(side, bg=BORDER, height=1).pack(fill="x", padx=20, pady=16)

        # N / S / E / W grid
        dir_frame = tk.Frame(side, bg=BG2)
        dir_frame.pack(fill="x", **pad)

        for (lbl_text, color, attr, row, col) in [
            ("↑  N", SEV_GREEN, "lbl_n", 0, 0),
            ("↓  S", "#f39c12",  "lbl_s", 0, 1),
            ("←  W", ACCENT,     "lbl_w", 1, 0),
            ("→  E", ACCENT2,    "lbl_e", 1, 1),
        ]:
            cell = tk.Frame(dir_frame, bg=BG3, padx=10, pady=8)
            cell.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
            tk.Label(cell, text=lbl_text, bg=BG3, fg=color,
                     font=("Helvetica", 10, "bold")).pack()
            count_lbl = tk.Label(cell, text="0", bg=BG3, fg=TEXT,
                                  font=("Helvetica", 18, "bold"))
            count_lbl.pack()
            setattr(self, attr, count_lbl)

        dir_frame.columnconfigure(0, weight=1)
        dir_frame.columnconfigure(1, weight=1)

        tk.Frame(side, bg=BORDER, height=1).pack(fill="x", padx=20, pady=16)

        # severity
        tk.Label(side, text="SEVERITY LEVEL",
                 bg=BG2, fg=TEXT_DIM,
                 font=("Helvetica", 9)).pack(**pad, anchor="w")

        sev_row = tk.Frame(side, bg=BG2)
        sev_row.pack(fill="x", padx=20, pady=(8, 0))

        self.sev_canvas = tk.Canvas(sev_row, width=28, height=28,
                                     bg=BG2, highlightthickness=0)
        self.sev_canvas.pack(side="left")
        self._sev_dot = self.sev_canvas.create_oval(3, 3, 25, 25,
                                                      fill=SEV_GREEN, outline="")
        self.lbl_sev = tk.Label(sev_row, text="Low", bg=BG2, fg=SEV_GREEN,
                                 font=("Helvetica", 18, "bold"))
        self.lbl_sev.pack(side="left", padx=10)

        bar_bg = tk.Frame(side, bg=BG3, height=8)
        bar_bg.pack(fill="x", padx=20, pady=(10, 0))
        bar_bg.pack_propagate(False)

        self._sev_bar = tk.Frame(bar_bg, bg=SEV_GREEN, height=8, width=0)
        self._sev_bar.place(x=0, y=0, relheight=1.0)

        # Spawn rate slider (simulation mode only)
        if self.mode == "sim":
            tk.Frame(side, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(18, 0))

            tk.Label(side, text="TRAFFIC DENSITY",
                     bg=BG2, fg=TEXT_DIM,
                     font=("Helvetica", 9)).pack(padx=20, pady=(10, 2), anchor="w")

            lbl_row = tk.Frame(side, bg=BG2)
            lbl_row.pack(fill="x", padx=20)
            tk.Label(lbl_row, text="Sparse", bg=BG2, fg=TEXT_DIM,
                     font=("Helvetica", 8)).pack(side="left")
            tk.Label(lbl_row, text="Dense", bg=BG2, fg=TEXT_DIM,
                     font=("Helvetica", 8)).pack(side="right")

            # Slider: left=sparse (interval 120), right=dense (interval 10)
            self._spawn_slider = tk.Scale(
                side, from_=120, to=10,
                orient="horizontal",
                bg=BG2, fg=TEXT, troughcolor=BG3,
                activebackground=ACCENT,
                highlightthickness=0, sliderrelief="flat",
                showvalue=False,
                command=self._on_spawn_rate,
            )
            self._spawn_slider.set(35)
            self._spawn_slider.pack(fill="x", padx=20, pady=(2, 10))

    # ── Main update loop ───────────────────────────────────────────────────────
    def _loop(self):
        if not self.running:
            return

        frame = self._get_frame()
        if frame is None:
            self._stop()
            return

        frame = self._process(frame)

        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img   = Image.fromarray(rgb)
        imgtk = ImageTk.PhotoImage(image=img)
        self.video_lbl.imgtk = imgtk          # prevent GC
        self.video_lbl.configure(image=imgtk)

        self._update_sidebar()
        self._after_id = self.root.after(30, self._loop)

    # ── Frame acquisition ──────────────────────────────────────────────────────
    def _get_frame(self):
        if self.mode == "sim":
            return self._inters_frame()
        else:
            ret, frame = self.cap.read()
            if not ret:
                return None
            return cv2.resize(frame, (FRAME_W, FRAME_H))

    # ── Detection & tracking ───────────────────────────────────────────────────
    def _process(self, frame):
        self.frame_num += 1
        
        # The iPad camera's distance causes nested cars to naturally compress visually down to ~150-200px.
        # Dropped min_area for camera mode down drastically to ensure these nested vehicles pass the contour check!
        min_area = 600 if self.mode == "sim" else 80

        if self.mode == "cam":
            frame = self._line_overlay(frame)

        mask = self._motion_mask(frame)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        detections = []
        for cnt in contours:
            if cv2.contourArea(cnt) < min_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            detections.append((x + w // 2, y + h // 2, x, y, w, h))

        # age every existing object
        for obj in self.objects.values():
            obj["disappeared"] += 1

        used_objs = set()
        for cx, cy, x, y, w, h in detections:
            mid = None
            best = float("inf")
            for oid, obj in self.objects.items():
                if oid in used_objs: continue
                d = math.hypot(cx - obj["centroid"][0], cy - obj["centroid"][1])
                if d < MATCH_DIST and d < best:
                    best, mid = d, oid

            if mid is None:
                self._register(cx, cy)
                mid = self.next_id - 1
            else:
                self.objects[mid].update({
                    "prev_centroid": self.objects[mid]["centroid"],
                    "centroid":      (cx, cy),
                    "disappeared":   0,
                    "age":           self.objects[mid].get("age", 0) + 1,
                    "last_seen":     time.time(),
                })
            used_objs.add(mid)

            obj = self.objects[mid]
            # Check physical presence in bounding box with a robust buffer margin
            margin = 12
            core_in_bounds = (self.box_x1 <= cx <= self.box_x2) and (self.box_y1 <= cy <= self.box_y2)
            buffer_in_bounds = (self.box_x1 - margin <= cx <= self.box_x2 + margin) and \
                               (self.box_y1 - margin <= cy <= self.box_y2 + margin)

            if not obj["counted"]:
                if core_in_bounds:
                    obj["in_box"] = True
                elif obj.get("in_box", False) and not buffer_in_bounds:
                    # Vehicle has definitively and cleanly exited the intersection boundaries
                    direction = None
                    # Exits Top -> Going North
                    if cy < self.box_y1:
                        direction = "N"
                    # Exits Bottom -> Going South
                    elif cy > self.box_y2:
                        direction = "S"
                    # Exits Left -> Going West
                    elif cx < self.box_x1:
                        direction = "W"
                    # Exits Right -> Going East
                    elif cx > self.box_x2:
                        direction = "E"

                    if direction:
                        obj["counted"]   = True
                        obj["direction"] = direction
                        self.count += 1
                        if direction == "N":
                            self.count_n += 1
                        elif direction == "S":
                            self.count_s += 1
                        elif direction == "W":
                            self.count_w += 1
                        elif direction == "E":
                            self.count_e += 1

            col       = (0, 255, 0) if obj["counted"] else (0, 255, 255)
            dir_label = obj.get("direction") or ""
            cv2.rectangle(frame, (x, y), (x + w, y + h), col, 2)
            cv2.circle(frame,    (cx, cy), 4, (255, 80, 80), -1)
            cv2.putText(frame, f"ID{mid}{dir_label}", (x, max(y - 8, 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)

        # congestion: count objects that are waiting
        if self.mode == "sim" and hasattr(self, "inters_sim"):
            self.congestion = len(self.inters_sim._stop_queue)
        else:
            self.congestion = sum(
                1 for obj in self.objects.values()
                if obj["disappeared"] == 0
                and obj.get("age", 0) >= 3
                and math.hypot(
                    obj["centroid"][0] - obj["prev_centroid"][0],
                    obj["centroid"][1] - obj["prev_centroid"][1],
                ) < 3.0
            )

        # remove lost objects
        gone = [oid for oid, o in self.objects.items()
                if o["disappeared"] > MAX_GONE]
        for oid in gone:
            del self.objects[oid]

        # dynamic intersection box
        x1, y1 = int(self.box_x1), int(self.box_y1)
        x2, y2 = int(self.box_x2), int(self.box_y2)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)
        
        # gate lines: N=red, S=yellow, W=magenta, E=cyan
        cv2.line(frame, (x1, y1), (x2, y1), (0,   0,   255), 1)
        cv2.line(frame, (x1, y2), (x2, y2), (255, 255,   0), 1)
        cv2.line(frame, (x1, y1), (x1, y2), (255,   0, 255), 1)
        cv2.line(frame, (x2, y1), (x2, y2), (  0, 255, 255), 1)

        return frame

    # ── Sidebar update ─────────────────────────────────────────────────────────
    def _update_sidebar(self):
        self.lbl_total.configure(text=str(self.count))
        self.lbl_n.configure(text=str(self.count_n))
        self.lbl_s.configure(text=str(self.count_s))
        self.lbl_w.configure(text=str(self.count_w))
        self.lbl_e.configure(text=str(self.count_e))

        if self.congestion < 2:
            sev, color = "Low",    SEV_GREEN
        elif self.congestion < 4:
            sev, color = "Medium", SEV_YELLOW
        else:
            sev, color = "High",   SEV_RED

        self.lbl_sev.configure(text=sev, fg=color)
        self.sev_canvas.itemconfig(self._sev_dot, fill=color)

        max_w  = SIDEBAR_W - 40
        # Fill based on number of waiting cars. Cap at 10 for full bar width.
        filled = min(int((self.congestion / 10.0) * max_w), max_w)
        self._sev_bar.configure(width=filled, bg=color)

    # ── Simulation helpers ─────────────────────────────────────────────────────
    def _inters_frame(self):
        frame = self.inters_sim.next_frame()
        return cv2.resize(frame, (FRAME_W, FRAME_H))

    # ── Mask helpers ───────────────────────────────────────────────────────────
    def _line_overlay(self, frame):
        # Best model for embedded CPUs: Color-isolated HoughLinesP
        # Mask out purely White pixels to flawlessly isolate the perimeter stop-lines exclusively!
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask_white  = cv2.inRange(hsv, np.array([0, 0, 200]),  np.array([180, 40, 255]))
        masked_frame = cv2.bitwise_and(frame, frame, mask=mask_white)

        gray  = cv2.cvtColor(masked_frame, cv2.COLOR_BGR2GRAY)
        blur  = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180,
                                 threshold=50, minLineLength=40, maxLineGap=20)
        valid_x = []
        valid_y = []

        if lines is not None:
            for ln in lines:
                x1, y1, x2, y2 = ln[0]
                angle = abs(math.degrees(math.atan2(y2 - y1, x2 - x1)))
                
                if angle >= 60:
                    valid_x.extend([x1, x2])
                elif angle <= 30:
                    valid_y.extend([y1, y2])

        # Fluid dynamic bounds tracking (Camera mode only)
        if self.mode == "cam":
            if valid_x:
                lefts = [x for x in valid_x if x < FRAME_W / 2]
                rights = [x for x in valid_x if x > FRAME_W / 2]
                if lefts: self.box_x1 = int(0.9 * self.box_x1 + 0.1 * np.median(lefts))
                if rights: self.box_x2 = int(0.9 * self.box_x2 + 0.1 * np.median(rights))
            
            if valid_y:
                tops = [y for y in valid_y if y < FRAME_H / 2]
                bottoms = [y for y in valid_y if y > FRAME_H / 2]
                if tops: self.box_y1 = int(0.9 * self.box_y1 + 0.1 * np.median(tops))
                if bottoms: self.box_y2 = int(0.9 * self.box_y2 + 0.1 * np.median(bottoms))

        return frame

    def _motion_mask(self, frame):
        if self.mode == "sim":
            # Diff against known empty road — works even when cars are stationary
            diff = cv2.absdiff(frame, self._sim_bg)
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _, fg = cv2.threshold(gray, 20, 255, cv2.THRESH_BINARY)
        else:
            # Apply MOG2 on full BGR color-space rather than grayscale! 
            # This allows it to detect vividly colored cars on roads that might have identical gray-luminance!
            blur = cv2.GaussianBlur(frame, (5, 5), 0)
            fg   = self.fgbg.apply(blur)
            _, fg = cv2.threshold(fg, 127, 255, cv2.THRESH_BINARY)
            
        # Enforce exact cross-shape ROI masking to perfectly ignore grass/off-road sensor noise!
        road_mask = np.zeros_like(fg)
        x1, y1 = int(self.box_x1), int(self.box_y1)
        x2, y2 = int(self.box_x2), int(self.box_y2)
        cv2.rectangle(road_mask, (0, y1), (FRAME_W, y2), 255, -1)   # West-East corridor
        cv2.rectangle(road_mask, (x1, 0), (x2, FRAME_H), 255, -1)   # North-South corridor
        fg = cv2.bitwise_and(fg, road_mask)
            
        # Morphology: strong open to kill small noise (stop signs, flicker), gentle close + dilate
        # to keep car outlines tight and prevent merging nearby vehicles
        open_kernel = np.ones((7, 7), np.uint8)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, open_kernel)
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, KERNEL)
        small_kernel = np.ones((3, 3), np.uint8)
        return cv2.dilate(fg, small_kernel, iterations=1)

    # ── Tracker helpers ────────────────────────────────────────────────────────
    def _register(self, cx, cy):
        self.objects[self.next_id] = {
            "centroid":      (cx, cy),
            "prev_centroid": (cx, cy),
            "direction":     None,
            "counted":       False,
            "disappeared":   0,
            "age":           0,
            "last_seen":     time.time()
        }
        self.next_id += 1

    def _on_spawn_rate(self, val):
        if self.inters_sim:
            self.inters_sim._SPAWN_INTERVAL = int(val)

    # ── Navigation ────────────────────────────────────────────────────────────
    def _stop(self):
        self.running = False
        self._cancel_loop()
        if self.cap:
            self.cap.release()
            self.cap = None
        self._show_launcher()

    def _cancel_loop(self):
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None

    def _on_close(self):
        self.running = False
        self._cancel_loop()
        if self.cap:
            self.cap.release()
        self.root.destroy()

    # ── Error screen ──────────────────────────────────────────────────────────
    def _show_error(self, msg):
        self._clear()
        self._center(400, 220)
        tk.Label(self.root, text="⚠  Error", bg=BG, fg=SEV_RED,
                 font=("Helvetica", 18, "bold")).pack(pady=(40, 10))
        tk.Label(self.root, text=msg, bg=BG, fg=TEXT,
                 font=("Helvetica", 11), justify="center").pack()
        tk.Button(self.root, text="← Back", bg=BG3, fg=TEXT,
                  relief="flat", font=("Helvetica", 10), cursor="hand2",
                  command=self._show_launcher).pack(pady=24)

    # ── Utilities ─────────────────────────────────────────────────────────────
    def _clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def _center(self, w, h):
        self.root.geometry(f"{w}x{h}")
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    TrafficApp()
