use std::{
    collections::HashMap,
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
    process::{Child, ChildStdin, ChildStdout, Command, Stdio},
    sync::{
        atomic::{AtomicBool, AtomicU64, Ordering},
        mpsc::{self, Sender},
        Arc, Mutex,
    },
    thread,
    time::{Duration, Instant},
};

use serde::Serialize;
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter};

const REQUEST_TIMEOUT: Duration = Duration::from_secs(30);
// Le premier ping inclut les imports Python/NumPy sur la machine modeste.
const PING_TIMEOUT: Duration = Duration::from_secs(30);
const SIMULATION_START_TIMEOUT: Duration = Duration::from_secs(10);
const SIMULATION_CANCEL_TIMEOUT: Duration = Duration::from_secs(2);
const PROVIDER_TIMEOUT: Duration = Duration::from_secs(120);
const AGENT_TIMEOUT: Duration = Duration::from_secs(300);
const SIMULATION_TIMEOUT: Duration = Duration::from_secs(600);
const SHUTDOWN_GRACE: Duration = Duration::from_secs(2);

const STATUS_EVENT: &str = "sidecar:status";
const SIMULATION_EVENT: &str = "simulation:event";
const LEGACY_PROGRESS_EVENT: &str = "simulation:progress";

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SidecarStatus {
    pub running: bool,
    pub pid: Option<u32>,
    pub error: Option<String>,
}

#[derive(Debug)]
enum RpcOutcome {
    Result(Value),
    Error(String),
}

struct PendingRequest {
    generation: u64,
    sender: Sender<RpcOutcome>,
}

struct ProcessState {
    child: Option<Child>,
    generation: u64,
    last_error: Option<String>,
    data_dir: Option<PathBuf>,
    benchmark_dir: Option<PathBuf>,
    examples_dir: Option<PathBuf>,
}

impl ProcessState {
    fn new() -> Self {
        Self {
            child: None,
            generation: 0,
            last_error: None,
            data_dir: None,
            benchmark_dir: None,
            examples_dir: None,
        }
    }
}

/// État partagé entre le handle et le thread lecteur.
///
/// Le lecteur ne capture que ce dispatcher (pas le handle complet), ce qui
/// évite tout cycle de vie ou pointeur brut : quand le manager disparaît, le
/// process est arrêté et le thread se termine sur EOF.
struct Dispatcher {
    app: Mutex<Option<AppHandle>>,
    pending: Mutex<HashMap<u64, PendingRequest>>,
}

impl Dispatcher {
    fn new() -> Self {
        Self {
            app: Mutex::new(None),
            pending: Mutex::new(HashMap::new()),
        }
    }

    fn attach_app(&self, app: AppHandle) {
        if let Ok(mut slot) = self.app.lock() {
            *slot = Some(app);
        }
    }

    fn dispatch(&self, message: Value) {
        if let Some(id) = message.get("id").and_then(Value::as_u64) {
            let pending = self
                .pending
                .lock()
                .ok()
                .and_then(|mut pending| pending.remove(&id));
            if let Some(pending) = pending {
                let outcome = match message.get("error") {
                    Some(error) => RpcOutcome::Error(
                        error
                            .get("message")
                            .and_then(Value::as_str)
                            .unwrap_or("erreur JSON-RPC")
                            .to_string(),
                    ),
                    None => {
                        RpcOutcome::Result(message.get("result").cloned().unwrap_or(Value::Null))
                    }
                };
                let _ = pending.sender.send(outcome);
                return;
            }
        }

        if let Some(method) = message.get("method").and_then(Value::as_str) {
            self.emit_notification(&message, method);
        }
    }

    fn emit_notification(&self, message: &Value, method: &str) {
        let app = self.app.lock().ok().and_then(|app| app.clone());
        let Some(app) = app else {
            return;
        };
        let _ = app.emit(SIMULATION_EVENT, message.clone());
        if method == "simulate.progress" {
            let payload = message.get("params").cloned().unwrap_or_else(|| json!({}));
            let _ = app.emit(LEGACY_PROGRESS_EVENT, payload);
        }
    }

    fn emit_status(&self, running: bool, error: Option<String>) {
        let app = self.app.lock().ok().and_then(|app| app.clone());
        if let Some(app) = app {
            let _ = app.emit(
                STATUS_EVENT,
                json!({ "running": running, "error": error }),
            );
        }
    }

