use axum::{body::Body, routing::post, Router};
use http::{Method, Request, StatusCode};
use http_body_util::BodyExt;
use std::sync::Arc;
use tower::ServiceExt;
use wrapper_service::{build_app, AppState};

async fn mock_chatgpt() -> &'static str {
    "data: {\"message\":{\"content\":{\"parts\":[\"hello\"]}}}\n\ndata: [DONE]\n"
}

async fn spawn_mock_chatgpt_server() -> String {
    let app = Router::new().route("/backend-api/conversation", post(mock_chatgpt));
    let listener = tokio::net::TcpListener::bind(("127.0.0.1", 0)).await.unwrap();
    let addr = listener.local_addr().unwrap();

    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    format!("http://{}/backend-api/conversation", addr)
}

fn build_test_app(backend_url: &str) -> Router {
    build_app(Arc::new(AppState {
        chatgpt_session_cookie: "__Secure-next-auth.session-token=fake".to_string(),
        chatgpt_backend_url: backend_url.to_string(),
        chatgpt_model: "auto".to_string(),
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
    let backend_url = spawn_mock_chatgpt_server().await;
    let app = build_test_app(&backend_url);

    let response = app.oneshot(ask_request("hello")).await.unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let body = response.into_body().collect().await.unwrap().to_bytes();
    assert_eq!(&body[..], br#"{"answer":"hello"}"#);
}

#[tokio::test]
async fn e2e_404_fallback_path_returns_not_found() {
    let app = build_test_app("http://127.0.0.1:1/backend-api/conversation");

    let response = app.oneshot(root_request()).await.unwrap();

    assert_eq!(response.status(), StatusCode::NOT_FOUND);
}
