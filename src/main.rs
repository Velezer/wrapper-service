use axum::{extract::State, http::StatusCode, response::IntoResponse, routing::post, Json, Router};
use serde::{Deserialize, Serialize};
use std::{env, sync::Arc};
use tokio::{
    process::Command,
    time::{timeout, Duration},
};

#[derive(Clone)]
struct AppState {
    bridge_cmd: String,
    timeout_ms: u64,
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

#[tokio::main]
async fn main() {
    let state = Arc::new(AppState {
        bridge_cmd: env::var("GPT_BRIDGE_CMD").unwrap_or_default(),
        timeout_ms: env::var("GPT_TIMEOUT_MS")
            .ok()
            .and_then(|v| v.parse::<u64>().ok())
            .unwrap_or(20_000),
    });

    let app = build_app(state);

    let port = env::var("PORT")
        .ok()
        .and_then(|v| v.parse::<u16>().ok())
        .unwrap_or(3000);

    let listener = tokio::net::TcpListener::bind(("0.0.0.0", port))
        .await
        .expect("bind failed");

    axum::serve(listener, app).await.expect("server failed");
}

fn build_app(state: Arc<AppState>) -> Router {
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

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use http::{Method, Request};
    use http_body_util::BodyExt;
    use tower::ServiceExt;

    fn test_app(bridge_cmd: &str) -> Router {
        build_app(Arc::new(AppState {
            bridge_cmd: bridge_cmd.to_string(),
            timeout_ms: 5_000,
        }))
    }

    #[tokio::test]
    async fn e2e_ask_returns_answer() {
        let app = test_app("printf '%s' \"$1\"");

        let response = app
            .oneshot(
                Request::builder()
                    .method(Method::POST)
                    .uri("/ask")
                    .header("content-type", "application/json")
                    .body(Body::from(r#"{"prompt":"hello"}"#))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
        let body = response.into_body().collect().await.unwrap().to_bytes();
        assert_eq!(&body[..], br#"{"answer":"hello"}"#);
    }

    #[tokio::test]
    async fn e2e_non_matching_route_returns_404() {
        let app = test_app("printf '%s' \"$1\"");

        let response = app
            .oneshot(
                Request::builder()
                    .method(Method::GET)
                    .uri("/")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::NOT_FOUND);
    }
}
