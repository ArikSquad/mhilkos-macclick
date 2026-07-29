#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use std::{
    collections::HashSet,
    sync::{
        atomic::{AtomicBool, Ordering},
        mpsc::{self, Receiver, Sender},
        Arc,
    },
    thread,
    time::Duration,
};

use device_query::{DeviceQuery, DeviceState, Keycode};
use eframe::egui;
use enigo::{Button, Coordinate, Direction, Enigo, Mouse, Settings};

fn main() -> eframe::Result {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([480.0, 610.0])
            .with_min_inner_size([420.0, 560.0]),
        ..Default::default()
    };
    eframe::run_native(
        "MacClik",
        options,
        Box::new(|cc| Ok(Box::new(MacClik::new(cc)))),
    )
}

#[derive(Clone, Copy, PartialEq)]
enum MouseButton {
    Left,
    Right,
    Middle,
}

impl MouseButton {
    fn label(self) -> &'static str {
        match self {
            Self::Left => "Left",
            Self::Right => "Right",
            Self::Middle => "Middle",
        }
    }

    fn enigo(self) -> Button {
        match self {
            Self::Left => Button::Left,
            Self::Right => Button::Right,
            Self::Middle => Button::Middle,
        }
    }
}

#[derive(Clone)]
struct ClickConfig {
    interval: Duration,
    button: MouseButton,
    double_click: bool,
    fixed_position: Option<(i32, i32)>,
    repeat_count: Option<u64>,
}

enum InputEvent {
    Keys(Vec<Keycode>),
    Position(i32, i32),
}

enum WorkerEvent {
    Finished,
    Error(String),
}

struct MacClik {
    hours: u32,
    minutes: u32,
    seconds: u32,
    milliseconds: u32,
    button: MouseButton,
    double_click: bool,
    fixed_position: bool,
    x: i32,
    y: i32,
    repeat_forever: bool,
    repeat_count: u64,
    hotkey: Vec<Keycode>,
    recording_hotkey: bool,
    picking_position: bool,
    previous_keys: HashSet<Keycode>,
    running: Arc<AtomicBool>,
    input_rx: Receiver<InputEvent>,
    worker_tx: Sender<WorkerEvent>,
    worker_rx: Receiver<WorkerEvent>,
    status: String,
}

impl MacClik {
    fn new(cc: &eframe::CreationContext<'_>) -> Self {
        cc.egui_ctx.set_visuals(egui::Visuals::dark());
        let (input_tx, input_rx) = mpsc::channel();
        let (worker_tx, worker_rx) = mpsc::channel();
        spawn_input_monitor(input_tx, cc.egui_ctx.clone());

        Self {
            hours: 0,
            minutes: 0,
            seconds: 0,
            milliseconds: 100,
            button: MouseButton::Left,
            double_click: false,
            fixed_position: false,
            x: 0,
            y: 0,
            repeat_forever: true,
            repeat_count: 10,
            hotkey: vec![Keycode::F6],
            recording_hotkey: false,
            picking_position: false,
            previous_keys: HashSet::new(),
            running: Arc::new(AtomicBool::new(false)),
            input_rx,
            worker_tx,
            worker_rx,
            status: "Stopped".into(),
        }
    }

    fn interval(&self) -> Duration {
        Duration::from_millis(
            u64::from(self.hours) * 3_600_000
                + u64::from(self.minutes) * 60_000
                + u64::from(self.seconds) * 1_000
                + u64::from(self.milliseconds),
        )
    }

    fn toggle(&mut self) {
        if self.running.load(Ordering::Relaxed) {
            self.stop();
        } else {
            self.start();
        }
    }

    fn start(&mut self) {
        let interval = self.interval();
        if interval.is_zero() {
            self.status = "Interval must be greater than zero".into();
            return;
        }
        if !self.repeat_forever && self.repeat_count == 0 {
            self.status = "Repeat count must be greater than zero".into();
            return;
        }

        let config = ClickConfig {
            interval,
            button: self.button,
            double_click: self.double_click,
            fixed_position: self.fixed_position.then_some((self.x, self.y)),
            repeat_count: (!self.repeat_forever).then_some(self.repeat_count),
        };
        self.running.store(true, Ordering::Relaxed);
        self.status = "Running".into();
        spawn_clicker(config, Arc::clone(&self.running), self.worker_tx.clone());
    }

