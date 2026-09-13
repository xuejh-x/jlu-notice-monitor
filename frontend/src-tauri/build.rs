fn main() {
    // The backend sidecar is rebuilt before Tauri. Track it explicitly so a
    // backend-only change also invalidates the NSIS bundle.
    println!("cargo:rerun-if-changed=binaries/jlu-notice-backend-x86_64-pc-windows-msvc.exe");
    tauri_build::build()
}
