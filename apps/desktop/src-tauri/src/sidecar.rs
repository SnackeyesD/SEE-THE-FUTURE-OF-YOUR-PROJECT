use std::{
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
    process::{Child, ChildStdin, Command, Stdio},
    sync::mpsc::{self, Receiver, RecvTimeoutError},
    thread,
    time::{Duration, Instant},
};

use serde::Serialize;
use serde_json::{json, Value};

const REQUEST_TIMEOUT: Duration = Duration::from_secs(30);
const PROVIDER_TIMEOUT: Duration = Duration::from_secs(120);
const AGENT_TIMEOUT: Duration = Duration::from_secs(300);
const SIMULATION_TIMEOUT: Duration = Duration::from_secs(600);
const SHUTDOWN_GRACE: Duration = Duration::from_secs(2);

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SidecarStatus {
    pub running: bool,
    pub pid: Option<u32>,
    pub error: Option<String>,
}

pub struct SidecarManager {
    child: Option<Child>,
    stdin: Option<ChildStdin>,
    rx: Option<Receiver<Value>>,
    next_id: u64,
    last_error: Option<String>,
    supervised: bool,
    data_dir: Option<PathBuf>,
    benchmark_dir: Option<PathBuf>,
}

impl Default for SidecarManager {
    fn default() -> Self {
        Self::new()
    }
}

impl SidecarManager {
    pub fn new() -> Self {
        Self {
            child: None,
            stdin: None,
            rx: None,
            next_id: 1,
            last_error: None,
            supervised: true,
            data_dir: None,
            benchmark_dir: None,
        }
    }

    pub fn set_data_dir(&mut self, data_dir: PathBuf) {
        self.data_dir = Some(data_dir);
    }

    pub fn set_benchmark_dir(&mut self, benchmark_dir: PathBuf) {
        self.benchmark_dir = Some(benchmark_dir);
    }

    pub fn supervision_enabled(&self) -> bool {
        self.supervised
    }

    pub fn ensure_running(&mut self) -> Result<(), String> {
        let is_running = match self.child.as_mut() {
            Some(child) => matches!(child.try_wait(), Ok(None)),
            None => false,
        };

        if is_running {
            return Ok(());
        }

        self.cleanup();
        self.spawn()
    }

