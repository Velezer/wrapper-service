use axum::{extract::State, http::StatusCode, response::IntoResponse, routing::post, Json, Router};
use serde::{Deserialize, Serialize};
use std::{env, sync::Arc};
use tokio::{
    process::Command,
    time::{timeout, Duration},
};

#[derive(Clone)]
pub struct AppState {
    pub bridge_cmd: String,
    pub timeout_ms: u64,
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
        bridge_cmd: env::var("GPT_BRIDGE_CMD").unwrap_or_default(),
        timeout_ms: env::var("GPT_TIMEOUT_MS")
            .ok()
            .and_then(|v| v.parse::<u64>().ok())
            .unwrap_or(20_000),
    })
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

    match ask_via_bridge(prompt, &state).await {
        Ok(answer) => (StatusCode::OK, Json(AskResponse { answer })).into_response(),
        Err(error) => (StatusCode::BAD_GATEWAY, Json(ErrorResponse { error })).into_response(),
    }
}

async fn ask_via_bridge(prompt: &str, state: &AppState) -> Result<String, String> {
    if state.bridge_cmd.is_empty() {
        return Err("GPT integration missing: set GPT_BRIDGE_CMD to a command that reads prompt from argv[1] and prints the answer to stdout".to_string());
    }

    let cmd = state.bridge_cmd.clone();
    let fut = Command::new("bash")
        .arg("-lc")
        .arg(cmd)
        .arg("--")
        .arg(prompt)
        .output();

    let output = timeout(Duration::from_millis(state.timeout_ms), fut)
        .await
        .map_err(|_| "GPT bridge timeout".to_string())
        .and_then(|res| res.map_err(|e| format!("GPT bridge failed to start: {e}")))?;

    if !output.status.success() {
        let status = output
            .status
            .code()
            .map(|c| c.to_string())
            .unwrap_or_else(|| "unknown".to_string());
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(format!("GPT bridge exited with status {status}: {stderr}"));
    }

    let answer = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if answer.is_empty() {
        return Err("GPT bridge returned empty output".to_string());
    }

    Ok(answer)
}

async fn not_found() -> impl IntoResponse {
    (
        StatusCode::NOT_FOUND,
        Json(ErrorResponse {
            error: "Not found".to_string(),
        }),
    )
}
