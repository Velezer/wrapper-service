use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
pub struct AskRequest {
    pub prompt: String,
}

#[derive(Debug, Serialize)]
pub struct AskResponse {
    pub answer: String,
    pub model: String,
}

#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub error: String,
}
