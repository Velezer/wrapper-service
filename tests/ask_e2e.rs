use axum::{body::Body, Router};
use http::{Method, Request, StatusCode};
use http_body_util::BodyExt;
use std::sync::Arc;
use tower::ServiceExt;
use wrapper_service::{build_app, AppState};

fn build_test_app() -> Router {
    build_app(Arc::new(AppState {
        timeout_ms: 5_000,
        chatgpt_browser_cmd: "echo hello".to_string(),
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
    let app = build_test_app();

    let response = app.oneshot(ask_request("hello")).await.unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let body = response.into_body().collect().await.unwrap().to_bytes();
    assert_eq!(&body[..], br#"{"answer":"hello"}"#);
}

#[tokio::test]
async fn e2e_404_fallback_path_returns_not_found() {
    let app = build_test_app();

    let response = app.oneshot(root_request()).await.unwrap();

    assert_eq!(response.status(), StatusCode::NOT_FOUND);
}
