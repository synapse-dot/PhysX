# (Full updated file content - copy this entire block into your app.py)
import sys
import math
import numpy as np
import time
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import pyqtgraph.opengl as gl
import pyqtgraph as pg

# ===================== CONSTANTS =====================
G = 6.67430e-1  # Scaled gravitational constant (tuned for visuals)
c = 1.0         # Scaled speed of light

# ===================== SPLASH SCREEN =====================
class PhysXSplashScreen(QSplashScreen):
    """Splash screen with twinkling stars and fade-in/out effect"""
    def __init__(self):
        pixmap = QPixmap(900, 520)
        pixmap.fill(QColor(0,0,0))
        super().__init__(pixmap)
        self.setFixedSize(900, 520)

        self.particles = np.zeros((120,4))  # x, y, size, alpha
        self.particles[:,0] = np.random.rand(len(self.particles)) * self.width()
        self.particles[:,1] = np.random.rand(len(self.particles)) * self.height()
        self.particles[:,2] = np.random.randint(1,4,len(self.particles))
        self.particles[:,3] = np.random.rand(len(self.particles))*0.6 + 0.4

        self.opacity = 0.0
        self.fade_in = True
        # fade_out holds whether we are currently fading out to close
        self.fade_out = False
        self.finish_target = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_particles)
        self.timer.start(30)
        self.show()

    def draw_splash(self):
        temp_pixmap = QPixmap(self.pixmap().size())
        # gradient background (deep space)
        grad = QLinearGradient(0,0,self.width(),self.height())
        grad.setColorAt(0, QColor(5,8,30))
        grad.setColorAt(1, QColor(10,12,50))
        brush = QBrush(grad)
        temp_pixmap.fill(QColor(0,0,0))
        painter = QPainter(temp_pixmap)
        painter.fillRect(self.rect(), brush)
        painter.setRenderHint(QPainter.Antialiasing)

        # draw twinkling particles with subtle glow
        for p in self.particles:
            color = QColor(200,220,255, int(255 * p[3] * (0.7 + 0.3*self.opacity)))
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            # draw tiny halo
            painter.setOpacity(0.12*self.opacity)
            painter.drawEllipse(int(p[0])-int(p[2]*2), int(p[1])-int(p[2]*2), int(p[2]*4), int(p[2]*4))
            painter.setOpacity(1.0)
            painter.drawEllipse(int(p[0]), int(p[1]), int(p[2]), int(p[2]))

        # Title with stylized ring logo (no emoji)
        title_color = QColor(0,230,255,int(255*self.opacity))
        painter.setPen(QPen(title_color))
        painter.setFont(QFont("Arial",48,QFont.Bold))
        # draw a subtle ring logo to the left of the title
        logo_center = QPoint(220,120)
        logo_radius = 26
        # soft radial glow inside the ring
        grad_logo = QRadialGradient(logo_center, logo_radius)
        grad_logo.setColorAt(0.0, QColor(0,230,255,int(100*self.opacity)))
        grad_logo.setColorAt(0.7, QColor(0,200,230,int(36*self.opacity)))
        grad_logo.setColorAt(1.0, QColor(0,200,230,0))
        painter.setBrush(QBrush(grad_logo))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(logo_center, int(logo_radius*0.9), int(logo_radius*0.9))
        # outer ring
        ring_color = QColor(0,200,230,int(180*self.opacity))
        painter.setPen(QPen(ring_color, 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(logo_center, logo_radius, logo_radius)
        painter.setFont(QFont("Arial",48,QFont.Bold))
        painter.setPen(QPen(title_color))
        painter.drawText(260,140,"PhysX")

        painter.setFont(QFont("Arial",20))
        painter.setPen(QColor(220,220,255,int(255*self.opacity)))
        painter.drawText(190,210,"Interactive Gravitational Lensing Visualizer")

        painter.end()
        self.setPixmap(temp_pixmap)

    def update_particles(self):
        # jitter
        self.particles[:,0] += (np.random.rand(len(self.particles))-0.5)*0.8
        self.particles[:,1] += (np.random.rand(len(self.particles))-0.5)*0.8
        # wrap around screen
        self.particles[:,0] %= self.width()
        self.particles[:,1] %= self.height()

        self.draw_splash()

        # fade in until fully visible; then hold until fade_out is requested
        if self.fade_in:
            self.opacity += 0.03
            if self.opacity >= 1.0:
                self.opacity = 1.0
                self.fade_in = False
        elif self.fade_out:
            # fade out smoothly and finish/hide when done
            self.opacity -= 0.04
            if self.opacity <= 0.0:
                self.opacity = 0.0
                try:
                    self.timer.stop()
                except Exception:
                    pass
                # if a target window was provided, call finish to hand focus to it
                if self.finish_target is not None:
                    try:
                        self.finish(self.finish_target)
                    except Exception:
                        try:
                            self.hide()
                        except Exception:
                            pass
                else:
                    try:
                        self.hide()
                    except Exception:
                        pass
        else:
            # hold full opacity
            self.opacity = min(1.0, max(0.0, self.opacity))

    def mousePressEvent(self, event):
        # start a graceful fade-out on click (non-blocking)
        try:
            self.fade_out = True
        except Exception:
            pass
        return super().mousePressEvent(event)

    def start_fade_and_finish(self, target_window=None):
        """Start a graceful fade-out and call finish on target_window when complete."""
        try:
            self.finish_target = target_window
            self.fade_out = True
        except Exception:
            pass

# ===================== LIGHT RAY =====================
class LightRay:
    """Light ray with bending and deflection accumulation."""
    def __init__(self, start_pos, direction, color=(1,1,0,0.8), width=1.2, max_history=300):
        self.pos = np.array(start_pos, dtype=np.float32)
        self.dir = np.array(direction, dtype=np.float32)
        if np.linalg.norm(self.dir) == 0:
            self.dir = np.array([1,0,0], dtype=np.float32)
        self.dir = self.dir / np.linalg.norm(self.dir)
        self.path = [self.pos.copy()]
        self.color = color
        self.width = width
        self.total_deflection_angle = 0.0  # radians
        self.max_history = max_history

    def update(self, masses, dt=0.1):
        # compute accumulated deflection from all masses
        total_deflection = np.zeros(3, dtype=np.float32)
        for mass in masses:
            r_vec = mass['pos'] - self.pos
            r = np.linalg.norm(r_vec)
            if r < 0.05:
                r = 0.05
            deflect_vec = (4 * G * mass['mass'] / (c**2 * r**2)) * (r_vec / r)
            total_deflection += deflect_vec
            self.total_deflection_angle += np.linalg.norm(deflect_vec) * dt
        self.dir += total_deflection * dt
        norm_dir = np.linalg.norm(self.dir)
        if norm_dir == 0:
            norm_dir = 1.0
        self.dir /= norm_dir
        self.pos = self.pos + self.dir * dt
        self.path.append(self.pos.copy())
        # keep path short for performance
        if len(self.path) > self.max_history:
            self.path = self.path[-self.max_history:]

# ===================== VISUALIZER =====================
class LensingVisualizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhysX — Gravitational Lensing Visualizer")
        self.setGeometry(80,40,1400,920)

        self.gl_widget = gl.GLViewWidget()
        self.gl_widget.setBackgroundColor((2,4,8))
        self.setCentralWidget(self.gl_widget)
        self.gl_widget.setCameraPosition(distance=36,elevation=18,azimuth=30)

        grid = gl.GLGridItem()
        grid.setSize(30,30,1)
        grid.setSpacing(1,1,1)
        self.gl_widget.addItem(grid)

        # decorative starfield to give a richer background
        try:
            self.init_starfield()
        except Exception:
            pass

        self.masses = []      # each mass is {'pos':np.array([x,y,z]), 'mass':float, 'mesh':GLMeshItem}
        self.light_rays = []
        self.n_rays = 200
        self.ray_items = []
        self.max_history = 300

        # Fixed ray width and default palette
        self.ray_width = 1.2
        self.palette_name = 'Sunset'

        self.paused = False
        self.dt = 0.2

        self.init_ui()
        self.init_light_rays()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_simulation)
        self.timer.start(30)

    # ----------------- UI -----------------
    def init_ui(self):
        dock = QDockWidget("Controls", self)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        control_widget = QWidget()
        dock.setWidget(control_widget)
        layout = QVBoxLayout(control_widget)

        # Theme selector (makes visuals more "gorgeous")
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Deep Space", "Aurora", "Solar Dawn"])
        self.theme_combo.currentIndexChanged.connect(self.apply_theme)
        theme_layout.addWidget(self.theme_combo)
        layout.addLayout(theme_layout)

        # Ray palette selector (fixed colors)
        palette_layout = QHBoxLayout()
        palette_layout.addWidget(QLabel("Ray Palette:"))
        self.palette_combo = QComboBox()
        self.palette_combo.addItems(["Sunset", "Ocean", "Iridescent", "Monochrome"])
        try:
            self.palette_combo.setCurrentText(self.palette_name)
        except Exception:
            pass
        palette_layout.addWidget(self.palette_combo)
        apply_pal_btn = QPushButton("Apply Palette")
        apply_pal_btn.setToolTip("Apply the selected fixed palette to rays (colors remain fixed during simulation).")
        apply_pal_btn.clicked.connect(self.apply_palette_to_rays)
        palette_layout.addWidget(apply_pal_btn)
        layout.addLayout(palette_layout)

        # Mass slider (with tooltip)
        mass_label = QLabel("Black Hole Mass")
        mass_label.setToolTip("Mass determines deflection strength (higher = stronger lensing).")
        layout.addWidget(mass_label)
        self.mass_slider = QSlider(Qt.Horizontal)
        self.mass_slider.setRange(5,3000)
        self.mass_slider.setValue(500)
        self.mass_slider.setToolTip("Drag to change the mass used when creating new black holes.")
        layout.addWidget(self.mass_slider)

        # Number of rays
        ray_label = QLabel("Number of Light Rays")
        ray_label.setToolTip("More rays = higher fidelity but slower performance.")
        layout.addWidget(ray_label)
        self.ray_slider = QSlider(Qt.Horizontal)
        self.ray_slider.setRange(50,1200)
        self.ray_slider.setValue(self.n_rays)
        self.ray_slider.setToolTip("Adjust how many light rays are simulated.")
        layout.addWidget(self.ray_slider)
        self.ray_slider.valueChanged.connect(self.on_ray_count_changed)

        # Timestep control
        dt_label = QLabel("Simulation Speed (dt)")
        dt_label.setToolTip("Larger dt = faster simulation steps (may reduce accuracy).")
        layout.addWidget(dt_label)
        self.dt_slider = QSlider(Qt.Horizontal)
        self.dt_slider.setRange(1,50)
        self.dt_slider.setValue(int(self.dt*10))
        self.dt_slider.setToolTip("Control the simulation step size.")
        layout.addWidget(self.dt_slider)
        self.dt_slider.valueChanged.connect(self.on_dt_changed)

        # Buttons (with icons-like labels and tooltips)
        btn_layout = QHBoxLayout()
        add_bh_btn = QPushButton("➕ Add Black Hole")
        add_bh_btn.setToolTip("Create a new black hole near the center with selected mass.")
        add_bh_btn.clicked.connect(self.add_black_hole)
        btn_layout.addWidget(add_bh_btn)

        clear_bh_btn = QPushButton("🗑️ Clear BHs")
        clear_bh_btn.setToolTip("Remove all black holes from the scene.")
        clear_bh_btn.clicked.connect(self.clear_black_holes)
        btn_layout.addWidget(clear_bh_btn)
        layout.addLayout(btn_layout)

        btn2_layout = QHBoxLayout()
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setToolTip("Pause or resume the simulation (Space).")
        self.pause_btn.clicked.connect(self.toggle_pause)
        btn2_layout.addWidget(self.pause_btn)

        reset_btn = QPushButton("Reset Rays")
        reset_btn.setToolTip("Reset the simulated light rays (R key).")
        reset_btn.clicked.connect(self.reset_rays)
        btn2_layout.addWidget(reset_btn)
        layout.addLayout(btn2_layout)

        # Histogram (pyqtgraph)
        layout.addWidget(QLabel("Deflection Angles Histogram (°)"))
        self.hist_plot = pg.PlotWidget()
        self.hist_plot.setFixedHeight(150)
        self.hist_plot.setBackground(None)
        self.hist_bar_item = pg.BarGraphItem(x=[], height=[], width=1.0, brush='y')
        self.hist_plot.addItem(self.hist_bar_item)
        self.hist_plot.setLabel('left', 'Count')
        self.hist_plot.setLabel('bottom', 'Angle (deg)')
        layout.addWidget(self.hist_plot)

        # Black hole list
        layout.addWidget(QLabel("Black Holes"))
        self.bh_list = QListWidget()
        self.bh_list.itemClicked.connect(self.select_bh)
        self.bh_list.setToolTip("Click a black hole to inspect its properties.")
        layout.addWidget(self.bh_list)

        # Educational info & toggle
        self.formula_toggle = QCheckBox("Show theoretical single-mass deflection (4GM/(c^2 b))")
        self.formula_toggle.setChecked(True)
        self.formula_toggle.setToolTip("Toggle showing theoretical predictions for comparison.")
        layout.addWidget(self.formula_toggle)

        self.info_label = QLabel("<b>Formula:</b> α = 4GM / (c^2 b)  — deflection angle (rad) for a point mass.")
        self.info_label.setWordWrap(True)
        self.info_label.setOpenExternalLinks(True)
        layout.addWidget(self.info_label)

        # status
        self.angle_label = QLabel("Average Deflection: 0.00°")
        layout.addWidget(self.angle_label)

        # bottom help/about row will be added when we create the Learn dock and status
        layout.addStretch()

        # Help and About buttons
        help_btn = QPushButton("Learn")
        help_btn.setToolTip("Open the educational panel with references and explanations")
        about_btn = QPushButton("About")
        about_btn.setToolTip("About this app and controls")
        # add them in a small horizontal layout at bottom of controls dock
        hb = QHBoxLayout()
        hb.addWidget(help_btn)
        hb.addWidget(about_btn)
        control_widget.layout().addLayout(hb)

        # Rich Learn dock
        learn_dock = QDockWidget("Learn", self)
        learn_dock.setObjectName('Learn')
        learn_browser = QTextBrowser()
        learn_browser.setOpenExternalLinks(True)
        learn_browser.setHtml("""
        <h2>Gravitational Lensing — Quick Guide</h2>
        <p><b>What you see:</b> Light rays are deflected as they pass near massive objects (black holes). The simulation integrates small deflections to show curving paths.</p>
        <p><b>Formula:</b> α = 4GM/(c^2 b) — for a point mass; b is the impact parameter (closest approach). α is small-angle deflection in radians.</p>
        <p><b>How to explore:</b> Use <i>Black Hole Mass</i> to increase deflection strength and <i>Number of Rays</i> to reveal caustics; enable <b>Teaching Mode</b> to see predicted α and estimate b for visible BHs.</p>
        <p>Try the presets below to see typical lensing patterns and remember: simulations are scaled for clarity rather than exact astrophysical units.</p>
        <p><a href='preset://strong'>Apply preset: Strong single BH</a> — highlights ring formation.</p>
        <p><a href='preset://binary'>Apply preset: Binary BH</a> — see interference of two lenses.</p>
        <p>Further reading: <a href='https://en.wikipedia.org/wiki/Gravitational_lensing'>Wikipedia</a> • <a href='https://arxiv.org/abs/astro-ph/0001491'>Intro notes</a></p>
        """)
        learn_browser.anchorClicked.connect(lambda url: self.handle_learn_link(url))
        learn_dock.setWidget(learn_browser)
        self.addDockWidget(Qt.LeftDockWidgetArea, learn_dock)

        # connect help/about
        help_btn.clicked.connect(lambda: learn_dock.raise_())
        about_btn.clicked.connect(self.show_about)

        # palette swatch preview
        self.palette_swatch = QLabel()
        self.palette_swatch.setFixedWidth(180)
        self.palette_swatch.setStyleSheet('color:#EEE;')
        self.update_palette_swatch()
        self.statusBar().addPermanentWidget(self.palette_swatch)

        # Presets and highlight controls
        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(6)
        p1 = QPushButton("Preset: Strong Single")
        p1.setToolTip("Apply a strong single black hole preset")
        p1.clicked.connect(self.preset_strong_single)
        preset_layout.addWidget(p1)
        p2 = QPushButton("Preset: Binary BH")
        p2.setToolTip("Apply a binary black hole preset")
        p2.clicked.connect(self.preset_binary)
        preset_layout.addWidget(p2)
        p3 = QPushButton("Highlight Max")
        p3.setToolTip("Highlight the ray with maximum accumulated deflection")
        p3.clicked.connect(self.highlight_max_ray)
        preset_layout.addWidget(p3)
        # Guided tour button
        p4 = QPushButton("Guided Tour")
        p4.setToolTip("Run a short guided tour of the UI and concepts")
        p4.clicked.connect(self.start_guided_tour)
        preset_layout.addWidget(p4)
        control_widget.layout().addLayout(preset_layout)

        # status legend to explain color mapping and UI hints
        self.legend_label = QLabel("<b>Legend:</b> Color = ray palette (fixed). Width fixed for clarity.")
        self.legend_label.setStyleSheet("color: #EEE; padding: 4px;")
        self.statusBar().addPermanentWidget(self.legend_label)

        # keyboard shortcuts
        QShortcut(QKeySequence("Space"), self, activated=self.toggle_pause)
        QShortcut(QKeySequence("R"), self, activated=self.reset_rays)
        QShortcut(QKeySequence("B"), self, activated=self.add_black_hole)

        # Apply initial theme
        try:
            self.apply_theme()
        except Exception:
            pass

    def apply_theme(self):
        idx = self.theme_combo.currentIndex() if hasattr(self, 'theme_combo') else 0
        if idx == 0:
            # Deep Space
            self.gl_widget.setBackgroundColor((2,4,8))
            self.setStyleSheet("QWidget{color:#E8F2FF; background-color:#0B0F1A;}")
        elif idx == 1:
            # Aurora
            self.gl_widget.setBackgroundColor((6,18,25))
            self.setStyleSheet("QWidget{color:#E8F5E9; background-color:#001F24;}")
        else:
            # Solar Dawn
            self.gl_widget.setBackgroundColor((28,14,8))
            self.setStyleSheet("QWidget{color:#3a260f; background-color:#FFF7EF;}")

    # ----------------- Palettes & Helpers -----------------
    def hex_to_rgba(self, s, alpha=1.0):
        s = s.lstrip('#')
        if len(s) == 3:
            s = ''.join([c*2 for c in s])
        r = int(s[0:2], 16) / 255.0
        g = int(s[2:4], 16) / 255.0
        b = int(s[4:6], 16) / 255.0
        return (r, g, b, alpha)

    def get_palette_colors(self, name, n=8):
        name = (name or 'Sunset')
        if name == 'Sunset':
            hexes = ['#FFB74D', '#FF8A65', '#FF7043', '#FFE082', '#FFEA00']
        elif name == 'Ocean':
            hexes = ['#81D4FA', '#4FC3F7', '#29B6F6', '#0288D1', '#01579B']
        elif name == 'Iridescent':
            # generate n hues
            hues = [(i / max(1, n)) for i in range(n)]
            hexes = []
            for h in hues:
                import colorsys
                r,g,b = colorsys.hsv_to_rgb(h, 0.6, 1.0)
                hexes.append('#%02x%02x%02x' % (int(r*255), int(g*255), int(b*255)))
        else:  # Monochrome
            hexes = ['#FFFFFF']
        colors = [self.hex_to_rgba(h, alpha=0.95) for h in hexes]
        # if more colors needed, repeat
        if len(colors) < n:
            colors = (colors * ((n // len(colors)) + 1))[:n]
        return colors

    def apply_palette_to_rays(self):
        name = self.palette_combo.currentText() if hasattr(self, 'palette_combo') else self.palette_name
        colors = self.get_palette_colors(name, max(8, self.n_rays))
        self.palette_name = name
        for i, ray in enumerate(self.light_rays):
            ray.color = colors[i % len(colors)]
            # update the GL item color if present
            if i < len(self.ray_items):
                try:
                    self.ray_items[i].setData(color=ray.color)
                except Exception:
                    pass
        try:
            self.statusBar().showMessage(f"Applied palette: {name}", 2000)
        except Exception:
            pass
        self.update_palette_swatch()

    def update_palette_swatch(self):
        name = getattr(self, 'palette_name', 'Sunset')
        colors = self.get_palette_colors(name, n=6)
        # create inline swatches
        html = '<span style="color:#EEE">Palette:</span> '
        for c in colors[:6]:
            r,g,b,a = c
            hexc = '#%02x%02x%02x' % (int(r*255), int(g*255), int(b*255))
            html += f"<span style='display:inline-block; width:14px; height:14px; background:{hexc}; border-radius:7px; margin-right:4px;'></span>"
        try:
            self.palette_swatch.setText(html)
        except Exception:
            pass

    def preset_strong_single(self):
        self.clear_black_holes()
        self.mass_slider.setValue(2200)
        self.ray_slider.setValue(400)
        self.reset_rays()
        # central massive BH
        self.add_black_hole(pos=np.array([0.0,0.0,0.0]), mass=2200)
        self.statusBar().showMessage('Applied preset: Strong single BH',1500)

    def preset_binary(self):
        self.clear_black_holes()
        self.mass_slider.setValue(900)
        self.ray_slider.setValue(600)
        self.reset_rays()
        # two BHs to create interesting lensing
        self.add_black_hole(pos=np.array([0.0, 1.2, 0.0]), mass=1200)
        self.add_black_hole(pos=np.array([0.0, -1.4, 0.0]), mass=1100)
        self.statusBar().showMessage('Applied preset: Binary BH',1500)

    def highlight_max_ray(self):
        if not self.light_rays:
            return
        vals = [r.total_deflection_angle for r in self.light_rays]
        idx = int(np.argmax(vals))
        # temporarily recolor and enlarge the width
        try:
            orig_color = self.light_rays[idx].color
            orig_width = getattr(self.light_rays[idx], 'width', self.ray_width)
            self.light_rays[idx].color = (1.0,0.0,1.0,1.0)
            if idx < len(self.ray_items):
                try:
                    self.ray_items[idx].setData(color=self.light_rays[idx].color)
                except Exception:
                    pass
            def restore():
                try:
                    self.light_rays[idx].color = orig_color
                    if idx < len(self.ray_items):
                        self.ray_items[idx].setData(color=orig_color)
                except Exception:
                    pass
            QTimer.singleShot(2200, restore)
        except Exception:
            pass

    def handle_learn_link(self, qurl):
        try:
            s = qurl.toString()
            if s.startswith('preset://'):
                p = s.split('://',1)[1]
                if p == 'strong':
                    self.preset_strong_single()
                elif p == 'binary':
                    self.preset_binary()
        except Exception:
            pass

    # ----------------- Guided Tour -----------------
    def start_guided_tour(self):
        # quick non-blocking tour of UI elements and concepts
        try:
            self.learn_dock = self.findChild(QDockWidget, 'Learn')
            if self.learn_dock is not None:
                br = self.learn_dock.widget()
                # tour steps: title, body
                self._tour_steps = [
                    ("Welcome to PhysX", "This short tour highlights the main controls: Theme, Ray Palette, Black Hole Mass, and the Teaching Mode HUD."),
                    ("Ray Palette", "Pick a palette and press Apply Palette to set fixed ray colors for clear demonstrations."),
                    ("Black Holes", "Use Add Black Hole or presets to place masses and observe deflection. The HUD shows predicted α values."),
                    ("Presets", "Try 'Strong Single' or 'Binary BH' presets to see classic lensing patterns.")
                ]
                self._tour_index = 0
                self.learn_dock.raise_()
                self._tour_next()
        except Exception:
            pass

    def _tour_next(self):
        if not hasattr(self, '_tour_steps'):
            return
        if self._tour_index >= len(self._tour_steps):
            try:
                self.statusBar().showMessage('Tour finished', 2000)
            except Exception:
                pass
            return
        title, body = self._tour_steps[self._tour_index]
        try:
            self.learn_dock.widget().setHtml(f"<h3>{title}</h3><p>{body}</p>")
            self.statusBar().showMessage(title, 2500)
        except Exception:
            pass
        self._tour_index += 1
        QTimer.singleShot(2400, self._tour_next)

    def show_about(self):
        QMessageBox.information(self, "About PhysX",
                                "PhysX — Interactive Gravitational Lensing Visualizer\n\n"
                                "An educational demo for gravitational lensing. Controls:\n"
                                "- Space: pause/resume\n- R: reset rays\n- B: add black hole\n\nEnjoy exploring lensing phenomena!")

    # ----------------- Light Rays -----------------
    def init_light_rays(self):
        # remove old
        for item in getattr(self, 'ray_items', []):
            try:
                self.gl_widget.removeItem(item)
            except Exception:
                pass
        self.light_rays = []
        self.ray_items = []
        # choose a palette for initial rays
        palette = self.get_palette_colors(getattr(self, 'palette_name', 'Sunset'), max(8, self.n_rays))
        for i in range(self.n_rays):
            y = np.random.uniform(-6,6)
            z = np.random.uniform(-6,6)
            color = palette[i % len(palette)]
            ray = LightRay(start_pos=[-20, y, z], direction=[1, 0, 0], color=color, width=self.ray_width, max_history=self.max_history)
            self.light_rays.append(ray)
            # initial GL item
            data = np.array(ray.path, dtype=np.float32)
            item = gl.GLLinePlotItem(pos=data, width=ray.width, color=ray.color, antialias=True)
            item.setGLOptions('additive')
            self.gl_widget.addItem(item)
            self.ray_items.append(item)

    # ----------------- Black Hole -----------------
    def add_black_hole(self, pos=None, mass=None):
        # allow presets to pass explicit position and mass
        if pos is None:
            pos = np.random.uniform(-3,3,3)
            pos[0] = 0.0  # keep near center for clearer lensing
        if mass is None:
            mass = float(self.mass_slider.value())
        mesh = gl.MeshData.sphere(rows=40, cols=40, radius=1.0)
        bh_mesh = gl.GLMeshItem(meshdata=mesh, smooth=True, color=(0.95,0.6,0.2,0.95), shader='shaded')
        bh_mesh.translate(*pos)
        # soft halo to make BH glow; store a small phase for gentle pulsing
        halo_mesh = gl.MeshData.sphere(rows=20, cols=20, radius=1.8)
        halo = gl.GLMeshItem(meshdata=halo_mesh, smooth=True, color=(1.0,0.7,0.2,0.22), shader='shaded')
        halo.translate(*pos)
        halo.setGLOptions('additive')
        self.gl_widget.addItem(halo)
        self.gl_widget.addItem(bh_mesh)
        self.masses.append({'pos': np.array(pos, dtype=np.float32), 'mass': mass, 'mesh': bh_mesh, 'halo': halo, 'halo_phase': np.random.rand()*6.28, 'halo_base_alpha':0.22})
        self.bh_list.addItem(f"BH {len(self.masses)-1}: mass={mass:.0f}")
        # create a simple luminous accretion spray (a few rays)
        self.create_accretion_disk(pos)
        try:
            self.statusBar().showMessage("Added black hole",1500)
        except Exception:
            pass

    def create_accretion_disk(self, center):
        n_points = 64
        radii = np.linspace(1.2, 2.6, 4)
        for r in radii:
            angles = np.linspace(0, 2*np.pi, n_points)
            for angle in angles[::2]:
                pos = np.array([center[0] + r*np.cos(angle),
                                center[1] + r*np.sin(angle),
                                center[2] + 0.05*np.sin(4*angle)])
                vel = np.array([-np.sin(angle)*0.4, np.cos(angle)*0.4, 0])
                ray = LightRay(pos, vel, color=(1.0, 0.65, 0.2, 0.85), width=self.ray_width, max_history=self.max_history)
                self.light_rays.append(ray)
                item = gl.GLLinePlotItem(pos=np.array(ray.path, dtype=np.float32), width=ray.width, color=ray.color, antialias=True)
                item.setGLOptions('additive')
                self.gl_widget.addItem(item)
                self.ray_items.append(item)

    def init_starfield(self, n=360):
        # place stars far away to provide depth; small random sizes
        pts = np.column_stack((np.random.uniform(-200,200,n), np.random.uniform(-200,200,n), np.random.uniform(-120,-20,n)))
        sizes = np.random.uniform(1.0,4.0,n)
        colors = np.ones((n,4), dtype=float) * np.array([0.92,0.94,1.0,0.65])
        try:
            self.star_item = gl.GLScatterPlotItem(pos=pts, size=sizes, color=colors, pxMode=False)
            self.gl_widget.addItem(self.star_item)
        except Exception:
            # if GLScatterPlotItem is not available we silently continue
            self.star_item = None
        for r in radii:
            angles = np.linspace(0, 2*np.pi, n_points)
            for angle in angles[::2]:
                pos = np.array([center[0] + r*np.cos(angle),
                                center[1] + r*np.sin(angle),
                                center[2] + 0.05*np.sin(4*angle)])
                vel = np.array([-np.sin(angle)*0.4, np.cos(angle)*0.4, 0])
                ray = LightRay(pos, vel, color=(1.0, 0.65, 0.2, 0.85), width=self.ray_width, max_history=self.max_history)
                self.light_rays.append(ray)
                item = gl.GLLinePlotItem(pos=np.array(ray.path, dtype=np.float32), width=ray.width, color=ray.color, antialias=True)
                item.setGLOptions('additive')
                self.gl_widget.addItem(item)
                self.ray_items.append(item)

    def clear_black_holes(self):
        for m in self.masses:
            try:
                self.gl_widget.removeItem(m['mesh'])
            except Exception:
                pass
            try:
                if 'halo' in m:
                    self.gl_widget.removeItem(m['halo'])
            except Exception:
                pass
        self.masses = []
        self.bh_list.clear()

    def select_bh(self, item):
        text = item.text()
        idx = int(text.split()[1].strip(':'))
        if idx < len(self.masses):
            m = self.masses[idx]
            QMessageBox.information(self, "Black Hole Selected",
                                    f"Index: {idx}\nMass: {m['mass']:.1f}\nPosition: {m['pos']}")

    # ----------------- Controls handlers -----------------
    def on_ray_count_changed(self, v):
        self.n_rays = v
        self.reset_rays()

    def on_dt_changed(self, v):
        self.dt = v / 10.0

    def toggle_pause(self):
        self.paused = not self.paused
        self.pause_btn.setText("Resume" if self.paused else "Pause")

    def reset_rays(self):
        # remove current ray items then re-init
        for item in self.ray_items:
            try:
                self.gl_widget.removeItem(item)
            except Exception:
                pass
        self.init_light_rays()

    # ----------------- Simulation -----------------
    def update_simulation(self):
        if not self.paused:
            dt = self.dt
            for i, ray in enumerate(self.light_rays):
                # update physics
                ray.update(self.masses, dt=dt)
                # prepare positions robustly
                pos = np.array(ray.path, dtype=np.float32)
                if pos.ndim == 1:
                    pos = pos[np.newaxis, :]
                if pos.shape[1] == 2:
                    pos = np.hstack([pos, np.zeros((pos.shape[0], 1), dtype=np.float32)])
                elif pos.shape[1] > 3:
                    pos = pos[:, :3]

                # ensure a corresponding GL item exists
                if i >= len(self.ray_items):
                    item = gl.GLLinePlotItem(pos=pos, width=ray.width, color=ray.color, antialias=True)
                    item.setGLOptions('additive')
                    self.gl_widget.addItem(item)
                    self.ray_items.append(item)

                # Keep ray colors fixed to their initial value (do NOT recolor dynamically)
                try:
                    # attempt to set positional data and preserve the ray's configured color
                    self.ray_items[i].setData(pos=pos, color=ray.color)
                except Exception:
                    # fallback if color kwarg isn't supported
                    try:
                        self.ray_items[i].setData(pos=pos)
                    except Exception:
                        pass

        # Compute aggregated stats for UI, independent of pause
        angles = []
        for ray in self.light_rays:
            angles.append(math.degrees(ray.total_deflection_angle))
        angles_arr = np.array(angles) if len(angles) else np.array([0.0])

        # histogram
        try:
            hist, edges = np.histogram(angles_arr, bins=np.linspace(0, max(1.0, angles_arr.max()), 25))
            centers = (edges[:-1] + edges[1:]) / 2.0
            self.hist_plot.clear()
            self.hist_bar_item = pg.BarGraphItem(x=centers, height=hist, width=(edges[1]-edges[0])*0.9, brush=pg.mkBrush(230,200,50))
            self.hist_plot.addItem(self.hist_bar_item)
        except Exception:
            pass

        # Show average deflection and theoretical predictions if requested
        avg_angle = float(np.mean(angles_arr)) if len(angles_arr) else 0.0
        self.angle_label.setText(f"Average Deflection: {avg_angle:.3f}°")

        if self.formula_toggle.isChecked() and len(self.masses) > 0:
            # compute simple predicted deflection for each BH: alpha = 4GM/(c^2 b)
            # approximate b as average perpendicular distance of rays to BH in yz plane
            preds = []
            for m in self.masses:
                b_list = []
                for ray in self.light_rays:
                    # use a quick estimate using initial ray positions (assuming trajectories mainly move along +x)
                    initial_pos = ray.path[0]
                    perp = initial_pos[1:] - m['pos'][1:]
                    b = np.linalg.norm(perp)
                    if b < 0.05: b = 0.05
                    b_list.append(b)
                b_avg = np.mean(b_list) if len(b_list) else 1.0
                alpha = 4 * G * m['mass'] / (c**2 * b_avg)  # radians
                preds.append(math.degrees(alpha))
            info = ", ".join([f"BH{i}: pred={p:.3f}°" for i,p in enumerate(preds)])
            self.info_label.setText(f"<b>Formula:</b> α = 4GM/(c^2 b). Predictions: {info}")
        else:
            self.info_label.setText("<b>Formula:</b> α = 4GM / (c^2 b) — deflection (rad) for a point mass.")

        # Animate halos and twinkle stars
        t = time.time()
        try:
            for m in self.masses:
                if 'halo' in m:
                    phase = m.get('halo_phase', 0.0)
                    base = m.get('halo_base_alpha', 0.22)
                    alpha = base + 0.08 * math.sin(t*2.2 + phase)
                    alpha = max(0.06, min(0.65, alpha))
                    try:
                        # attempt to set color with new alpha
                        c = list(m['halo'].color)
                        if len(c) >= 4:
                            newc = (c[0], c[1], c[2], alpha)
                            try:
                                m['halo'].setColor(newc)
                            except Exception:
                                # fallback: replace halo by re-adding a fresh one with adjusted alpha
                                pass
                    except Exception:
                        pass
            # star twinkle
            if getattr(self, 'star_item', None) is not None:
                try:
                    n = len(self.star_item.pos)
                    col = np.ones((n,4), dtype=float) * np.array([0.92,0.94,1.0,0.6])
                    col[:,3] = col[:,3] * (0.85 + 0.25 * np.sin(t*3.0 + np.arange(n)*0.02))
                    self.star_item.setData(color=col)
                except Exception:
                    pass
        except Exception:
            pass

        # Update Teaching HUD if enabled
        if getattr(self, 'teach_toggle', None) and self.teach_toggle.isChecked():
            hud_lines = ["<b>Teaching Mode:</b>"]
            hud_lines.append(f"Average deflection (deg): <b>{avg_angle:.3f}°</b>")
            if len(self.masses) > 0:
                # show predictions for first few BHs
                for i,m in enumerate(self.masses[:3]):
                    # compute simple prediction using mean impact parameter as in the formula
                    b_list = []
                    for ray in self.light_rays:
                        initial_pos = ray.path[0]
                        perp = initial_pos[1:] - m['pos'][1:]
                        b = np.linalg.norm(perp)
                        if b < 0.05: b = 0.05
                        b_list.append(b)
                    b_avg = np.mean(b_list) if len(b_list) else 1.0
                    alpha_deg = math.degrees(4 * G * m['mass'] / (c**2 * b_avg))
                    hud_lines.append(f"BH{i}: mass={m['mass']:.0f}, predicted α≈{alpha_deg:.3f}° (b≈{b_avg:.2f})")
            hud_lines.append("Tip: Try changing mass or number of rays to see lensing patterns evolve.")
            self.hud_label.setText('<br>'.join(hud_lines))
            self.hud_label.show()
        else:
            try:
                self.hud_label.hide()
            except Exception:
                pass

        # subtle orbit/auto-rotate for a pleasant view
        self.gl_widget.orbit(0.12, 0.06)

# ===================== MAIN =====================
def main():
    app = QApplication(sys.argv)
    splash = PhysXSplashScreen()
    window = LensingVisualizer()
    # show after a short splash; start a graceful fade-and-finish after timeout
    QTimer.singleShot(3000, lambda: splash.start_fade_and_finish(window))
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()