use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};

pub mod commands;
pub mod notifications;
pub mod screen_capture;
pub mod ws_client;
pub mod logger;

pub struct AppState {
    pub device_token: Arc<Mutex<Option<String>>>,
    pub server_url: Arc<Mutex<String>>,
    pub monitoring_active: Arc<AtomicBool>,
    pub running: Arc<AtomicBool>,
    pub capture_interval: Arc<std::sync::atomic::AtomicU32>,
}
