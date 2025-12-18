PhysX — Interactive Gravitational Lensing Visualizer

Overview
--------
PhysX is a small educational app that simulates gravitational lensing by integrating tiny light-ray deflections from massive objects (black holes). The app is designed for exploration and teaching — change parameters and see how lensing patterns evolve.

Controls
--------
- Space: Pause / Resume
- R: Reset rays
- B: Add a black hole at the center
- Use the control dock to change **Black Hole Mass**, **Number of Light Rays**, and **Simulation Speed**.
- Use the **Ray Palette** to pick presentation-friendly ray colors and press **Apply Palette**.
- Use the **Presets** (Strong Single / Binary) or run the **Guided Tour** from the controls for quick demos.
- Open the **Learn** dock for a short guide and references, and enable **Teaching Mode** in the controls to show per-black-hole predictions and HUD annotations.

Educational Notes
-----------------
- The primary formula shown is α = 4GM / (c^2 b), which is the small-angle deflection by a point mass (α in radians).
- The simulation accumulates small deflections as light rays pass near massive objects to produce curved paths.
- Try increasing the number of rays and mass to see strong lensing patterns appear.

Install
-------
Create a virtual environment and install dependencies:

    python -m venv .venv
    .venv\Scripts\activate  # Windows
    pip install -r requirements.txt

Run
---
Start the app:

    python app.py

Repository readiness
--------------------
- Added `.gitignore`, `requirements.txt`, `LICENSE` (MIT), `CONTRIBUTING.md`, and a basic GitHub Actions workflow (`.github/workflows/ci.yml`) that runs a smoke test (import `app`).

License & Credits
-----------------
This project is available under the MIT license. See `LICENSE` for details.