    fn fail_all_pending(&self, message: &str) {
        if let Ok(mut pending) = self.pending.lock() {
            for (_, request) in pending.drain() {
                let _ = request.sender.send(RpcOutcome::Error(message.to_string()));
            }
        }
    }

    fn fail_pending_generation(&self, generation: u64, message: &str) {
        if let Ok(mut pending) = self.pending.lock() {
            let ids: Vec<u64> = pending
                .iter()
                .filter(|(_, request)| request.generation == generation)
                .map(|(id, _)| *id)
                .collect();
            for id in ids {
                if let Some(request) = pending.remove(&id) {
                    let _ = request.sender.send(RpcOutcome::Error(message.to_string()));
                }
            }
        }
    }
}

/// Handle de communication partagé, indépendant du cycle de vie du process.
///
/// Le verrou global Tauri ne protège plus que la récupération du handle : ni
/// l'écriture ni l'attente d'une réponse ne le tiennent.
pub struct SidecarHandle {
    dispatcher: Arc<Dispatcher>,
    state: Mutex<ProcessState>,
    writer: Mutex<Option<ChildStdin>>,
    next_id: AtomicU64,
    supervised: AtomicBool,
    shutting_down: AtomicBool,
}

impl SidecarHandle {
    pub fn new() -> Self {
        Self {
            dispatcher: Arc::new(Dispatcher::new()),
            state: Mutex::new(ProcessState::new()),
            writer: Mutex::new(None),
            next_id: AtomicU64::new(1),
            supervised: AtomicBool::new(false),
            shutting_down: AtomicBool::new(false),
        }
    }

    pub fn attach_app(&self, app: AppHandle) {
        self.dispatcher.attach_app(app);
    }

    pub fn set_data_dir(&self, data_dir: PathBuf) {
        if let Ok(mut state) = self.state.lock() {
            state.data_dir = Some(data_dir);
        }
    }

    pub fn set_benchmark_dir(&self, benchmark_dir: PathBuf) {
        if let Ok(mut state) = self.state.lock() {
            state.benchmark_dir = Some(benchmark_dir);
        }
    }

    pub fn set_examples_dir(&self, examples_dir: PathBuf) {
        if let Ok(mut state) = self.state.lock() {
            state.examples_dir = Some(examples_dir);
        }
    }

    pub fn supervision_enabled(&self) -> bool {
        self.supervised.load(Ordering::SeqCst)
    }

    pub fn status(&self) -> SidecarStatus {
        let mut state = match self.state.lock() {
            Ok(state) => state,
            Err(error) => {
                return SidecarStatus {
                    running: false,
                    pid: None,
                    error: Some(error.to_string()),
                }
            }
        };
        let running = match state.child.as_mut() {
            Some(child) => matches!(child.try_wait(), Ok(None)),
            None => false,
        };
        let pid = if running {
            state.child.as_ref().map(Child::id)
        } else {
            None
        };

        SidecarStatus {
            running,
            pid,
            error: state.last_error.clone(),
        }
    }

