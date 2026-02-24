mod handlers;
mod models;

use axum::{routing::post, Router};

use crate::AppState;

#[allow(unused_imports)]
pub use handlers::{ask, not_found};
#[allow(unused_imports)]
pub use models::{AskRequest, AskResponse, ErrorResponse};

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/ask", post(ask))
        .fallback(not_found)
        .with_state(state)
}
