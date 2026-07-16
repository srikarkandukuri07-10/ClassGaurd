use std::fs::OpenOptions;
use std::io::Write;

pub fn log(msg: &str) {
    let mut path = std::env::temp_dir();
    path.push("classguard_agent.log");
    
    if let Ok(mut file) = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
    {
        let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S");
        let _ = writeln!(file, "[{}] {}", now, msg);
    }
    
    // Also print to stdout for terminal debugging
    println!("{}", msg);
}