    fn stop(&mut self) {
        self.running.store(false, Ordering::Relaxed);
        self.status = "Stopped".into();
    }

    fn handle_events(&mut self) {
        while let Ok(event) = self.input_rx.try_recv() {
            match event {
                InputEvent::Position(x, y) if self.picking_position => {
                    self.x = x;
                    self.y = y;
                }
                InputEvent::Keys(keys) => self.handle_keys(keys),
                _ => {}
            }
        }
        while let Ok(event) = self.worker_rx.try_recv() {
            self.running.store(false, Ordering::Relaxed);
            match event {
                WorkerEvent::Finished => self.status = "Finished".into(),
                WorkerEvent::Error(error) => self.status = error,
            }
        }
    }

    fn handle_keys(&mut self, keys: Vec<Keycode>) {
        let current: HashSet<_> = keys.into_iter().collect();
        let newly_pressed = current
            .difference(&self.previous_keys)
            .copied()
            .collect::<Vec<_>>();

        if self.picking_position && newly_pressed.contains(&Keycode::Enter) {
            self.picking_position = false;
            self.status = format!("Position set to {}, {}", self.x, self.y);
        } else if self.recording_hotkey {
            if newly_pressed.contains(&Keycode::Escape) {
                self.recording_hotkey = false;
                self.status = "Hotkey unchanged".into();
            } else if newly_pressed.iter().any(|key| !is_modifier(*key)) {
                let mut combo: Vec<_> = current.iter().copied().collect();
                combo.sort_by_key(|key| format!("{key:?}"));
                self.hotkey = combo;
                self.recording_hotkey = false;
                self.status = "Hotkey updated".into();
            }
        } else if !newly_pressed.is_empty()
            && current == self.hotkey.iter().copied().collect()
            && newly_pressed.iter().any(|key| !is_modifier(*key))
        {
            self.toggle();
        }
        self.previous_keys = current;
    }
}

impl eframe::App for MacClik {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.handle_events();
        let running = self.running.load(Ordering::Relaxed);

        egui::CentralPanel::default().show(ctx, |ui| {
            ui.heading("MacClik");
            ui.label("A small autoclicker that stays out of your way.");
            ui.add_space(12.0);

            ui.group(|ui| {
                ui.strong("Click interval");
                ui.horizontal(|ui| {
                    number(ui, &mut self.hours, "hours", 0..=23);
                    number(ui, &mut self.minutes, "min", 0..=59);
                    number(ui, &mut self.seconds, "sec", 0..=59);
                    number(ui, &mut self.milliseconds, "ms", 0..=999);
                });
            });
            ui.add_space(8.0);

            ui.group(|ui| {
                ui.strong("Click");
                ui.horizontal(|ui| {
                    egui::ComboBox::from_id_salt("button")
                        .selected_text(self.button.label())
                        .show_ui(ui, |ui| {
                            ui.selectable_value(&mut self.button, MouseButton::Left, "Left");
                            ui.selectable_value(&mut self.button, MouseButton::Right, "Right");
                            ui.selectable_value(&mut self.button, MouseButton::Middle, "Middle");
                        });
                    ui.checkbox(&mut self.double_click, "Double click");
                });
            });
            ui.add_space(8.0);

            ui.group(|ui| {
                ui.strong("Position");
                ui.radio_value(&mut self.fixed_position, false, "Follow the pointer");
                ui.horizontal(|ui| {
                    ui.radio_value(&mut self.fixed_position, true, "Fixed");
                    ui.add_enabled(
                        self.fixed_position,
                        egui::DragValue::new(&mut self.x).prefix("X "),
                    );
                    ui.add_enabled(
                        self.fixed_position,
                        egui::DragValue::new(&mut self.y).prefix("Y "),
                    );
                    if ui
                        .add_enabled(self.fixed_position, egui::Button::new("Pick"))
                        .clicked()
                    {
                        self.picking_position = true;
                        self.status = "Move the pointer and press Enter".into();
                    }
                });
            });
            ui.add_space(8.0);

            ui.group(|ui| {
                ui.strong("Repeat");
                ui.horizontal(|ui| {
                    ui.radio_value(&mut self.repeat_forever, true, "Until stopped");
                    ui.radio_value(&mut self.repeat_forever, false, "Count");
                    ui.add_enabled(
                        !self.repeat_forever,
                        egui::DragValue::new(&mut self.repeat_count).range(1..=u64::MAX),
                    );
                });
            });
            ui.add_space(8.0);

            ui.group(|ui| {
                ui.strong("Global hotkey");
                ui.horizontal(|ui| {
                    ui.monospace(hotkey_name(&self.hotkey));
                    if ui
                        .add_enabled(!self.recording_hotkey, egui::Button::new("Change"))
                        .clicked()
                    {
                        self.recording_hotkey = true;
                        self.status = "Press a key combination (Escape cancels)".into();
                    }
                });
            });
            ui.add_space(14.0);

            ui.horizontal(|ui| {
                let color = if running {
                    egui::Color32::from_rgb(80, 200, 120)
                } else {
                    egui::Color32::from_rgb(220, 100, 100)
                };
                ui.colored_label(color, &self.status);
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if ui
                        .add_sized(
                            [100.0, 34.0],
                            egui::Button::new(if running { "Stop" } else { "Start" }),
                        )
                        .clicked()
                    {
                        self.toggle();
                    }
                });
            });
        });
    }

    fn on_exit(&mut self, _gl: Option<&eframe::glow::Context>) {
        self.running.store(false, Ordering::Relaxed);
    }
}

