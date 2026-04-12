import sys

with open('intersection_generator.py', 'r') as f:
    content = f.read()

# LOW
c_low = content.replace('OUTPUT_FILE = "intersection_scripted.mp4"', 'OUTPUT_FILE = "intersection_low.mp4"')
c_low = c_low.replace('DURATION_SEC = 60', 'DURATION_SEC = 30')
c_low = c_low.replace('_SPAWN_INTERVAL = 45', '_SPAWN_INTERVAL = 120')
c_low = c_low.replace('cycle_frame < TOTAL_FRAMES - 450:', 'cycle_frame < TOTAL_FRAMES - 300:')
c_low = c_low.replace('BG_COLOR = (53, 110, 61)', 'BG_COLOR = (80, 140, 70)')
c_low = c_low.replace('ROAD_COLOR = (60, 65, 70)', 'ROAD_COLOR = (70, 75, 80)')
with open('intersection_generator_low.py', 'w') as f:
    f.write(c_low)

# MEDIUM
c_med = content.replace('OUTPUT_FILE = "intersection_scripted.mp4"', 'OUTPUT_FILE = "intersection_medium.mp4"')
c_med = c_med.replace('DURATION_SEC = 60', 'DURATION_SEC = 45')
c_med = c_med.replace('cycle_frame < TOTAL_FRAMES - 450:', 'cycle_frame < TOTAL_FRAMES - 450:')
c_med = c_med.replace('BG_COLOR = (53, 110, 61)', 'BG_COLOR = (80, 140, 70)')
c_med = c_med.replace('ROAD_COLOR = (60, 65, 70)', 'ROAD_COLOR = (70, 75, 80)')
with open('intersection_generator_medium.py', 'w') as f:
    f.write(c_med)

# HIGH
c_high = content.replace('OUTPUT_FILE = "intersection_scripted.mp4"', 'OUTPUT_FILE = "intersection_high.mp4"')
c_high = c_high.replace('DURATION_SEC = 60', 'DURATION_SEC = 52')
c_high = c_high.replace('_SPAWN_INTERVAL = 45', '_SPAWN_INTERVAL = 8')
c_high = c_high.replace('cycle_frame < TOTAL_FRAMES - 450:', 'cycle_frame < 600:')
c_high = c_high.replace('BG_COLOR = (53, 110, 61)', 'BG_COLOR = (80, 140, 70)')
c_high = c_high.replace('ROAD_COLOR = (60, 65, 70)', 'ROAD_COLOR = (70, 75, 80)')
with open('intersection_generator_high.py', 'w') as f:
    f.write(c_high)

print('Scripts generated successfully.')