    pub fn ensure_running(&self) -> Result<(), String> {
        if self.shutting_down.load(Ordering::SeqCst) {
            return Err("le sidecar est en cours d'arrêt".to_string());
        }

        let mut state = self
            .state
            .lock()
            .map_err(|error| format!("état du sidecar indisponible: {error}"))?;

        if let Some(child) = state.child.as_mut() {
            match child.try_wait() {
                Ok(None) => return Ok(()),
                Ok(Some(_)) => {
                    state.child = None;
                }
                Err(_) => {
                    state.child = None;
                }
            }
        }
        if state.child.is_none() {
            let _ = self.writer.lock().map(|mut writer| writer.take());
        }

        let (program, args, cwd) = command(&state);
        let mut process = Command::new(&program);
        process.args(&args);
        process.stdin(Stdio::piped());
        process.stdout(Stdio::piped());
        process.stderr(Stdio::piped());
        if let Some(cwd) = &cwd {
            process.current_dir(cwd);
        }
        if let Some(dir) = &state.data_dir {
            process.env("SEE_DATA_DIR", dir);
        }
        if let Some(dir) = &state.benchmark_dir {
            process.env("SEE_BENCHMARK_DIR", dir);
        }
        if let Some(dir) = &state.examples_dir {
            process.env("SEE_EXAMPLES_DIR", dir);
        }

        let mut child = process.spawn().map_err(|error| {
            let message = format!("impossible de démarrer le sidecar ({program}): {error}");
            state.last_error = Some(message.clone());
            message
        })?;

        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| "stdin du sidecar indisponible".to_string())?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "stdout du sidecar indisponible".to_string())?;
        let stderr = child.stderr.take();

        state.generation += 1;
        let generation = state.generation;
        state.child = Some(child);
        state.last_error = None;
        drop(state);
        *self
            .writer
            .lock()
            .map_err(|error| format!("writer du sidecar indisponible: {error}"))? = Some(stdin);

        self.spawn_reader(stdout, generation);
        if let Some(stderr) = stderr {
            thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines().map_while(Result::ok) {
                    eprintln!("[sidecar] {line}");
                }
            });
        }
        Ok(())
    }

    pub fn request(&self, method: &str, params: Value) -> Result<Value, String> {
        self.request_with_timeout(method, params, timeout_for(method))
    }

    pub fn request_with_timeout(
        &self,
        method: &str,
        params: Value,
        timeout: Duration,
    ) -> Result<Value, String> {
        self.ensure_running()?;

        let id = self.next_id.fetch_add(1, Ordering::SeqCst);
        let generation = self
            .state
            .lock()
            .map_err(|error| format!("état du sidecar indisponible: {error}"))?
            .generation;
        let (sender, receiver) = mpsc::channel();
        self.dispatcher
            .pending
            .lock()
            .map_err(|error| format!("registre des requêtes indisponible: {error}"))?
            .insert(id, PendingRequest { generation, sender });

        let payload = json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": method,
            "params": params,
        });

        if let Err(error) = self.write_value(&payload) {
            self.forget_pending(id);
            return Err(error);
        }

        match receiver.recv_timeout(timeout) {
            Ok(RpcOutcome::Result(result)) => Ok(result),
            Ok(RpcOutcome::Error(message)) => Err(message),
            Err(mpsc::RecvTimeoutError::Timeout) => {
                self.forget_pending(id);
                Err(format!("timeout en attendant la réponse à « {method} »"))
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                self.forget_pending(id);
                Err("le sidecar s'est arrêté".to_string())
            }
        }
    }

    pub fn restart(&self) -> SidecarStatus {
        self.shutdown();
        self.supervised.store(true, Ordering::SeqCst);
        if let Err(error) = self.ensure_running() {
            if let Ok(mut state) = self.state.lock() {
                state.last_error = Some(error);
            }
        }
        self.status()
    }

    pub fn shutdown(&self) {
        self.supervised.store(false, Ordering::SeqCst);
        self.shutting_down.store(true, Ordering::SeqCst);

        let request = json!({
            "jsonrpc": "2.0",
            "id": 0,
            "method": "shutdown",
            "params": {},
        });
        let _ = self.write_value(&request);

        let child = self.state.lock().ok().and_then(|mut state| state.child.take());
        if let Some(mut child) = child {
            let start = Instant::now();
            loop {
                match child.try_wait() {
                    Ok(Some(_)) => break,
                    Ok(None) if start.elapsed() < SHUTDOWN_GRACE => {
                        thread::sleep(Duration::from_millis(50));
                    }
                    _ => {
                        let _ = child.kill();
                        let _ = child.wait();
                        break;
                    }
                }
            }
        }

        if let Ok(mut writer) = self.writer.lock() {
            *writer = None;
        }
        self.dispatcher.fail_all_pending("le sidecar a été arrêté");
        self.dispatcher.emit_status(false, None);
        self.shutting_down.store(false, Ordering::SeqCst);
    }

    fn write_value(&self, payload: &Value) -> Result<(), String> {
        let mut line =
            serde_json::to_vec(payload).map_err(|error| format!("JSON: {error}"))?;
        line.push(b'\n');
        let mut writer = self
            .writer
            .lock()
            .map_err(|error| format!("writer du sidecar indisponible: {error}"))?;
        let stdin = writer
            .as_mut()
            .ok_or_else(|| "stdin du sidecar indisponible".to_string())?;
        stdin
            .write_all(&line)
            .map_err(|error| format!("écriture vers le sidecar: {error}"))?;
        stdin
            .flush()
            .map_err(|error| format!("flush du sidecar: {error}"))
    }

    fn forget_pending(&self, id: u64) {
        if let Ok(mut pending) = self.dispatcher.pending.lock() {
            pending.remove(&id);
        }
    }

    fn spawn_reader(&self, stdout: ChildStdout, generation: u64) {
        let dispatcher = Arc::clone(&self.dispatcher);
        thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                match line {
                    Ok(line) if line.trim().is_empty() => continue,
                    Ok(line) => match serde_json::from_str::<Value>(&line) {
                        Ok(value) => dispatcher.dispatch(value),
                        Err(error) => eprintln!("[sidecar] message JSON invalide: {error}"),
                    },
                    Err(error) => {
                        eprintln!("[sidecar] lecture stdout: {error}");
                        break;
                    }
                }
            }
            dispatcher.fail_pending_generation(generation, "le sidecar s'est arrêté");
            dispatcher.emit_status(false, Some("le sidecar s'est arrêté".to_string()));
        });
    }
}

