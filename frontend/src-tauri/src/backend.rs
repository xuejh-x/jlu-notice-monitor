use serde::Serialize;
use serde_json::Value;
use std::{
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    time::{Duration, Instant},
};
use tauri::{AppHandle, State};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: u16 = 8000;
const SIDECAR_NAME: &str = "jlu-notice-backend";
const STARTUP_TIMEOUT: Duration = Duration::from_secs(20);
const SHUTDOWN_TIMEOUT: Duration = Duration::from_secs(5);
const POLL_INTERVAL: Duration = Duration::from_millis(150);

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum BackendPhase {
    Idle,
    Starting,
    ReadyOwned,
    ReadyExternal,
    Failed,
    Stopping,
}

impl BackendPhase {
    fn label(self) -> &'static str {
        match self {
            Self::Idle => "idle",
            Self::Starting => "starting",
            Self::ReadyOwned | Self::ReadyExternal => "ready",
            Self::Failed => "failed",
            Self::Stopping => "stopping",
        }
    }
}

struct BackendInner {
    phase: BackendPhase,
    error: Option<String>,
    child: Option<CommandChild>,
    pid: Option<u32>,
    terminated: Option<Arc<AtomicBool>>,
    generation: u64,
}

impl Default for BackendInner {
    fn default() -> Self {
        Self {
            phase: BackendPhase::Idle,
            error: None,
            child: None,
            pid: None,
            terminated: None,
            generation: 0,
        }
    }
}

