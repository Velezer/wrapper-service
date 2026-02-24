use axum::{extract::State, http::StatusCode, response::IntoResponse, routing::post, Json, Router};
use serde::{Deserialize, Serialize};
use std::{env, sync::Arc};
use tokio::{
    process::Command,
    time::{timeout, Duration},
};

#[derive(Clone)]
pub struct AppState {
    pub chatgpt_session_cookie: String,
    pub chatgpt_backend_url: String,
    pub chatgpt_model: String,
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
        chatgpt_session_cookie: env::var("CHATGPT_SESSION_COOKIE").unwrap_or_default(),
        chatgpt_backend_url: env::var("CHATGPT_BACKEND_URL")
            .unwrap_or_else(|_| "https://chatgpt.com/backend-api/conversation".to_string()),
        chatgpt_model: env::var("CHATGPT_MODEL").unwrap_or_else(|_| "auto".to_string()),
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
    if state.chatgpt_session_cookie.is_empty() {
        return Err("GPT integration missing: set CHATGPT_SESSION_COOKIE copied from your logged-in chatgpt.com browser session".to_string());
    }

    let escaped_prompt = json_escape(prompt);
    let model = json_escape(&state.chatgpt_model);
    let payload = format!(
        "{{\"action\":\"next\",\"messages\":[{{\"id\":\"msg-1\",\"author\":{{\"role\":\"user\"}},\"content\":{{\"content_type\":\"text\",\"parts\":[\"{escaped_prompt}\"]}}}}],\"parent_message_id\":\"msg-0\",\"model\":\"{model}\",\"history_and_training_disabled\":true}}"
    );

    let command = format!(
        "curl -sS -N '{}' \\\n          -H 'content-type: application/json' \\\n          -H 'origin: https://chatgpt.com' \\\n          -H 'referer: https://chatgpt.com/' \\\n          -H 'user-agent: Mozilla/5.0' \\\n          -H 'cookie: {}' \\\n          --data-raw '{}'",
        state.chatgpt_backend_url,
        shell_escape_single_quotes(&state.chatgpt_session_cookie),
        shell_escape_single_quotes(&payload)
    );

    let fut = Command::new("bash").arg("-lc").arg(command).output();
    let output = timeout(Duration::from_millis(state.timeout_ms), fut)
        .await
        .map_err(|_| "ChatGPT web request timeout".to_string())
        .and_then(|res| res.map_err(|e| format!("Failed to launch curl: {e}")))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(format!("ChatGPT web request failed: {stderr}"));
    }

    let body = String::from_utf8_lossy(&output.stdout).to_string();
    parse_sse_answer(&body).ok_or_else(|| "ChatGPT response did not contain an answer".to_string())
}

fn json_escape(s: &str) -> String {
    s.replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
}

fn shell_escape_single_quotes(s: &str) -> String {
    s.replace("'", "'\\''")
}

fn parse_sse_answer(raw_response: &str) -> Option<String> {
    raw_response
        .lines()
        .filter_map(|line| line.strip_prefix("data: "))
        .filter(|chunk| *chunk != "[DONE]")
        .filter_map(extract_text_part)
        .last()
}

fn extract_text_part(json_line: &str) -> Option<String> {
    let key = "\"parts\":[\"";
    let start = json_line.find(key)? + key.len();
    let rest = &json_line[start..];
    let end = rest.find("\"]")?;
    let text = &rest[..end];
    let text = text
        .replace("\\n", "\n")
        .replace("\\r", "\r")
        .replace("\\\"", "\"")
        .replace("\\\\", "\\");
    let trimmed = text.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed.to_string())
    }
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
    use super::parse_sse_answer;

    #[test]
    fn parses_sse_parts_field() {
        let input = "data: {\"message\":{\"content\":{\"parts\":[\"hello\"]}}}\ndata: [DONE]";
        assert_eq!(parse_sse_answer(input).as_deref(), Some("hello"));
    }
}
