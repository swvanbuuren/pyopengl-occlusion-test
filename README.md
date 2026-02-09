# OpenGL Occlusion Detection Test

This program tests 3D point occlusion detection using OpenGL's depth buffer, translated from C++ to Python using PyOpenGL.

## Setup

### Option 1: Using UV (Recommended)

1. Install UV if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install and run the project:
```bash
uv run occlusion-test
```

Or sync dependencies and run manually:
```bash
uv sync
uv run python occlusion_test.py
```

### Option 2: Using pip

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Run the test:
```bash
python occlusion_test.py
```

## How It Works

The program:
1. Creates a flat horizontal plane at a random y-coordinate
2. Positions a camera at (0, 5, 10) looking at the origin
3. Generates 20 random 3D test points
4. Determines which points *should* be occluded by the plane geometrically
5. Renders the scene to fill the depth buffer
6. Tests each point using the depth buffer method (translated from C++)
7. Compares expected vs calculated occlusion results

## The Algorithm

The occlusion test follows these steps:

1. **Project 3D to 2D**: Use `gluProject()` to convert 3D world coordinates to 2D screen coordinates with depth
2. **Read Depth Buffer**: Use `glReadPixels()` to read the depth value at the projected 2D location
3. **Compare Depths**: Compare the projected depth with the buffer depth:
   - If they match (within epsilon): point is visible
   - If buffer depth is less: point is occluded by something closer

## Expected Output

The program prints a table showing:
- Point coordinates
- Expected occlusion status (based on geometry)
- Calculated occlusion status (based on depth buffer)
- Whether they match

## Notes

- The test uses a fixed random seed (42) for reproducibility
- An epsilon of 0.001 is used for floating-point comparison
- The camera is positioned above the origin looking down
- Points below the plane (when camera is above) are expected to be occluded