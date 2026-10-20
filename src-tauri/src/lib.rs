// Manages the same background processes scripts/start.sh and stop.sh do
// (ollama, ComfyUI, the FastAPI backend), as native child processes owned by
// the Tauri app window instead of separate terminal-launched scripts.
//
// Scope note: this resolves the project root as the parent of the running
// binary's working directory (matching `tauri dev`'s cwd of `src-tauri/`),
// or `NOVELLA_PROJECT_ROOT` if set. It does NOT bundle comfyui/ollama/model
// weights inside the .app itself - that's a separate, much larger piece of
// work (PyInstaller-style bundling of a multi-GB ML dependency tree) left
// for later. Today this wraps the existing native dev setup in a real
// window instead of requiring the terminal scripts, for the same
// single-machine use case the README's "moving to another machine" section
// already documents.

use std::collections::HashMap;
use std::env;
use std::fs::{self, OpenOptions};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Mutex, OnceLock};
use std::time::Duration;

struct ManagedProcesses {
    ollama: Mutex<Option<Child>>,
    comfyui: Mutex<Option<Child>>,
    backend: Mutex<Option<Child>>,
}

// A plain global rather than Tauri-managed state: a SIGTERM/SIGINT handler
// (registered via ctrlc, for the common "someone killed the app process
// directly" case - Activity Monitor force-quit, `kill`, system shutdown)
// needs to reach the same child handles that the window's CloseRequested
// event does, and ctrlc's handler closure has no path back into Tauri's
// app-state system.
static PROCESSES: OnceLock<ManagedProcesses> = OnceLock::new();

// CARGO_MANIFEST_DIR is resolved by cargo at compile time to this crate's
// directory (src-tauri/), independent of whatever cwd the binary is launched
// with at runtime. `tauri dev` happens to also run with cwd == src-tauri/,
// which is why the old runtime "parent of cwd" heuristic worked there - but a
// packaged .app launched from Finder has an unrelated cwd (commonly "/"),
// so that heuristic silently resolved to the wrong directory, every path
// check in start_all() failed `.exists()`, and no child process ever spawned.
// This only stays correct for the current single-machine distribution scope
// (binary never moves off the machine it was built on); true relocatable
// distribution needs the project bundled inside the .app, a separate effort.
const BUILD_TIME_PROJECT_ROOT: &str = env!("CARGO_MANIFEST_DIR");

fn project_root() -> PathBuf {
    if let Ok(p) = env::var("NOVELLA_PROJECT_ROOT") {
        return PathBuf::from(p);
    }
    PathBuf::from(BUILD_TIME_PROJECT_ROOT)
        .parent()
        .map(|p| p.to_path_buf())
        .unwrap_or_else(|| PathBuf::from("."))
}

/// Minimal `.env` loader (KEY=VALUE per line, `#` comments, blank lines
/// skipped) - mirrors start.sh's `source .env`, but without executing
/// arbitrary shell syntax since this file lands in untrusted project dirs.
fn load_dotenv(root: &Path) -> HashMap<String, String> {
    let mut vars = HashMap::new();
    let Ok(content) = fs::read_to_string(root.join(".env")) else {
        return vars;
    };
    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some((key, value)) = line.split_once('=') {
            let value = value.trim().trim_matches('"').trim_matches('\'');
            vars.insert(key.trim().to_string(), value.to_string());
        }
    }
    vars
}

fn ollama_reachable() -> bool {
    TcpStream::connect_timeout(
        &"127.0.0.1:11434".parse().unwrap(),
        Duration::from_millis(300),
    )
    .is_ok()
}

fn open_log(root: &Path, name: &str) -> std::fs::File {
    let logs_dir = root.join("logs");
    let _ = fs::create_dir_all(&logs_dir);
    OpenOptions::new()
        .create(true)
        .append(true)
        .open(logs_dir.join(format!("{name}.log")))
        .unwrap_or_else(|e| panic!("failed to open log file for {name}: {e}"))
}

fn spawn_logged(
    root: &Path,
    name: &str,
    program: &Path,
    args: &[&str],
    cwd: Option<&Path>,
    env_vars: &HashMap<String, String>,
) -> Option<Child> {
    let stdout = open_log(root, name);
    let stderr = match stdout.try_clone() {
        Ok(f) => f,
        Err(e) => {
            log::error!("failed to clone log handle for {name}: {e}");
            return None;
        }
    };

    let mut cmd = Command::new(program);
    cmd.args(args)
        .stdout(Stdio::from(stdout))
        .stderr(Stdio::from(stderr))
        .envs(env_vars);
    if let Some(dir) = cwd {
        cmd.current_dir(dir);
    }

    match cmd.spawn() {
        Ok(child) => {
            log::info!("started {name} (pid {})", child.id());
            Some(child)
        }
        Err(err) => {
            log::error!(
                "failed to start {name} ({}): {err} - is it installed at that path?",
                program.display()
            );
            None
        }
    }
}