fn timeout_for(method: &str) -> Duration {
    if method == "ping" || method == "health" {
        PING_TIMEOUT
    } else if method == "simulation.start"
        || method == "simulation.surface"
        || method == "simulation.goalseek"
    {
        SIMULATION_START_TIMEOUT
    } else if method == "simulation.cancel" {
        SIMULATION_CANCEL_TIMEOUT
    } else if method.starts_with("provider.") {
        PROVIDER_TIMEOUT
    } else if method.starts_with("agent.") {
        AGENT_TIMEOUT
    } else if method == "project.simulate" || method == "simulate" {
        SIMULATION_TIMEOUT
    } else {
        REQUEST_TIMEOUT
    }
}

fn command(_state: &ProcessState) -> (String, Vec<String>, Option<PathBuf>) {
    let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
    let sidecar_dir = manifest.join("sidecar");
    let module_args = vec!["-m".to_string(), "sidecar".to_string()];

    if let Ok(python) = std::env::var("SIDECAR_PYTHON") {
        return (python, module_args, Some(sidecar_dir));
    }

    if cfg!(debug_assertions) {
        let candidates = [
            sidecar_dir.join(".venv/Scripts/python.exe"),
            sidecar_dir.join(".venv/bin/python"),
            manifest.join("../../../.venv/Scripts/python.exe"),
            manifest.join("../../../.venv/bin/python"),
        ];

        for candidate in candidates {
            if candidate.exists() {
                return (
                    candidate.to_string_lossy().into_owned(),
                    module_args,
                    Some(sidecar_dir),
                );
            }
        }

        return ("python".to_string(), module_args, Some(sidecar_dir));
    }

    let executable = if cfg!(windows) {
        "sidecar.exe"
    } else {
        "sidecar"
    };
    let path = std::env::current_exe()
        .ok()
        .and_then(|exe| exe.parent().map(|dir| dir.join(executable)))
        .unwrap_or_else(|| PathBuf::from(executable));

    (path.to_string_lossy().into_owned(), Vec::new(), None)
}

/// Superviseur : démarrage, redémarrage, arrêt du process fils.
pub struct SidecarManager {
    handle: Arc<SidecarHandle>,
}

impl Default for SidecarManager {
    fn default() -> Self {
        Self::new()
    }
}

impl SidecarManager {
    pub fn new() -> Self {
        Self {
            handle: Arc::new(SidecarHandle::new()),
        }
    }

    /// Clone léger du handle de communication, à utiliser sans tenir le verrou
    /// du manager Tauri pendant l'attente d'une réponse.
    pub fn handle(&self) -> Arc<SidecarHandle> {
        Arc::clone(&self.handle)
    }

    pub fn attach_app(&self, app: AppHandle) {
        self.handle.attach_app(app);
    }

    pub fn set_data_dir(&self, data_dir: PathBuf) {
        self.handle.set_data_dir(data_dir);
    }

    pub fn set_benchmark_dir(&self, benchmark_dir: PathBuf) {
        self.handle.set_benchmark_dir(benchmark_dir);
    }

    pub fn set_examples_dir(&self, examples_dir: PathBuf) {
        self.handle.set_examples_dir(examples_dir);
    }

    pub fn supervision_enabled(&self) -> bool {
        self.handle.supervision_enabled()
    }

    pub fn ensure_running(&self) -> Result<(), String> {
        self.handle.ensure_running()
    }

    #[cfg(test)]
    pub fn request(&self, method: &str, params: Value) -> Result<Value, String> {
        self.handle.request(method, params)
    }

