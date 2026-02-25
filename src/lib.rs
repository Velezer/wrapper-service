use axum::{extract::State, http::StatusCode, response::IntoResponse, routing::post, Json, Router};
use serde::{Deserialize, Serialize};
use std::{env, path::Path, process::Stdio, sync::Arc};
use tokio::time::{timeout, Duration};

#[derive(Clone)]
pub struct AppState {
    pub timeout_ms: u64,
    pub chatgpt_browser_cmd: String,
}

#[derive(Deserialize)]
struct AskRequest {
    prompt: String,
}

#[derive(Serialize)]
struct AskResponse {
    answer: String,
}

#[derive(Serialize)]
struct ErrorResponse {
    error: String,
}

pub fn app_state_from_env() -> Arc<AppState> {
    Arc::new(AppState {
        timeout_ms: env::var("GPT_TIMEOUT_MS")
            .ok()
            .and_then(|v| v.parse::<u64>().ok())
            .unwrap_or(20_000),
        chatgpt_browser_cmd: env::var("CHATGPT_BROWSER_CMD")
            .unwrap_or_else(|_| default_chatgpt_browser_cmd()),
    })
}

fn default_chatgpt_browser_cmd() -> String {
    default_chatgpt_browser_cmd_with_venv(Path::new("/opt/venv/bin/python").exists())
}

fn default_chatgpt_browser_cmd_with_venv(venv_python_exists: bool) -> String {
    if venv_python_exists {
        "/opt/venv/bin/python scripts/chatgpt_browser_bridge.py".to_string()
    } else {
        "python3 scripts/chatgpt_browser_bridge.py".to_string()
    }
}

pub fn server_port_from_env() -> u16 {
    env::var("PORT")
        .ok()
        .and_then(|v| v.parse::<u16>().ok())
        .unwrap_or(3000)
}

pub async fn run_server(app: Router, port: u16) {
    let listener = tokio::net::TcpListener::bind(("0.0.0.0", port))
        .await
        .expect("bind failed");

    axum::serve(listener, app).await.expect("server failed");
}

pub fn build_app(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/ask", post(ask))
        .fallback(not_found)
        .with_state(state)
}

async fn ask(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<AskRequest>,
) -> impl IntoResponse {
    let prompt = payload.prompt.trim();
    if prompt.is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse {
                error: "Field \"prompt\" must be a non-empty string".to_string(),
            }),
        )
            .into_response();
    }

    match ask_llm(prompt, &state).await {
        Ok(answer) => (StatusCode::OK, Json(AskResponse { answer })).into_response(),
        Err(error) => (StatusCode::BAD_GATEWAY, Json(ErrorResponse { error })).into_response(),
    }
}

async fn ask_llm(prompt: &str, state: &AppState) -> Result<String, String> {
    ask_via_browser(prompt, state).await
}

async fn ask_via_browser(prompt: &str, state: &AppState) -> Result<String, String> {
    let output = timeout(
        Duration::from_millis(state.timeout_ms),
        tokio::process::Command::new("bash")
            .arg("-lc")
            .arg(&state.chatgpt_browser_cmd)
            .env("CHATGPT_PROMPT", prompt)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output(),
    )
    .await
    .map_err(|_| "ChatGPT browser automation timeout".to_string())
    .and_then(|res| res.map_err(|e| format!("Failed to start browser automation command: {e}")))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(format_browser_command_error(&stderr, output.status.to_string()));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let answer = stdout.trim();
    if answer.is_empty() {
        return Err("Browser automation did not return an answer".to_string());
    }

    Ok(answer.to_string())
}

fn format_browser_command_error(stderr: &str, status: String) -> String {
    if stderr.is_empty() {
        return format!("Browser automation command failed with status {status}");
    }

    if stderr.contains("playwright import failed")
        && stderr.contains("No module named 'playwright'")
    {
        return format!(
            "Browser automation command failed: {stderr}. Install Playwright with `pip install playwright` and then run `python3 -m playwright install chromium`."
        );
    }

    format!("Browser automation command failed: {stderr}")
}

async fn not_found() -> impl IntoResponse {
    (
        StatusCode::NOT_FOUND,
        Json(ErrorResponse {
            error: "Not found".to_string(),
        }),
    )
}

#[cfg(test)]
mod tests {
    use super::{
        app_state_from_env, default_chatgpt_browser_cmd_with_venv, format_browser_command_error,
    };

    #[test]
    fn uses_browser_command_by_default() {
        let state = app_state_from_env();
        assert!(!state.chatgpt_browser_cmd.is_empty());
    }

    #[test]
    fn uses_venv_python_if_present() {
        let cmd = default_chatgpt_browser_cmd_with_venv(true);
        assert_eq!(cmd, "/opt/venv/bin/python scripts/chatgpt_browser_bridge.py");
    }

    #[test]
    fn uses_system_python_when_venv_is_missing() {
        let cmd = default_chatgpt_browser_cmd_with_venv(false);
        assert_eq!(cmd, "python3 scripts/chatgpt_browser_bridge.py");
    }

    #[test]
    fn playwright_import_errors_include_install_hint() {
        let err = format_browser_command_error(
            "playwright import failed: No module named 'playwright'",
            "exit status: 3".to_string(),
        );

        assert!(err.contains("pip install playwright"));
        assert!(err.contains("python3 -m playwright install chromium"));
    }
}
