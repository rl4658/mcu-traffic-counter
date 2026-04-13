import cv2
import numpy as np
import intersection_generator as inters5

def generate_figure():
    print("Starting simulation to generate vertical IEEE figure...")
    
    # Initialize simulator and background subtractor just like in your main.py
    sim = inters5.IntersectionSimulator()
    fgbg = cv2.createBackgroundSubtractorMOG2(history=2000, varThreshold=16, detectShadows=False)

    # Fast forward 250 frames to ensure there are cars actively in the intersection
    for i in range(250):
        raw_frame = sim.next_frame()
        frame = cv2.resize(raw_frame, (640, 480)) # Match main.py resolution
        
        # Apply MOG2 to build history
        blur = cv2.GaussianBlur(frame, (5, 5), 0)
        mask = fgbg.apply(blur)

    print("Capturing frame 250 and applying morphological filters...")
    
    # Apply your exact morphological noise-cleanup logic from main.py
    _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    kernel = np.ones((5, 5), np.uint8)
    open_kernel = np.ones((7, 7), np.uint8)
    
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    small_kernel = np.ones((3, 3), np.uint8)
    mask = cv2.dilate(mask, small_kernel, iterations=1)

    # Convert the 1-channel black-and-white mask to 3-channel BGR so we can stitch them
    mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)

    # Add text labels to make it look professional for the academic paper
    cv2.putText(frame, "RGB Simulation Input", (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(mask_bgr, "MOG2 Foreground Mask", (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    # Create a thin white divider line (4 pixels tall, 640 pixels wide)
    divider = np.full((4, 640, 3), 255, dtype=np.uint8)

    # Stitch them together top-to-bottom vertically with the divider in the middle
    combined_image = np.vstack((frame, divider, mask_bgr))

    # Save the file
    filename = "vision_mask_vertical.png"
    cv2.imwrite(filename, combined_image)
    print(f"Success! '{filename}' has been saved to your folder.")

if __name__ == "__main__":
    generate_figure()