#[derive(Clone, Default)]
pub struct BackendController {
    inner: Arc<Mutex<BackendInner>>,
    start_in_progress: Arc<AtomicBool>,
    shutdown_started: Arc<AtomicBool>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BackendStatus {
    phase: &'static str,
    ready: bool,
    owned: bool,
    pid: Option<u32>,
    error: Option<String>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum PortState {
    Free,
    OurService,
    Occupied,
}

impl BackendController {
    pub fn status(&self) -> BackendStatus {
        let inner = self.inner.lock().unwrap_or_else(|error| error.into_inner());
        BackendStatus {
            phase: inner.phase.label(),
            ready: matches!(
                inner.phase,
                BackendPhase::ReadyOwned | BackendPhase::ReadyExternal
            ),
            owned: inner.phase == BackendPhase::ReadyOwned,
            pid: inner.pid,
            error: inner.error.clone(),
        }
    }

    fn set_failed(&self, message: impl Into<String>) {
        let mut inner = self.inner.lock().unwrap_or_else(|error| error.into_inner());
        inner.phase = BackendPhase::Failed;
        inner.error = Some(message.into());
    }

    pub async fn ensure_started(&self, app: &AppHandle) -> BackendStatus {
        if self.status().ready {
            return self.status();
        }

        if self.start_in_progress.swap(true, Ordering::AcqRel) {
            while self.start_in_progress.load(Ordering::Acquire) {
                tokio::time::sleep(POLL_INTERVAL).await;
            }
            return self.status();
        }

        self.shutdown_started.store(false, Ordering::Release);
        let result = self.start(app).await;
        self.start_in_progress.store(false, Ordering::Release);
        if let Err(message) = result {
            self.stop_owned_child_now();
            self.set_failed(message);
        }
        self.status()
    }

    async fn start(&self, app: &AppHandle) -> Result<(), String> {
        {
            let mut inner = self.inner.lock().unwrap_or_else(|error| error.into_inner());
            inner.phase = BackendPhase::Starting;
            inner.error = None;
            inner.generation = inner.generation.wrapping_add(1);
        }

        match probe_backend() {
            PortState::OurService => {
                let mut inner = self.inner.lock().unwrap_or_else(|error| error.into_inner());
                inner.phase = BackendPhase::ReadyExternal;
                return Ok(());
            }
            PortState::Occupied => {
                return Err("端口 8000 已被其他程序占用，无法启动本地通知服务。".into());
            }
            PortState::Free => {}
        }

        let command = app
            .shell()
            .sidecar(SIDECAR_NAME)
            .map_err(|_| "未找到随应用打包的本地通知服务。请重新安装应用。".to_string())?
            .args([
                "serve",
                "--managed",
                "--host",
                BACKEND_HOST,
                "--port",
                "8000",
            ])
            .env("JLU_ENVIRONMENT", "production")
            .env("JLU_HOST", BACKEND_HOST)
            .env("JLU_PORT", "8000");

        let (mut events, child) = command
            .spawn()
            .map_err(|_| "本地通知服务无法启动。请重试或重新安装应用。".to_string())?;
        let pid = child.pid();
        let terminated = Arc::new(AtomicBool::new(false));
        let generation = {
            let mut inner = self.inner.lock().unwrap_or_else(|error| error.into_inner());
            inner.child = Some(child);
            inner.pid = Some(pid);
            inner.terminated = Some(terminated.clone());
            inner.generation
        };

        let controller = self.clone();
        tauri::async_runtime::spawn(async move {
            while let Some(event) = events.recv().await {
                match event {
                    CommandEvent::Terminated(_) | CommandEvent::Error(_) => {
                        terminated.store(true, Ordering::Release);
                        controller.handle_child_exit(generation);
                        break;
                    }
                    _ => {}
                }
            }
        });

        let deadline = Instant::now() + STARTUP_TIMEOUT;
        while Instant::now() < deadline {
            let has_terminated = {
                let inner = self.inner.lock().unwrap_or_else(|error| error.into_inner());
                inner
                    .terminated
                    .as_ref()
                    .is_some_and(|flag| flag.load(Ordering::Acquire))
            };
            if has_terminated {
                return Err("本地通知服务在完成启动前意外退出。".into());
            }

            match probe_backend() {
                PortState::OurService => {
                    let mut inner = self.inner.lock().unwrap_or_else(|error| error.into_inner());
                    if inner.generation == generation {
                        inner.phase = BackendPhase::ReadyOwned;
                        inner.error = None;
                    }
                    return Ok(());
                }
                PortState::Occupied => {
                    return Err("端口 8000 出现了非预期服务，本地通知服务未能安全启动。".into());
                }
                PortState::Free => {}
            }
            tokio::time::sleep(POLL_INTERVAL).await;
        }

        Err("本地通知服务启动超时。请重试；若问题持续，请重新启动应用。".into())
    }

    fn handle_child_exit(&self, generation: u64) {
        let mut inner = self.inner.lock().unwrap_or_else(|error| error.into_inner());
        if inner.generation != generation || inner.phase == BackendPhase::Stopping {
            return;
        }
        inner.phase = BackendPhase::Failed;
        inner.error = Some("本地通知服务意外停止。请重新启动应用。".into());
    }

    fn stop_owned_child_now(&self) {
        let child = {
            let mut inner = self.inner.lock().unwrap_or_else(|error| error.into_inner());
            inner.child.take()
        };
        if let Some(child) = child {
            let _ = child.kill();
        }
        let mut inner = self.inner.lock().unwrap_or_else(|error| error.into_inner());
        inner.pid = None;
        inner.terminated = None;
    }

    pub fn should_intercept_exit(&self) -> bool {
        let owns_child = self
            .inner
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .child
            .is_some();
        owns_child && !self.shutdown_started.swap(true, Ordering::AcqRel)
    }

    pub async fn shutdown(&self) {
        let terminated = {
            let mut inner = self.inner.lock().unwrap_or_else(|error| error.into_inner());
            if inner.child.is_none() {
                return;
            }
            inner.phase = BackendPhase::Stopping;
            inner.error = None;
            if let Some(child) = inner.child.as_mut() {
                let _ = child.write(b"shutdown\n");
            }
            inner.terminated.clone()
        };

        let deadline = Instant::now() + SHUTDOWN_TIMEOUT;
        while Instant::now() < deadline {
            if terminated
                .as_ref()
                .is_some_and(|flag| flag.load(Ordering::Acquire))
            {
                break;
            }
            tokio::time::sleep(POLL_INTERVAL).await;
        }

        if !terminated
            .as_ref()
            .is_some_and(|flag| flag.load(Ordering::Acquire))
        {
            self.stop_owned_child_now();
        }

        let mut inner = self.inner.lock().unwrap_or_else(|error| error.into_inner());
        inner.child = None;
        inner.pid = None;
        inner.terminated = None;
        inner.phase = BackendPhase::Idle;
        inner.error = None;
    }
}

fn probe_backend() -> PortState {
    let address = SocketAddr::from(([127, 0, 0, 1], BACKEND_PORT));
    let mut stream = match TcpStream::connect_timeout(&address, Duration::from_millis(250)) {
        Ok(stream) => stream,
        Err(_) => return PortState::Free,
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(500)));

    if stream
        .write_all(b"GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:8000\r\nConnection: close\r\n\r\n")
        .is_err()
    {
        return PortState::Occupied;
    }

    let mut response = String::new();
    if stream.take(65_536).read_to_string(&mut response).is_err() {
        return PortState::Occupied;
    }
    if health_response_is_ours(&response) {
        PortState::OurService
    } else {
        PortState::Occupied
    }
}

fn health_response_is_ours(response: &str) -> bool {
    let Some((headers, body)) = response.split_once("\r\n\r\n") else {
        return false;
    };
    let status_ok = headers
        .lines()
        .next()
        .is_some_and(|line| line.starts_with("HTTP/1.1 200") || line.starts_with("HTTP/1.0 200"));
    if !status_ok {
        return false;
    }
    let Ok(payload) = serde_json::from_str::<Value>(body) else {
        return false;
    };
    payload.get("service").and_then(Value::as_str) == Some("jlu-notice-monitor")
        && payload.get("status").and_then(Value::as_str) == Some("ok")
        && payload.get("database").and_then(Value::as_str) == Some("ok")
}

#[tauri::command]
pub fn backend_status(state: State<'_, BackendController>) -> BackendStatus {
    state.status()
}

#[tauri::command]
pub async fn retry_backend(
    app: AppHandle,
    state: State<'_, BackendController>,
) -> Result<BackendStatus, String> {
    Ok(state.ensure_started(&app).await)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn health_probe_requires_our_service_marker_and_healthy_database() {
        let valid = "HTTP/1.1 200 OK\r\ncontent-type: application/json\r\n\r\n{\"status\":\"ok\",\"service\":\"jlu-notice-monitor\",\"database\":\"ok\"}";
        assert!(health_response_is_ours(valid));
        assert!(!health_response_is_ours(
            "HTTP/1.1 200 OK\r\n\r\n{\"status\":\"ok\",\"database\":\"ok\"}"
        ));
        assert!(!health_response_is_ours(
            "HTTP/1.1 503 Service Unavailable\r\n\r\n{\"service\":\"jlu-notice-monitor\"}"
        ));
    }

    #[test]
    fn status_distinguishes_owned_and_external_ready_services() {
        let controller = BackendController::default();
        {
            let mut inner = controller.inner.lock().unwrap();
            inner.phase = BackendPhase::ReadyExternal;
        }
        let external = controller.status();
        assert!(external.ready);
        assert!(!external.owned);

        {
            let mut inner = controller.inner.lock().unwrap();
            inner.phase = BackendPhase::ReadyOwned;
        }
        let owned = controller.status();
        assert!(owned.ready);
        assert!(owned.owned);
    }

    #[test]
    fn failed_state_is_safe_for_retry() {
        let controller = BackendController::default();
        controller.set_failed("safe message");
        let status = controller.status();
        assert_eq!(status.phase, "failed");
        assert!(!status.ready);
        assert_eq!(status.error.as_deref(), Some("safe message"));
        assert!(!controller.start_in_progress.load(Ordering::Acquire));
    }
}
