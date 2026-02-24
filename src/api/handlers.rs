use axum::{
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};

use crate::AppState;

use super::models::{AskRequest, AskResponse, ErrorResponse};

pub async fn ask(
    State(state): State<AppState>,
    Json(payload): Json<AskRequest>,
) -> Result<Json<AskResponse>, (StatusCode, Json<ErrorResponse>)> {
    let prompt = payload.prompt.trim();
    if prompt.is_empty() {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse {
                error: "prompt must not be empty".to_string(),
            }),
        ));
    }

    Ok(Json(AskResponse {
        answer: format!("Echo: {prompt}"),
        model: state.model_name,
    }))
}

pub async fn not_found() -> Response {
    (
        StatusCode::NOT_FOUND,
        Json(ErrorResponse {
            error: "route not found".to_string(),
        }),
    )
        .into_response()
}
