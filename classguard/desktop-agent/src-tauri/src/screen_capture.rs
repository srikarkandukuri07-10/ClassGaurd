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

    // Resize to 960x540 to minimise bandwidth
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
    // Wait for ws_client to establish its connection first
    thread::sleep(Duration::from_secs(5));

    let scheme = if server_url.contains("localhost") || server_url.contains("127.0.0.1") { "http" } else { "https" };
    let classify_url = format!("{}://{}/api/ai/classify", scheme, server_url);
    let result_url   = format!("{}://{}/api/ai/result", scheme, server_url);
    let dt = device_token.to_string();

    let r  = running.clone();
    let ma = monitoring_active.clone();

    thread::spawn(move || {
        let client = reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(20))
            .build()
            .unwrap_or_default();

        while r.load(Ordering::SeqCst) {
            if !ma.load(Ordering::SeqCst) {
                thread::sleep(Duration::from_secs(2));
                continue;
            }

            let title      = get_active_window_title();
            let screenshot = capture_screen_base64();

            if title.is_empty() {
                thread::sleep(Duration::from_secs(5));
                continue;
            }

            // Step 1 — classify via backend (Gemini Vision or keyword fallback)
            let classify_body = serde_json::json!({
                "device_id":    dt,
                "window_title": title,
                "image":        screenshot,
            });

            if let Ok(resp) = client.post(&classify_url).json(&classify_body).send() {
                if let Ok(result) = resp.json::<serde_json::Value>() {
                    let status     = result["status"].as_str().unwrap_or("studying").to_string();
                    let reason     = result["reason"].as_str().unwrap_or("").to_string();
                    let confidence = result["confidence"].as_f64().unwrap_or(0.8);

                    // Step 2 — push result back so backend fires warnings + notifications
                    let result_body = serde_json::json!({
                        "device_id":    dt,
                        "status":       status,
                        "reason":       reason,
                        "window_title": title,
                        "screenshot":   screenshot,
                        "confidence":   confidence,
                    });
                    let _ = client.post(&result_url).json(&result_body).send();
                }
            }

            thread::sleep(Duration::from_secs(10));
        }
    });
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
