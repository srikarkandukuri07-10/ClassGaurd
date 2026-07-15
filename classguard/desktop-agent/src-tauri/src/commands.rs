use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, State};
use crate::AppState;

const TOKEN_FILE: &str = "classguard_token.json";

#[derive(Serialize, Deserialize, Clone)]
pub struct StudentInfo {
    pub student_name: String,
    pub section: String,
    pub device_token: String,
    pub monitoring_enabled: bool,
    pub monitoring_paused: bool,
}

#[derive(Serialize, Deserialize)]
struct TokenData {
    device_token: String,
    server_url: String,
}

fn read_token() -> Option<TokenData> {
    let content = std::fs::read_to_string(TOKEN_FILE).ok()?;
    serde_json::from_str(&content).ok()
}

fn write_token(token: &str, server_url: &str) {
    let data = serde_json::json!({ "device_token": token, "server_url": server_url });
    let _ = std::fs::write(TOKEN_FILE, data.to_string());
}

pub fn clear_token_file() {
    let _ = std::fs::remove_file(TOKEN_FILE);
}

fn start_background_threads(
    app_handle: AppHandle,
    device_token: String,
    server_url: String,
) {
    let mon_active = app_handle.state::<AppState>().monitoring_active.clone();
    let running = Arc::new(AtomicBool::new(true));

    let (http_scheme, ws_scheme) = if server_url.contains("localhost") || server_url.contains("127.0.0.1") {
        ("http", "ws")
    } else {
        ("https", "wss")
    };
    let ws_url = format!("{}://{}/ws/agent?device_token={}", ws_scheme, server_url, device_token);
    let http_url = format!("{}://{}", http_scheme, server_url);

    let r1 = running.clone();
    let r2 = running.clone();
    let r3 = running.clone();
    let m1 = mon_active.clone();
    let a1 = app_handle.clone();
    let a2 = app_handle;
    let dt_ws = device_token.clone();
    let dt_hb = device_token.clone();
    let dt_cap = device_token;
    let su_hb = server_url.clone();
    let su_cap = server_url;
    let hu_ws = http_url.clone();
    let wu_ws = ws_url;

    thread::spawn(move || {
        crate::ws_client::run_forever(&wu_ws, &hu_ws, &dt_ws, &a1, &r1, &m1);
    });

    thread::spawn(move || {
        loop {
            if !r2.load(Ordering::SeqCst) {
                break;
            }
            let scheme = if su_hb.contains("localhost") || su_hb.contains("127.0.0.1") { "http" } else { "https" };
            if let Some(c) = reqwest::blocking::Client::builder()
                .timeout(Duration::from_secs(5))
                .build()
                .ok()
            {
                let body = serde_json::json!({ "device_token": dt_hb });
                let _ = c.post(format!("{}://{}/api/monitoring/heartbeat", scheme, su_hb))
                    .json(&body)
                    .send();
            }
            thread::sleep(Duration::from_secs(10));
        }
    });

    thread::spawn(move || {
        crate::screen_capture::run_forever(&su_cap, &dt_cap, &a2, &r3, &mon_active);
    });
}

#[tauri::command]
pub async fn check_token(
    app_handle: AppHandle,
    state: State<'_, AppState>,
) -> Result<Option<StudentInfo>, String> {
    let token_data = read_token();
    if let Some(data) = token_data {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(10))
            .build()
            .map_err(|e| e.to_string())?;
        let scheme = if data.server_url.contains("localhost") || data.server_url.contains("127.0.0.1") { "http" } else { "https" };
        let resp = client
            .post(format!("{}://{}/api/monitoring/reconnect", scheme, data.server_url))
            .json(&serde_json::json!({ "device_token": data.device_token }))
            .send()
            .await
            .map_err(|_| "Cannot reach server".to_string())?;
        if resp.status().is_success() {
            let json: serde_json::Value = resp.json().await.map_err(|_| "Bad response".to_string())?;
            if json["success"].as_bool().unwrap_or(false) {
                if let Ok(mut token) = state.device_token.lock() {
                    *token = Some(data.device_token.clone());
                }
                if let Ok(mut url) = state.server_url.lock() {
                    *url = data.server_url.clone();
                }
                start_background_threads(app_handle, data.device_token.clone(), data.server_url.clone());
                return Ok(Some(StudentInfo {
                    student_name: json["student_name"].as_str().unwrap_or("Student").to_string(),
                    section: json["section"].as_str().unwrap_or("").to_string(),
                    device_token: data.device_token,
                    monitoring_enabled: json["monitoring_enabled"].as_bool().unwrap_or(false),
                    monitoring_paused: json["monitoring_paused"].as_bool().unwrap_or(false),
                }));
            }
        }
        clear_token_file();
    }
    Ok(None)
}

#[tauri::command]
pub async fn link_device(
    app_handle: AppHandle,
    state: State<'_, AppState>,
    code: String,
    server_url: String,
) -> Result<StudentInfo, String> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(15))
        .build()
        .map_err(|e| e.to_string())?;

    let scheme = if server_url.contains("localhost") || server_url.contains("127.0.0.1") { "http" } else { "https" };
    let resp = client
        .post(format!("{}://{}/api/students/link-device", scheme, server_url))
        .json(&serde_json::json!({ "code": code }))
        .send()
        .await
        .map_err(|_| "Cannot reach server. Make sure you're connected to the same network.".to_string())?;

    let json: serde_json::Value = resp.json().await.map_err(|_| "Bad response".to_string())?;
    let success = json["success"].as_bool().unwrap_or(false);
    if !success {
        return Err(json["message"].as_str().unwrap_or("Invalid code").to_string());
    }

    let device_token = json["device_token"].as_str().unwrap_or("").to_string();
    let student_name = json["student_name"].as_str().unwrap_or("Student").to_string();
    let section = json["section"].as_str().unwrap_or("").to_string();

    write_token(&device_token, &server_url);

    if let Ok(mut token) = state.device_token.lock() {
        *token = Some(device_token.clone());
    }
    if let Ok(mut url) = state.server_url.lock() {
        *url = server_url.clone();
    }

    start_background_threads(app_handle.clone(), device_token.clone(), server_url);

    Ok(StudentInfo {
        student_name,
        section,
        device_token,
        monitoring_enabled: false,
        monitoring_paused: false,
    })
}

#[tauri::command]
pub async fn disconnect(
    state: State<'_, AppState>,
) -> Result<(), String> {
    state.monitoring_active.store(false, Ordering::SeqCst);
    if let Ok(mut token) = state.device_token.lock() {
        *token = None;
    }
    clear_token_file();
    Ok(())
}

#[tauri::command]
pub async fn request_pause(
    state: State<'_, AppState>,
    reason: String,
) -> Result<(), String> {
    let token = state.device_token.lock().map_err(|e| e.to_string())?.clone();
    let url = state.server_url.lock().map_err(|e| e.to_string())?.clone();
    let device_token = token.ok_or("Not connected")?;

    let client = reqwest::Client::new();
    let resp = client
        .post(format!("http://{}/api/disable-requests/", url))
        .json(&serde_json::json!({ "device_id": device_token, "reason": reason }))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if resp.status().is_success() {
        Ok(())
    } else {
        Err("Failed to send request".to_string())
    }
}
