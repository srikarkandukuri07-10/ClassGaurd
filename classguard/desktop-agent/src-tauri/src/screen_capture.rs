use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;
use tauri::AppHandle;
use screenshots::Screen;
use image::ImageOutputFormat;
use base64::{engine::general_purpose, Engine as _};
use std::io::Cursor;

fn capture_screen_base64() -> Option<String> {
    let screens = Screen::all().ok()?;
    let screen = screens.first()?;
    let image = screen.capture().ok()?;
    
    // Convert to dynamic image and resize to 960x540 to optimize bandwidth
    let dynamic_img = image::DynamicImage::ImageRgba8(image);
    let resized = dynamic_img.resize(960, 540, image::imageops::FilterType::Triangle);
    
    let mut buffer = Vec::new();
    let mut cursor = Cursor::new(&mut buffer);
    resized.write_to(&mut cursor, ImageOutputFormat::Jpeg(55)).ok()?;
    
    Some(general_purpose::STANDARD.encode(buffer))
}

pub fn run_forever(
    server_url: &str,
    device_token: &str,
    _app_handle: &AppHandle,
    running: &Arc<AtomicBool>,
    monitoring_active: &Arc<AtomicBool>,
) {
    thread::sleep(Duration::from_secs(3));

    let scheme = if server_url.contains("localhost") || server_url.contains("127.0.0.1") { "http" } else { "https" };
    let http_url = format!("{}://{}", scheme, server_url);
    let ai_url = format!("{}://{}/api/ai/classify", scheme, server_url);
    let dt = device_token.to_string();
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(15))
        .build()
        .unwrap_or_default();

    while running.load(Ordering::SeqCst) {
        if monitoring_active.load(Ordering::SeqCst) {
            let title = get_active_window_title();
            if !title.is_empty() {
                // Capture the screen natively in Rust
                let screenshot = capture_screen_base64();

                let body = serde_json::json!({
                    "device_id": dt,
                    "window_title": title,
                    "image": screenshot,
                });

                if let Ok(resp) = client.post(&ai_url).json(&body).send() {
                    if let Ok(result) = resp.json::<serde_json::Value>() {
                        let status = result.get("status").and_then(|v| v.as_str()).unwrap_or("studying");
                        let reason = result.get("reason").and_then(|v| v.as_str()).unwrap_or("");

                        let _ = client
                            .post(format!("{}/api/ai/result", http_url))
                            .json(&serde_json::json!({
                                "device_id": dt,
                                "status": status,
                                "reason": reason,
                                "window_title": title,
                                "screenshot": screenshot,
                            }))
                            .send();
                    }
                }
            }
        }
        thread::sleep(Duration::from_secs(5));
    }
}

fn get_active_window_title() -> String {
    unsafe {
        let hwnd = winapi::um::winuser::GetForegroundWindow();
        if hwnd.is_null() {
            return String::new();
        }
        let length = winapi::um::winuser::GetWindowTextLengthW(hwnd) + 1;
        let mut buf: Vec<u16> = vec![0; length as usize];
        let len = winapi::um::winuser::GetWindowTextW(hwnd, buf.as_mut_ptr(), length);
        if len > 0 {
            String::from_utf16_lossy(&buf[..len as usize])
        } else {
            String::new()
        }
    }
}