    fn spawn(&mut self) -> Result<(), String> {
        let (program, args, cwd) = self.command();
        let mut command = Command::new(&program);
        command
            .args(&args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        if let Some(dir) = &cwd {
            command.current_dir(dir);
        }

        if let Some(dir) = &self.data_dir {
            command.env("SEE_DATA_DIR", dir);
        }

        if let Some(dir) = &self.benchmark_dir {
            command.env("SEE_BENCHMARK_DIR", dir);
        }

        let mut child = command.spawn().map_err(|error| {
            let message = format!("impossible de démarrer le sidecar ({program}): {error}");
            self.last_error = Some(message.clone());
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

        let (tx, rx) = mpsc::channel::<Value>();
        thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                match line {
                    Ok(line) if line.trim().is_empty() => continue,
                    Ok(line) => match serde_json::from_str::<Value>(&line) {
                        Ok(value) => {
                            if tx.send(value).is_err() {
                                break;
                            }
                        }
                        Err(error) => eprintln!("[sidecar] message JSON invalide: {error}"),
                    },
                    Err(error) => {
                        eprintln!("[sidecar] lecture stdout: {error}");
                        break;
                    }
                }
            }
        });

        if let Some(stderr) = stderr {
            thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines().map_while(Result::ok) {
                    eprintln!("[sidecar] {line}");
                }
            });
        }

        self.child = Some(child);
        self.stdin = Some(stdin);
        self.rx = Some(rx);
        self.last_error = None;
        Ok(())
    }

    fn command(&self) -> (String, Vec<String>, Option<PathBuf>) {
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

    pub fn request(&mut self, method: &str, params: Value) -> Result<Value, String> {
        self.request_with(method, params, |_| {})
    }

    pub fn request_with<F>(
        &mut self,
        method: &str,
        params: Value,
        mut on_event: F,
    ) -> Result<Value, String>
    where
        F: FnMut(&Value),
    {
        self.ensure_running()?;

        let id = self.next_id;
        self.next_id += 1;
        let payload = json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": method,
            "params": params,
        });

        {
            let stdin = self
                .stdin
                .as_mut()
                .ok_or_else(|| "stdin du sidecar indisponible".to_string())?;
            let mut line =
                serde_json::to_vec(&payload).map_err(|error| format!("JSON: {error}"))?;
            line.push(b'\n');
            stdin
                .write_all(&line)
                .map_err(|error| format!("écriture vers le sidecar: {error}"))?;
            stdin
                .flush()
                .map_err(|error| format!("flush du sidecar: {error}"))?;
        }

        let timeout = if method.starts_with("provider.") {
            PROVIDER_TIMEOUT
        } else if method.starts_with("agent.") {
            AGENT_TIMEOUT
        } else if method.starts_with("project.simulate") || method == "simulate" {
            SIMULATION_TIMEOUT
        } else {
            REQUEST_TIMEOUT
        };
        let deadline = Instant::now() + timeout;

        loop {
            let remaining = deadline.saturating_duration_since(Instant::now());
            if remaining.is_zero() {
                return Err(format!("timeout en attendant la réponse à « {method} »"));
            }

            let received = {
                let rx = self
                    .rx
                    .as_ref()
                    .ok_or_else(|| "canal du sidecar indisponible".to_string())?;
                rx.recv_timeout(remaining)
            };

            match received {
                Ok(message) => {
                    if message.get("id").and_then(Value::as_u64) != Some(id) {
                        if message.get("method").is_some() {
                            on_event(&message);
                        }
                        continue;
                    }

                    if let Some(error) = message.get("error") {
                        let text = error
                            .get("message")
                            .and_then(Value::as_str)
                            .unwrap_or("erreur JSON-RPC");
                        return Err(text.to_string());
                    }

                    return Ok(message.get("result").cloned().unwrap_or(Value::Null));
                }
                Err(RecvTimeoutError::Timeout) => {
                    return Err(format!("timeout en attendant la réponse à « {method} »"));
                }
                Err(RecvTimeoutError::Disconnected) => {
                    self.cleanup();
                    return Err("le sidecar s'est arrêté".to_string());
                }
            }
        }
    }

    pub fn status(&mut self) -> SidecarStatus {
        let running = match self.child.as_mut() {
            Some(child) => matches!(child.try_wait(), Ok(None)),
            None => false,
        };
        let pid = if running {
            self.child.as_ref().map(Child::id)
        } else {
            None
        };

        SidecarStatus {
            running,
            pid,
            error: self.last_error.clone(),
        }
    }

    pub fn restart(&mut self) -> SidecarStatus {
        self.shutdown();
        self.supervised = true;
        if let Err(error) = self.spawn() {
            self.last_error = Some(error);
        }
        self.status()
    }

    pub fn shutdown(&mut self) {
        self.supervised = false;
        if let Some(stdin) = self.stdin.as_mut() {
            let request = json!({
                "jsonrpc": "2.0",
                "id": 0,
                "method": "shutdown",
                "params": {},
            });
            if let Ok(mut bytes) = serde_json::to_vec(&request) {
                bytes.push(b'\n');
                let _ = stdin.write_all(&bytes);
                let _ = stdin.flush();
            }
        }

        if let Some(mut child) = self.child.take() {
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

        self.stdin = None;
        self.rx = None;
    }

    fn cleanup(&mut self) {
        self.stdin = None;
        self.rx = None;
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
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
        let mut manager = SidecarManager::new();
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
        let mut manager = SidecarManager::new();
        let result = manager
            .request("health", json!({}))
            .expect("le sidecar doit répondre au health");

        assert_eq!(result["status"], json!("ok"));
        assert_eq!(result["protocolVersion"], json!("1.7.0"));
        manager.shutdown();
    }

    #[test]
    fn respawns_after_an_unexpected_exit() {
        let mut manager = SidecarManager::new();
        manager
            .request("ping", json!({}))
            .expect("premier ping attendu");

        if let Some(child) = manager.child.as_mut() {
            child.kill().expect("le sidecar doit pouvoir être tué");
            child.wait().expect("le sidecar doit être récolté");
        }

        let result = manager
            .request("ping", json!({ "echo": "after-crash" }))
            .expect("le sidecar doit redémarrer");
        assert_eq!(result["pong"], json!(true));
        assert_eq!(result["echo"], json!("after-crash"));
        manager.shutdown();
    }
}
