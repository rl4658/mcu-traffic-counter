import cv2
import numpy as np
import math
import random as _random

WIDTH, HEIGHT = 1280, 720
FPS = 30
DURATION_SEC = 60
TOTAL_FRAMES = FPS * DURATION_SEC
OUTPUT_FILE = "intersection_scripted.mp4"

BG_COLOR = (53, 110, 61)       # Rich grass
ROAD_COLOR = (60, 65, 70)      # Dark realistic asphalt
LANE_COLOR = (0, 200, 255)     # Yellow double lane divider
CURB_COLOR = (160, 160, 160)   # Concrete curb
OUTLINE_COLOR = (30, 30, 30)

CX, CY = WIDTH // 2, HEIGHT // 2
ROAD_W = 260
HALF_ROAD = ROAD_W // 2

CAR_W = 50
CAR_H = 100
LOOKAHEAD = 8
STEP_PX = 4

CAR_COLORS = [
    (0, 215, 255),
    (90, 220, 90),
    (255, 180, 80),
    (180, 140, 255),
    (80, 180, 255),
]

def dist(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def lerp(a, b, t):
    return a + (b - a) * t

def lerp_point(p1, p2, t):
    return (lerp(p1[0], p2[0], t), lerp(p1[1], p2[1], t))

def angle_to_target_deg(p1, p2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return math.degrees(math.atan2(dx, -dy))

def clamp_angle_deg(angle):
    while angle > 180:
        angle -= 360
    while angle < -180:
        angle += 360
    return angle

def rotate_points(points, angle_deg, cx, cy):
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for px, py in points:
        rx = cx + (px - cx) * ca - (py - cy) * sa
        ry = cy + (px - cx) * sa + (py - cy) * ca
        out.append((int(rx), int(ry)))
    return out

def line_points(p1, p2, step=STEP_PX):
    d = dist(p1, p2)
    n = max(2, int(d / step))
    return [lerp_point(p1, p2, i / n) for i in range(n + 1)]

def bezier_points(p0, p1, p2, p3, n=70):
    pts = []
    for i in range(n + 1):
        t = i / n
        x = ((1 - t) ** 3) * p0[0] + 3 * ((1 - t) ** 2) * t * p1[0] + 3 * (1 - t) * (t ** 2) * p2[0] + (t ** 3) * p3[0]
        y = ((1 - t) ** 3) * p0[1] + 3 * ((1 - t) ** 2) * t * p1[1] + 3 * (1 - t) * (t ** 2) * p2[1] + (t ** 3) * p3[1]
        pts.append((x, y))
    return pts

def concat_paths(*segments):
    out = []
    for seg in segments:
        if not out:
            out.extend(seg)
        else:
            out.extend(seg[1:])
    return out

north_down_x = CX - 65
south_up_x   = CX + 65
west_right_y = CY + 65
east_left_y  = CY - 65

top_y = -120
bottom_y = HEIGHT + 120
left_x = -120
right_x = WIDTH + 120

PATHS = {
    # Straight routes — stay in own lane the whole way
    "W_E": line_points((left_x, west_right_y), (right_x, west_right_y)),
    "E_W": line_points((right_x, east_left_y), (left_x, east_left_y)),
    "N_S": line_points((north_down_x, top_y), (north_down_x, bottom_y)),
    "S_N": line_points((south_up_x, bottom_y), (south_up_x, top_y)),

    # Left turn: southbound → left → eastbound
    # Enters west/southbound lane (x=CX-65), arcs through intersection centre,
    # exits on south/eastbound lane (y=CY+65).
    "N_E": concat_paths(
        line_points((north_down_x, top_y), (north_down_x, CY - 25)),
        bezier_points(
            (north_down_x, CY - 25),
            (north_down_x, CY + 25),
            (CX - 25, west_right_y),
            (CX + HALF_ROAD + 10, west_right_y)
        ),
        line_points((CX + HALF_ROAD + 10, west_right_y), (right_x, west_right_y))
    ),

    "S_W": concat_paths(
        line_points((south_up_x, bottom_y), (south_up_x, CY + 25)),
        bezier_points(
            (south_up_x, CY + 25),
            (south_up_x, CY - 25),
            (CX + 25, east_left_y),
            (CX - HALF_ROAD - 10, east_left_y)
        ),
        line_points((CX - HALF_ROAD - 10, east_left_y), (left_x, east_left_y))
    ),

    "W_N": concat_paths(
        line_points((left_x, west_right_y), (CX - 25, west_right_y)),
        bezier_points(
            (CX - 25, west_right_y),
            (CX + 25, west_right_y),
            (south_up_x, CY + 25),
            (south_up_x, CY - HALF_ROAD - 10)
        ),
        line_points((south_up_x, CY - HALF_ROAD - 10), (south_up_x, top_y))
    ),

    "E_S": concat_paths(
        line_points((right_x, east_left_y), (CX + 25, east_left_y)),
        bezier_points(
            (CX + 25, east_left_y),
            (CX - 25, east_left_y),
            (north_down_x, CY - 25),
            (north_down_x, CY + HALF_ROAD + 10)
        ),
        line_points((north_down_x, CY + HALF_ROAD + 10), (north_down_x, bottom_y))
    ),
}

# Scripted schedule: one car enters, clears, then next
SCHEDULE = [
    {"start":    0, "route": "W_E",  "color": CAR_COLORS[0], "speed": 1.8},
    {"start":   80, "route": "N_S",  "color": CAR_COLORS[1], "speed": 1.8},
    {"start":  160, "route": "E_W",  "color": CAR_COLORS[2], "speed": 1.8},
    {"start":  240, "route": "S_N",  "color": CAR_COLORS[3], "speed": 1.8},
    {"start":  320, "route": "N_E",  "color": CAR_COLORS[4], "speed": 1.7},
    {"start":  420, "route": "S_W",  "color": CAR_COLORS[0], "speed": 1.7},
    {"start":  520, "route": "W_N",  "color": CAR_COLORS[1], "speed": 1.7},
    {"start":  620, "route": "E_S",  "color": CAR_COLORS[2], "speed": 1.7},
    {"start":  720, "route": "W_E",  "color": CAR_COLORS[3], "speed": 2.0},
    {"start":  800, "route": "N_S",  "color": CAR_COLORS[4], "speed": 2.0},
    {"start":  880, "route": "E_W",  "color": CAR_COLORS[0], "speed": 2.0},
    {"start":  960, "route": "S_N",  "color": CAR_COLORS[1], "speed": 2.0},
    {"start": 1040, "route": "N_E",  "color": CAR_COLORS[2], "speed": 1.9},
    {"start": 1120, "route": "W_N",  "color": CAR_COLORS[3], "speed": 1.9},
    {"start": 1200, "route": "S_W",  "color": CAR_COLORS[4], "speed": 1.9},
    {"start": 1280, "route": "E_S",  "color": CAR_COLORS[0], "speed": 1.9},
    {"start": 1360, "route": "W_E",  "color": CAR_COLORS[1], "speed": 1.8},
    {"start": 1440, "route": "N_S",  "color": CAR_COLORS[2], "speed": 1.8},
    {"start": 1520, "route": "E_W",  "color": CAR_COLORS[3], "speed": 1.8},
    {"start": 1600, "route": "S_N",  "color": CAR_COLORS[4], "speed": 1.8},
    {"start": 1680, "route": "N_E",  "color": CAR_COLORS[0], "speed": 1.7},
    {"start": 1760, "route": "E_S",  "color": CAR_COLORS[1], "speed": 1.7},
]
def build_conflict_matrix(paths):
    """
    Precomputes which routes structurally intersect in the intersection box.
    Returns a dict {route: set_of_conflicting_routes}.
    """
    matrix = {r: set() for r in paths}
    for r1, path1 in paths.items():
        matrix[r1].add(r1) # A route natively conflicts with itself (enforces sequential flow per lane)
        for r2, path2 in paths.items():
            if r1 == r2: continue
            
            conflict = False
            for p1 in path1:
                # Only check points inside the intersection box
                if not (CX - 150 < p1[0] < CX + 150 and CY - 150 < p1[1] < CY + 150): continue
                for p2 in path2:
                    if not (CX - 150 < p2[0] < CX + 150 and CY - 150 < p2[1] < CY + 150): continue
                    if dist(p1, p2) < 45: # Broad 45px collision bounding circle
                        conflict = True
                        break
                if conflict: break
            if conflict:
                matrix[r1].add(r2)
    return matrix

def _intersection_entry_idx(path):
    for i, (px, py) in enumerate(path):
        if (CX - HALF_ROAD <= px <= CX + HALF_ROAD and
                CY - HALF_ROAD <= py <= CY + HALF_ROAD):
            return max(0, i - 14) 
    return 80  

def _intersection_exit_idx(path):
    for i in range(len(path) - 1, -1, -1):
        px, py = path[i]
        if (CX - HALF_ROAD <= px <= CX + HALF_ROAD and
                CY - HALF_ROAD <= py <= CY + HALF_ROAD):
            return min(len(path) - 1, i + 14)
    return len(path) - 1

class Car:
    def __init__(self, path, color, speed, route):
        self.path      = path
        self.color     = color
        self.base_speed = speed
        self.speed     = speed
        self.route     = route
        self.s         = 0.0
        self.angle     = 0.0
        self.alive     = True
        
        self.has_stopped = False
        self.cleared = False
        
        self.entry_threshold = _intersection_entry_idx(path)
        self.exit_threshold  = _intersection_exit_idx(path)

    def pos(self):
        i = max(0, min(int(self.s), len(self.path) - 1))
        return self.path[i]

    def update(self):
        # Physics and boundary cleanup only. Position handling is strictly centrally managed.
        if self.s >= len(self.path) - 2:
            self.alive = False

        i1 = min(int(self.s), len(self.path) - 1)
        i2 = min(i1 + LOOKAHEAD, len(self.path) - 1)
        p1 = self.path[i1]
        p2 = self.path[i2]
        target = angle_to_target_deg(p1, p2)
        delta  = clamp_angle_deg(target - self.angle)
        self.angle += delta * 0.25

    def draw(self, frame):
        x, y = self.pos()
        draw_car(frame, int(x), int(y), CAR_W, CAR_H, self.angle, self.color)

def draw_scene():
    frame = np.full((HEIGHT, WIDTH, 3), BG_COLOR, dtype=np.uint8)

    cv2.rectangle(frame, (CX - HALF_ROAD, 0), (CX + HALF_ROAD, HEIGHT), ROAD_COLOR, -1)
    cv2.rectangle(frame, (0, CY - HALF_ROAD), (WIDTH, CY + HALF_ROAD), ROAD_COLOR, -1)

    cv2.rectangle(frame, (CX - HALF_ROAD, 0), (CX + HALF_ROAD, HEIGHT), CURB_COLOR, 10)
    cv2.rectangle(frame, (0, CY - HALF_ROAD), (WIDTH, CY + HALF_ROAD), CURB_COLOR, 10)
    cv2.rectangle(frame, (CX - HALF_ROAD, 0), (CX + HALF_ROAD, HEIGHT), OUTLINE_COLOR, 2)
    cv2.rectangle(frame, (0, CY - HALF_ROAD), (WIDTH, CY + HALF_ROAD), OUTLINE_COLOR, 2)

    dash = 22
    gap = 24

    # Center lines (Yellow)
    y = 0
    while y < CY - 135:
        cv2.line(frame, (CX, y), (CX, min(y + dash, CY - 135)), LANE_COLOR, 4)
        y += dash + gap

    y = CY + 135
    while y < HEIGHT:
        cv2.line(frame, (CX, y), (CX, min(y + dash, HEIGHT)), LANE_COLOR, 4)
        y += dash + gap

    x = 0
    while x < CX - 135:
        cv2.line(frame, (x, CY), (min(x + dash, CX - 135), CY), LANE_COLOR, 4)
        x += dash + gap

    x = CX + 135
    while x < WIDTH:
        cv2.line(frame, (x, CY), (min(x + dash, WIDTH), CY), LANE_COLOR, 4)
        x += dash + gap

    # Thick White Stop Lines at entry points (130px from center)
    cv2.line(frame, (CX - HALF_ROAD, CY - 130), (CX, CY - 130), (255, 255, 255), 6) # North incoming
    cv2.line(frame, (CX, CY + 130), (CX + HALF_ROAD, CY + 130), (255, 255, 255), 6) # South incoming
    cv2.line(frame, (CX - 130, CY), (CX - 130, CY + HALF_ROAD), (255, 255, 255), 6) # West incoming
    cv2.line(frame, (CX + 130, CY - HALF_ROAD), (CX + 130, CY), (255, 255, 255), 6) # East incoming

    return frame

def draw_stop_signs(frame):
    """Draw red stop signs at the four intersection corners."""
    r = 16
    corners = [
        (CX - HALF_ROAD + 22, CY - HALF_ROAD + 22),  # NW
        (CX + HALF_ROAD - 22, CY - HALF_ROAD + 22),  # NE
        (CX - HALF_ROAD + 22, CY + HALF_ROAD - 22),  # SW
        (CX + HALF_ROAD - 22, CY + HALF_ROAD - 22),  # SE
    ]
    for x, y in corners:
        # Create octagon polygon
        oct_pts = []
        for i in range(8):
            angle = math.pi / 8 + i * math.pi / 4
            oct_pts.append((int(x + r * math.cos(angle)), int(y + r * math.sin(angle))))
        cv2.fillPoly(frame, [np.array(oct_pts, dtype=np.int32)], (0, 0, 220))
        cv2.polylines(frame, [np.array(oct_pts, dtype=np.int32)], True, (255, 255, 255), 2)
        cv2.putText(frame, "STOP", (x - 12, y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)


def draw_car(frame, x, y, w, h, angle, color):
    # Body
    body = [(x - w//2, y - h//2), (x + w//2, y - h//2),
            (x + w//2, y + h//2), (x - w//2, y + h//2)]
    body_r = rotate_points(body, angle, x, y)
    cv2.fillPoly(frame, [np.array(body_r, dtype=np.int32)], color)
    cv2.polylines(frame, [np.array(body_r, dtype=np.int32)], True, OUTLINE_COLOR, 1)

    # Roof (darker, inset from body edges)
    rw, rh = w - 10, h - 24
    roof = [(x - rw//2, y - rh//2), (x + rw//2, y - rh//2),
            (x + rw//2, y + rh//2), (x - rw//2, y + rh//2)]
    roof_color = (max(0, color[0] - 55), max(0, color[1] - 55), max(0, color[2] - 55))
    roof_r = rotate_points(roof, angle, x, y)
    cv2.fillPoly(frame, [np.array(roof_r, dtype=np.int32)], roof_color)

    # Front windshield (top edge of car = front)
    fw = w - 14
    front = [(x - fw//2, y - h//2 + 3), (x + fw//2, y - h//2 + 3),
             (x + fw//2, y - h//2 + 13), (x - fw//2, y - h//2 + 13)]
    front_r = rotate_points(front, angle, x, y)
    cv2.fillPoly(frame, [np.array(front_r, dtype=np.int32)], (195, 210, 230))

    # Rear windshield
    rear = [(x - fw//2, y + h//2 - 13), (x + fw//2, y + h//2 - 13),
            (x + fw//2, y + h//2 - 3), (x - fw//2, y + h//2 - 3)]
    rear_r = rotate_points(rear, angle, x, y)
    cv2.fillPoly(frame, [np.array(rear_r, dtype=np.int32)], (160, 175, 195))

    # Headlights (front corners, yellow)
    hl = rotate_points([(x - w//2 + 5, y - h//2 + 5)], angle, x, y)[0]
    hr = rotate_points([(x + w//2 - 5, y - h//2 + 5)], angle, x, y)[0]
    cv2.circle(frame, hl, 4, (0, 230, 255), -1)
    cv2.circle(frame, hr, 4, (0, 230, 255), -1)

    # Taillights (rear corners, red)
    tl = rotate_points([(x - w//2 + 5, y + h//2 - 5)], angle, x, y)[0]
    tr = rotate_points([(x + w//2 - 5, y + h//2 - 5)], angle, x, y)[0]
    cv2.circle(frame, tl, 4, (0, 0, 210), -1)
    cv2.circle(frame, tr, 4, (0, 0, 210), -1)

class IntersectionSimulator:
    """Owns all simulation state. Call next_frame() each tick to get a rendered BGR frame."""
    _ROUTES         = list(PATHS.keys())   # all 8 routes
    _SPAWN_INTERVAL = 45                   # frames between spawn attempts (~1.5s at 30fps)
    _CLEARANCE      = 140                  # min dist from entry before spawn allowed

    def __init__(self):
        self._frame_idx    = 0
        self._cars          = []
        self._spawn_timer   = 0
        self._stop_queue    = []
        self._conflict_matrix = build_conflict_matrix(PATHS)

    def _entry_point(self, route):
        return PATHS[route][0]

    def _try_spawn(self):
        route = _random.choice(self._ROUTES)
        entry = self._entry_point(route)
        for car in self._cars:
            if dist(car.pos(), entry) < self._CLEARANCE:
                return
        color = _random.choice(CAR_COLORS)
        speed = _random.uniform(1.6, 2.2)
        self._cars.append(Car(PATHS[route], color, speed, route))

    def next_frame(self):
        self._frame_idx += 1
        
        # Determine the current frame within the loop cycle
        cycle_frame = self._frame_idx % TOTAL_FRAMES
        
        # Stop spawning cars towards the end of the generator cycle so the video loop ends empty!
        if cycle_frame < TOTAL_FRAMES - 450:
            self._spawn_timer += 1
            if self._spawn_timer >= self._SPAWN_INTERVAL:
                self._spawn_timer = 0
                self._try_spawn()

        # 1. Update stop queue for newly arriving cars
        for car in self._cars:
            if not car.has_stopped and car.s <= car.entry_threshold and car.s + car.speed >= car.entry_threshold:
                car.has_stopped = True
                car.s = car.entry_threshold
                car.speed = 0
                car.cleared = False
                self._stop_queue.append(car)

        # 2. Check active cars inside the strict intersection boundaries
        active_cars = [c for c in self._cars if c.cleared and c.s > c.entry_threshold and c.s < c.exit_threshold]

        # 3. Attempt to release cars from the front of the queue
        while self._stop_queue:
            front_car = self._stop_queue[0]
            can_go = True
            for a_car in active_cars:
                if a_car.route in self._conflict_matrix[front_car.route]:
                    can_go = False
                    break
            
            if can_go:
                front_car = self._stop_queue.pop(0)
                front_car.cleared = True
                front_car.speed = front_car.base_speed
                active_cars.append(front_car)  # Add to active so next popped car checks against it
            else:
                break

        # 4. Process movement and rear-end collision avoidance
        alive = []
        for i, car in enumerate(self._cars):
            must_stop = False
            for j, other in enumerate(self._cars):
                if j == i:
                    continue
                # Radar prevents physical collision overlaps universally
                for look in (5, 10, 16, 23):
                    fi = min(int(car.s) + look, len(car.path) - 1)
                    if dist(car.path[fi], other.pos()) < 26 and other.s > car.s:
                        must_stop = True
                        break
                if must_stop:
                    break

            if must_stop:
                car.speed = 0
            elif car.has_stopped and not car.cleared:
                car.speed = 0 # Still waiting in queue
            else:
                car.speed = car.base_speed
                
            car.s += car.speed
            car.update()
            
            if car.alive:
                alive.append(car)
            else:
                if car in self._stop_queue:
                    self._stop_queue.remove(car)
                    
        self._cars = alive

        # 5. Render Scene Backing
        frame = draw_scene()
        draw_stop_signs(frame)
        for car in self._cars:
            car.draw(frame)
            
        return frame


def main():
    sim    = IntersectionSimulator()
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out    = cv2.VideoWriter(OUTPUT_FILE, fourcc, FPS, (WIDTH, HEIGHT))
    for _ in range(TOTAL_FRAMES):
        out.write(sim.next_frame())
    out.release()
    print(f"Saved: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()