fn start_all(root: &PathBuf, state: &ManagedProcesses) {
    log::info!("project root resolved to {}", root.display());
    let env_vars = load_dotenv(root);

    if ollama_reachable() {
        log::info!("ollama already running on :11434 - not managing it");
    } else if let Ok(ollama_bin) = which_ollama() {
        let child = spawn_logged(root, "ollama", &ollama_bin, &["serve"], None, &env_vars);
        *state.ollama.lock().unwrap() = child;
    } else {
        log::error!("ollama binary not found on PATH - scene breakdown will be unavailable");
    }

    let comfyui_dir = root.join("comfyui/src/ComfyUI");
    let comfyui_python = comfyui_dir.join(".venv/bin/python");
    let comfyui_main = comfyui_dir.join("main.py");
    if comfyui_python.exists() {
        let child = spawn_logged(
            root,
            "comfyui",
            &comfyui_python,
            &[
                comfyui_main.to_str().unwrap(),
                "--listen",
                "127.0.0.1",
                "--port",
                "8188",
            ],
            Some(&comfyui_dir),
            &env_vars,
        );
        *state.comfyui.lock().unwrap() = child;
    } else {
        log::error!(
            "ComfyUI venv not found at {} - run scripts/setup.sh first",
            comfyui_python.display()
        );
    }

    let backend_uvicorn = root.join("backend/.venv/bin/uvicorn");
    if backend_uvicorn.exists() {
        let child = spawn_logged(
            root,
            "backend",
            &backend_uvicorn,
            &[
                "app.main:app",
                "--app-dir",
                "backend",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            Some(root),
            &env_vars,
        );
        *state.backend.lock().unwrap() = child;
    } else {
        log::error!(
            "backend venv not found at {} - run scripts/setup.sh first",
            backend_uvicorn.display()
        );
    }
}

fn which_ollama() -> Result<PathBuf, ()> {
    for candidate in ["/opt/homebrew/bin/ollama", "/usr/local/bin/ollama"] {
        let path = PathBuf::from(candidate);
        if path.exists() {
            return Ok(path);
        }
    }
    Err(())
}

fn stop_all(state: &ManagedProcesses) {
    for child_mutex in [&state.backend, &state.comfyui, &state.ollama] {
        if let Some(mut child) = child_mutex.lock().unwrap().take() {
            log::info!("stopping pid {}", child.id());
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

/// Explicit "quit the whole app" action invokable from the UI, rather than
/// relying on the window close button or Cmd+Q being obvious/reliable ways
/// to actually stop everything - stops the managed processes first (same as
/// every other exit path), then exits the app process itself.
#[tauri::command]
fn quit_app(app: tauri::AppHandle) {
    log::info!("quit_app invoked from the UI - stopping managed processes");
    stop_all(PROCESSES.get().expect("PROCESSES initialized before run()"));
    app.exit(0);
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let processes = PROCESSES.get_or_init(|| ManagedProcesses {
        ollama: Mutex::new(None),
        comfyui: Mutex::new(None),
        backend: Mutex::new(None),
    });

    // Covers termination paths that never reach Tauri's own window-close
    // event: `kill <pid>`, Activity Monitor's "Quit", system shutdown/logout.
    // A plain `kill -9` still bypasses this (SIGKILL can't be caught by
    // anything, in any app) - that's an unavoidable property of Unix
    // signals, not a gap specific to this handler.
    ctrlc::set_handler(|| {
        log::info!("received termination signal - stopping managed processes");
        stop_all(PROCESSES.get().expect("PROCESSES initialized before run()"));
        std::process::exit(0);
    })
    .expect("failed to register signal handler");

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![quit_app])
        .setup(move |app| {
            app.handle().plugin(
                tauri_plugin_log::Builder::default()
                    .level(log::LevelFilter::Info)
                    .build(),
            )?;

            let root = project_root();
            start_all(&root, processes);

            Ok(())
        })
        .on_window_event(|_window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                stop_all(PROCESSES.get().expect("PROCESSES initialized before run()"));
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|_app_handle, event| {
            // Cmd+Q / the app menu's Quit / Dock > Quit are a Cocoa-level
            // "application should terminate" request, not a window close and
            // not a Unix signal - WindowEvent::CloseRequested and the ctrlc
            // SIGTERM handler above both miss it entirely. stop_all() is
            // safe to call more than once (each Option<Child> is just a
            // no-op the second time), so overlapping with the other two
            // handlers on a given quit sequence is harmless.
            if let tauri::RunEvent::ExitRequested { .. } = event {
                log::info!("app exit requested (e.g. Cmd+Q) - stopping managed processes");
                stop_all(PROCESSES.get().expect("PROCESSES initialized before run()"));
            }
        });
}
