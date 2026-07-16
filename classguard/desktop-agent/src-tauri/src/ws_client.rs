use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;
use tauri::Emitter;
use tauri::AppHandle;
use tungstenite::{connect, Message};

pub fn run_forever(
    ws_url: &str,
    _http_url: &str,
    _device_token: &str,
    app_handle: &AppHandle,
    running: &Arc<AtomicBool>,
    monitoring_active: &Arc<AtomicBool>,
    capture_interval: &Arc<std::sync::atomic::AtomicU32>,
) {
    let app = app_handle.clone();
    let wu = ws_url.to_string();
    let r = running.clone();
    let ma = monitoring_active.clone();
    let cap_int = capture_interval.clone();

    thread::spawn(move || {
        while r.load(Ordering::SeqCst) {
            crate::logger::log(&format!("Connecting to WebSocket: {}", wu));
            match connect(&wu) {
                Ok((mut socket, _)) => {
                    crate::logger::log("WebSocket connection established successfully.");

                    let _ = app.emit("connection_state", serde_json::json!({ "connected": true }));

                    loop {
                        if !r.load(Ordering::SeqCst) {
                            break;
                        }

                        match socket.read() {
                            Ok(Message::Text(text)) => {
                                if let Ok(msg) = serde_json::from_str::<serde_json::Value>(&text) {
                                    let event = msg["event"].as_str().unwrap_or("");
                                    let data = msg.get("data");

                                    crate::logger::log(&format!("WS Event Received: '{}'", event));

                                    match event {
                                        "monitoring_started" => {
                                            ma.store(true, Ordering::SeqCst);
                                            if let Some(d) = data {
                                                if let Some(sec) = d.get("interval_seconds").and_then(|v| v.as_u64()) {
                                                    cap_int.store(sec as u32, Ordering::SeqCst);
                                                    crate::logger::log(&format!("Monitoring active. Capture interval updated to: {}s", sec));
                                                }
                                            } else {
                                                crate::logger::log("Monitoring active. Interval: default");
                                            }
                                            let _ = app.emit("monitoring_state", serde_json::json!({ "active": true }));
                                            let _ = app.emit("monitoring_paused", serde_json::json!({ "paused": false, "reason": "" }));
                                        }
                                        "monitoring_stopped" => {
                                            ma.store(false, Ordering::SeqCst);
                                            crate::logger::log("Monitoring stopped by faculty command.");
                                            let _ = app.emit("monitoring_state", serde_json::json!({ "active": false }));
                                            let _ = app.emit("monitoring_paused", serde_json::json!({ "paused": false, "reason": "" }));
                                        }
                                        "monitoring_paused" => {
                                            ma.store(false, Ordering::SeqCst);
                                            let reason = data.and_then(|d| d.get("reason")).and_then(|v| v.as_str()).unwrap_or("");
                                            crate::logger::log(&format!("Monitoring paused by faculty. Reason: '{}'", reason));
                                            let _ = app.emit("monitoring_paused", serde_json::json!({ "paused": true, "reason": reason }));
                                            let _ = crate::notifications::send_monitoring_paused(reason);
                                        }
                                        "warning" => {
                                            if let Some(d) = data {
                                                let level = d.get("level").and_then(|v| v.as_u64()).unwrap_or(1);
                                                let message = d.get("message").and_then(|v| v.as_str()).unwrap_or("");
                                                let reason = d.get("reason").and_then(|v| v.as_str()).unwrap_or("");
                                                
                                                crate::logger::log(&format!("🚨 WARNING TRIGGERED (Level {}): '{}' | Reason: '{}'", level, message, reason));
                                                
                                                let _ = app.emit("warning", serde_json::json!({
                                                    "level": level,
                                                    "message": message,
                                                    "reason": reason,
                                                }));
                                                let _ = crate::notifications::send_warning(level as u32);
                                            }
                                        }
                                        _ => {}
                                    }
                                }
                            }
                            Ok(Message::Close(_)) => {
                                crate::logger::log("WebSocket connection closed by server.");
                                break;
                            }
                            Err(e) => {
                                crate::logger::log(&format!("WebSocket read error: {}", e));
                                break;
                            }
                            _ => {}
                        }
                    }
                }
                Err(e) => {
                    crate::logger::log(&format!("WebSocket connection failed: {}. Retrying in 5 seconds...", e));
                    thread::sleep(Duration::from_secs(5));
                }
            }

            if !r.load(Ordering::SeqCst) {
                break;
            }
            thread::sleep(Duration::from_secs(3));
        }
    });
}
