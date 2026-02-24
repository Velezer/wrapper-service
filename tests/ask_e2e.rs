use axum::{body::Body, Router};
use http::{Method, Request, StatusCode};
use http_body_util::BodyExt;
use std::sync::Arc;
use tower::ServiceExt;
use wrapper_service::{build_app, AppState};

fn mock_bridge_echo_cmd() -> &'static str {
    "printf '%s' \"$1\""
}

fn build_test_app(bridge_cmd: &str) -> Router {
    build_app(Arc::new(AppState {
        bridge_cmd: bridge_cmd.to_string(),
        timeout_ms: 5_000,
    }))
}

fn ask_request(prompt: &str) -> Request<Body> {
    Request::builder()
        .method(Method::POST)
        .uri("/ask")
        .header("content-type", "application/json")
        .body(Body::from(format!(r#"{{"prompt":"{prompt}"}}"#)))
        .unwrap()
}

fn root_request() -> Request<Body> {
    Request::builder()
        .method(Method::GET)
        .uri("/")
        .body(Body::empty())
        .unwrap()
}

#[tokio::test]
async fn e2e_post_ask_success_path_returns_answer() {
    let app = build_test_app(mock_bridge_echo_cmd());

    let response = app.oneshot(ask_request("hello")).await.unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let body = response.into_body().collect().await.unwrap().to_bytes();
    assert_eq!(&body[..], br#"{"answer":"hello"}"#);
}

#[tokio::test]
async fn e2e_404_fallback_path_returns_not_found() {
    let app = build_test_app(mock_bridge_echo_cmd());

    let response = app.oneshot(root_request()).await.unwrap();

    assert_eq!(response.status(), StatusCode::NOT_FOUND);
}