    pub fn status(&self) -> SidecarStatus {
        self.handle.status()
    }

    pub fn restart(&self) -> SidecarStatus {
        self.handle.restart()
    }

    pub fn shutdown(&self) {
        self.handle.shutdown();
    }
}

impl Drop for SidecarManager {
    fn drop(&mut self) {
        self.shutdown();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn starts_sidecar_and_answers_ping() {
        let manager = SidecarManager::new();
        let result = manager
            .request("ping", json!({ "echo": "test" }))
            .expect("le sidecar doit répondre au ping");

        assert_eq!(result["pong"], json!(true));
        assert_eq!(result["echo"], json!("test"));
        assert!(manager.status().running);
        manager.shutdown();
    }

    #[test]
    fn health_reports_protocol_version() {
        let manager = SidecarManager::new();
        let result = manager
            .request("health", json!({}))
            .expect("le sidecar doit répondre au health");

        assert_eq!(result["status"], json!("ok"));
        assert_eq!(result["protocolVersion"], json!("1.16.0"));
        manager.shutdown();
    }

    #[test]
    fn respawns_after_an_unexpected_exit() {
        let manager = SidecarManager::new();
        manager
            .request("ping", json!({}))
            .expect("premier ping attendu");

        if let Ok(mut state) = manager.handle.state.lock() {
            if let Some(child) = state.child.as_mut() {
                child.kill().expect("le sidecar doit pouvoir être tué");
                child.wait().expect("le sidecar doit être récolté");
            }
        }

        let result = manager
            .request("ping", json!({ "echo": "after-crash" }))
            .expect("le sidecar doit redémarrer");
        assert_eq!(result["pong"], json!(true));
        assert_eq!(result["echo"], json!("after-crash"));
        manager.shutdown();
    }

    #[test]
    fn dispatcher_resolves_the_matching_pending_request() {
        let handle = SidecarHandle::new();
        let (sender, receiver) = mpsc::channel();
        handle
            .dispatcher
            .pending
            .lock()
            .expect("registre verrouillable")
            .insert(7, PendingRequest { generation: 0, sender });

        handle.dispatcher.dispatch(json!({
            "jsonrpc": "2.0",
            "id": 7,
            "result": { "runId": "abc", "accepted": true },
        }));

        match receiver.recv_timeout(Duration::from_secs(1)) {
            Ok(RpcOutcome::Result(value)) => {
                assert_eq!(value["runId"], json!("abc"));
            }
            other => panic!("résultat attendu, reçu {other:?}"),
        }
    }

    #[test]
    fn dispatcher_maps_error_responses() {
        let handle = SidecarHandle::new();
        let (sender, receiver) = mpsc::channel();
        handle
            .dispatcher
            .pending
            .lock()
            .expect("registre verrouillable")
            .insert(3, PendingRequest { generation: 0, sender });

        handle.dispatcher.dispatch(json!({
            "jsonrpc": "2.0",
            "id": 3,
            "error": { "code": -32006, "message": "run inconnu" },
        }));

        match receiver.recv_timeout(Duration::from_secs(1)) {
            Ok(RpcOutcome::Error(message)) => assert!(message.contains("run inconnu")),
            other => panic!("erreur attendue, reçu {other:?}"),
        }
    }

    #[test]
    fn dispatcher_ignores_notifications_without_failing() {
        let handle = SidecarHandle::new();
        handle.dispatcher.dispatch(json!({
            "jsonrpc": "2.0",
            "method": "simulation.partial",
            "params": { "runId": "abc", "seq": 1 },
        }));
        assert!(handle
            .dispatcher
            .pending
            .lock()
            .expect("registre verrouillable")
            .is_empty());
    }

    #[test]
    fn timeouts_are_adapted_to_the_method() {
        assert_eq!(timeout_for("ping"), PING_TIMEOUT);
        assert_eq!(timeout_for("health"), PING_TIMEOUT);
        assert_eq!(timeout_for("simulation.start"), SIMULATION_START_TIMEOUT);
        assert_eq!(timeout_for("simulation.cancel"), SIMULATION_CANCEL_TIMEOUT);
        assert_eq!(timeout_for("provider.chat"), PROVIDER_TIMEOUT);
        assert_eq!(timeout_for("agent.turn"), AGENT_TIMEOUT);
        assert_eq!(timeout_for("project.simulate"), SIMULATION_TIMEOUT);
    }
}