fn number(ui: &mut egui::Ui, value: &mut u32, suffix: &str, range: std::ops::RangeInclusive<u32>) {
    ui.vertical(|ui| {
        ui.add(egui::DragValue::new(value).range(range));
        ui.small(suffix);
    });
}

fn is_modifier(key: Keycode) -> bool {
    matches!(
        key,
        Keycode::LShift
            | Keycode::RShift
            | Keycode::LControl
            | Keycode::RControl
            | Keycode::LAlt
            | Keycode::RAlt
            | Keycode::LMeta
            | Keycode::RMeta
    )
}

fn hotkey_name(keys: &[Keycode]) -> String {
    keys.iter()
        .map(|key| format!("{key:?}"))
        .collect::<Vec<_>>()
        .join(" + ")
}

fn spawn_input_monitor(tx: Sender<InputEvent>, ctx: egui::Context) {
    thread::spawn(move || {
        let device = DeviceState::new();
        let mut old_keys = Vec::new();
        let mut old_position = (i32::MIN, i32::MIN);
        loop {
            let keys = device.get_keys();
            if keys != old_keys {
                old_keys = keys.clone();
                if tx.send(InputEvent::Keys(keys)).is_err() {
                    break;
                }
                ctx.request_repaint();
            }
            let mouse = device.get_mouse();
            if mouse.coords != old_position {
                old_position = mouse.coords;
                if tx
                    .send(InputEvent::Position(mouse.coords.0, mouse.coords.1))
                    .is_err()
                {
                    break;
                }
            }
            thread::sleep(Duration::from_millis(15));
        }
    });
}

fn spawn_clicker(config: ClickConfig, running: Arc<AtomicBool>, tx: Sender<WorkerEvent>) {
    thread::spawn(move || {
        let mut enigo = match Enigo::new(&Settings::default()) {
            Ok(enigo) => enigo,
            Err(error) => {
                let _ = tx.send(WorkerEvent::Error(format!(
                    "Could not access input: {error}"
                )));
                return;
            }
        };
        let mut completed = 0;
        while running.load(Ordering::Relaxed) {
            if let Some((x, y)) = config.fixed_position {
                if let Err(error) = enigo.move_mouse(x, y, Coordinate::Abs) {
                    let _ = tx.send(WorkerEvent::Error(format!(
                        "Could not move pointer: {error}"
                    )));
                    return;
                }
            }
            let clicks = if config.double_click { 2 } else { 1 };
            for _ in 0..clicks {
                if let Err(error) = enigo.button(config.button.enigo(), Direction::Click) {
                    let _ = tx.send(WorkerEvent::Error(format!("Could not click: {error}")));
                    return;
                }
            }
            completed += 1;
            if config.repeat_count.is_some_and(|limit| completed >= limit) {
                let _ = tx.send(WorkerEvent::Finished);
                return;
            }
            let mut remaining = config.interval;
            while running.load(Ordering::Relaxed) && !remaining.is_zero() {
                let nap = remaining.min(Duration::from_millis(25));
                thread::sleep(nap);
                remaining = remaining.saturating_sub(nap);
            }
        }
    });
}
